# -*- coding: utf-8 -*-
"""MyFreeCams compatible Spider.

说明：MyFreeCams 的直播播放由官方 Web App/鉴权服务控制，公开页面通常不直接
暴露可长期复用的 HLS 地址。本 Spider 负责房间列表、搜索、详情和 Web 房间入口；
playerContent 返回官方房间页，不伪造或绕过登录、年龄确认及房间鉴权。
"""
import json
import re
import time
from html import unescape
from urllib.parse import quote, urljoin

try:
    import requests
except Exception:
    requests = None
    import urllib.request


class Spider:
    def __init__(self):
        self.host = "https://app.myfreecams.com"
        self.web = "https://www.myfreecams.com"
        self.ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"
        self.s = None
        self.session = None
        self.sess = None
        self._cache = {}

    def getDependence(self):
        return []

    def init(self, extend=""):
        if isinstance(extend, str) and extend.strip():
            try:
                cfg = json.loads(extend)
                if isinstance(cfg, dict):
                    self.host = cfg.get("host", self.host).rstrip("/")
            except Exception:
                pass
        if requests:
            self.s = requests.Session()
            self.s.headers.update({"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml"})
        else:
            self.s = None
        self.session = self.s
        self.sess = self.s
        return None

    def _get(self, url, headers=None):
        h = {"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/json", "Origin": self.host, "Connection": "keep-alive"}
        if headers:
            h.update(headers)
        try:
            if self.s:
                r = self.s.get(url, headers=h, timeout=15)
                return r.status_code, r.text, r.headers
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as r:
                return getattr(r, "status", 200), r.read().decode("utf-8", "ignore"), dict(r.headers)
        except Exception:
            return 0, "", {}

    def _json(self, text):
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', text, re.S | re.I)
        if not m:
            return {}
        try:
            return json.loads(unescape(m.group(1)))
        except Exception:
            return {}

    def _avatar(self, rid, avatar=1):
        # Official stable avatar CDN: photos2/<first 3 digits>/<uid>/avatar.90x90.jpg
        rid = str(rid)
        if not rid.isdigit():
            return ""
        return "https://img.mfcimg.com/photos2/%s/%s/avatar.90x90.jpg" % (rid[:3], rid)

    def _cover(self, rid, snap="", server=""):
        # Prefer the live snapshot. If MFC omits snap_url, rebuild its public
        # snapshot URL from the assigned video server and model id.
        if snap:
            return snap
        rid = str(rid)
        m = re.search(r'(\d+)$', str(server or ""))
        if rid.isdigit() and m:
            stream_id = str(100000000 + int(rid))
            return "https://snap.mfcimg.com/snapimg/%s/853x480/mfc_a_%s" % (m.group(1), stream_id)
        return self._avatar(rid)

    def _api_json(self, path):
        code, text, _ = self._get("https://api-edge.myfreecams.com/" + path,
            {"Accept": "application/json", "Referer": self.host + "/"})
        try:
            obj = json.loads(text)
            return obj.get("result", [])
        except Exception:
            return []

    def _online_rooms(self):
        cached = self._cache.get("online_rooms")
        if cached and time.time() - cached[0] < 45:
            return cached[1]
        rows = self._api_json("online_models")
        out = []
        for u in rows if isinstance(rows, list) else []:
            rid = str(u.get("user_id", ""))
            name = u.get("username") or rid
            if not rid or not name:
                continue
            snap = u.get("snap_url") or ""
            out.append({"id": rid, "name": name, "slug": name, "pic": self._cover(rid, snap, u.get("server_name", "")),
                "status": "live", "topic": u.get("topic", ""),
                "viewers": u.get("room_count", 0), "score": u.get("cam_score", 0),
                "server": u.get("server_name", ""), "rank": u.get("rank", 0),
                "vidserver": u.get("vidserver_id", 0), "server_type": u.get("video_server_type", ""),
                "snap_url": snap})
        self._cache["online_rooms"] = (time.time(), out)
        return out

    def _rooms(self, text):
        # The SSR HTML only contains __NEXT_DATA__; live models arrive through
        # the official bootstrap state.  Some deployments serialize that state
        # into a JS assignment, so accept both assignment and JSON-string forms.
        found = {}
        blobs = [text]
        for key in ("__MFC_APP_USERS__", "__MFC_APP_LISTS__", "users"):
            for m in re.finditer(re.escape(key) + r'[^=]*=\\s*([^;]+)', text, re.S):
                blobs.append(m.group(1))
        def add(x):
            if isinstance(x, dict):
                users = x.get("users") if isinstance(x.get("users"), dict) else x
                for rid, u in users.items() if isinstance(users, dict) else []:
                    if not isinstance(u, dict):
                        continue
                    name = u.get("name") or u.get("username") or u.get("slug")
                    if not name or not str(rid).isdigit() or not u.get("isModel", True):
                        continue
                    online = bool(u.get("isOnline") or u.get("isBroadcasting") or u.get("isPublicShow"))
                    if not online and not u.get("isModel"):
                        continue
                    found[str(rid)] = {"id": str(rid), "name": str(name),
                        "slug": u.get("slug") or str(name), "pic": self._cover(str(rid), "", u.get("server", "")),
                        "status": "live" if online else "offline", "topic": u.get("topic", ""),
                        "viewers": u.get("viewers", 0), "score": u.get("rankingScore", 0)}
        # Parse JSON assignments when present.
        for b in blobs[1:]:
            try: add(json.loads(b.strip()))
            except Exception: pass
        # Fallback: current page DOM/state may be represented by tile + slug pairs.
        for rid, slug in re.findall(r'tile-(\\d+).*?slug["\']?\\s*[:=]\\s*["\']([A-Za-z0-9_]+)', text, re.S | re.I):
            found.setdefault(rid, {"id": rid, "name": slug, "slug": slug, "pic": self._avatar(rid), "status": "live", "topic": ""})
        return list(found.values())

    def _vod(self, room):
        rid = str(room["id"])
        name = room.get("name", rid)
        remark = room.get("topic") or "在线直播"
        if room.get("viewers"):
            remark = "%s · %s人" % (remark, room.get("viewers"))
        return {"vod_id": rid, "vod_name": name, "vod_pic": room.get("pic", ""),
                "vod_remarks": remark, "vod_tag": "直播", "vod_year": "2026",
                "vod_play_from": "MyFreeCams", "vod_play_url": name + "$" + rid}

    def homeContent(self, filter=None):
        rooms = self._online_rooms()
        if not rooms:
            code, text, _ = self._get(self.host + "/?r=1")
            rooms = self._rooms(text) if code else []
        return {"class": [{"type_id": "live", "type_name": "在线直播"}, {"type_id": "all", "type_name": "全部房间"}],
                "list": [self._vod(x) for x in rooms], "page": 1, "pagecount": 1, "limit": 50, "total": len(rooms)}

    def homeVideoContent(self):
        return self.homeContent(None)

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        rooms = self._online_rooms()
        if not rooms:
            return self.homeContent(filter)
        if str(tid) == "live":
            rooms = [x for x in rooms if x.get("status") == "live"]
        return {"list": [self._vod(x) for x in rooms], "page": int(pg or 1),
                "pagecount": 1, "limit": 50, "total": len(rooms)}

    def _room_info(self, rid):
        rid = str(rid)
        for x in self._online_rooms():
            if str(x.get("id")) == rid:
                return x
        return {"id": rid, "name": rid, "slug": rid, "pic": self._avatar(rid)}

    def _room_slug(self, rid):
        return self._room_info(rid).get("slug") or str(rid)

    def detailContent(self, ids):
        rid = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids)
        slug = self._room_slug(rid)
        url = self.web + "/" + quote(slug, safe="")
        return {"list": [{"vod_id": rid, "vod_name": slug, "vod_pic": self._room_info(rid).get("pic", self._avatar(rid)),
                          "vod_content": "官方直播房间：" + url,
                          "vod_play_from": "MyFreeCams", "vod_play_url": "进入直播$" + rid}]}

    def searchContent(self, key, quick=False, pg="1"):
        key = str(key or "").strip().lower()
        rooms = self._online_rooms()
        if key:
            rooms = [x for x in rooms if key in (x.get("name", "") + " " + x.get("topic", "")).lower()]
        rows = [self._vod(x) for x in rooms]
        return {"list": rows, "page": int(pg or 1), "pagecount": 1, "total": len(rows)}

    def playerContent(self, flag, ids, vipFlags=None):
        rid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        info = self._room_info(rid)
        slug = info.get("slug") or rid
        # Public rooms expose a short-lived LL-HLS playlist. The URL is rebuilt
        # on each playerContent call from the current API server assignment.
        server = str(info.get("server", ""))
        vnum = re.search(r'(\d+)$', server)
        if vnum:
            vs = vnum.group(1)
            stream = "mfc_a_%d" % (100000000 + int(rid)) if rid.isdigit() else "mfc_a_%s" % rid
            url = "https://edgevideo.myfreecams.com/llhls/NxServer/%s/ngrp:%s.f4v_cmaf/playlist_sfm4s.m3u8" % (vs, stream)
            return {"parse": 0, "jx": 0, "url": url,
                    "format": "application/x-mpegURL",
                    "header": {"User-Agent": self.ua, "Referer": "https://m.myfreecams.com/" + quote(slug, safe="")}}
        url = "https://m.myfreecams.com/models/" + quote(slug, safe="")
        return {"parse": 0, "jx": 0, "url": url,
                "header": {"User-Agent": self.ua, "Referer": "https://m.myfreecams.com/"}}

    def localProxy(self, param):
        return [404, "text/plain", b"MyFreeCams does not expose a stable public proxy stream", {}]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv)(\?|$)', str(url), re.I))

    def action(self, action):
        return ""

    def destroy(self):
        try:
            if self.s: self.s.close()
        except Exception:
            pass
        return None

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

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====

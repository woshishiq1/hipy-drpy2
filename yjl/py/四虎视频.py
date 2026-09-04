# -*- coding: utf-8 -*-
"""
遮天 · 4虎 / 四虎
入口: https://4h.tv  可用: https://www.9k88x.com
API: https://data.7wzx9.com/forward + getDataInit
播放: macVodLinkMap[server].LINK_n + vod_url (多线路)
"""
import re
import sys
import json
from urllib import parse, request as urlrequest

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def __init__(self):
            pass

try:
    import requests

    HAS_REQ = True
except Exception:
    HAS_REQ = False

try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


class Spider(BaseSpider):
    host = "https://www.9k88x.com"
    hosts = ["https://www.9k88x.com", "https://9k88x.com", "https://4h.tv"]
    api = "https://data.7wzx9.com/forward"
    init_api = "https://data.7wzx9.com/getDataInit"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.9k88x.com/",
        "Origin": "https://www.9k88x.com",
    }
    _mac = None
    _cats = None

    def init(self, extend=""):
        extend = (extend or "").strip()
        if extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            self.headers["Origin"] = self.host
        self._load_init()
        return True

    def getName(self):
        return "4虎"

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    def _post(self, url, obj, timeout=15):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        headers = dict(self.headers)
        try:
            if HAS_REQ:
                r = requests.post(url, headers=headers, data=body, timeout=timeout, verify=False)
                return r.json()
            req = urlrequest.Request(url, data=body, headers=headers)
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            print("[4虎] post", url, e)
            return None

    def _load_init(self):
        if self._mac is not None and self._cats is not None:
            return
        j = self._post(self.init_api, {})
        if not j or j.get("errorCode") not in ("0", 0, None):
            # 空 body 有时也行
            j = self._post(self.init_api, {"languageType": "CN"})
        data = (j or {}).get("data") or {}
        self._mac = data.get("macVodLinkMap") or {}
        cats = []
        for m in data.get("menu0ListMap") or []:
            mid = m.get("typeMid")
            if mid != 1 and mid != "1":
                # 只要视频大类；子类 typeMid2=1
                pass
            # 大类本身若是视频
            if mid == 1 or mid == "1":
                tid = str(m.get("typeId") or "")
                name = m.get("typeName") or tid
                if tid:
                    cats.append((tid, name, "1"))
            for s in m.get("menu2List") or []:
                if s.get("typeMid2") in (1, "1"):
                    tid = str(s.get("typeId2") or "")
                    name = s.get("typeName2") or tid
                    if tid and name:
                        cats.append((tid, name, "1"))
        # 去重保序
        seen = set()
        uniq = []
        for c in cats:
            if c[0] in seen:
                continue
            seen.add(c[0])
            uniq.append(c)
        if not uniq:
            # 兜底首页三大类
            uniq = [
                ("1", "传媒", "1"),
                ("2", "视频", "1"),
                ("3", "电影", "1"),
            ]
        self._cats = uniq

    def _card(self, it):
        if not it:
            return None
        vid = str(it.get("id") or "")
        if not vid:
            return None
        pic = it.get("vod_pic") or ""
        if pic and not pic.startswith("http"):
            # 用 server 图床
            sid = str(it.get("vod_server_id") or "")
            link = (self._mac.get(sid) or {}).get("PIC_LINK_1") or ""
            if link:
                pic = link.rstrip("/") + (pic if pic.startswith("/") else "/" + pic)
        return {
            "vod_id": "%s_%s" % (it.get("type_Mid") or 1, vid),
            "vod_name": it.get("vod_name") or vid,
            "vod_pic": pic,
            "vod_remarks": it.get("vod_class") or it.get("typeName") or "",
        }

    def homeContent(self, filter=False):
        self._load_init()
        classes = [{"type_id": c[0], "type_name": c[1]} for c in self._cats]
        j = self._post(
            self.api,
            {"command": "WEB_GET_ALL", "languageType": "CN", "content": ""},
        )
        videos = []
        for block in ((j or {}).get("data") or {}).get("resultList") or []:
            if block.get("t_type") != "M_VOIDE" and block.get("type_Mid") not in (1, "1"):
                continue
            for it in block.get("t_list") or []:
                card = self._card(it)
                if card:
                    videos.append(card)
            if len(videos) >= 24:
                break
        return {"class": classes, "list": videos[:24]}

    def homeVideoContent(self):
        return self.categoryContent(self._cats[0][0] if self._cats else "1", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        self._load_init()
        page = int(pg) if str(pg).isdigit() else 1
        tid = str(tid or "1")
        type_mid = "1"
        for c in self._cats or []:
            if c[0] == tid:
                type_mid = c[2]
                break
        j = self._post(
            self.api,
            {
                "command": "WEB_GET_INFO",
                "pageNumber": page,
                "RecordsPage": 20,
                "typeId": int(tid) if tid.isdigit() else tid,
                "typeMid": int(type_mid) if str(type_mid).isdigit() else type_mid,
                "languageType": "CN",
                "content": "",
            },
        )
        data = (j or {}).get("data") or {}
        videos = []
        for it in data.get("resultList") or []:
            card = self._card(it)
            if card:
                videos.append(card)
        pages = int(data.get("pageAllNumber") or 0) or (page + (1 if videos else 0))
        total = int(data.get("count") or 0) or pages * 20
        return {
            "list": videos,
            "page": page,
            "pagecount": pages,
            "limit": 20,
            "total": total,
        }

    def detailContent(self, ids):
        self._load_init()
        raw = str(ids[0] if isinstance(ids, list) else ids).strip()
        type_mid, vid = "1", raw
        if "_" in raw:
            type_mid, vid = raw.split("_", 1)
        j = self._post(
            self.api,
            {
                "command": "WEB_GET_INFO_DETAIL",
                "type_Mid": int(type_mid) if str(type_mid).isdigit() else type_mid,
                "id": int(vid) if str(vid).isdigit() else vid,
                "languageType": "CN",
            },
        )
        data = (j or {}).get("data") or {}
        res = data.get("result") or {}
        if not res:
            return {"list": []}

        title = res.get("vod_name") or vid
        sid = str(res.get("vod_server_id") or "")
        pic = res.get("vod_pic") or ""
        srv = self._mac.get(sid) or {}
        if pic and not pic.startswith("http"):
            pl = srv.get("PIC_LINK_1") or ""
            if pl:
                pic = pl.rstrip("/") + (pic if pic.startswith("/") else "/" + pic)

        path = res.get("vod_url") or ""
        # 多线路 LINK_1/2/3
        play_from = []
        play_url = []
        for i, key in enumerate(("LINK_1", "LINK_2", "LINK_3"), 1):
            base = (srv.get(key) or "").rstrip("/")
            if not base or not path:
                continue
            full = base + (path if path.startswith("/") else "/" + path)
            # 去重
            if full in play_url:
                continue
            play_from.append("线路%d" % i)
            play_url.append("正片$%s" % full)

        if not play_url and path.startswith("http"):
            play_from = ["线路1"]
            play_url = ["正片$%s" % path]

        return {
            "list": [
                {
                    "vod_id": raw,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": res.get("typeName") or "",
                    "vod_play_from": "$$$".join(play_from) if play_from else "4虎",
                    "vod_play_url": "$$$".join(play_url),
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags=None):
        header = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
            "Origin": self.host,
        }
        url = (id or "").strip()
        if url.startswith("http") and (".m3u8" in url or ".mp4" in url):
            return {"parse": 0, "url": url, "header": header}
        return {"parse": 1, "url": url, "header": header}

    def searchContent(self, key, quick, pg="1"):
        self._load_init()
        page = int(pg) if str(pg).isdigit() else 1
        key = (key or "").strip()
        if not key:
            return {"list": []}
        j = self._post(
            self.api,
            {
                "command": "WEB_GET_INFO",
                "pageNumber": page,
                "RecordsPage": 20,
                "typeId": 1,
                "typeMid": 1,
                "languageType": "CN",
                "content": key,
                "type": "search",
            },
        )
        data = (j or {}).get("data") or {}
        videos = []
        for it in data.get("resultList") or []:
            card = self._card(it)
            if card:
                videos.append(card)
        # 无 type 字段时再试
        if not videos:
            j = self._post(
                self.api,
                {
                    "command": "WEB_GET_INFO",
                    "pageNumber": page,
                    "RecordsPage": 20,
                    "typeId": 2,
                    "typeMid": 1,
                    "languageType": "CN",
                    "content": key,
                },
            )
            data = (j or {}).get("data") or {}
            for it in data.get("resultList") or []:
                card = self._card(it)
                if card:
                    videos.append(card)
        return {"list": videos, "page": page}

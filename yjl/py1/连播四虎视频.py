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

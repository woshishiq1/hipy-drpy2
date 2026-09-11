#联系我们的官方邮箱，您将收到最新地址信息。Email： dizhi@rebao.vip
import sys
import json
import requests
from urllib.parse import quote
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):
    site = "https://rb.jnyk08.icu"
    api = "https://api.vuecloudrb.com"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": site + "/", "Origin": site}

    def getName(self):
        return "91热爆"

    def init(self, extend=""):
        self.site = "https://rb.jnyk08.icu"
        self.api = "https://api.vuecloudrb.com"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.site + "/", "Origin": self.site}

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def _ok(self):
        if not hasattr(self, "api"):
            self.init("")

    def _get(self, path, params=None):
        self._ok()
        r = requests.get(self.api + path, headers=self.headers, params=params or {}, timeout=10)
        return r.json()

    def _time(self, s):
        try:
            s = int(s or 0)
            h, m, sec = s // 3600, s % 3600 // 60, s % 60
            return "%02d:%02d:%02d" % (h, m, sec) if h else "%02d:%02d" % (m, sec)
        except Exception:
            return ""

    def _pic(self, i):
        return i.get("video_img") or i.get("screenshot1") or ""

    def _items(self, data):
        if isinstance(data, dict):
            data = data.get("data") or data.get("list_new", {}).get("data") or data.get("list_hot", {}).get("data") or []
        return [{
            "vod_id": str(i.get("video_id") or i.get("id") or ""),
            "vod_name": i.get("title") or i.get("name") or "",
            "vod_pic": self._pic(i),
            "vod_remarks": self._time(i.get("duration", 0))
        } for i in (data or []) if i.get("video_id") or i.get("id")]

    def homeContent(self, filter):
        cls = [{"type_id": "all", "type_name": "推荐"}, {"type_id": "new", "type_name": "最新"}, {"type_id": "hot", "type_name": "热门"}]
        try:
            c = self._get("/videos/classification", {"page": 1, "size": 50, "categories": 0, "sort": "post_date"}).get("content", [])
            cls += [{"type_id": str(i.get("category_id")), "type_name": i.get("title", "")} for i in c if i.get("category_id")]
        except Exception:
            pass
        data = self._get("/videos/index_byall", {"page": 1, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {})
        return {"class": cls, "list": self._items(data.get("list_new", {}))}

    def homeVideoContent(self):
        data = self._get("/videos/index_byall", {"page": 1, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {})
        return {"list": self._items(data.get("list_new", {}))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        if tid == "all":
            data = self._get("/videos/index", {"page": pg, "size": 24}).get("content", {})
        elif tid == "new":
            data = self._get("/videos/index_byall", {"page": pg, "size": 24, "categories": 0, "sort": "post_date"}).get("content", {}).get("list_new", {})
        elif tid == "hot":
            data = self._get("/videos/index_byall", {"page": pg, "size": 24, "categories": 0, "sort": "video_viewed"}).get("content", {}).get("list_hot", {})
        elif str(tid).startswith("tag_"):
            data = self._get("/videos/list_bytags", {"page": pg, "size": 24, "categories": 0, "sort": "post_date", "tags": str(tid)[4:]}).get("content", {})
        else:
            data = self._get("/videos/index", {"page": pg, "size": 24, "categories": tid, "sort": "post_date"}).get("content", {})
        return {"list": self._items(data), "page": pg, "pagecount": data.get("last_page", pg), "limit": 24, "total": data.get("total", 0)}

    def detailContent(self, ids):
        vid = str(ids[0])
        c = self._get("/videos/detail", {"id": vid}).get("content", {})
        name = c.get("title") or vid
        pic = c.get("video_img") or ""
        tags = ",".join([i.get("tag", "") for i in c.get("tags", []) if isinstance(i, dict)])
        cats = ",".join([i.get("title", "") for i in c.get("categories", []) if isinstance(i, dict)])
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": cats,
            "vod_year": c.get("post_date", ""),
            "vod_area": "",
            "vod_remarks": self._time(c.get("duration", 0)),
            "vod_actor": tags,
            "vod_director": "",
            "vod_content": name,
            "vod_play_from": "直连",
            "vod_play_url": name + "$" + vid
        }]}

    def searchContent(self, key, quick, pg="1"):
        data = self._get("/videos/search", {"keyword": key, "page": int(pg or 1), "limit": 20}).get("content", {})
        return {"list": self._items(data), "page": int(pg or 1), "pagecount": data.get("last_page", 1), "limit": 20, "total": data.get("total", 0)}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        vid = str(id).strip()
        base = str((int(vid) // 1000) * 1000) if vid.isdigit() else vid[:-3] + "000"
        url = "https://delivery.douyinpaly.com/hls/contents/videos/%s/%s/%s.mp4/index.m3u8" % (base, vid, vid)
        return {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": "Mozilla/5.0", "Referer": self.site + "/", "Origin": self.site}}

    def localProxy(self, param):
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

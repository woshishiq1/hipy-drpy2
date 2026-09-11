#电报号https://t.me/canhuakefu
import re
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "一抖阁"

    def init(self, extend=""):
        self.host = "https://yidouge.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Cookie": "gv_age_verified=1",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "Destroy"

    def _html(self, url):
        try:
            return self.session.get(url if url.startswith("http") else self.host + url, timeout=15).text
        except Exception:
            return ""

    def _text(self, s):
        if not s:
            return ""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

    def _pic(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if "images.weserv.nl" in url:
            return url
        if url.endswith(".webp") or "webp" in url.lower():
            return "https://images.weserv.nl/?url=" + url + "&output=jpg"
        return url

    def _list(self, html):
        out = []
        seen = set()
        if not html:
            return out
        # 普通单集卡片
        for block in re.findall(r'<article class="video-card"[^>]*>(.*?)</article>', html, re.S | re.I):
            lm = re.search(r'<a class="video-card__link" href="([^"]+)"', block, re.I)
            if not lm:
                lm = re.search(r'<a class="video-card__body-link" href="([^"]+)"', block, re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm = re.search(r'<h2 class="video-card__title">([^<]+)</h2>', block, re.I)
            im = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
            dm = re.search(r'<span class="video-card__duration">([^<]+)</span>', block, re.I)
            out.append({
                "vod_id": lm.group(1),
                "vod_name": self._text(tm.group(1)) if tm else "",
                "vod_pic": self._pic(im.group(1)) if im else "",
                "vod_remarks": self._text(dm.group(1)) if dm else "",
            })
        # 合集卡片
        for block in re.findall(r'<article class="video-card ydg-author-collection-card"[^>]*>(.*?)</article>', html, re.S | re.I):
            lm = re.search(r'class="ydg-author-collection-link">\s*<a[^>]+href="([^"]+)"', block, re.S | re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm = re.search(r'<strong class="ydg-author-collection-title">([^<]+)</strong>', block, re.I)
            im = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
            nm = re.search(r'共\s*(\d+)\s*部', block, re.I)
            out.append({
                "vod_id": lm.group(1),
                "vod_name": self._text(tm.group(1)) if tm else "",
                "vod_pic": self._pic(im.group(1)) if im else "",
                "vod_remarks": "合集·共{}部".format(nm.group(1)) if nm else "合集",
            })
        return out

    def _cats(self, html):
        cats = []
        seen = set()
        if not html:
            return cats
        for m in re.finditer(r'<a class="category-parent-link[^"]*"\s+href="([^"]+)"[^>]*>\s*<span>([^<]+)</span>', html, re.I):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            cats.append({"type_name": self._text(m.group(2)), "type_id": href})
        return cats

    def homeContent(self, filter):
        html = self._html("/")
        cats = self._cats(html)
        vods = self._list(html)
        return {"class": cats, "list": vods}

    def homeVideoContent(self):
        html = self._html("/")
        return {"list": self._list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        base = tid.rstrip("/")
        path = base if pg == 1 else base + "/page/{}/".format(pg)
        vods = self._list(self._html(path))
        return {
            "page": pg,
            "pagecount": pg + 1 if vods else pg,
            "limit": len(vods),
            "total": 999999 if vods else 0,
            "list": vods
        }

    def detailContent(self, ids):
        vid = str(ids[0]).strip() if isinstance(ids, list) else str(ids).strip()
        if not vid.startswith("http"):
            vid = self.host + vid
        html = self._html(vid)
        if not html:
            return {"list": []}

        name = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        pic = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)

        vod_name = self._text(name.group(1)) if name else vid
        vod_pic = self._pic(pic.group(1)) if pic else ""
        vod_content = desc.group(1).strip() if desc else ""

        # 合集页：进入后拆出多集
        if "/creator/" in vid:
            episodes = self._list(html)
            parts = []
            for i, v in enumerate(episodes, 1):
                title = v.get("vod_name") or ("第{}集".format(i))
                parts.append("{}${}".format(title, v.get("vod_id")))
            if not parts:
                parts = ["播放${}".format(vid)]
            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic or (episodes[0].get("vod_pic") if episodes else ""),
                "type_name": "",
                "vod_year": "",
                "vod_content": vod_content,
                "vod_play_from": "合集",
                "vod_play_url": "#".join(parts),
            }
            return {"list": [vod]}

        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "type_name": "",
            "vod_year": "",
            "vod_content": vod_content,
            "vod_play_from": "一抖阁",
            "vod_play_url": "播放${}".format(vid),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        wd = quote(str(key), safe="")
        path = "/?s={}&post_type=video".format(wd) if pg == 1 else "/?s={}&post_type=video&paged={}".format(wd, pg)
        vods = self._list(self._html(path))
        return {
            "page": pg,
            "pagecount": pg + 1 if vods else pg,
            "limit": len(vods),
            "total": 999999 if vods else 0,
            "list": vods
        }

    def playerContent(self, flag, id, vipFlags):
        page = str(id).strip()
        if not page.startswith("http"):
            page = self.host + page
        html = self._html(page)
        url = ""
        # 方法1: 从 ld+json 提取
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
            data = m.group(1).strip()
            if '"contentUrl"' not in data and '"embedUrl"' not in data:
                continue
            cm = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', data)
            if cm:
                url = cm.group(1)
                break
        # 方法2: 从页面直接找 mp4
        if not url:
            mp4_match = re.search(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', html, re.I)
            if mp4_match:
                url = mp4_match.group(0)
        # 方法3: 从 goon player config 找
        if not url:
            cfg = re.search(r'var GoonPlayerConfig\s*=\s*({.*?});', html, re.S)
            if cfg:
                try:
                    import json
                    cdata = json.loads(cfg.group(1))
                    # 尝试从API获取视频源
                except Exception:
                    pass
        return {
            "parse": 0 if url else 1,
            "playUrl": "",
            "url": url or page,
            "header": self.headers
        }

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

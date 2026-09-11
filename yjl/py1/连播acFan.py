#!/usr/bin/python
# coding=utf-8
#发任意消息到邮箱，自动获取回家地址
#邮箱地址： acfancom430@gmail.com
import re, json, requests
from urllib.parse import quote, unquote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://acf.f76typd0.work"
        self.hosts = ["https://acf.f76typd0.work"]
        self.name = "AcFan"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G9750 Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/89.0.4389.72 MQQBrowser/6.2 TBS/046279 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.verify = False
        self.cat_path = {
            "guochan": "GC/2075051039321464834",
            "Ai漫剧": "MANJU/2089978565981192194",
            "rifan": "3/2072212947517390849",
            "pao": "ITEM_LI9_TWI_N6Y/2072654840359600130",
            "motion": "MOTION_ANIME/2072654931050029058",
            "dcg": "2/2072212891277045761",
            "twofived": "2_5D/2072655042194890753",
            "twod": "2D/2072655119809298434",
            "aigen": "AI/2072655204107608066",
            "mmd": "MMD/2072655243595792385",
            "cosplay": "COSPLAY/2075576278568513538",
        }
        self.class_list = [
            {"type_name": "国产动漫", "type_id": "guochan"},
            {"type_name": "Ai漫剧", "type_id": "Ai漫剧"},
            {"type_name": "里番", "type_id": "rifan"},
            {"type_name": "泡面番", "type_id": "pao"},
            {"type_name": "Motion Anime", "type_id": "motion"},
            {"type_name": "3DCG", "type_id": "dcg"},
            {"type_name": "2.5D", "type_id": "twofived"},
            {"type_name": "2D动画", "type_id": "twod"},
            {"type_name": "AI生成", "type_id": "aigen"},
            {"type_name": "MMD", "type_id": "mmd"},
            {"type_name": "Cosplay", "type_id": "cosplay"},
        ]
        self.default_pic = self.host + "/images/default-cover.svg"

    def init(self, extend=""):
        pass

    def proxy_img(self, url):
        if not url or not url.startswith("http") or "127.0.0.1" in url or "/media-proxy" in url:
            return url
        return self.host + "/media-proxy?url=" + quote(url, safe="")

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".avi", ".flv", ".mkv", ".ts"]) or "m3u8" in url.lower()

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        data = []
        try:
            html = self.fetch(self.host + "/")
            data = self.parseList(html)
        except:
            pass
        return {"class": self.class_list, "list": data}

    def homeVideoContent(self):
        try:
            html = self.fetch(self.host + "/")
            return {"list": self.parseList(html)[:24]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg and str(pg).isdigit() else 1
        path = self.cat_path.get(tid, "")
        if not path:
            return {"page": page, "pagecount": 1, "limit": 24, "total": 0, "list": []}
        if page > 1:
            url = self.host + "/category/" + path + "/page/" + str(page)
        else:
            url = self.host + "/category/" + path
        html = self.fetch(url)
        pages = [int(p) for p in re.findall(r"/category/[^\"']+/page/(\d+)", html)]
        pc = max(pages) if pages else 1
        data = self.parseList(html)
        return {"page": page, "pagecount": pc, "limit": 24, "total": pc * 24, "list": data}

    def detailContent(self, ids):
        sid = ids[0] if ids else ""
        ps = sid.split("@@@")
        vid = ps[0] if len(ps) > 0 else sid
        play = ps[1] if len(ps) > 1 else ""
        name = unquote(ps[2]) if len(ps) > 2 else vid
        pic = unquote(ps[3]) if len(ps) > 3 else ""
        if play:
            return {"list": [{
                "vod_id": sid, "vod_name": name, "vod_pic": self.proxy_img(pic),
                "vod_content": name, "vod_play_from": "AcFan",
                "vod_play_url": "播放$" + play
            }]}
        html = self.fetch(self.host + "/watch/" + vid)
        vod_name, vod_pic, vod_content, m3u8, cat_name = vid, "", "", "", ""
        for jm in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            try:
                data = json.loads(jm.group(1))
                if isinstance(data, list):
                    for item in data:
                        t = item.get("@type", "")
                        if t == "VideoObject":
                            vod_name = item.get("name", vod_name)
                            vod_content = item.get("description", "")
                            vod_pic = item.get("thumbnailUrl", "")
                            m3u8 = item.get("contentUrl", "")
                        elif t == "BreadcrumbList":
                            els = item.get("itemListElement", [])
                            if len(els) >= 2:
                                cat_name = els[1].get("name", "")
            except:
                pass
        if not vod_pic:
            og = re.search(r'property="og:image"[^>]*content="([^"]*)"', html)
            vod_pic = og.group(1) if og else ""
        if vod_name == vid:
            tm = re.search(r"<title>(.*?)</title>", html)
            vod_name = tm.group(1).replace(" - AcFan", "").strip() if tm else vid
        tags = list(dict.fromkeys(re.findall(r'href="/search\?tag=([^"]*)"', html)))
        tag_text = " ".join(unquote(t) for t in tags)
        vod_content = (vod_content + "\n" + tag_text).strip() if vod_content else tag_text
        if cat_name:
            vod_content = "分类: " + cat_name + "\n" + vod_content
        play_url = ("播放$" + m3u8) if m3u8 else ""
        return {"list": [{
            "vod_id": sid, "vod_name": vod_name, "vod_pic": self.proxy_img(vod_pic),
            "vod_content": vod_content, "vod_play_from": "AcFan",
            "vod_play_url": play_url
        }]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        wd = quote(key)
        html = self.fetch(self.host + "/search?q=" + wd + "&page=" + str(page))
        pages = [int(p) for p in re.findall(r"/search\?page=(\d+)", html)]
        pc = max(pages) if pages else 1
        return {"list": self.parseList(html), "page": page, "pagecount": pc, "limit": 24, "total": pc * 24}

    def playerContent(self, flag, id, vipFlags):
        sid = id or ""
        ps = sid.split("@@@")
        url = ps[1] if len(ps) > 1 else sid
        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": self.headers}
        html = self.fetch(self.host + "/watch/" + ps[0])
        m3u8 = ""
        for jm in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            try:
                data = json.loads(jm.group(1))
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "VideoObject":
                            m3u8 = item.get("contentUrl", "")
                            break
            except:
                pass
        if m3u8:
            return {"parse": 0, "url": m3u8, "header": self.headers}
        return {"parse": 1, "url": url, "header": self.headers}

    def localProxy(self, param):
        return [200, "text/plain", b""]

    def destroy(self):
        return "success"

    def fetch(self, url):
        for _ in range(3):
            try:
                r = self.session.get(url, headers=self.headers, timeout=10, verify=False)
                return r.text or ""
            except:
                pass
        return ""

    def parseList(self, html):
        res = []
        if not html:
            return res
        cover_map = self.getCoverMap(html)
        seen = set()
        for m in re.finditer(r'href="/watch/(CNT\d+)"', html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            block = html[m.start():m.start() + 6000]
            name = self.match(block, r'<img[^>]*alt="([^"]*)"') or vid
            duration = self.match(block, r'>(\d{1,3}:\d{2}(?::\d{2})?)</span>') or ""
            pic = cover_map.get(vid, self.default_pic)
            sid = vid + "@@@" + "" + "@@@" + quote(name) + "@@@" + quote(pic)
            res.append({
                "vod_id": sid,
                "vod_name": self.clean(name),
                "vod_pic": self.proxy_img(pic),
                "vod_remarks": self.clean(duration) if duration else ""
            })
        if not res:
            res = self.parseListFromPush(html)
        return res

    def getCoverMap(self, html):
        m = {}
        if not html:
            return m
        try:
            for cm in re.finditer(r'coverUrl', html):
                pos = cm.end()
                rest = html[pos:pos + 200]
                um = re.search(r'https?://[^\s"\\]+', rest)
                if not um:
                    continue
                cover = um.group(0)
                back = html[max(0, cm.start() - 300):cm.start()]
                im = re.findall(r'CNT\d+', back)
                if not im:
                    continue
                vid = im[-1]
                if vid not in m:
                    m[vid] = cover
        except:
            pass
        return m

    def parseListFromPush(self, html):
        res = []
        if not html:
            return res
        try:
            cover_map = self.getCoverMap(html)
            seen = set()
            for cm in re.finditer(r'coverUrl', html):
                pos = cm.end()
                rest = html[pos:pos + 200]
                um = re.search(r'https?://[^\s"\\]+', rest)
                if not um:
                    continue
                cover = um.group(0)
                back = html[max(0, cm.start() - 300):cm.start()]
                ids = re.findall(r'CNT\d+', back)
                if not ids:
                    continue
                vid = ids[-1]
                if vid in seen:
                    continue
                seen.add(vid)
                tm = re.search(r'title[^h]*([^\s"\\]{2,})', back)
                name = tm.group(1) if tm else vid
                sid = vid + "@@@" + "" + "@@@" + quote(name) + "@@@" + quote(cover)
                res.append({
                    "vod_id": sid,
                    "vod_name": self.clean(name),
                    "vod_pic": self.proxy_img(cover),
                    "vod_remarks": ""
                })
        except:
            pass
        return res

    def match(self, text, pat):
        m = re.search(pat, text or "", re.I)
        return m.group(1) if m else ""

    def clean(self, text):
        text = re.sub(r"<[^>]+>", " ", text or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def fix(self, url):
        url = (url or "").strip().replace("\\/", "/")
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.host + url
        return url

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

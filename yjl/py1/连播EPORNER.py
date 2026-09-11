#author Kyle
import sys
import time
import json
import re
import urllib.parse
from base64 import b64decode, b64encode
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://www.eporner.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': self.host + '/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        self.timeout = 10
        self.retries = 2
        self.cookies = {"EPRNS": "1"}

    def getName(self):
        return "EP涩"

    def isVideoFormat(self, url): 
        return True

    def manualVideoCheck(self): 
        return False

    def destroy(self): 
        pass

    def homeContent(self, filter):
        result = {}
        result['class'] = [
            {"type_id": "/cat/all/", "type_name": "最新"},
            {"type_id": "/best-videos/", "type_name": "最佳视频"},
            {"type_id": "/top-rated/", "type_name": "最高评分"},
            {"type_id": "/cat/4k-porn/", "type_name": "4K"},
        ]
        return result

    def homeVideoContent(self):
        result = {}
        videos = self._api_search(query="all", page=1, order="latest", gay="0", per_page=20)
        result['list'] = videos
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        params = self._map_tid_to_api(tid)
        videos = self._api_search(page=int(pg), **params)
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = len(videos) or 20
        result['total'] = 999999
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {}
        videos = self._api_search(query=key or "all", page=int(pg), order="latest", gay="0")
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = len(videos) or 20
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        result = {}
        url = ids[0]
        if not url.startswith('http'): 
            url = self.host + url
        r = self.fetch(url, headers=self.headers)
        root = self.html(r.text)
        og_title = root.xpath('//meta[@property="og:title"]/@content')
        if og_title:
            title = og_title[0].replace(' - EPORNER', '').strip()
        else:
            h1 = "".join(root.xpath('//h1//text()'))
            title = re.sub(r"\s*(\d+\s*min.*)$", "", h1).strip() or "爱看AV"
        img_elem = root.xpath('//meta[@property="og:image"]/@content') or root.xpath('//img[@id="mainvideoimg"]/@src')
        thumbnail = img_elem[0] if img_elem else ""
        meta_desc = (root.xpath('//meta[@name="description"]/@content') or root.xpath('//meta[@property="og:description"]/@content'))
        desc_text = meta_desc[0] if meta_desc else ""
        dur_match = re.search(r"Duration:\s*([0-9:]+)", desc_text)
        duration = dur_match.group(1) if dur_match else ""
        encoded_url = self.e64(url)
        play_url = f"播放${encoded_url}"
        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": thumbnail,
            "vod_remarks": duration,
            "vod_content": desc_text.strip(),
            "vod_play_from": "🍑Play",
            "vod_play_url": play_url
        }
        result['list'] = [vod]
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        url = self.d64(id)
        if not url.startswith('http'):
            url = self.host + url
        r = self.fetch(url, headers=self.headers)
        html_content = r.text
        pattern = r"vid\s*=\s*'([^']+)';\s*[\w*\.]+hash\s*=\s*['\"]([\da-f]{32})"
        match = re.search(pattern, html_content)
        if match:
            vid, hash_val = match.groups()
            hash_code = ''.join((self.encode_base_n(int(hash_val[i:i + 8], 16), 36) for i in range(0, 32, 8)))
            xhr_url = f"{self.host}/xhr/video/{vid}?hash={hash_code}&device=generic&domain=www.eporner.com&fallback=false&embed=false&supportedFormats=mp4"
            xhr_headers = {
                **self.headers,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            resp = self.fetch(xhr_url, headers=xhr_headers)
            data = json.loads(resp.text)
            if data.get("available", True):
                sources_block = data.get("sources", {})
                sources = sources_block.get("mp4", {})
                final_url = None
                if sources:
                    quality_sorted = sorted(sources.keys(), key=lambda q: int(re.sub(r"\D", "", q) or 0), reverse=True)
                    best_quality = quality_sorted[0]
                    final_url = sources[best_quality].get("src")
                else:
                    hls = sources_block.get("hls")
                    if isinstance(hls, dict):
                        final_url = hls.get("src")
                    elif isinstance(hls, list) and hls:
                        final_url = hls[0].get("src")
                    best_quality = "hls"
                if final_url:
                    result["parse"] = 0
                    result["url"] = final_url
                    result["header"] = {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': url,
                        'Origin': self.host,
                        'Accept': '*/*'
                    }
        return result

    def encode_base_n(self, num, n, table=None):
        FULL_TABLE = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        if not table:
            table = FULL_TABLE[:n]
        if n > len(table):
            raise ValueError('base %d exceeds table length %d' % (n, len(table)))
        if num == 0:
            return table[0]
        ret = ''
        while num:
            ret = table[num % n] + ret
            num = num // n
        return ret

    def e64(self, text):
        return b64encode(text.encode()).decode()

    def d64(self, encoded_text):
        return b64decode(encoded_text.encode()).decode()

    def html(self, content):
        from lxml import etree
        return etree.HTML(content)

    def fetch(self, url, headers=None, timeout=None):
        import requests, ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        if headers is None:
            headers = self.headers
        if timeout is None:
            timeout = self.timeout
        for _ in range(self.retries + 1):
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False, cookies=getattr(self, 'cookies', None))
            resp.encoding = 'utf-8'
            return resp
            time.sleep(1)
        raise Exception("Fetch failed")

    def _parse_video_list(self, root):
        videos = []
        items = root.xpath('//div[contains(@class, "mb") and @data-id]')
        for item in items:
            link = item.xpath('.//a[contains(@href, "/video-")]/@href')
            if not link: 
                continue
            vod_id = self.host + link[0]
            title = "".join(item.xpath('.//p[contains(@class, "mbtit")]//text()')).strip()
            img = item.xpath('.//img/@src')
            thumbnail = img[0] if img else ""
            duration = "".join(item.xpath('.//span[contains(@class,"mbtim")]/text()')).strip()
            videos.append({
                "vod_id": vod_id,
                "vod_name": title or "爱看AV",
                "vod_pic": thumbnail,
                "vod_remarks": duration
            })
        return videos

    def _map_tid_to_api(self, tid: str):
        params = {"query": "all", "order": "latest", "gay": "0", "per_page": 30}
        t = (tid or '').strip('/').lower()
        if t.startswith('best-videos'):
            params["order"] = "most-popular"
        elif t.startswith('top-rated'):
            params["order"] = "top-rated"
        elif t.startswith('cat/4k-porn'):
            params["query"] = "4k"
        elif t.startswith('cat/gay'):
            params["gay"] = "2"
            params["order"] = "latest"
        else:
            params["gay"] = "0"
        return params

    def _api_search(self, query="all", page=1, order="latest", gay="0", per_page=30, thumbsize="medium"):
        base = f"{self.host}/api/v2/video/search/"
        q = {
            "query": query,
            "per_page": per_page,
            "page": page,
            "thumbsize": thumbsize,
            "order": order,
            "format": "json"
        }
        if gay is not None:
            q["gay"] = gay
        url = base + "?" + urllib.parse.urlencode(q)
        r = self.fetch(url, headers={**self.headers, 'X-Requested-With': 'XMLHttpRequest'})
        data = json.loads(r.text)
        return self._parse_api_list(data)

    def _parse_api_list(self, data: dict):
        videos = []
        for v in (data or {}).get('videos', []):
            vurl = v.get('url') or ''
            title = v.get('title') or ''
            thumb = (v.get('default_thumb') or {}).get('src') or ''
            remarks = v.get('length_min') or ''
            videos.append({
                "vod_id": vurl if vurl.startswith('http') else (self.host + vurl),
                "vod_name": title or "爱看AV",
                "vod_pic": thumb,
                "vod_remarks": remarks
            })
        return videos

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

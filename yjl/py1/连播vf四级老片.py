# coding=utf-8
import re
import json
import random
import string
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    R_IFRAME = re.compile(r'src=["\'](https?://(?:[^"\'/]*(?:d000d|doood|myvidplay)\.[a-z]+)/e/[a-zA-Z0-9]+)', re.I)
    R_MD5 = re.compile(r"/pass_md5/[^'\"]+")
    R_EXT = re.compile(r"\.(mp4|flv|m3u8)(\?|$)", re.I)

    def init(self, extend=""):
        self.host = 'https://vintagepornfun.com'
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host, 'Origin': self.host, 'Connection': 'keep-alive'
        }
        self.session.headers.update(self.headers)
        
        self.sort_conf = {"key": "order", "name": "排序", "value": [
            {"n": "默认", "v": ""},
            {"n": "最新", "v": "date"},
            {"n": "随机", "v": "rand"},
            {"n": "标题", "v": "title"},
            {"n": "热度", "v": "comment_count"}
        ]}

        self.tag_conf = {"key": "tag", "name": "标签", "value": [
            {"n": "全部", "v": ""},
            {"n": "70年代", "v": "70s-porn"},
            {"n": "80年代", "v": "80s-porn"},
            {"n": "90年代", "v": "90s-porn"},
            {"n": "肛交", "v": "anal-sex"},
            {"n": "亚洲", "v": "asian"},
            {"n": "大胸", "v": "big-boobs"},
            {"n": "金发", "v": "blonde"},
            {"n": "经典", "v": "classic"},
            {"n": "喜剧", "v": "comedy"},
            {"n": "绿帽", "v": "cuckold"},
            {"n": "黑人", "v": "ebony"},
            {"n": "欧洲", "v": "european"},
            {"n": "法国", "v": "french"},
            {"n": "德国", "v": "german"},
            {"n": "群交", "v": "group-sex"},
            {"n": "多毛", "v": "hairy-porn"},
            {"n": "跨种族", "v": "interracial"},
            {"n": "意大利", "v": "italian"},
            {"n": "女同", "v": "lesbian"},
            {"n": "熟女", "v": "milf"},
            {"n": "乱交", "v": "orgy"},
            {"n": "户外", "v": "public-sex"},
            {"n": "复古", "v": "retro"},
            {"n": "少女", "v": "teen-sex"},
            {"n": "3P", "v": "threesome"},
            {"n": "老片", "v": "vintage-porn"},
            {"n": "偷窥", "v": "voyeur"}
        ]}

    def getName(self): return "复古片"
    def isVideoFormat(self, url): return bool(url) and ('.m3u8' in url or self.R_EXT.search(url))

    def _fetch(self, url, headers=None):
        try:
            r = self.session.get(url, headers=headers or self.headers, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except: return None

    def _resolve_myvidplay(self, url):
        try:
            embed = url.replace("/d/", "/e/")
            for d in ['d000d.com', 'doood.com']: 
                if d in embed: embed = embed.replace(d, 'myvidplay.com')
            
            host = f"{urlparse(embed).scheme}://{urlparse(embed).netloc}"
            h_req = {"User-Agent": self.headers['User-Agent'], "Referer": self.host}
            
            if not (r := self.session.get(embed, headers=h_req, timeout=15)) or not (m := self.R_MD5.search(r.text)):
                return {'parse': 1, 'url': url, 'header': h_req}
            
            h_req["Referer"] = embed
            prefix = self.session.get(host + m.group(0), headers=h_req, timeout=15).text.strip()
            
            if not prefix.startswith("http"): return {'parse': 1, 'url': url, 'header': h_req}
            
            token = m.group(0).split("/")[-1]
            rnd = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            return {
                'parse': 0, 'url': f"{prefix}{rnd}?token={token}",
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': f"{host}/", 'Connection': 'keep-alive'}
            }
        except: return {'parse': 1, 'url': url, 'header': self.headers}

    def homeContent(self, filter):
        classes = [
            {"type_name": "最新更新", "type_id": "latest"},
            {"type_name": "70年代", "type_id": "70s-porn"},
            {"type_name": "80年代", "type_id": "80s-porn"},
            {"type_name": "亚洲经典", "type_id": "asian-vintage-porn"},
            {"type_name": "欧洲经典", "type_id": "euro-porn-movies"},
            {"type_name": "日本经典", "type_id": "japanese-vintage-porn"},
            {"type_name": "法国经典", "type_id": "french-vintage-porn"},
            {"type_name": "德国经典", "type_id": "german-vintage-porn"},
            {"type_name": "意大利经典", "type_id": "italian-vintage-porn"},
            {"type_name": "经典影片", "type_id": "classic-porn-movies"}
        ]
        
        filters = {item['type_id']: [self.sort_conf, self.tag_conf] for item in classes}
        return {"class": classes, "filters": filters}

    def homeVideoContent(self): 
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        if tid == "latest":
            url = self.host if pg == "1" else f"{self.host}/page/{pg}/"
        else:
            base = f"{self.host}/category/{tid}"
            url = f"{base}/" if pg == "1" else f"{base}/page/{pg}/"
        
        query_parts = []
        if 'order' in extend and extend['order']:
            query_parts.append(f"orderby={extend['order']}")
        if 'tag' in extend and extend['tag']:
            query_parts.append(f"tag={extend['tag']}")
            
        if query_parts:
            sep = '&' if '?' in url else '?'
            url += sep + '&'.join(query_parts)

        return self._get_list(url, int(pg))

    def _get_list(self, url, page=1):
        videos = []
        if soup := self._fetch(url):
            for item in soup.select('article'):
                if not (a := item.select_one('a[href]')): continue
                
                img = item.select_one('img')
                pic = img.get('data-src') or img.get('src') or ""
                if pic and not pic.startswith('http'): pic = urljoin(self.host, pic)
                
                head = item.select_one('.entry-header')
                rem = item.select_one('.rating-bar')
                
                videos.append({
                    "vod_id": a['href'],
                    "vod_name": head.get_text(strip=True) if head else a.get('title', ''),
                    "vod_pic": pic,
                    "vod_remarks": rem.get_text(strip=True) if rem else ""
                })
        
        return {
            "list": videos, 
            "page": page, 
            "pagecount": page + 1 if videos else page, 
            "limit": 20, 
            "total": 999
        }

    def detailContent(self, ids):
        if not (soup := self._fetch(ids[0])): return {'list': []}
        
        meta_img = soup.find('meta', property='og:image')
        meta_desc = soup.find('meta', property='og:description')
        
        play_url = ""
        if m := self.R_IFRAME.search(str(soup)): play_url = m.group(1)
        elif iframe := soup.select_one('iframe[src*="/e/"]'): play_url = iframe['src']

        return {"list": [{
            "vod_id": ids[0],
            "vod_name": soup.select_one('h1').get_text(strip=True) if soup.select_one('h1') else "",
            "vod_pic": meta_img['content'] if meta_img else "",
            "vod_content": meta_desc['content'] if meta_desc else "",
            "vod_play_from": "文艺复兴",
            "vod_play_url": f"HD${play_url}" if play_url else "无资源$#"
        }]}

    def searchContent(self, key, quick, pg="1"):
        return self._get_list(f"{self.host}/page/{pg}/?s={requests.utils.quote(key)}", int(pg))

    def playerContent(self, flag, id, vipFlags):
        if flag == 'myvidplay' or any(x in id for x in ['myvidplay', 'd000d', 'doood']):
            return self._resolve_myvidplay(id)
        return {'parse': 1, 'url': id, 'header': self.headers}

    def localProxy(self, params): pass

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

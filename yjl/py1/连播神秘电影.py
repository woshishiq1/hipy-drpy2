# -*- coding: utf-8 -*-
#神秘
import re
import urllib.parse
from base.spider import Spider as BaseSpile
import requests
from bs4 import BeautifulSoup


class VideoDecryptor:
    """XOR 128 解密"""
    @staticmethod
    def decrypt(text: str) -> str:
        if not text:
            return ""
        try:
            return ''.join(chr(128 ^ ord(c)) for c in text)
        except:
            return text

    @staticmethod
    def from_js(js: str) -> str:
        return VideoDecryptor.decrypt(m.group(1)) if (m := re.search(r"document\.write\(l\('([^']+)'\)\)", js)) else ""


class Spider(BaseSpile):

    def init(self, extend=""):
        self.host = "https://h4ivs.sm431.vip"
        self.video_host = "https://38.je:38"
        self.image_host = "https://38.je:36"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22127RK46C Build/TKQ1.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/104.0.5112.97 Mobile Safari/537.36",
            "Referer": self.host,
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.cache = {}

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except:
            return "神秘电影"

    def img_url(self, url):
        """格式化图片URL"""
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = self.image_host + url
        return f"{url}@User-Agent={self.headers['User-Agent']}@Referer={self.host}/"

    def parse(self, el):
        """解析卡片"""
        a = el if el.name == 'a' else el.find('a')
        if not a or not (href := a.get("href", "")):
            return None
        
        href = self.host + href if href.startswith("/") else href
        if not (vid := re.search(r"/vid/(\d+)", href)):
            return None
        
        vid = vid.group(1)
        title = ""

        # 解密标题
        if p := el.find('p'):
            if s := p.find('script'):
                if s.string:
                    title = VideoDecryptor.from_js(s.string)
            title = title or p.get_text(strip=True)
        
        if not title:
            for attr in ['data-title', 'data-name', 'title']:
                if el.has_attr(attr) and (val := el[attr]):
                    if (de := VideoDecryptor.decrypt(val)) and len(de) > 3:
                        title = de
                        break
        
        title = title or "未知标题"
        if title != "未知标题":
            self.cache[vid] = title

        # 图片
        img = ""
        if node := el.select_one("img"):
            img = node.get("data-src") or node.get("src") or ""
        img = img or f"{self.image_host}/{vid}.jpg"

        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self.img_url(img),
            "vod_remarks": "",
        }

    def get_title(self, vid):
        """从缓存或首页获取标题"""
        if vid in self.cache:
            return self.cache[vid]
        
        if html := self.get(self.host):
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.select('a[href*="/vid/"]'):
                if f'/vid/{vid}' in link.get('href', ''):
                    if p := link.find('p'):
                        if s := p.find('script'):
                            if s.string and (t := VideoDecryptor.from_js(s.string)):
                                self.cache[vid] = t
                                return t
                        if t := p.get_text(strip=True):
                            self.cache[vid] = t
                            return t
        return None

    def homeContent(self, filter):
        return {
            "class": [
                {"type_name": "国产", "type_id": "1"},
                {"type_name": "日本", "type_id": "2"},
                {"type_name": "韩国", "type_id": "3"},
                {"type_name": "欧美", "type_id": "4"},
                {"type_name": "三级", "type_id": "5"},
                {"type_name": "动漫", "type_id": "6"},
            ]
        }

    def homeVideoContent(self):
        if not (html := self.get(self.host)):
            return {"list": []}
        
        soup = BeautifulSoup(html, "html.parser")
        videos = [v for v in (self.parse(el) for el in soup.select(".vodbox, .stui-vodlist__box, .vodlist__box, .video-card, .item")) if v]
        
        if not videos:
            videos = [{"vod_id": v, "vod_name": "未知标题", "vod_pic": self.img_url(f"{self.image_host}/{v}.jpg"), "vod_remarks": ""} 
                     for v in re.findall(r'\[]\(/vid/(\d+)\.html\)', html)]
        
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        if tid == "0":
            url = self.host if int(pg) == 1 else f"{self.host}/page/{pg}.html"
        else:
            url = f"{self.host}/list/{tid}.html" if int(pg) == 1 else f"{self.host}/list/{tid}/{pg}.html"
        
        if not (html := self.get(url)):
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
        
        soup = BeautifulSoup(html, "html.parser")
        videos = [v for v in (self.parse(el) for el in soup.select(".vodbox, .stui-vodlist__box, .vodlist__box, .video-card, .item")) if v]
        
        if not videos:
            videos = [{"vod_id": v, "vod_name": "未知标题", "vod_pic": self.img_url(f"{self.image_host}/{v}.jpg"), "vod_remarks": ""} 
                     for v in re.findall(r'\[]\(/vid/(\d+)\.html\)', html)]
        
        last = max([int(m.group(1)) for a in soup.select("a[href*='list/']") if (m := re.search(r"/list/\d+/(\d+)\.html", a.get("href", "")))], default=int(pg))
        
        return {"list": videos, "page": pg, "pagecount": max(last, 1), "limit": 30, "total": 99999}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/so.html"
        params = {"wd": key}
        if int(pg) > 1:
            params["page"] = pg
        
        html = ""
        for method in [requests.get, requests.post]:
            try:
                r = method(url, params=params if method == requests.get else None, 
                          data=params if method == requests.post else None, 
                          headers=self.headers, timeout=15)
                r.raise_for_status()
                r.encoding = "utf-8"
                html = r.text
                break
            except:
                continue
        
        if not html:
            return {"list": []}
        
        soup = BeautifulSoup(html, "html.parser")
        videos = [v for v in (self.parse(el) for el in soup.select(".vodbox, .stui-vodlist__box, .vodlist__box, .video-card, .item")) if v]
        
        if not videos:
            videos = [{"vod_id": v, "vod_name": "未知标题", "vod_pic": self.img_url(f"{self.image_host}/{v}.jpg"), "vod_remarks": ""} 
                     for v in re.findall(r'\[]\(/vid/(\d+)\.html\)', html)]
        
        last = max([int(m.group(1)) for a in soup.select("a[href*='so.html'], .pagination a, .page-link") 
                   if (m := re.search(r"[?&]page=(\d+)", a.get("href", "")))], default=int(pg))
        
        return {"list": videos, "page": pg, "pagecount": max(last, 1), "limit": 30, "total": 99999}

    def detailContent(self, ids):
        vid = ids[0]
        if not (html := self.get(f"{self.host}/vid/{vid}.html")):
            return {"list": []}
        
        soup = BeautifulSoup(html, "html.parser")
        
        # 标题
        title = self.get_title(vid)
        if not title:
            if t := soup.find('title'):
                title = re.sub(r'\s*[-_|]\s*.{0,20}$', '', t.get_text(strip=True)).strip()
            
            if not title or len(title) < 5:
                for sel in ['h1', 'h2', '.video-title', '.title']:
                    if (el := soup.select_one(sel)) and (txt := el.get_text(strip=True)) and len(txt) > 5:
                        title = txt
                        break
        
        title = title or f"视频{vid}"
        
        # 图片
        pic = ""
        for sel in ['.picbox img', '.vodimg img', '.video-pic img', '.poster img', 'img[data-id]']:
            if (node := soup.select_one(sel)) and (p := node.get("data-src") or node.get("src")) and 'favicon' not in p.lower():
                pic = p
                break
        
        if not pic or 'favicon' in pic.lower():
            if meta := soup.select_one('meta[property="og:image"]'):
                pic = meta.get('content', '')
        
        pic = pic or f"{self.image_host}/{vid}.jpg"
        
        # 简介
        desc = soup.select_one(".vodinfo, .video-info, .content, .intro, .description")
        desc = desc.get_text(strip=True) if desc else ""
        
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self.img_url(pic),
            "vod_content": desc,
            "vod_play_from": "神秘线路",
            "vod_play_url": f"全集${vid}@@0@@1",
        }]}

    def playerContent(self, flag, id, vipFlags):
        vid = id.split("@@")[0]
        return {"parse": 0, "url": f"{self.video_host}/{vid}/hls/index.m3u8", "header": self.headers}

    def localProxy(self, param):
        return {"code": 404, "content": ""}

    def isVideoFormat(self, url):
        return ".m3u8" in url.lower()

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

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

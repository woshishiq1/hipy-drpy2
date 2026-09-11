#方法2:邮箱发送任意内容邮件可获取最新地址
#官方邮箱： baoguawang1@gmail.com
#方法3:收藏爆瓜网官方最新地址发布页 https://gitlab.com/bgw1com/bgw1com


import re
import json
import base64
try:
    import requests as _requests
except Exception:
    _requests = None
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.site = "https://besides.vumjtkcnc.cc"
        self.name = "爆瓜网"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._home = None
        self._cat_map = {
            "zxcgbl": "最新吃瓜",
            "rmcgbl": "热搜排行",
            "pronhub": "亚洲精选",
            "zsxybl": "桃色校园",
            "tpzq": "偷拍专区",
            "whscbl": "明星网红",
            "fcnsbl": "反差网黄",
            "crycll": "伦理道德",
            "mxbzbg": "AI专区",
            "rmbl": "欧美精选",
        }

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

    def init(self, extend=""):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                pass

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15, allow_redirects=True)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _html_unescape(self, s):
        import html as _h
        return _h.unescape(s) if s else s

    def _pic_proxy(self, url):
        url = self._u(url or "")
        if not url:
            return ""
        try:
            proxy = self.getProxyUrl()
            if not proxy:
                return url
            sep = "&" if "?" in proxy else "?"
            enc = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
            site_key = ""
            try:
                from urllib.parse import quote
                site_key = quote(str(getattr(self, "siteKey", "") or ""), safe="")
                enc = quote(enc, safe="")
            except Exception:
                pass
            target = proxy + sep + "do=py" if "do=py" not in proxy else proxy
            if site_key:
                target += "&siteKey=" + site_key
            return target + "&type=img&url=" + enc
        except Exception:
            return url

    def _extract_posts(self, html, allow_hot=True):
        out = []
        seen = set()
        # 策略1: 精确匹配 <article> 结构 (Typecho Mirages 主题)
        for m in re.finditer(r'<article\b[^>]*>([\s\S]*?)</article>', html, re.S):
            raw = m.group(0)
            block = m.group(1)
            # 跳过广告项
            if 'class="ad-item"' in raw:
                continue
            hm = re.search(r'<a[^>]+href="((?:https?://[^"]+)?/archives/(\d+)\.html)"', block)
            if not hm:
                continue
            href, vid = hm.group(1), hm.group(2)
            if vid in seen:
                continue
            # 提取图片: z-image-loader-url 属性 (Mirages 懒加载)
            im = re.search(r'<img[^>]+z-image-loader-url="([^"]+)"', block)
            pic = im.group(1) if im else ""
            # 提取标题: h2.post-card-title
            tm = re.search(r'<h2[^>]+class="[^"]*post-card-title[^"]*"[^>]*itemprop="headline"[^>]*>([^<]+)</h2>', block)
            title = tm.group(1).strip() if tm else ""
            if not title:
                alt = re.search(r'<img[^>]+alt="([^"]+)"', block)
                if alt:
                    title = alt.group(1).strip()
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": self._html_unescape(title),
                "vod_pic": self._pic_proxy(pic),
                "vod_remarks": "",
            })
        # 策略2: 兜底 — 从 JS 变量 hotRankList 提取 (首页推荐)
        if not out and allow_hot:
            hm = re.search(r'var\s+hotRankList\s*=\s*(\[.*?\]);', html, re.S)
            if hm:
                try:
                    hot_list = json.loads(hm.group(1))
                    for item in hot_list:
                        vid = str(item.get("cid", ""))
                        if not vid or vid in seen:
                            continue
                        seen.add(vid)
                        out.append({
                            "vod_id": vid,
                            "vod_name": self._html_unescape(item.get("title", "")),
                            "vod_pic": "",
                            "vod_remarks": "",
                        })
                except Exception:
                    pass
        return out

    def _extract_video(self, html):
        # 策略1: DPlayer data-config
        m = re.search(r'<div[^>]*class="[^"]*dplayer[^"]*"[^>]*data-config=\'([^\']+)\'', html)
        if m:
            try:
                cfg = json.loads(m.group(1))
                url = cfg.get("video", {}).get("url", "")
                if url and self.isVideoFormat(url):
                    return url
            except Exception:
                pass
        # 策略2: DPlayer data-config 双引号
        m = re.search(r'<div[^>]*class="[^"]*dplayer[^"]*"[^>]*data-config="([^"]+)"', html)
        if m:
            try:
                cfg = json.loads(m.group(1))
                url = cfg.get("video", {}).get("url", "")
                if url and self.isVideoFormat(url):
                    return url
            except Exception:
                pass
        # 策略3: 直接找 m3u8/mp4
        for pat in [r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)']:
            m = re.search(pat, html)
            if m:
                return m.group(1)
        # 策略4: iframe
        m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if m:
            return m.group(1)
        return ""

    def _cats(self):
        return [{"type_id": k, "type_name": v} for k, v in self._cat_map.items()]

    def homeContent(self, filter=None):
        if self._home is None:
            self._home = self._get(self.site + "/")
        cats = self._cats()
        vod_list = self._extract_posts(self._home)
        return {"class": cats, "list": vod_list}

    def homeVideoContent(self):
        if self._home is None:
            self._home = self._get(self.site + "/")
        return {"list": self._extract_posts(self._home)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        url = "%s/category/%s/" % (self.site, tid)
        if pg > 1:
            url += "%d/" % pg
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 20, "total": 0}
        vod_list = self._extract_posts(html)
        # 提取总页数
        pagecount = pg
        total_m = re.search(r'<span class="page-info" data-total="(\d+)">', html)
        if total_m:
            pagecount = int(total_m.group(1))
        else:
            if re.search(r'href="[^"]*/category/%s/\d+/"' % re.escape(tid), html):
                pagecount = pg + 1
        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 20, "total": len(vod_list)}

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        vid = str(vid or "").strip()
        if not vid:
            return {"list": []}
        url = "%s/archives/%s.html" % (self.site, vid)
        html = self._get(url)
        if not html:
            return {"list": []}
        # 标题
        title = ""
        tm = re.search(r'<h1[^>]*class="[^"]*post-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
        if tm:
            title = self._html_unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        if not title:
            tm = re.search(r'<title[^>]*>([^<]{2,80})</title>', html)
            if tm:
                title = self._html_unescape(tm.group(1)).strip()
        # 图片: 内容区 data-xkrkllgl 或 og:image
        pic = ""
        im = re.search(r'<img[^>]+data-xkrkllgl="([^"]+)"', html)
        if im:
            pic = im.group(1)
        if not pic:
            im = re.search(r'property="og:image" content="([^"]+)"', html)
            if im:
                pic = im.group(1)
        # 视频
        video_url = self._extract_video(html)
        play_from = self.name
        play_url_str = ""
        if video_url:
            play_url_str = "正片$%s" % video_url
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._pic_proxy(pic),
                "vod_content": "",
                "vod_play_from": play_from,
                "vod_play_url": play_url_str,
            }]
        }

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        try:
            from urllib.parse import quote
            qkey = quote(str(key))
        except Exception:
            qkey = str(key)
        # Typecho搜索: 先尝试 /search/keyword/ (JS重定向后的URL)
        url = "%s/search/%s/" % (self.site, qkey)
        if pg > 1:
            url += "%d/" % pg
        html = self._get(url)
        posts = self._extract_posts(html, allow_hot=False) if html else []
        if not html or len(posts) == 0:
            # fallback: ?s=
            url = "%s/?s=%s" % (self.site, qkey)
            html = self._get(url)
            posts = self._extract_posts(html, allow_hot=False) if html else []
        if not html:
            return {"list": []}
        return {"list": posts}

    def playerContent(self, flag, id, vipFlags=None):
        ids = id
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": dict(self.header), "format": "application/x-mpegURL"}
        if url.startswith("http"):
            return {"parse": 1, "url": url, "header": dict(self.header)}
        return {"parse": 0, "url": "", "header": dict(self.header)}

    def _decode_pic(self, data):
        raw = data or b""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            key = b"f5d965df75336270"
            iv = b"97b60394abc2fbe1"
            if raw and len(raw) % 16 == 0 and not raw.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8", b"RIFF")):
                try:
                    raw = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(raw), 16)
                except Exception:
                    raw = AES.new(key, AES.MODE_CBC, iv).decrypt(raw)
        except Exception:
            pass
        mime = "image/jpeg"
        if raw.startswith(b"\xff\xd8"):
            mime = "image/jpeg"
        elif raw.startswith(b"\x89PNG"):
            mime = "image/png"
        elif raw.startswith(b"GIF8"):
            mime = "image/gif"
        elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            mime = "image/webp"
        return raw, mime

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = {}
        if not isinstance(param, dict):
            param = {}
        ptype = str(param.get("type") or param.get("ptype") or "").lower()
        u = str(param.get("url") or param.get("u") or "")
        try:
            from urllib.parse import unquote_plus
            u = unquote_plus(u)
        except Exception:
            pass
        try:
            pad = "=" * ((4 - len(u) % 4) % 4)
            dec = base64.urlsafe_b64decode((u + pad).encode("ascii")).decode("utf-8")
            if dec.startswith("http"):
                u = dec
        except Exception:
            pass
        if not u or not u.startswith("http"):
            return [403, "text/plain", b"", {}]
        h = dict(self.header)
        data = b""
        ctype = "application/octet-stream"
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15)
                if r.status_code >= 400:
                    return [r.status_code, "text/plain", b"", {}]
                data = r.content
                ctype = r.headers.get("Content-Type", ctype)
            except Exception:
                pass
        if not data:
            try:
                import urllib.request
                req = urllib.request.Request(u, headers=h)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ctype = resp.headers.get("Content-Type", ctype)
                    data = resp.read()
            except Exception:
                return [403, "text/plain", b"", {}]
        if ptype in ("img", "image"):
            data, ctype = self._decode_pic(data)
        return [200, ctype, data, {}]

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

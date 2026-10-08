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

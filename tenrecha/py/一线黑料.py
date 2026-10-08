import json
import re
import math
import posixpath
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

try:
    from concurrent.futures import ThreadPoolExecutor
except ImportError:
    ThreadPoolExecutor = None


class Spider(BaseSpider):

    # ---- 由 m3u8_analyzer 取证结论决定 ----
    # True  = 存在广告目录，走 localProxy 五层清洗
    # False = 无广告特征，直接返回直链
    NEED_CLEAN = True
    AD_ANCHOR = "/20260911/pmWBKnV6/1500kb/hls/"
    AD_DIRS = ["/20260731/UTxI1Mxv/9567kb/hls/"]

    def __init__(self):
        self.extend = ""
        self.hosts = [
            "https://danbady4042982.buzz",
            "https://danbady3674328.xyz",
        ]
        self.host = self.hosts[0]
        self._host_ok = False

        self.classes = [
            {"type_id": "video/type/913", "type_name": "91精选"},
            {"type_id": "video/type/957", "type_name": "精选传媒"},
            {"type_id": "video/type/1234", "type_name": "杏吧资源"},
            {"type_id": "video/type/955", "type_name": "热点专题"},
            {"type_id": "video/type/1304", "type_name": "AI成人"},
            {"type_id": "video/type/956", "type_name": "国产传媒"},
            {"type_id": "video/type/1138", "type_name": "特殊资源"},
            {"type_id": "video/type/1052", "type_name": "少女仓库"},
            {"type_id": "video/type/441", "type_name": "网曝黑料"},
            {"type_id": "video/type/822", "type_name": "精品资源"},
            {"type_id": "video/type/910", "type_name": "大众精品"},
            {"type_id": "video/type/911", "type_name": "番号大全"},
            {"type_id": "video/type/912", "type_name": "热门视频"},
            {"type_id": "video/type/1262", "type_name": "玉兔资源"},
            {"type_id": "video/type/1299", "type_name": "大奶资源"},
            {"type_id": "image/type/961", "type_name": "激情图漫"},
            {"type_id": "novel/type/962", "type_name": "情色小说"},
        ]
        self.filters = {}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
    def getName(self):
        return "一线黑料"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络；域名探测懒加载，放 _pick_host
        self.extend = extend or ""

    def destroy(self):
        self._host_ok = False
        pass

    def _pick_host(self):
        """懒加载域名探测，禁止放 __init__ / homeContent（法则16）"""
        if self._host_ok:
            return
        for h in self.hosts:
            try:
                r = self.fetch(h + "/", headers={"User-Agent": self.headers["User-Agent"]}, timeout=8)
                if r and getattr(r, "status_code", 0) == 200:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    break
            except Exception:
                continue
        self._host_ok = True

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.host + "/", url.lstrip("/"))

    def _get(self, url, timeout=15):
        self._pick_host()
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return getattr(r, "text", "") or ""
        except Exception:
            return ""

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 可能是 list/str/int/bytes"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            out = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {}

    # ==================== 首页 ====================

    def homeContent(self, filter):
        # 零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：取热门视频分类第一页
        return self.categoryContent("video/type/912", "1", False, {})

    # ==================== 列表 ====================

    # 列表卡片: div.pic > ul > li[id^=content] > a[href][title] > img[src] ; span=日期
    _CARD_RE = re.compile(
        r"<li[^>]*id=[\"']?content\d+[\"']?[^>]*>.*?<a[^>]*href=[\"']([^\"']+)[\"'][^>]*title=[\"']([^\"']*)[\"'][^>]*>.*?<img[^>]*?(?:data-src|data-original|src)=[\"']([^\"']+)[\"']",
        re.S | re.I,
    )

    # 有图卡片: li[id^=content] > a[href][title] > img
    _CARD_RE = re.compile(
        r"<li[^>]*id=[\"']?content\d+[\"']?[^>]*>.*?<a[^>]*href=[\"']([^\"']+)[\"'][^>]*title=[\"']([^\"']*)[\"'][^>]*>.*?<img[^>]*?(?:data-src|data-original|src)=[\"']([^\"']+)[\"']",
        re.S | re.I,
    )
    # 无图卡片(小说): <li ...> <a href='/novel/info/xxx.html' title="...">...</a>
    _CARD_NOTXT_RE = re.compile(
        r"<li[^>]*>\s*<a[^>]*href=[\"']([^\"']*(?:novel|video|image)/info/[^\"']+)[\"'][^>]*title=[\"']([^\"']*)[\"']",
        re.S | re.I,
    )

    def _parse_cards(self, html):
        items = []
        seen = set()
        # 先抓有图卡片
        for m in self._CARD_RE.finditer(html or ""):
            href, title, pic = m.group(1), m.group(2), m.group(3)
            vid = self._abs(href)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(title),
                "vod_pic": self._abs(pic),
                "vod_remarks": "",
            })
        # 再抓无图卡片(小说等)，避免漏项
        for m in self._CARD_NOTXT_RE.finditer(html or ""):
            href, title = m.group(1), m.group(2)
            vid = self._abs(href)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(title),
                "vod_pic": "",
                "vod_remarks": "",
            })
        return items
    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", t or "")
        t = t.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        t = t.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
        return t.strip()

    def categoryContent(self, tid, pg, filter, extend):
        self._pick_host()
        page = str(pg or "1")
        tid = str(tid or "").strip().strip("/")
        # tid 形如 video/type/912 或 image/type/961 或 novel/type/962
        if page == "1":
            url = f"{self.host}/{tid}.html"
        else:
            url = f"{self.host}/{tid}/{page}.html"
        html = self._get(url)
        items = self._parse_cards(html)
        # 总页数：页面文本 "共N条数据,当前x/y页"
        pagecount = 9999
        m = re.search(r"当前\s*\d+\s*/\s*(\d+)\s*页", html or "")
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = 9999
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        self._pick_host()
        kw = quote(str(key or "").strip(), safe="")
        page = str(pg or "1")
        urls = [
            f"{self.host}/video/search/{kw}.html",
            f"{self.host}/image/search/{kw}.html",
            f"{self.host}/novel/search/{kw}.html",
        ]
        if page != "1":
            urls = [u.replace(".html", f"/{page}.html") for u in urls]

        results = []
        if ThreadPoolExecutor:
            with ThreadPoolExecutor(max_workers=3) as ex:
                for lst in ex.map(self._search_one, urls):
                    results += lst
        else:
            for u in urls:
                results += self._search_one(u)

        # 去重保序
        seen, out = set(), []
        for it in results:
            if it["vod_id"] not in seen:
                seen.add(it["vod_id"])
                out.append(it)
        return {"list": out, "page": int(page)}

    def _search_one(self, url):
        try:
            html = self._get(url)
            return self._parse_cards(html)
        except Exception:
            return []

    # ==================== 详情 ====================

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            # raw 可能是列表返回的绝对详情URL
            detail_url = raw if raw.startswith("http") else self._abs(raw)
            html = self._get(detail_url)

            # 分类判定
            if "/image/" in detail_url:
                return self._detail_image(detail_url, html)
            if "/novel/" in detail_url:
                return self._detail_novel(detail_url, html)
            return self._detail_video(detail_url, html)
        except Exception as e:
            self.log({"detail": "exception", "error": type(e).__name__})
            return self._skeleton(raw)

    def _page_title(self, html):
        m = re.search(r"<title>(.*?)</title>", html or "", re.S | re.I)
        return self._clean(m.group(1)) if m else ""

    def _page_pic(self, html):
        # 优先 data-img（真实图），src 常为占位 gif
        m = re.search(r'class=["\']detail-img["\'][^>]*?(?:data-img|data-src)=["\']([^"\']+)["\']', html or "", re.S | re.I)
        if m and m.group(1).strip():
            return self._abs(m.group(1))
        m = re.search(r'class=["\']detail-img["\'][^>]*?src=["\']([^"\']+)["\']', html or "", re.S | re.I)
        if m and m.group(1).strip() and not m.group(1).endswith(".gif"):
            return self._abs(m.group(1))
        m = re.search(r'<img[^>]*?(?:data-img|data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html or "", re.S | re.I)
        return self._abs(m.group(1)) if m else ""
    def _detail_video(self, detail_url, html):
        vid = detail_url
        title = self._page_title(html).split("｜")[0].strip()
        title = re.sub(r"\s*[-－]\s*一线黑料.*$", "", title).strip() or "视频"
        pic = self._page_pic(html)
        m = re.search(r"href=[\"']([^\"']*/video/play/[^\"']+)[\"']", html or "")
        if m:
            play_url = self._abs(m.group(1))
        else:
            m2 = re.search(r"/(\d+)\.html", detail_url)
            play_url = f"{self.host}/video/play/{m2.group(1)}.html" if m2 else detail_url

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "线路1",
            "vod_play_url": "正片$" + play_url,
        }]}
    def _detail_image(self, detail_url, html):
        vid = detail_url
        title = self._page_title(html).split("｜")[0].strip() or "图集"
        pic = self._page_pic(html)
        m = re.search(r"href=[\"']([^\"']*/image/play/[^\"']+)[\"']", html or "")
        if m:
            play_url = self._abs(m.group(1))
        else:
            m2 = re.search(r"/(\d+)\.html", detail_url)
            play_url = f"{self.host}/image/play/{m2.group(1)}.html" if m2 else detail_url
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "图片浏览",
            "vod_play_url": "浏览图片$" + play_url,
        }]}
    def _detail_novel(self, detail_url, html):
        vid = detail_url
        title = self._page_title(html).split("｜")[0].strip() or "小说"
        pic = self._page_pic(html)
        m = re.search(r"href=[\"']([^\"']*/novel/play/[^\"']+)[\"']", html or "")
        if m:
            play_url = self._abs(m.group(1))
        else:
            m2 = re.search(r"/(\d+)\.html", detail_url)
            play_url = f"{self.host}/novel/play/{m2.group(1)}.html" if m2 else detail_url
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "章节",
            "vod_play_url": "正文$" + play_url,
        }]}

    def _skeleton(self, vid, title="", pic=""):
        pid = str(vid).replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": "", "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        if not play_url.startswith("http"):
            if play_url.startswith("//"):
                play_url = "https:" + play_url
            else:
                play_url = self._abs(play_url)

        # 图片播放页 -> pics://
        if "/image/play/" in play_url:
            return self._play_image(play_url)
        # 小说播放页 -> novel://
        if "/novel/" in play_url:
            return self._play_novel(play_url)
        # 视频播放页 -> 提取 m3u8
        if "/video/play/" in play_url or "playUrl" in play_url:
            m3u8 = self._extract_play_url(play_url)
            if m3u8:
                return self._wrap_m3u8(m3u8)
        # 已经是直链
        if ".m3u8" in play_url or ".mp4" in play_url:
            if ".m3u8" in play_url:
                return self._wrap_m3u8(play_url)
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}

        # 兜底：当作播放页再试一次
        m3u8 = self._extract_play_url(play_url)
        if m3u8:
            return self._wrap_m3u8(m3u8)
        return {"parse": 1, "url": play_url, "header": self.headers}

    def _extract_play_url(self, play_page_url):
        """L1 直链 + L2 播放器变量"""
        html = self._get(play_page_url)
        if not html:
            return ""
        # L2: var playUrl = '...'
        m = re.search(r"var\s+playUrl\s*=\s*[\"']([^\"']+)[\"']", html)
        if m and ".m3u8" in m.group(1):
            return m.group(1).replace("\\/", "/")
        # L1: 直接出现 contentUrl / .m3u8
        m = re.search(r'"(?:contentUrl|url)"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', html)
        if m:
            return m.group(1).replace("\\/", "/")
        m = re.search(r"(https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", html)
        if m:
            return m.group(1).replace("\\/", "/")
        return ""

    def _wrap_m3u8(self, url):
        ua = self.headers.get("User-Agent", "")
        if self.NEED_CLEAN:
            return {"parse": 0, "url": self._m3u8_proxy_url(url), "header": {"User-Agent": ua}}
        return {"parse": 0, "url": url, "header": {"User-Agent": ua}}

    # ---------- 图片 pics:// ----------

    def _play_image(self, play_url):
        imgs = self._collect_images(play_url)
        if not imgs:
            return {"parse": 0, "url": "", "header": {}, "msg": "未提取到图片"}
        # 图床 img.177pica.com 有 Referer 防盗链：带站点 Referer 会 403，必须不带
        imgs = ["https://" + u[7:] if u.startswith("http://") else u for u in imgs]
        payload = "pics://" + "&&".join(imgs)
        return {"parse": 0, "url": payload, "header": {}}
    def _collect_images(self, play_url):
        # 规范化到首章：/image/play/{id}.html 或 /image/play/{id}/number-N.html
        m = re.search(r"(/image/play/\d+)", play_url)
        if m:
            first_url = self._abs(m.group(1) + ".html")
        else:
            first_url = play_url
        first = self._get(first_url)
        if not first:
            return []
        imgs = self._extract_images(first)
        nums = re.findall(r"/number-(\d+)\.html", first)
        total = min(max([int(n) for n in nums], default=1), 200)
        if total > 1:
            base = self._abs(m.group(1)) if m else re.sub(r"\.html.*$", "", first_url)
            for p in range(2, total + 1):
                html = self._get(f"{base}/number-{p}.html")
                if html:
                    imgs += self._extract_images(html)
        seen, out = set(), []
        for u in imgs:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out
    _IMG_RE = re.compile(
        r'<img[^>]+(?:data-original|data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        re.I,
    )

    def _extract_images(self, html):
        raw = self._IMG_RE.findall(html or "")
        out = []
        for u in raw:
            if self._is_noise_image(u):
                continue
            # Android 9+ 默认禁明文 HTTP，图片统一升级 HTTPS
            if u.startswith("http://"):
                u = "https://" + u[7:]
            out.append(u)
        if raw and not out:
            # 过滤过度，回退
            return [self._abs(u) for u in raw]
        return out
    _NOISE_KW = ("logo", "icon", "favicon", "banner", "avatar", "loading",
                 "placeholder", "default", "blank", "qrcode", "share", "btn",
                 "arrow", "star")

    def _is_noise_image(self, url):
        low = str(url or "").lower()
        path = low.split("?")[0]
        name = path.rsplit("/", 1)[-1]
        for k in self._NOISE_KW:
            if k in name:
                return True
        if path.endswith((".gif", ".svg", ".ico")):
            return True
        if low.startswith("data:"):
            return True
        return False

    # ---------- 小说 novel:// ----------

    def _play_novel(self, play_url):
        html = self._get(play_url)
        if not html:
            return {"parse": 0, "url": "", "header": {}, "msg": "读取失败"}
        title = self._page_title(html).split("｜")[0].strip() or "正文"
        content = self._extract_novel_text(html)
        chapter = {"title": title, "content": content}
        return {"parse": 0,
                "url": "novel://" + json.dumps(chapter, ensure_ascii=False),
                "header": {"User-Agent": self.headers["User-Agent"]}}

    def _extract_novel_text(self, html):
        # 只取正文容器 novel-wrap，避免混入导航/标签/页脚
        m = re.search(r'<div[^>]*class=["\'][^"\']*novel-wrap[^"\']*["\'][^>]*>(.*?)</div>\s*(?:</div>|<div|<section|$)', html or "", re.S | re.I)
        body = m.group(1) if m else ""
        if not body or len(body) < 100:
            # 兜底：取 <body> 到「相关推荐」之间
            bm = re.search(r"<body[^>]*>(.*?)(?:相关推荐|友情链接|</body>)", html or "", re.S | re.I)
            body = bm.group(1) if bm else (html or "")
        t = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.S | re.I)
        t = re.sub(r"<style[^>]*>.*?</style>", "", t, flags=re.S | re.I)
        t = re.sub(r"</p>", "\n", t, flags=re.I)
        t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
        t = re.sub(r"<[^>]+>", "", t)
        for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&quot;", '"'), ("&#160;", " "), ("&#39;", "'")):
            t = t.replace(a, b)
        t = re.sub(r"[ \t\xa0]+", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        bad = ("本站", "最新章节", "请收藏", "手机阅读", "笔趣", "推荐本书",
               "加入书签", "一线黑料", "友情链接", "网站地图", "警告：")
        lines = [l.strip() for l in t.split("\n")]
        lines = [l for l in lines if l and not any(b in l for b in bad)]
        return "\n\n".join(lines)
    def recommendContent(self, ids, pg):
        try:
            return self.categoryContent("video/type/912", str(pg or "1"), False, {})
        except Exception:
            return {"list": []}

    # ==================== m3u8 代理清洗 ====================

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = unquote(target)
                m = re.search(r"[?&]url=([^&]+)", qs)
                if m:
                    target = m.group(1)
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            r = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"],
                                            "Referer": self.host + "/"}, timeout=20)
            if not r or getattr(r, "status_code", 0) != 200:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(r, "content", b"") or b""
            if not content and getattr(r, "text", ""):
                content = r.text.encode("utf-8", errors="ignore")
            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: %s" % type(e).__name__).encode("utf-8")]

    def _is_fake_image_stream(self, text):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_v = has_i = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("?")[0].split("#")[0].lower()
            if p.endswith(VIDEO_EXT):
                has_v = True
            elif p.endswith(IMAGE_EXT):
                has_i = True
        return has_i and not has_v

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            kp = urlparse(key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)).path
            kd = posixpath.dirname(kp)
            if kd and kd != "/":
                return kd + "/"
        return base_dir

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流检测（只打标记，不 return）
        is_img = self._is_fake_image_stream(text)

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 第3层：锚点
        main_dir = self.AD_ANCHOR if self.AD_ANCHOR else self._resolve_main_dir(lines, source_url, is_img)

        # 第4层：过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter", "removed": removed, "kept": kept})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _filter_segments(self, lines, source_url, main_dir):
        segments, pending = [], []
        removed = kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                path = urlparse(media).path
                is_ad = any(ad in path for ad in self.AD_DIRS)
                if not is_ad and main_dir and not path.startswith(main_dir):
                    is_ad = True
                if is_ad:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(self._rewrite_m3u8_tag(media, source_url))
                    kept += 1
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line
# coding=utf-8
# //@name:麻椒視頻
# //@id:mjv015
# //@version:1

import base64
import re
import sys
import threading
import time
from urllib.parse import quote, urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass
        def homeContent(self, filter):
            pass
        def homeVideoContent(self):
            pass
        def categoryContent(self, tid, pg, filter, extend):
            pass
        def detailContent(self, ids):
            pass
        def searchContent(self, key, quick, pg="1"):
            pass
        def playerContent(self, flag, id, vipFlags):
            pass
        def localProxy(self, param):
            pass
        def isVideoFormat(self, url):
            pass
        def manualVideoCheck(self):
            pass
        def action(self, action):
            pass
        def destroy(self):
            pass

DEFAULT_HOST = "https://mjv015.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
PLAYER_UA = DEFAULT_UA
NAV_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
}

_MINORS = ("萝莉", "幼女", "少女", "童", "teen", "loli", "schoolgirl", "未成年", "豆蔻", "玉蕊", "碧玉", "稚子")


def _has_minor(text):
    if not text:
        return False
    low = str(text).lower()
    return any(k in low for k in _MINORS)


def _fix_cover_url(url):
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    return url


class Spider(_BaseSpider):
    def __init__(self):
        self.session = None
        self.siteUrl = DEFAULT_HOST
        self.ua = DEFAULT_UA
        self.cookie_name = "YES_Eighteen"
        self.cookie_value = "IamOverEighteenYearsOld"
        self.lock = threading.RLock()
        self._cache = {}
        self._cache_ttl = 60

    def getDependence(self):
        return ""

    def init(self, extend=""):
        with self.lock:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": self.ua})
            self.session.mount("https://", HTTPAdapter(max_retries=1))
            self.session.mount("http://", HTTPAdapter(max_retries=1))
            self._ensure_cookie()

    def _ensure_cookie(self):
        try:
            self.session.get(
                f"{self.siteUrl}/zh/chinese_IamOverEighteenYearsOld/19/index.html",
                headers=dict(NAV_HEADERS, **{"User-Agent": self.ua}),
                timeout=15,
                allow_redirects=True,
            )
        except Exception:
            pass
        self.session.cookies.set(self.cookie_name, self.cookie_value, domain="mjv015.com", path="/")

    def _fetch(self, url, headers=None, timeout=15):
        h = dict(NAV_HEADERS, **{"User-Agent": self.ua})
        if headers:
            h.update(headers)
        now = time.time()
        key = url
        with self.lock:
            if key in self._cache:
                cached, ts = self._cache[key]
                if now - ts < self._cache_ttl:
                    return cached
        try:
            r = self.session.get(url, headers=h, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            txt = r.text
            with self.lock:
                self._cache[key] = (txt, now)
            return txt
        except Exception as e:
            return ""

    def homeContent(self, *args):
        html = self._fetch(f"{self.siteUrl}/zh/chinese_random/all/index.html")
        if not html:
            html = self._fetch(f"{self.siteUrl}/")
        classes = self._parse_classes(html)
        vlist = self._parse_list(html)
        filters = {}
        for c in classes:
            filters[c["type_id"]] = []
        return {"class": classes, "filters": filters, "list": vlist}

    def homeVideoContent(self):
        return {"page": 1, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def categoryContent(self, *args):
        tid = args[0] if len(args) > 0 else ""
        pg = args[1] if len(args) > 1 else "1"
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        page_str = "index" if pg == 1 else str(pg)
        url = f"{self.siteUrl}/zh/{tid}_random/all/{page_str}.html"
        html = self._fetch(url)
        vlist = self._parse_list(html)
        total = self._parse_total(html, vlist)
        pagecount = max(1, (total + 23) // 24) if total else 999
        return {"page": pg, "pagecount": pagecount, "limit": 24, "total": total, "list": vlist}

    def detailContent(self, *args):
        ids = args[0] if len(args) > 0 else []
        if isinstance(ids, str):
            ids = [ids]
        result = []
        for vod_id in ids:
            item = self._detail_one(vod_id)
            if item:
                result.append(item)
        return {"list": result}

    def searchContent(self, *args):
        wd = args[0] if len(args) > 0 else ""
        pg = args[1] if len(args) > 1 else "1"
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if not wd:
            return {"page": pg, "pagecount": 1, "limit": 24, "total": 0, "list": []}
        kw = quote(str(wd))
        page_str = str(pg)
        url = f"{self.siteUrl}/zh/chinese_search/all/{kw}/{page_str}.html"
        html = self._fetch(url)
        vlist = self._parse_list(html)
        total = self._parse_total(html, vlist)
        pagecount = max(1, (total + 23) // 24) if total else 999
        return {"page": pg, "pagecount": pagecount, "limit": 24, "total": total, "list": vlist}

    def playerContent(self, *args):
        flag = args[0] if len(args) > 0 else ""
        video_id = args[1] if len(args) > 1 else ""
        if not video_id:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        url = video_id
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            url = urljoin(self.siteUrl, url)
        html = self._fetch(url, headers={"Referer": self.siteUrl + "/", "Origin": self.siteUrl})
        m3u8 = self._extract_m3u8(html)
        header = {
            "User-Agent": PLAYER_UA,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl,
        }
        if m3u8:
            if m3u8.startswith("//"):
                m3u8 = "https:" + m3u8
            return {"parse": 0, "jx": 0, "url": m3u8, "header": header, "format": "application/x-mpegURL"}
        return {"parse": 0, "jx": 0, "url": url, "header": header}

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or param.get("u") or ""
            elif isinstance(param, str):
                url = param
            if not url:
                return [404, "text/plain", ""]
            if url.startswith("local://"):
                url = url[8:]
                if url.startswith("cover/"):
                    url = base64.urlsafe_b64decode(url[6:].split("/")[0] + "==").decode("utf-8", "ignore")
            if url.startswith("//"):
                url = "https:" + url
            r = self.session.get(url, headers={"User-Agent": self.ua, "Referer": self.siteUrl + "/"}, timeout=15)
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            return [r.status_code, ctype, r.content]
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        return ".m3u8" in url.lower() or ".mp4" in url.lower()

    def manualVideoCheck(self):
        return True

    def action(self, action):
        return ""

    def destroy(self):
        with self.lock:
            if self.session:
                try:
                    self.session.close()
                except Exception:
                    pass
                self.session = None

    # ---------- 解析辅助 ----------

    def _parse_classes(self, html):
        classes = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="https://mjv015\.com/zh/([^"_]+)_random/all/[^"]+"[^>]*>([^<]+)</a>', html):
            tid = m.group(1)
            name = m.group(2).strip()
            if not tid or not name or tid in seen:
                continue
            if _has_minor(name):
                continue
            seen.add(tid)
            classes.append({"type_id": tid, "type_name": name})
        if not classes:
            default = [
                ("chinese", "中文字幕AV"),
                ("censored", "有碼AV"),
                ("uncensored", "無碼AV"),
                ("amateurjav", "素人AV"),
                ("reducing-mosaic", "無碼破解"),
                ("animation", "H動畫"),
                ("CensoredAnimation", "H有碼動畫"),
                ("UncensoredAnimation", "H無碼動畫"),
                ("tdAnimation", "H_3D動畫"),
                ("dt", "國產自拍"),
                ("18H", "18H漫畫"),
                ("doujin", "18H短篇同人"),
                ("cg", "寫真圖片"),
                ("cwp", "國產寫真"),
                ("novel", "小說"),
            ]
            for tid, name in default:
                if _has_minor(name):
                    continue
                classes.append({"type_id": tid, "type_name": name})
        return classes

    def _parse_list(self, html):
        vlist = []
        for m in re.finditer(
            r'<div[^>]*class=["\']post["\'][^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\'][^>]*>.*?</a>.*?<h3[^>]*>.*?<a[^>]+href="[^"]+"[^>]*>([^<]+)</a>.*?</h3>.*?<div[^>]*class=["\']meta["\'][^>]*>([^<]+)</div>.*?</div>',
            html, re.S | re.I,
        ):
            href = m.group(1)
            pic = _fix_cover_url(m.group(2))
            title = m.group(3).strip()
            meta = m.group(4).strip()
            if _has_minor(title):
                continue
            vlist.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": meta,
                "vod_year": "",
                "vod_area": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_content": "",
            })
        return vlist

    def _parse_total(self, html, vlist):
        m = re.search(r'class=["\']pagination[^"\']*["\'][^>]*>.*?(\d+)\s*</a>\s*</div>', html, re.S)
        if m:
            try:
                return int(m.group(1)) * 24
            except Exception:
                pass
        m = re.search(r'href=["\'][^"\']*_random/all/(\d+)\.html["\'][^>]*>\s*\d+\s*</a>\s*</div>', html, re.S)
        if m:
            try:
                return int(m.group(1)) * 24
            except Exception:
                pass
        return len(vlist)

    def _detail_one(self, vod_id):
        url = vod_id
        if not url.startswith("http"):
            url = urljoin(self.siteUrl, url)
        html = self._fetch(url, headers={"Referer": self.siteUrl + "/", "Origin": self.siteUrl})
        if not html:
            return None
        title = ""
        tm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
        if tm:
            title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if _has_minor(title):
            return None
        pic = ""
        pm = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if pm:
            pic = _fix_cover_url(pm.group(1))
        content = ""
        cm = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
        if cm:
            content = cm.group(1).strip()
        date = ""
        dm = re.search(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if not dm:
            dm = re.search(r'<div[^>]*class=["\']meta["\'][^>]*>([^<]+)</div>', html, re.I)
        if dm:
            date = dm.group(1).strip()

        # 提取解密参数
        key, iv, hcdee, hadee = self._extract_keys(html)

        # 提取播放源
        lines = []
        urls = []
        for label, arr_name in [("1080P", "10_1"), ("720P", "11_1")]:
            m_arr = re.search(
                rf"mvarr\['{arr_name}'\]=\[\['([^']+)'\s*,\s*'([^']+)'\s*,\s*'(.*?)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\],\];",
                html, re.S,
            )
            if m_arr:
                encoded = m_arr.group(2)
                prefix = m_arr.group(4)
                suffix = m_arr.group(5)
                real_id = self._decode_id(encoded, hcdee, hadee, key, iv)
                if real_id:
                    play_url = f"{prefix}{real_id}{suffix}"
                    if play_url.startswith("//"):
                        play_url = "https:" + play_url
                    lines.append(label)
                    urls.append(f"{label}${play_url}")
        if not urls:
            return None
        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": date,
            "vod_year": "",
            "vod_area": "",
            "vod_director": "",
            "vod_actor": "",
            "vod_content": content,
            "vod_play_from": "$$$".join(lines),
            "vod_play_url": "$$$".join(urls),
        }

    def _extract_keys(self, html):
        key = "862a8b27af5fcaf4"
        iv = "fa65d78624871c49"
        hcdee = 21
        hadee = 15
        m = re.search(r"argdeqweqweqwe\s*=\s*['\"]([a-f0-9]+)['\"]", html)
        if m:
            key = m.group(1)
        m = re.search(r"hdddedg252\s*=\s*['\"]([a-f0-9]+)['\"]", html)
        if m:
            iv = m.group(1)
        m = re.search(r"hcdeedg252\s*=\s*(\d+)", html)
        if m:
            hcdee = int(m.group(1))
        m = re.search(r"hadeedg252\s*=\s*(\d+)", html)
        if m:
            hadee = int(m.group(1))
        return key, iv, hcdee, hadee

    def _decode_id(self, encoded, hcdee, hadee, key, iv):
        if not HAS_CRYPTO:
            return ""
        try:
            sep = chr(hcdee + 97)
            parts = [p for p in encoded.split(sep) if p]
            decoded = "".join(chr(int(p, hcdee) ^ hadee) for p in parts)
            if not decoded:
                return ""
            cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
            pt = unpad(cipher.decrypt(base64.b64decode(decoded)), AES.block_size)
            return pt.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _extract_m3u8(self, html):
        m = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m:
            return m.group(1)
        m = re.search(r'(//[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m:
            return m.group(1)
        return ""

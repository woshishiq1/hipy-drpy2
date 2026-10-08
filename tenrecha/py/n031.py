# -*- coding: utf-8 -*-
import re
import json
import time
import base64
import urllib.parse
from collections import OrderedDict

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass

try:
    from curl_cffi import requests as _cf_requests
    _HAS_CFFI = True
except ImportError:
    _HAS_CFFI = False
    import requests as _py_requests

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
NAV_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
    "User-Agent": UA,
}
CFFI_FP = "safari17_2_ios"
MINOR_KEYWORDS = ["萝莉", "幼女", "少女", "童", "teen", "loli", "schoolgirl", "豆蔻", "玉蕊", "碧玉", "稚子"]

CLASS_LIST = [
    {"type_id": "21", "type_name": "激情口交"},
    {"type_id": "22", "type_name": "亚洲日韩"},
    {"type_id": "23", "type_name": "人妖激情"},
    {"type_id": "24", "type_name": "重咸口味"},
    {"type_id": "25", "type_name": "国产专区"},
    {"type_id": "26", "type_name": "日韩专区"},
    {"type_id": "27", "type_name": "欧美专区"},
    {"type_id": "28", "type_name": "卡通动漫"},
    {"type_id": "29", "type_name": "三级伦理"},
]

FILTERS = {
    c["type_id"]: [{"key": "sort", "name": "排序", "init": "", "value": [{"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}]
    for c in CLASS_LIST
}


class Spider(_BaseSpider):
    def __init__(self):
        self.rawSite = "https://kux.yyll3.yachts"
        self.siteUrl = self.rawSite
        self.HOST = self.siteUrl
        self.basePath = "/cn/home/web"
        self._session = None
        self._cache = OrderedDict()
        self._cache_ttl = 60
        self._preferred_fp = CFFI_FP

    def getDependence(self):
        return ""

    def init(self, extend=""):
        if isinstance(extend, dict):
            cfg = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                cfg = json.loads(extend)
            except Exception:
                try:
                    import ast
                    cfg = ast.literal_eval(extend)
                except Exception:
                    cfg = {}
        else:
            cfg = {}
        if cfg.get("direct"):
            self.siteUrl = self.rawSite
        elif cfg.get("proxy"):
            self.siteUrl = cfg["proxy"].rstrip("/")
        elif cfg.get("siteUrl"):
            self.siteUrl = cfg["siteUrl"].rstrip("/")
        self.HOST = self.siteUrl
        self._get_session()
        try:
            self._fetch(self._cat_url("25", 1), timeout=8)
        except Exception:
            pass

    def homeContent(self, *args):
        result = {"class": CLASS_LIST, "filters": FILTERS, "list": []}
        try:
            html = self._fetch(self._cat_url("25", 1))
            result["list"] = self._parse_list(html)[:20]
        except Exception:
            pass
        return result

    def homeVideoContent(self, *args):
        return self._empty_page()

    def categoryContent(self, *args):
        tid = str(args[0]) if args else "25"
        page = 1
        if len(args) >= 2:
            try:
                page = int(args[1])
            except Exception:
                page = 1
        filters = args[2] if len(args) >= 3 else {}
        try:
            html = self._fetch(self._cat_url(tid, page))
            vlist = self._parse_list(html)
            total = self._parse_total(html)
            pagecount = max(1, (total + len(vlist) - 1) // len(vlist)) if vlist else 1
            return {"page": page, "pagecount": pagecount, "limit": len(vlist) or 20, "total": total, "list": vlist}
        except Exception:
            return self._empty_page(page)

    def detailContent(self, *args):
        ids = args[0] if args else []
        if isinstance(ids, str):
            ids = [ids]
        results = []
        for vod_id in ids:
            vod_id = str(vod_id).strip()
            if not vod_id:
                continue
            try:
                play_url = self._play_url(vod_id)
                html = self._fetch(play_url)
                detail = self._parse_detail(html, vod_id)
                if detail:
                    results.append(detail)
            except Exception:
                continue
        return {"list": results}

    def searchContent(self, *args):
        wd = str(args[0]) if args else ""
        page = 1
        if len(args) >= 2:
            try:
                page = int(args[1])
            except Exception:
                page = 1
        if not wd:
            return self._empty_page(page)
        try:
            url = self._search_url(wd, page)
            html = self._fetch(url)
            vlist = self._parse_list(html)
            total = self._parse_total(html)
            pagecount = max(1, (total + len(vlist) - 1) // len(vlist)) if vlist else 1
            return {"page": page, "pagecount": pagecount, "limit": len(vlist) or 20, "total": total, "list": vlist}
        except Exception:
            return self._empty_page(page)

    def playerContent(self, *args):
        flag = args[0] if args else ""
        vid = str(args[1]) if len(args) >= 2 else ""
        vipFlags = args[2] if len(args) >= 3 else []
        real_url = ""
        if vid.startswith("http"):
            real_url = vid
        elif vid.isdigit():
            try:
                play_url = self._play_url(vid)
                html = self._fetch(play_url)
                pd = self._extract_player_data(html)
                if pd and pd.get("url"):
                    real_url = pd["url"]
            except Exception:
                pass
        if not real_url and vid and not vid.startswith("http"):
            real_url = self._proxy_m3u_url(vid)
        return {
            "parse": 0,
            "jx": 0,
            "url": real_url,
            "header": {
                "User-Agent": UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        if not param:
            return [404, "text/plain", ""]
        try:
            if isinstance(param, dict):
                url = param.get("url", "")
                if not url and "do" in param:
                    url = param.get("key", "")
            else:
                url = str(param)
            if url.startswith("local://"):
                url = url[len("local://"):]
            elif "://" not in url and not url.startswith("/"):
                pass
            if not url or (not url.startswith("http") and ".m3u8" not in url and "proxy" not in url):
                return [404, "text/plain", ""]
            if ".m3u8" in url or url.endswith(".m3u8"):
                return self._proxy_m3u8(url)
            return [404, "text/plain", ""]
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".m4a", ".mp3", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def action(self, actionKey, *args):
        return ""

    def destroy(self):
        self._cache.clear()

    def _get_session(self):
        if self._session is not None:
            return self._session
        if _HAS_CFFI:
            self._session = _cf_requests.Session()
            self._session.headers.update(NAV_HEADERS)
        else:
            self._session = _py_requests.Session()
            self._session.headers.update(NAV_HEADERS)
        return self._session

    def _fetch(self, url, timeout=12):
        cache_key = url
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[cache_key]
        if _HAS_CFFI:
            try:
                r = self._session.get(url, impersonate=self._preferred_fp, timeout=timeout, allow_redirects=True)
                if r.status_code == 200 and self._is_valid_response(r.text):
                    self._cache_put(cache_key, r.text)
                    return r.text
                for fp in ["chrome131", "chrome124", "chrome"]:
                    if fp == self._preferred_fp:
                        continue
                    r = self._session.get(url, impersonate=fp, timeout=timeout, allow_redirects=True)
                    if r.status_code == 200 and self._is_valid_response(r.text):
                        self._preferred_fp = fp
                        self._cache_put(cache_key, r.text)
                        return r.text
            except Exception:
                pass
        try:
            r = self._session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                self._cache_put(cache_key, r.text)
                return r.text
        except Exception:
            pass
        return ""

    def _is_valid_response(self, text):
        if not text or len(text) < 500:
            return False
        low = text[:3000].lower()
        if "attention required" in low and "cloudflare" in low:
            return False
        if "just a moment" in low:
            return False
        if "sorry, you have been blocked" in low:
            return False
        return True

    def _cache_put(self, key, val):
        self._cache[key] = (time.time(), val)
        if len(self._cache) > 24:
            oldest = next(iter(self._cache))
            del self._cache[oldest]

    def _cat_url(self, tid, page=1):
        if page <= 1:
            return f"{self.siteUrl}{self.basePath}/index.php/vod/type/id/{tid}.html"
        return f"{self.siteUrl}{self.basePath}/index.php/vod/show/id/{tid}/page/{page}.html"

    def _play_url(self, vod_id):
        return f"{self.siteUrl}{self.basePath}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"

    def _search_url(self, wd, page=1):
        q = urllib.parse.quote(wd)
        if page <= 1:
            return f"{self.siteUrl}{self.basePath}/index.php/vod/search.html?wd={q}"
        return f"{self.siteUrl}{self.basePath}/index.php/vod/search.html?wd={q}&page={page}"

    def _parse_list(self, html):
        if not html:
            return []
        target = self._extract_list_container(html)
        results = []
        seen = set()
        pattern = re.compile(
            r'<a[^>]+href="([^"]*vod/play/id/(\d+)[^"]*)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>',
            re.S,
        )
        for m in pattern.finditer(target):
            href, vid, title, inner = m.groups()
            title = title.strip()
            if not title or vid in seen:
                continue
            if self._is_minor(title):
                continue
            seen.add(vid)
            pic = self._find_nearby_image(target, m.start())
            remarks = self._find_nearby_text(target, m.start(), r'(\d+\.\d+)')
            results.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks or "",
                "vod_play_url": self._play_url(vid),
            })
        if not results:
            pattern2 = re.compile(
                r'<a[^>]+href="([^"]*vod/play/id/(\d+)[^"]*)"[^>]*>(.*?)</a>',
                re.S,
            )
            for m in pattern2.finditer(target):
                href, vid, inner = m.groups()
                name_m = re.search(r'class="sName"[^>]*>([^<]+)<', inner)
                title = name_m.group(1).strip() if name_m else re.sub(r'<[^>]+>', '', inner).strip()[:50]
                if not title or vid in seen:
                    continue
                if self._is_minor(title):
                    continue
                seen.add(vid)
                pic = self._find_nearby_image(target, m.start())
                results.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                    "vod_play_url": self._play_url(vid),
                })
        return results

    def _extract_list_container(self, html):
        for cls in ["list_vod", "list_tab_img", "vodlist", "video-list"]:
            content = self._extract_tag_by_class(html, cls)
            if content and "vod/play" in content:
                return content
        return html

    def _extract_tag_by_class(self, html, cls):
        m = re.search(r'<(div|ul)[^>]*class="[^"]*' + re.escape(cls) + r'[^"]*"[^>]*>', html)
        if not m:
            return ""
        tag = m.group(1)
        start = m.end()
        depth = 1
        pos = start
        while depth > 0 and pos < len(html):
            nxt_open = html.find("<" + tag, pos)
            nxt_close = html.find("</" + tag + ">", pos)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                pos = nxt_open + len(tag) + 1
            else:
                depth -= 1
                pos = nxt_close + len(tag) + 3
        return html[start:pos - len(tag) - 3]

    def _find_nearby_image(self, html, pos, radius=800):
        start = max(0, pos - radius)
        end = min(len(html), pos + radius)
        chunk = html[start:end]
        m = re.search(r'data-original="([^"]+)"', chunk)
        if m:
            url = m.group(1)
            if url.startswith("//"):
                url = "https:" + url
            return url
        m = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        if m:
            url = m.group(1)
            if "placeholder" in url or "220x307" in url or url.startswith("/"):
                return ""
            if url.startswith("//"):
                url = "https:" + url
            return url
        return ""

    def _find_nearby_text(self, html, pos, pattern, radius=600):
        start = max(0, pos - radius)
        end = min(len(html), pos + radius)
        chunk = html[start:end]
        m = re.search(pattern, chunk)
        return m.group(1) if m else ""

    def _parse_total(self, html):
        if not html:
            return 0
        m = re.search(r'共\s*(\d+)\s*[条个]', html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            max_page = max(int(p) for p in pages)
            return max_page * 20
        return 0

    def _parse_detail(self, html, vod_id):
        if not html:
            return None
        pd = self._extract_player_data(html)
        play_url = ""
        play_from = "ckplayer"
        if pd:
            play_url = pd.get("url", "")
            if pd.get("from"):
                play_from = pd["from"]
        title = ""
        m = re.search(r'<title>(.*?)</title>', html, re.S)
        if m:
            title = m.group(1).split(" - ")[0].split("|")[0].strip()
        if not title:
            title = vod_id
        if self._is_minor(title):
            return None
        pic = self._find_nearby_image(html, html.find("player_data") if "player_data" in html else 0, radius=2000)
        vod_play_url = ""
        if play_url:
            vod_play_url = f"正片${play_url}"
        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": play_from,
            "vod_play_url": vod_play_url,
            "vod_content": title,
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
        }

    def _extract_player_data(self, html):
        if not html:
            return {}
        m = re.search(r'var player_data\s*=\s*(\{.*?\})\s*;?', html, re.S)
        if not m:
            m = re.search(r'player_data\s*[:=]\s*(\{.*?\})\s*[;<]', html, re.S)
        if not m:
            return {}
        raw = m.group(1)
        try:
            return json.loads(raw)
        except Exception:
            try:
                raw = re.sub(r'//.*?$', '', raw, flags=re.M)
                return json.loads(raw)
            except Exception:
                url_m = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                from_m = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
                enc_m = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
                return {
                    "url": url_m.group(1) if url_m else "",
                    "from": from_m.group(1) if from_m else "ckplayer",
                    "encrypt": int(enc_m.group(1)) if enc_m else 0,
                }

    def _is_minor(self, text):
        if not text:
            return False
        low = text.lower()
        for kw in MINOR_KEYWORDS:
            if kw.lower() in low:
                return True
        return False

    def _empty_page(self, page=1):
        return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def _proxy_m3u_url(self, vid):
        return f"local://m3u8/{vid}"

    def _proxy_m3u8(self, url):
        try:
            headers = {"User-Agent": UA, "Referer": self.rawSite + "/"}
            if _HAS_CFFI:
                r = _cf_requests.get(url, headers=headers, impersonate=self._preferred_fp, timeout=10)
            else:
                import requests as _rq
                r = _rq.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                return [404, "text/plain", ""]
            content = r.text
            cleaned = self._clean_m3u8(content, url)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception:
            return [404, "text/plain", ""]

    def _clean_m3u8(self, content, base_url=""):
        if not content:
            return content
        lines = content.split("\n")
        out = []
        seq = 0
        has_ad = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                out.append(line)
                continue
            if stripped.startswith("#EXT-X-MEDIA-SEQUENCE"):
                continue
            if stripped.startswith("#"):
                out.append(line)
                continue
            if self._is_ad_segment(stripped):
                has_ad = True
                continue
            if base_url and not stripped.startswith("http"):
                stripped = urllib.parse.urljoin(base_url, stripped)
            out.append(stripped)
            seq += 1
        if has_ad:
            out.insert(0, f"#EXT-X-MEDIA-SEQUENCE:{seq}")
        return "\n".join(out)

    def _is_ad_segment(self, url):
        if not url:
            return False
        low = url.lower()
        ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告", "promo", "banner"]
        for kw in ad_keywords:
            if kw in low:
                return True
        if any(low.endswith(ext) for ext in [".jpg", ".png", ".gif", ".html"]):
            return True
        return False

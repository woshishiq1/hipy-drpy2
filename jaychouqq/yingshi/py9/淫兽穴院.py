# -*- coding: utf-8 -*-
"""淫兽穴院 Spider
实测结构：/y.php?class=分类&page=页码，详情 ?detail=ID，播放地址在详情页 HlsJsPlayer 配置中。
"""
import json
import re
import html as _html
from html import unescape
from urllib.parse import quote, urljoin, urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    import urllib.request as _urlreq
    import urllib.error as _urlerr
except ImportError:
    _urlreq = None
    _urlerr = None


class _Response:
    def __init__(self, status=0, text="", content=b"", headers=None, url=""):
        self.status_code = status
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = url


def _clean(value):
    value = unescape(str(value or ""))
    value = re.sub(r"<[^>]*>", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _first(value, default=""):
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    if isinstance(value, dict):
        return next(iter(value.values()), default)
    return value if value is not None else default


def _page(value):
    try:
        value = int(str(_first(value, 1)).strip())
        return value if value > 0 else 1
    except (ValueError, TypeError):
        return 1


def _fix_url(value, host):
    value = unescape(str(value or "")).strip().strip("\"'")
    if not value or value.startswith("data:"):
        return ""
    if value.startswith("//"):
        return "https:" + value
    return urljoin(host.rstrip("/") + "/", value)


def _parse_extend(extend):
    if isinstance(extend, dict):
        return dict(extend)
    if isinstance(extend, (list, tuple)):
        return dict(extend) if all(isinstance(x, (list, tuple)) and len(x) >= 2 for x in extend) else {}
    text = str(extend or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {"host": text} if text.startswith(("http://", "https://")) else {}


def _extract_items(source, host):
    """解析站点真实列表卡片，避免把底部推荐链接当成视频。"""
    result = []
    pattern = re.compile(
        r'<a\s+[^>]*class=["\'][^"\']*\bitem_a\b[^"\']*["\'][^>]*'
        r'href=["\']([^"\']*?[?&]detail=(\d+))[^"\']*["\'][^>]*>.*?</a>'
        r'\s*<span\s+class=["\'][^"\']*\bitem_title\b[^"\']*["\']>(.*?)</span>',
        re.I | re.S,
    )
    for match in pattern.finditer(source or ""):
        href, vid, title = match.group(1), match.group(2), match.group(3)
        block = match.group(0)
        img = re.search(r'<img\b[^>]*?(?:original|data-original|data-src)=["\']([^"\']+)', block, re.I | re.S)
        if not img:
            img = re.search(r'<img\b[^>]*?src=["\']([^"\']+)', block, re.I | re.S)
        pic = _fix_url(img.group(1), host) if img else ""
        item = {"vod_id": vid, "vod_name": _clean(title), "vod_pic": pic}
        if not any(x["vod_id"] == vid for x in result):
            result.append(item)
    return result


def _pagecount(source, current=1):
    nums = []
    for value in re.findall(r'(?:[?&])page=(\d+)', source or "", re.I):
        try:
            nums.append(int(value))
        except ValueError:
            pass
    return max([current] + nums) if nums else 1


def _extract_player(source, host):
    text = source or ""
    patterns = (
        r'["\']url["\']\s*:\s*["\'](https?://[^"\'<> ]+?\.m3u8(?:\?[^"\'<> ]*)?)["\']',
        r'url\s*:\s*["\'](https?://[^"\'<> ]+?\.m3u8(?:\?[^"\'<> ]*)?)["\']',
        r'(https?://[^"\'<> ]+?\.m3u8(?:\?[^"\'<> ]*)?)',
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return _fix_url(match.group(1).replace(r"\/", "/"), host)
    return ""


def _extract_poster(source, host):
    match = re.search(r'["\']poster["\']\s*:\s*["\']([^"\']+)', source or "", re.I)
    return _fix_url(match.group(1), host) if match else ""


class Spider:
    def __init__(self):
        self.host = "https://xn--b4w04e.ysxysp.buzz"
        self.name = "淫兽穴院"
        self.timeout = 20
        self.verify = False
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/y.php",
        }
        self.session = requests.Session() if requests else None
        self.s = self.session

    def getDependence(self):
        return []

    def init(self, extend=""):
        cfg = _parse_extend(extend)
        host = str(cfg.get("host") or cfg.get("HOST") or "").strip().rstrip("/")
        if host.startswith(("http://", "https://")):
            self.host = host
        ua = str(cfg.get("ua") or cfg.get("userAgent") or cfg.get("User-Agent") or "").strip()
        if ua:
            self.headers["User-Agent"] = ua
        cookie = str(cfg.get("cookie") or cfg.get("Cookie") or "").strip()
        if cookie:
            self.headers["Cookie"] = cookie
        referer = str(cfg.get("referer") or cfg.get("Referer") or "").strip()
        self.headers["Referer"] = referer if referer.startswith(("http://", "https://")) else self.host + "/y.php"
        try:
            self.timeout = max(3, int(cfg.get("timeout", self.timeout)))
        except (ValueError, TypeError):
            pass
        if self.session:
            self.session.headers.update(self.headers)
        return None

    def getName(self):
        return self.name

    def homeContent(self, filter=None):
        return {
            "class": [
                {"type_name": "国产", "type_id": "1050"},
                {"type_name": "无码", "type_id": "1051"},
                {"type_name": "有码", "type_id": "1052"},
                {"type_name": "字幕", "type_id": "1053"},
                {"type_name": "欧美", "type_id": "1054"},
                {"type_name": "动漫", "type_id": "1055"},
                {"type_name": "伦理", "type_id": "1056"},
            ],
            "filters": {},
        }

    def homeVideoContent(self):
        return self.categoryContent("", 1, {}, {})

    def _get(self, url, headers=None):
        url = _fix_url(url, self.host)
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        try:
            if self.session:
                response = self.session.get(url, headers=merged, timeout=self.timeout, verify=self.verify, allow_redirects=True)
                return response
            if _urlreq:
                request = _urlreq.Request(url, headers=merged)
                with _urlreq.urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    return _Response(getattr(response, "status", 200), body.decode("utf-8", "ignore"), body, dict(response.headers), url)
        except Exception:
            return None
        return None

    def _list(self, url, page):
        response = self._get(url)
        source = getattr(response, "text", "") if response else ""
        result = {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}
        if not source:
            return result
        result["list"] = _extract_items(source, self.host)
        result["pagecount"] = _pagecount(source, page)
        result["limit"] = len(result["list"])
        result["total"] = len(result["list"])
        return result

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        page = _page(pg)
        tid = str(_first(tid, "")).strip()
        query = "?page=%d" % page
        if tid:
            query = "?class=%s&page=%d" % (quote(tid, safe=""), page)
        return self._list(self.host + "/y.php" + query, page)

    def detailContent(self, ids):
        if isinstance(ids, str):
            text = ids.strip()
            if text.startswith("[") or text.startswith("{"):
                try:
                    ids = json.loads(text)
                except (ValueError, TypeError):
                    pass
        if isinstance(ids, dict):
            ids = ids.get("id") or ids.get("vod_id") or ids.get("ids") or ""
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        vid = str(ids or "").strip()
        if vid.startswith("?detail="):
            vid = vid.split("=", 1)[1]
        match = re.search(r"(\d+)", vid)
        vid = match.group(1) if match else vid
        if not vid:
            return {"list": []}
        url = self.host + "/y.php?detail=" + quote(vid, safe="")
        response = self._get(url)
        source = getattr(response, "text", "") if response else ""
        if not source:
            return {"list": []}
        title_match = re.search(r'<h1\b[^>]*class=["\'][^"\']*videotitle[^"\']*["\'][^>]*>(.*?)</h1>', source, re.I | re.S)
        if not title_match:
            title_match = re.search(r"<title>(.*?)</title>", source, re.I | re.S)
        title = _clean(title_match.group(1) if title_match else vid)
        title = re.sub(r"_淫兽穴院\s*$", "", title).strip()
        pic = _extract_poster(source, self.host)
        play_id = url
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "默认",
            "vod_play_url": "播放$" + play_id,
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        page = _page(pg)
        key = str(_first(key, "")).strip()
        url = self.host + "/y.php?wd=" + quote(key, safe="") + "&page=%d" % page
        return self._list(url, page)

    def playerContent(self, flag, ids, vipFlags=None):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        if isinstance(ids, dict):
            ids = ids.get("url") or ids.get("id") or ""
        value = str(ids or "").strip()
        if "$" in value and not value.startswith(("http://", "https://")):
            value = value.rsplit("$", 1)[-1]
        if value.startswith("//"):
            value = "https:" + value
        if re.search(r"\.(?:m3u8|mp4)(?:$|\?)", value, re.I):
            return {"parse": 0, "jx": 0, "url": value, "playUrl": "", "header": self._media_headers()}
        source = ""
        if value.startswith(("http://", "https://")):
            response = self._get(value)
            source = getattr(response, "text", "") if response else ""
        play_url = _extract_player(source, self.host)
        if play_url:
            return {"parse": 0, "jx": 0, "url": play_url, "playUrl": "", "format": "application/x-mpegURL", "header": self._media_headers()}
        return {"parse": 1, "jx": 0, "url": value, "playUrl": "", "header": self._media_headers()}

    def _media_headers(self):
        result = {"User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"), "Referer": self.host + "/y.php"}
        if self.headers.get("Cookie"):
            result["Cookie"] = self.headers["Cookie"]
        return result

    def _clean_m3u8(self, source, playlist_url):
        lines = []
        for line in str(source or "").replace("\r", "").split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                match = re.search(r'URI="([^"]+)"', line)
                if match and not match.group(1).startswith(("http://", "https://")):
                    line = line.replace('URI="' + match.group(1) + '"', 'URI="' + urljoin(playlist_url, match.group(1)) + '"')
                lines.append(line)
            else:
                lines.append(urljoin(playlist_url, line))
        return "\n".join(lines) + ("\n" if lines else "")

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param) if param.strip() else {}
            except (ValueError, TypeError):
                param = {"url": param}
        if not isinstance(param, dict):
            return [404, "text/plain", b""]
        url = str(param.get("url") or "").strip()
        if not url:
            return [404, "text/plain", b""]
        response = self._get(url)
        if response is None or getattr(response, "status_code", 0) >= 400:
            return [404, "text/plain", b""]
        content_type = str(getattr(response, "headers", {}).get("Content-Type", ""))
        if ".m3u8" in url.lower() or "mpegurl" in content_type.lower() or "m3u8" in content_type.lower():
            body = self._clean_m3u8(getattr(response, "text", ""), url).encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", body, {"Content-Type": "application/vnd.apple.mpegurl", "Access-Control-Allow-Origin": "*"}]
        body = getattr(response, "content", b"") or getattr(response, "text", "").encode("utf-8")
        return [200, content_type or "application/octet-stream", body]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4|m4v|flv|webm|ts)(?:$|[?#])", str(url or ""), re.I))

    def action(self, action):
        return {}

    def destroy(self):
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass
        return None

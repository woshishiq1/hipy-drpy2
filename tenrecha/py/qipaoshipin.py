# -*- coding: utf-8 -*-
"""气泡视频 www.qpsp.cc Spider
页面型站点：/type/{分类}[?page=N]、/search?keyword=、/play/{slug}
"""
import json
import re
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen


class Spider:
    def __init__(self):
        self.host = "https://www.qpsp.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Android 13; Mobile) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.categories = [
            ("最新视频", "latest"),
            ("极速传媒", "/type/3-极速传媒"),
            ("极速视频", "/type/19-极速视频"),
            ("极速影视", "/type/27-极速影视"),
            ("备用专区", "/type/2-备用专区"),
            ("91传媒", "/type/91传媒"),
            ("精东传媒", "/type/精东传媒"),
            ("麻豆传媒", "/type/麻豆传媒"),
            ("蜜桃传媒", "/type/蜜桃传媒"),
            ("天美传媒", "/type/天美传媒"),
            ("星空传媒", "/type/星空传媒"),
        ]

    def getDependence(self):
        return []

    def init(self, extend=""):
        if extend:
            try:
                obj = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(obj, dict) and obj.get("host"):
                    self.host = str(obj["host"]).rstrip("/")
            except Exception:
                pass
        return None

    def _text(self, s):
        s = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", s, flags=re.I)
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s))).strip()

    def _get(self, path):
        if str(path).startswith("http"):
            url = str(path)
        else:
            raw = str(path).lstrip("/")
            parts = raw.split("?", 1)
            route = "/".join(quote(x, safe=":@%+-._~") for x in parts[0].split("/"))
            url = urljoin(self.host + "/", route)
            if len(parts) > 1:
                url += "?" + parts[1]

        try:
            req = Request(url, headers=self.headers)
            with urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "ignore"), r.geturl()
        except Exception:
            return "", url

    def _page(self, page):
        try:
            return max(1, int(page))
        except Exception:
            return 1

    def _cards(self, html, base):
        out, seen = [], set()
        pat = re.compile(r'<a[^>]+href=["\']([^"\']*/play/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', re.I)
        for href, body in pat.findall(html):
            href = urljoin(base, unescape(href))
            if href in seen:
                continue
            title = re.search(r'class=["\'][^"\']*video-title[^"\']*["\'][^>]*>([\s\S]*?)</(?:p|div)>', body, re.I)
            if not title:
                title = re.search(r'<p[^>]*>([\s\S]*?)</p>', body, re.I)
            name = self._text(title.group(1) if title else body)
            if not name:
                continue
            img = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', body, re.I)
            pic = urljoin(base, unescape(img.group(1))) if img else ""
            date = re.search(r'(20\d{2}-\d{2}-\d{2})', self._text(body))
            out.append({"vod_id": href, "vod_name": name, "vod_pic": pic, "vod_remarks": date.group(1) if date else ""})
            seen.add(href)
        return out

    def homeContent(self, filter):
        return {"class": [{"type_id": p, "type_name": n} for n, p in self.categories], "filters": {}}

    def homeVideoContent(self):
        html, base = self._get("/")
        latest = []
        marker = re.search(r'<h4[^>]*>\s*[⏱️]*\s*最新视频\s*</h4>([\s\S]*?)(?=<h4|</main>)', html, re.I)
        if marker:
            latest = self._cards(marker.group(1), base)
        all_items = self._cards(html, base)
        seen = set()
        result = []
        for item in latest + all_items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                result.append(item)
        return {"list": result}

    def categoryContent(self, tid, pg, filter, extend):
        path = str(tid)
        if path == "latest":
            html, base = self._get("/")
            marker = re.search(r'<h4[^>]*>\s*[⏱️]*\s*最新视频\s*</h4>([\s\S]*?)(?=<h4|</main>)', html, re.I)
            items = self._cards(marker.group(1), base) if marker else []
            return {"page": 1, "pagecount": 1, "limit": len(items), "total": len(items), "list": items}
        if not path.startswith("/"):
            path = "/type/" + path
        page = self._page(pg)
        if page > 1:
            path += ("&" if "?" in path else "?") + "page=" + str(page)
        html, base = self._get(path)
        items = self._cards(html, base)
        nums = [int(x) for x in re.findall(r'href=["\'][^"\']*[?&]page=(\d+)', html, re.I)]
        last = max(nums) if nums else page
        if last < page:
            last = page
        return {"page": page, "pagecount": last, "limit": len(items), "total": last * len(items), "list": items}

    def _detail(self, url):
        html, base = self._get(url)
        title = ""
        m = re.search(r'<h1[^>]*>\s*正在播放：([\s\S]*?)</h1>', html, re.I)
        if m:
            title = self._text(m.group(1))
        if not title:
            m = re.search(r'<title>\s*在线观看\s+([\s\S]*?)(?:\s+-\s+高清播放|</title>)', html, re.I)
            title = self._text(m.group(1)) if m else ""
        pic = ""
        m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if m:
            pic = urljoin(base, unescape(m.group(1)))
        play = ""
        for key in ("contentUrl", "src"):
            m = re.search(r'"' + key + r'"\s*:\s*"(https?[^"\\]+(?:m3u8|mp4)[^"\\]*)"', html, re.I)
            if m:
                play = m.group(1).replace("\\/", "/")
                break
        if not play:
            m = re.search(r'(?:[?&]src=|var\s+playUrl\s*=\s*[\'\"])(https?[^\'\"&]+)', html, re.I)
            play = unquote(m.group(1)) if m else ""
        cat = ""
        m = re.search(r'分类：\s*<a[^>]*>([^<]+)', html, re.I)
        if m:
            cat = self._text(m.group(1))
        return {"vod_id": url, "vod_name": title, "vod_pic": pic, "vod_play_from": "气泡视频", "vod_play_url": ("正片$" + play) if play else "", "vod_content": cat}

    def detailContent(self, ids):
        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except Exception:
                ids = [ids]
        if isinstance(ids, dict):
            ids = [ids.get("vod_id") or ids.get("id") or ""]
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        return {"list": [self._detail(str(x)) for x in ids if x]}

    def searchContent(self, key, quick, pg=1):
        if isinstance(key, (list, tuple, dict)):
            key = key[0] if isinstance(key, (list, tuple)) else key.get("key", "")
        path = "/search?keyword=" + quote(str(key), safe="")
        if self._page(pg) > 1:
            path += "&page=" + str(self._page(pg))
        html, base = self._get(path)
        items = self._cards(html, base)
        return {"page": self._page(pg), "pagecount": 1, "limit": len(items), "total": len(items), "list": items}

    def playerContent(self, flag, id, vipFlags):
        url = str(id)
        if "$" in url:
            url = url.split("$", 1)[-1]
        return {"parse": 0, "jx": 0, "playUrl": "", "url": url, "header": dict(self.headers), "format": "m3u8" if ".m3u8" in url.lower() else "mp4"}

    def localProxy(self, param):
        return [200, "text/plain", "", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4|mpd)(?:$|[?#])", str(url), re.I))

    def action(self, action, value):
        return {}

    def destroy(self):
        return None

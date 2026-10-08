# -*- coding: utf-8 -*-
import re
import urllib.parse
import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    BASE_URL = "https://www.motv.app"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://www.motv.app/",
        "Accept": "*/*"
    }

    CATES = [
        {"type_name": "日本有碼", "type_id": "20"},
        {"type_name": "日本無碼", "type_id": "50"},
        {"type_name": "歐美风情", "type_id": "25"},
        {"type_name": "國產原創", "type_id": "41"},
        {"type_name": "動畫", "type_id": "29"},
        {"type_name": "水果AV", "type_id": "35"},
        {"type_name": "色情情燴", "type_id": "30"},
        {"type_name": "經典四級", "type_id": "47"},
        {"type_name": "鹹濕電台", "type_id": "169"}
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def getName(self):
        return "MOTV"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {"class": self.CATES, "filters": {}, "list": self._ajax_list("20", 1), "parse": 0, "jx": 0}

    def homeVideoContent(self):
        return {"list": self._ajax_list("20", 1)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self._ajax_json(tid, pg)
        return {
            "list": self._json_list(data),
            "page": pg,
            "pagecount": self._to_int(data.get("pagecount") or data.get("page_count") or data.get("last_page"), 999),
            "limit": self._to_int(data.get("limit"), 20),
            "total": self._to_int(data.get("total"), 9999)
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        html = self._get(urllib.parse.urljoin(self.BASE_URL, "/voddetail/%s/" % vid))
        name = self._match(html, r"<h1[^>]*>(.*?)</h1>") or self._match(html, r"vod_name\s*=\s*['\"]([^'\"]+)")
        pic = self._match(html, r"vod_pic\s*=\s*['\"]([^'\"]+)")
        desc = self._clean(self._match(html, r'<div[^>]+class="[^"]*(?:content|detail|desc|sketch)[^"]*"[^>]*>(.*?)</div>'))
        play_urls = self._play_urls(html, vid)
        vod = {
            "vod_id": vid,
            "vod_name": self._clean(name) or vid,
            "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic or ""),
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": desc,
            "vod_play_from": "MOTV",
            "vod_play_url": play_urls
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        wd = urllib.parse.quote(key)
        url = "%s/index.php/ajax/data?mid=1&wd=%s&page=%s&limit=20" % (self.BASE_URL, wd, pg)
        return {"list": self._json_list(self._json(url))}

    def playerContent(self, flag, id, vipFlags):
        play_url = urllib.parse.urljoin(self.BASE_URL, id or "")
        page = self._get(play_url)
        watch = self._player_url(page)
        if watch:
            watch_html = self._get(watch, {"Referer": play_url, "Origin": self.BASE_URL, "Accept": "*/*"})
            m3u8 = self._match(watch_html, r"var\s+src\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)")
            if not m3u8:
                m3u8 = self._match(watch_html, r"['\"]([^'\"]+\.m3u8[^'\"]*)")
            if m3u8:
                real = urllib.parse.urljoin(watch, m3u8.replace("\\/", "/"))
                u = urllib.parse.urlparse(watch)
                return {"parse": 0, "playUrl": "", "url": real, "jx": 0, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": watch, "Origin": u.scheme + "://" + u.netloc}}
            return {"parse": 0, "playUrl": "", "url": watch, "jx": 0, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": play_url, "Origin": self.BASE_URL}}
        return {"parse": 1, "playUrl": "", "url": play_url, "jx": 0, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": self.BASE_URL + "/"}}

    def localProxy(self, param):
        return None

    def _ajax_json(self, tid, pg):
        tid = str(tid or "20")
        pg = str(pg or "1")
        url = "%s/index.php/ajax/data?mid=1&tid=%s&page=%s&limit=20" % (self.BASE_URL, urllib.parse.quote(tid), urllib.parse.quote(pg))
        return self._json(url, {"Referer": "%s/vodtype/%s/" % (self.BASE_URL, tid)})

    def _ajax_list(self, tid, pg):
        return self._json_list(self._ajax_json(tid, pg))

    def _json_list(self, data):
        arr = data.get("list") or data.get("data") or []
        if isinstance(arr, dict):
            arr = arr.get("list") or arr.get("data") or []
        result = []
        seen = set()
        for item in arr:
            vid = str(item.get("vod_id") or item.get("id") or item.get("vodid") or "")
            name = item.get("vod_name") or item.get("name") or item.get("title") or ""
            pic = item.get("vod_pic") or item.get("pic") or item.get("cover") or item.get("vod_pic_thumb") or ""
            remarks = item.get("vod_remarks") or item.get("remarks") or item.get("note") or item.get("vod_time") or ""
            if vid and name and vid not in seen:
                seen.add(vid)
                result.append({"vod_id": vid, "vod_name": self._clean(name), "vod_pic": urllib.parse.urljoin(self.BASE_URL, pic), "vod_remarks": self._clean(remarks)})
        return result

    def _play_urls(self, html, vid):
        rows = re.findall(r'href=["\']([^"\']*/vodplay/%s-\d+-\d+/?)["\'][^>]*>(.*?)<' % re.escape(str(vid)), html, re.S)
        if not rows:
            return "第1集$%s/vodplay/%s-1-1/" % (self.BASE_URL, vid)
        result = []
        seen = set()
        for url, name in rows:
            full = urllib.parse.urljoin(self.BASE_URL, url)
            if full not in seen:
                seen.add(full)
                result.append("%s$%s" % (self._clean(name) or ("第%s集" % len(result + [1])), full))
        return "#".join(result) or "第1集$%s/vodplay/%s-1-1/" % (self.BASE_URL, vid)

    def _player_url(self, html):
        raw = self._match(html, r"player_aaaa\s*=\s*(\{.*?\})")
        if not raw:
            raw = self._match(html, r"player_data\s*=\s*(\{.*?\})")
        if raw:
            url = self._match(raw, r'"url"\s*:\s*"([^"]+)"') or self._match(raw, r"'url'\s*:\s*'([^']+)'")
            if url:
                return url.replace("\\/", "/")
        iframe = self._match(html, r'<iframe[^>]+src=["\']([^"\']+)')
        return urllib.parse.urljoin(self.BASE_URL, iframe) if iframe else ""

    def _json(self, url, headers=None):
        try:
            h = self.HEADERS.copy()
            if headers:
                h.update(headers)
            r = self.session.get(url, headers=h, timeout=15)
            r.encoding = "utf-8"
            return r.json()
        except Exception:
            return {}

    def _get(self, url, headers=None):
        try:
            h = self.HEADERS.copy()
            if headers:
                h.update(headers)
            r = self.session.get(url, headers=h, timeout=15)
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _match(self, text, pattern):
        m = re.search(pattern, text or "", re.S)
        return m.group(1).strip() if m else ""

    def _clean(self, text):
        text = re.sub(r"<[^>]+>", " ", text or "")
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        return re.sub(r"\s+", " ", text).strip()

    def _to_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default
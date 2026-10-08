# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass

class Spider(_BaseSpider):
    name = "JAVRYO"
    host = "https://javryo.com"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def init(self, extend=""):
        self.categories = [
            {"type_id": "movies", "type_name": "最新电影"},
            {"type_id": "release/2025", "type_name": "2025年"},
            {"type_id": "release/2024", "type_name": "2024年"},
            {"type_id": "release/2023", "type_name": "2023年"},
            {"type_id": "release/2022", "type_name": "2022年"},
            {"type_id": "genre/jav-superheroine", "type_name": "特摄女英雄"},
            {"type_id": "genre/2d", "type_name": "2D动画"},
            {"type_id": "genre/accelerator-girl", "type_name": "加速器少女"},
        ]
        self.filter_dict = {}
        for c in self.categories:
            self.filter_dict[c["type_id"]] = []
        self._ssl_ctx = ssl.create_default_context()
        try:
            self._ssl_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass

    def getDependence(self):
        return ""

    def _fetch(self, url, timeout=20):
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.host + "/",
        })
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"})
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=self._ssl_ctx))
        except Exception:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self._ssl_ctx))
        resp = opener.open(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="ignore")

    def _fetch_json(self, url, timeout=20):
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.host + "/",
        })
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"})
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=self._ssl_ctx))
        except Exception:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self._ssl_ctx))
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8", errors="ignore"))

    def _parse_list(self, html):
        vod_list = []
        items = re.findall(r'<article[^>]*>(.*?)</article>', html, re.S)
        for item in items:
            try:
                link_m = re.search(r'href=["\'](' + re.escape(self.host) + r'/movies/[^"\']+)["\']', item)
                if not link_m:
                    continue
                vod_url = link_m.group(1)
                vod_id = vod_url.rstrip("/").split("/")[-1]
                title_m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', item, re.S)
                vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else vod_id
                img_m = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', item)
                vod_pic = img_m.group(1) if img_m else ""
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
            except Exception:
                continue
        return vod_list

    def _parse_total(self, html):
        total_m = re.search(r'class=["\']pages["\'][^>]*>.*?(\d+)\s*</a>', html, re.S)
        if total_m:
            return int(total_m.group(1)) * 20
        page_nums = re.findall(r'/page/(\d+)/', html)
        if page_nums:
            return max(int(p) for p in page_nums) * 20
        return 0

    def _get_post_id(self, html):
        m = re.search(r'postid-(\d+)', html)
        return m.group(1) if m else ""

    def homeContent(self, *args):
        result = {"class": self.categories, "filters": self.filter_dict, "list": []}
        try:
            html = self._fetch(self.host + "/movies/")
            result["list"] = self._parse_list(html)
        except Exception:
            pass
        return result

    def homeVideoContent(self, *args):
        return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def categoryContent(self, *args):
        tid = str(args[0]) if args else "movies"
        pg = int(args[1]) if len(args) > 1 and args[1] else 1
        if isinstance(tid, dict):
            tid = tid.get("tid", "movies")
            pg = int(tid.get("pg", 1))
        page_path = f"/page/{pg}/" if pg > 1 else "/"
        url = f"{self.host}/{tid}{page_path}"
        try:
            html = self._fetch(url)
            vod_list = self._parse_list(html)
            total = self._parse_total(html)
            pagecount = (total + 20 - 1) // 20 if total else 1
            return {"page": pg, "pagecount": pagecount, "limit": 20, "total": total, "list": vod_list}
        except Exception:
            return {"page": pg, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def detailContent(self, *args):
        ids = args[0] if args else []
        if isinstance(ids, str):
            ids = [ids]
        result_list = []
        for vid in ids:
            try:
                url = f"{self.host}/movies/{str(vid)}/"
                html = self._fetch(url)
                post_id = self._get_post_id(html)
                title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
                vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else str(vid)
                img_m = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
                vod_pic = img_m.group(1) if img_m else ""
                if not vod_pic:
                    img_m2 = re.search(r'<img[^>]*class=["\'][^"\']*poster[^"\']*["\'][^>]*src=["\']([^"\']+)["\']', html)
                    if img_m2:
                        vod_pic = img_m2.group(1)
                if not vod_pic:
                    imgs = re.findall(r'<img[^>]*src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html)
                    if imgs:
                        vod_pic = imgs[0]
                desc_m = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']', html)
                vod_content = desc_m.group(1) if desc_m else ""

                play_from = "Server 1"
                play_url = f"{post_id}#{vid}" if post_id else ""

                vod = {
                    "vod_id": str(vid),
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_content": vod_content,
                    "vod_play_from": play_from,
                    "vod_play_url": play_url,
                    "vod_remarks": "",
                    "type_name": "电影",
                }
                result_list.append(vod)
            except Exception:
                continue
        return {"list": result_list}

    def playerContent(self, *args):
        flag = args[0] if args else ""
        id_str = str(args[1]) if len(args) > 1 else ""
        try:
            parts = id_str.split("#")
            post_id = parts[0]
            if not post_id:
                return {"parse": 0, "jx": 0, "url": "", "header": {}}
            api_url = f"{self.host}/wp-json/dooplayer/v1/post/{post_id}?type=movie&source=1"
            data = self._fetch_json(api_url)
            embed_url = data.get("embed_url", "")
            if embed_url:
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": embed_url,
                    "header": {"User-Agent": self.ua, "Referer": self.host + "/"}
                }
        except Exception:
            pass
        return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def searchContent(self, *args):
        wd = args[0] if args else ""
        pg = int(args[1]) if len(args) > 1 and args[1] else 1
        if isinstance(wd, dict):
            wd = wd.get("wd", "")
            pg = int(wd.get("pg", 1))
        try:
            search_url = f"{self.host}/page/{pg}/?s={urllib.parse.quote(str(wd))}"
            html = self._fetch(search_url)
            vod_list = self._parse_list(html)
            total = self._parse_total(html)
            pagecount = (total + 20 - 1) // 20 if total else 1
            return {"page": pg, "pagecount": pagecount, "limit": 20, "total": total, "list": vod_list}
        except Exception:
            return {"page": pg, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def localProxy(self, *args):
        return [404, "text/plain", ""]

    def getProxyUrl(self, *args):
        return ""

    def isVideoFormat(self, url):
        return any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".avi", ".mkv", ".flv"])

    def check(self, *args):
        return True

    def destroy(self, *args):
        pass

    def getName(self):
        return self.name

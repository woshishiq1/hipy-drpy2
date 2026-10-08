#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
床前侍卫 - 四壳通用Python Spider
站点：https://ctq.cqsw3.buzz/cqsw/
结构：苹果CMS
"""
import re
import urllib.request
import urllib.parse

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass
        def getName(self):
            return ""
        def isVideoFormat(self, url):
            return False
        def manualVideoCheck(self):
            return False
        def homeContent(self, filter):
            return {}
        def homeVideoContent(self):
            return {}
        def categoryContent(self, tid, pg, filter, extend):
            return {}
        def detailContent(self, ids):
            return {}
        def searchContent(self, key, quick, pg=1):
            return {}
        def playerContent(self, flag, id, vipFlags):
            return {}
        def localProxy(self, param):
            return [404, "text/plain", ""]
        def destroy(self):
            pass
        def setProxy(self, proxy):
            pass
        def getProxy(self):
            return None
        def getDependence(self):
            return ""


class Spider(Spider):
    def init(self, extend=""):
        self.siteUrl = "https://ctq.cqsw3.buzz"
        self.HOST = self.siteUrl
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        return self

    def getName(self):
        return "床前侍卫"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _fetch(self, url):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self.ua)
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"fetch error: {e}")
            return ""

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "国产自拍", "type_id": "20"},
            {"type_name": "强奸乱伦", "type_id": "21"},
            {"type_name": "男同女同", "type_id": "22"},
            {"type_name": "重口味", "type_id": "23"},
            {"type_name": "日本AV", "type_id": "24"},
            {"type_name": "无码视频", "type_id": "25"},
            {"type_name": "有码视频", "type_id": "26"},
            {"type_name": "中文字幕", "type_id": "27"},
            {"type_name": "欧美极品", "type_id": "28"},
            {"type_name": "三级伦理", "type_id": "29"},
            {"type_name": "动漫精品", "type_id": "30"},
        ]
        result["class"] = classes
        result["filters"] = {}
        
        # 首页推荐
        html = self._fetch(self.siteUrl + "/cn/home/web/")
        videos = []
        items = re.findall(
            r'<li[^>]*class="thumb item"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"',
            html, re.S
        )
        for url, img, title in items[:20]:
            vid = re.search(r"/id/(\d+)/", url)
            if vid:
                videos.append({
                    "vod_id": vid.group(1),
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
        result["list"] = videos
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        page = int(pg) if pg else 1
        url = f"{self.siteUrl}/cn/home/web/index.php/vod/type/id/{tid}.html"
        if page > 1:
            url = f"{self.siteUrl}/cn/home/web/index.php/vod/type/id/{tid}/page/{page}.html"
        
        html = self._fetch(url)
        videos = []
        items = re.findall(
            r'<li[^>]*class="thumb item"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"',
            html, re.S
        )
        for url, img, title in items:
            vid = re.search(r"/id/(\d+)/", url)
            if vid:
                videos.append({
                    "vod_id": vid.group(1),
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
        
        result["list"] = videos
        result["page"] = page
        result["pagecount"] = 100
        result["limit"] = 30
        result["total"] = 3000
        return result

    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.siteUrl}/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch(url)
        
        title = re.search(r"<title>([^<]*)</title>", html)
        title = title.group(1).split("_")[0] if title else ""
        
        # 找m3u8
        m3u8 = re.search(r"['\"]([^'\"]*\.m3u8[^'\"]*)['\"]", html)
        m3u8_url = m3u8.group(1).replace('\\/', '/') if m3u8 else ""
        
        list_data = [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "直链",
            "vod_play_url": m3u8_url,
        }]
        return {"list": list_data}

    def searchContent(self, key, quick, pg=1):
        result = {}
        url = f"{self.siteUrl}/cn/home/web/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        html = self._fetch(url)
        
        videos = []
        items = re.findall(
            r'<li[^>]*class="thumb item"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"',
            html, re.S
        )
        for url, img, title in items:
            vid = re.search(r"/id/(\d+)/", url)
            if vid:
                videos.append({
                    "vod_id": vid.group(1),
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
        
        result["list"] = videos
        result["page"] = 1
        result["pagecount"] = 1
        result["limit"] = 30
        result["total"] = len(videos)
        return result

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.siteUrl + "/"
            }
        }

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def destroy(self):
        pass

    def setProxy(self, proxy):
        pass

    def getProxy(self):
        return None

    def getDependence(self):
        return ""

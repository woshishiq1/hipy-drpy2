# -*- coding: utf-8 -*-
"""
探索妹妹 四壳通用Python Spider
站点: https://www.tsmm3.boats/tsmm/
特点: 自定义CMS（107vip48_wtpl模板），m3u8直链在详情页HTML中
分类: 10个分类
注意: 实际访问URL不带/tsmm/前缀
"""

import re
import json

try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            self.extend = {}
        def init(self, extend):
            self.extend = extend or {}

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://www.tsmm3.boats"
        self.rawSite = "https://www.tsmm3.boats"
        self.HOST = self.siteUrl
        self.cookie = ""
        self.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"

    def init(self, extend=""):
        if extend and isinstance(extend, str):
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        elif extend and isinstance(extend, dict):
            self.extend = extend
        else:
            self.extend = {}
        if self.extend.get("siteUrl"):
            self.siteUrl = self.extend["siteUrl"]
            self.HOST = self.siteUrl
        if self.extend.get("rawSite"):
            self.rawSite = self.extend["rawSite"]

    def homeContent(self, *args):
        classes = [
            {"type_id": "20", "type_name": "绝美少女"},
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
        filters = {}
        for c in classes:
            filters[c["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        list = self._parse_list(self._get(f"{self.siteUrl}/vodtype/20.html"))
        return {"class": classes, "list": list[:6], "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._get(url)
        list = self._parse_list(html)
        total = len(list)
        pagecount = 999 if total >= 36 else 1
        return {"page": page, "pagecount": pagecount, "limit": 36, "total": total * pagecount, "list": list}

    def detailContent(self, ids, *args):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        list = []
        for vod_id in ids:
            if not vod_id:
                continue
            if vod_id.startswith("http"):
                url = vod_id
            elif vod_id.startswith("/"):
                url = f"{self.siteUrl}{vod_id}"
            else:
                url = f"{self.siteUrl}/{vod_id}.html"
            html = self._get(url)
            if not html:
                continue
            title = ""
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).replace("正在播放:", "").replace("正在播放", "").strip()
                title = re.sub(r"\s*[-–—]\s*探索妹妹\s*$", "", title).strip()
            pic = ""
            pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', html)
            if pic_match:
                pic = pic_match.group(1)
            play_url = ""
            m3u8_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
            vod_play_from = "探索妹妹"
            vod_play_url = f"第1集${play_url}" if play_url else ""
            list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": title,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            })
        return {"list": list}

    def playerContent(self, flag, id, vipFlags, *args):
        url = id
        if not url.startswith("http"):
            url = f"{self.siteUrl}/{url}"
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self.ua,
                "Referer": f"{self.rawSite}/",
                "Origin": self.rawSite,
            },
        }

    def searchContent(self, key, page, *args):
        from urllib.parse import quote
        page = int(page) if page else 1
        url = f"{self.siteUrl}/s/index.html?wd={quote(key)}"
        html = self._get(url)
        list = self._parse_list(html)
        return {"page": page, "pagecount": 1, "limit": 36, "total": len(list), "list": list}

    def _parse_list(self, html):
        if not html:
            return []
        list = []
        # 107vip48_wtpl模板：封面链接+标题分开（和Didi长视频一样）
        # 封面：<a href="/123.html"><img src="封面"></a>
        # 标题：<h5><a href="/123.html" class="title">标题</a></h5>
        title_items = re.findall(r'href=["\']/(\d+)\.html["\'][^>]*class=["\']title["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        pic_items = re.findall(r'href=["\']/(\d+)\.html["\'][^>]*>\s*<img[^>]*src=["\']([^"\']+)["\']', html, re.DOTALL)
        pic_map = {vid: pic for vid, pic in pic_items}

        # 如果title方式没匹配到，尝试备用方式
        if not title_items:
            alt_items = re.findall(r'href=["\']/(\d+)\.html["\'][^>]*>\s*<img[^>]*alt=["\']([^"\']+)["\']', html, re.DOTALL)
            title_items = [(vid, title) for vid, title in alt_items if title]

        seen = set()
        for vod_id, content in title_items:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = re.sub(r"<[^>]+>", "", content).strip()
            pic = pic_map.get(vod_id, "")
            if title and len(title) > 1:
                list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return list

    def _get(self, url):
        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            resp = opener.open(req, timeout=20)
            return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[探索妹妹] 请求失败 {url}: {e}")
            return ""

    def getDependence(self, *args):
        return ""

    def localProxy(self, *args):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url, *args):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".avi", ".mkv", ".flv"])

    def manualVideoCheck(self, *args):
        return False

    def destroy(self, *args):
        pass

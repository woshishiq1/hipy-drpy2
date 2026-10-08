# -*- coding: utf-8 -*-
# 青霄视频 - yangmu.qxhuolaier.site
# TVBox/FongMi 爬虫源 - 苹果CMS HTML站

import re
import json
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://yangmu.qxhuolaier.site"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": self.host,
        }
        self.classes = []
        self._init_classes()

    def _init_classes(self):
        self.classes = [
            {"type_id": "42", "type_name": "国产视频"},
            {"type_id": "34", "type_name": "中文有码"},
            {"type_id": "22", "type_name": "女同性爱"},
            {"type_id": "28", "type_name": "人妖系列"},
            {"type_id": "30", "type_name": "虐待调教"},
        ]

    def getName(self):
        return "青霄视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            res = self.fetch(self.host, headers=self.headers)
            if res:
                html = self._get_text(res)
                if html:
                    items = self._parse_list(html)
                    if items:
                        return {"list": items[:20]}
            return {"list": []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend={}):
        try:
            page = pg or "1"
            tid = str(tid)
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            html = self._get_text(res)
            if not html:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            items = self._parse_list(html)
            total_pages = self._parse_total_pages(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": total_pages or 99,
                "limit": 20,
                "total": 0
            }
        except Exception:
            return {"list": [], "page": int(pg or "1"), "pagecount": 0, "limit": 20}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        try:
            vid = str(ids[0])
            url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}
            html = self._get_text(res)
            if not html:
                return {"list": []}

            # 提取标题
            title_match = re.search(r'<h1[^>]*class="headline-title"[^>]*>.*?正在观看-(.*?)</h1>', html, re.DOTALL)
            if title_match:
                vod_name = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            else:
                title_match2 = re.search(r'vod_name":"([^"]+)"', html)
                vod_name = title_match2.group(1) if title_match2 else vid

            # 提取播放地址
            play_url = ""
            start = html.find('var player_aaaa=')
            if start == -1:
                start = html.find('var player_aaaa =')
            if start != -1:
                segment = html[start:start+2000]
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', segment)
                if url_match:
                    play_url = url_match.group(1).replace('\\/', '/')
                    if 'test.cn' in play_url:
                        play_url = ""

            # 如果没提取到，从 iframe 提取
            if not play_url:
                iframe_match = re.search(r'<iframe[^>]*src="[^"]*aojiexi\.com[^"]*url=([^&"]+)"', html)
                if iframe_match:
                    from urllib.parse import unquote
                    play_url = unquote(iframe_match.group(1))

            if play_url and play_url.startswith('http'):
                vod = {
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "直链",
                    "vod_play_url": f"直链${play_url}"
                }
                return {"list": [vod]}
            else:
                vod = {
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "嗅探",
                    "vod_play_url": f"嗅探${url}"
                }
                return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{self.host}/index.php/vod/search.html"
            res = self.post(url, data={"wd": key}, headers=self.headers)
            if not res:
                return {"list": [], "page": int(pg)}
            html = self._get_text(res)
            if not html:
                return {"list": [], "page": int(pg)}
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception:
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags=""):
        if not id:
            return {"parse": 1, "url": ""}
        if ".m3u8" in id.lower() or ".mp4" in id.lower() or ".m3u" in id.lower():
            return {"parse": 0, "url": id, "header": self.headers}
        if "/play/" in id or "sid=" in id:
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def _get_text(self, res):
        if hasattr(res, 'text'):
            return res.text
        if hasattr(res, 'content'):
            try:
                return res.content.decode('utf-8')
            except:
                return str(res.content)
        if isinstance(res, str):
            return res
        return str(res)

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        pattern = r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<span[^>]*class="thumbs-title"[^>]*>.*?>(.*?)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        for full_url, vid, img, title in matches:
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title and vid:
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": ""
                })
        return items

    def _parse_total_pages(self, html):
        page_match = re.search(r'class="pagination".*?<span>.*?(\d+)</span>', html, re.DOTALL)
        if page_match:
            return int(page_match.group(1))
        return 1
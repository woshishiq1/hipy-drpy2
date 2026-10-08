import base64
import hashlib
import json
import os
import re
from requests import Session

from base.spider import Spider as BaseSpider


class RouAVSpider(BaseSpider):
    def getName(self):
        return "RouAVSpider_V2"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".webm" in url

    def manualVideoCheck(self):
        return False

    def init(self, extend=""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://rou.video/"
        }
        self.session = Session()
        self.session.headers.update(self.headers)
        self.cache = {}

    def homeContent(self, filter):
        try:
            return {
                "class": [
                    {"type_id": "1", "type_name": "全部视频"},
                    {"type_id": "2", "type_name": "国产"},
                    {"type_id": "3", "type_name": "日本"},
                    {"type_id": "4", "type_name": "欧美"},
                    {"type_id": "5", "type_name": "自拍"}
                ]
            }
        except Exception as e:
            return {"class": [{"type_id": "1", "type_name": "全部视频"}]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(max(1, int(pg)))
            return {
                "list": [{"vod_id": f"vid_{i}", "vod_name": f"视频{i}", "vod_pic": f"https://rou.video/pic{i}.jpg"} for i in range(page)],
                "page": page,
                "pagecount": 2,
                "limit": 20,
                "total": 80
            }
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if ids else "1"
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": f"肉视频第 {vid} 集",
                    "vod_pic": "https://rou.video/cover.jpg",
                    "vod_play_from": "在线播放",
                    "vod_play_url": f"https://rou.video/play/{vid}.m3u8"
                }]
            }
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            return {
                "list": [{"vod_id": f"search_{i}", "vod_name": f"搜索{i}", "vod_pic": f"https://rou.video/search{i}.jpg"} for i in range(10)],
                "page": int(pg),
                "pagecount": 2,
                "limit": 20
            }
        except Exception as e:
            return {"list": [], "page": 1, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if ".m3u8" in id:
                return {
                    "parse": 0,
                    "url": id,
                    "header": {"User-Agent": "Mozilla/5.0 Chrome/120"}
                }
            return {
                "parse": 0,
                "url": id,
                "header": {}
            }
        except Exception as e:
            return {"parse": 0, "url": id, "header": {}}

    def searchContent(self, key, quick, pg="1"):
        try:
            return {
                "list": [{"vod_id": f"search_{i}", "vod_name": f"搜索{i}", "vod_pic": f"https://rou.video/search{i}.jpg"} for i in range(10)],
                "page": int(pg),
                "pagecount": 2,
                "limit": 20
            }
        except Exception as e:
            return {"list": [], "page": 1, "pagecount": 1}

    def localProxy(self, param):
        try:
            return [200, "application/vnd.apple.mpegurl", b"success"]
        except:
            return [500, "text/plain", b"error"]

import sys
import json
import base64
from urllib.parse import urljoin
try:
    from base.spider import Spider as BaseSpider
except:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def searchContent(self, key, quick): pass
        def playerContent(self, flag, id, vipFlags): pass
        def localProxy(self, param): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def getName(self): pass

import requests

class Spider(BaseSpider):
    def __init__(self):
        self.domain = "http://api.vipmisss.com:81/xcdsw"

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.domain
        })

    def getName(self):
        return "百年直播"

    def homeContent(self, filter):
        url = f"{self.domain}/json.txt"
        try:
            rsp = self.session.get(url, timeout=10)
            json_data = rsp.json()
        except:
            return {"class": [], "list": []}
        classes = []
        for pt in json_data.get("pingtai", []):
            classes.append({
                "type_id": pt.get("address", ""),
                "type_name": pt.get("title", "")
            })
        return {"class": classes, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.domain}/{tid}"
        try:
            rsp = self.session.get(url, timeout=10)
            json_data = rsp.json()
        except:
            return {"page": int(pg), "pagecount": 1, "limit": 999, "total": 0, "list": []}
        videos = []
        for zb in json_data.get("zhubo", []):
            addr = zb.get("address", "")
            if not addr or "rtmp" in addr.lower():
                continue
            img = zb.get("img", "")
            if img and not img.startswith("http"):
                img = urljoin(f"{self.domain}/", img)
            vid = base64.b64encode(f"{zb.get('title', '')}|{addr}|{img}".encode()).decode()
            videos.append({
                "vod_id": vid,
                "vod_name": zb.get("title", ""),
                "vod_pic": img,
                "vod_remarks": "直播中"
            })
        return {
            "page": int(pg),
            "pagecount": 1,
            "limit": 999,
            "total": len(videos),
            "list": videos
        }

    def detailContent(self, ids):
        vid = ids[0]
        try:
            info = base64.b64decode(vid).decode()
            parts = info.split("|")
            title = parts[0] if len(parts) > 0 else ""
            addr = parts[1] if len(parts) > 1 else ""
            img = parts[2] if len(parts) > 2 else ""
        except:
            title = ""
            addr = vid
            img = ""
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": "直播",
                "vod_play_from": "直播源",
                "vod_play_url": f"第1集${addr}"
            }]
        }

    def searchContent(self, key, quick):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": json.dumps({"User-Agent": "Mozilla/5.0"})
        }

    def localProxy(self, param):
        return [200, "application/vnd.apple.mpegurl", ""]

    def isVideoFormat(self, url):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        pass

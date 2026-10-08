import json
import requests
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://ypsrpgrpv3l.ys91h.top"
        self.apiUrl = "https://api.heiapi.cc/api.php/provide/vod"
        self.header = {"Referer": self.siteUrl + "/"}
        self.classes = []
        self.filterData = {}

    def getName(self):
        return "91精品"

    def init(self, extend=""):
        try:
            r = requests.get(self.siteUrl + "/class.json", headers=self.header, timeout=10)
            data = r.json()
            for item in data:
                self.classes.append({
                    "type_id": str(item.get("type_id", "")),
                    "type_name": item.get("type_name", "")
                })
        except Exception:
            pass
        if not self.classes:
            self.classes = [
                {"type_id": "49", "type_name": "国产自拍"},
                {"type_id": "56", "type_name": "麻豆传媒"},
                {"type_id": "73", "type_name": "日本无码"},
                {"type_id": "102", "type_name": "美女写真"},
            ]
        return

    def homeContent(self, filter):
        result = self.categoryContent("", 1, filter, {})
        result["class"] = self.classes
        return result

    def homeVideoContent(self):
        return self.categoryContent("", 1, False, {})

    def categoryContent(self, tid, pg, filter, extend):
        params = {"ac": "detail", "pg": str(pg), "limit": "20"}
        if tid:
            params["t"] = tid
        sort = extend.get("sort", "")
        if sort and sort != "latest":
            params["sort"] = sort
        try:
            r = requests.get(self.apiUrl, params=params, headers=self.header, timeout=15)
            data = r.json()
        except Exception:
            return {"list": [], "page": pg, "pagecount": 0, "limit": 20, "total": 0}
        return self._parseList(data, pg)

    def detailContent(self, ids):
        if isinstance(ids, list):
            ids = ids[0]
        try:
            r = requests.get(self.apiUrl, params={"ac": "detail", "ids": ids}, headers=self.header, timeout=15)
            data = r.json()
        except Exception:
            return {"list": []}
        return self._parseDetail(data)

    def searchContent(self, key, quick, pg="1"):
        try:
            r = requests.get(self.apiUrl, params={"ac": "detail", "wd": key, "pg": str(pg), "limit": "20"}, headers=self.header, timeout=15)
            data = r.json()
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 0, "limit": 20, "total": 0}
        return self._parseList(data, int(pg))

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": id,
            "header": self.header,
            "playUrl": "",
            "jx": 0
        }

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def _parseList(self, data, pg):
        videos = []
        for item in data.get("list", []):
            videos.append({
                "vod_id": str(item.get("vod_id", "")),
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", "") or item.get("vod_pic_thumb", ""),
                "vod_remarks": item.get("vod_remarks", "") or item.get("type_name", ""),
                "vod_year": str(item.get("vod_year", "")),
                "vod_area": item.get("vod_area", ""),
            })
        return {
            "list": videos,
            "page": data.get("page", pg),
            "pagecount": data.get("pagecount", 0),
            "limit": data.get("limit", 20),
            "total": data.get("total", 0)
        }

    def _parseDetail(self, data):
        videos = []
        for item in data.get("list", []):
            vod = {
                "vod_id": str(item.get("vod_id", "")),
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", "") or item.get("vod_pic_thumb", ""),
                "type_name": item.get("type_name", ""),
                "vod_year": str(item.get("vod_year", "")),
                "vod_area": item.get("vod_area", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_actor": item.get("vod_actor", ""),
                "vod_director": item.get("vod_director", ""),
                "vod_content": item.get("vod_content", ""),
            }
            play_from = item.get("vod_play_from", "heihei")
            play_url = item.get("vod_play_url", "")
            if play_url:
                urls = []
                for line in play_url.split("$$$"):
                    for ep in line.split("#"):
                        if "$" in ep:
                            name, url = ep.split("$", 1)
                            urls.append(name + "$" + url)
                        else:
                            urls.append("第1集$" + ep)
                vod["vod_play_from"] = play_from
                vod["vod_play_url"] = "#".join(urls)
            else:
                vod["vod_play_from"] = ""
                vod["vod_play_url"] = ""
            videos.append(vod)
        return {"list": videos}

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def getHeaders(self):
        return self.header

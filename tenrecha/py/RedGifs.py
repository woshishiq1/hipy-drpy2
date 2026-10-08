# coding=utf-8
import sys
import requests
import time

try:
    from base.spider import Spider
except:
    class Spider(): pass

class Spider(Spider):
    def getName(self):
        return "RedGifs"

    def init(self, extend=""):
        self.api_base = "https://api.redgifs.com/v2"
        self.token = ""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.redgifs.com',
            'Referer': 'https://www.redgifs.com/'
        }

    def fetch_token(self):
        if self.token: return self.token
        try:
            # RedGifs 获取临时 Token 的标准接口
            url = f"{self.api_base}/auth/temporary"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                self.token = r.json().get('token')
                return self.token
        except:
            pass
        return None

    def homeContent(self, filter):
        result = {"class": [
            {"type_id": "trending", "type_name": "🔥 Trending"},
            {"type_id": "top", "type_name": "🏆 Top"},
            {"type_id": "latest", "type_name": "✨ New"}
        ], "list": []}
        result["list"] = self.categoryContent("trending", "1", False, {}).get("list", [])
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 10, "limit": 20, "total": 200}
        token = self.fetch_token()
        if not token: return result

        # 注意：RedGifs API 的 search_text 不能留空，默认搜 trending
        url = f"{self.api_base}/gifs/search?search_text=trending&order={tid}&count=20&page={pg}"
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                for item in r.json().get('gifs', []):
                    result["list"].append({
                        "vod_id": item['id'],
                        "vod_name": f"Video {item['id']}",
                        "vod_pic": item.get('urls', {}).get('thumbnail', ''),
                        "vod_remarks": f"👁️ {item.get('views', 0)}"
                    })
        except:
            pass
        return result

    def detailContent(self, ids):
        tid = ids[0]
        token = self.fetch_token()
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        try:
            r = requests.get(f"{self.api_base}/gifs/{tid}", headers=headers, timeout=10)
            gif = r.json().get('gif', {})
            return {"list": [{
                "vod_id": gif['id'],
                "vod_name": gif['id'],
                "vod_pic": gif['urls'].get('thumbnail'),
                "vod_play_from": "RedGifs",
                "vod_play_url": f"HD${gif['urls'].get('hd')}#SD${gif['urls'].get('sd')}",
                "vod_content": f"Tags: {','.join(gif.get('tags', []))}"
            }]}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "playUrl": "", "url": id}

    def searchContent(self, key, quick, pg=1):
        return self.categoryContent(key, pg, False, {})
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

        url = f"{self.api_base}/gifs/search?search_text=trending&order={tid}&count=20&page={pg}"
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                for item in r.json().get('gifs', []):
                    # 将分类信息（tid）嵌入 vod_id，便于详情页识别
                    result["list"].append({
                        "vod_id": f"{tid}:{item['id']}",
                        "vod_name": f"Video {item['id']}",
                        "vod_pic": item.get('urls', {}).get('thumbnail', ''),
                        "vod_remarks": f"👁️ {item.get('views', 0)}"
                    })
        except:
            pass
        return result

    def detailContent(self, ids):
        # 解析传入的ID，格式为 "分类:真实ID"
        vid = ids[0]
        if ':' in vid:
            category, real_id = vid.split(':', 1)
        else:
            category, real_id = "trending", vid  # 默认分类

        token = self.fetch_token()
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        # 获取当前视频的详细信息
        try:
            r = requests.get(f"{self.api_base}/gifs/{real_id}", headers=headers, timeout=10)
            current_gif = r.json().get('gif', {})
        except:
            return {"list": []}

        # 获取同分类下的其他视频（作为选集）
        playlist = []
        try:
            # 请求分类列表（第一页，20个）
            url = f"{self.api_base}/gifs/search?search_text=trending&order={category}&count=20&page=1"
            r2 = requests.get(url, headers=headers, timeout=10)
            if r2.status_code == 200:
                for item in r2.json().get('gifs', []):
                    # 跳过当前视频（可选，避免重复）
                    if item['id'] == real_id:
                        continue
                    # 每个视频作为一集，链接优先选择hd，其次sd
                    video_url = item.get('urls', {}).get('hd') or item.get('urls', {}).get('sd')
                    if video_url:
                        # 格式： "视频ID$播放链接"
                        playlist.append(f"Video {item['id']}${video_url}")
        except:
            pass

        # 将当前视频加入播放列表（放在第一位）
        current_url = current_gif.get('urls', {}).get('hd') or current_gif.get('urls', {}).get('sd')
        if current_url:
            playlist.insert(0, f"Video {current_gif['id']}${current_url}")

        # 构建返回数据
        vod = {
            "vod_id": vid,
            "vod_name": current_gif.get('id', ''),
            "vod_pic": current_gif.get('urls', {}).get('thumbnail', ''),
            "vod_play_from": "RedGifs 合集",          # 来源名称
            "vod_play_url": "#".join(playlist),       # 用#连接多个剧集
            "vod_content": f"Tags: {','.join(current_gif.get('tags', []))}"
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        # 直接返回视频链接，无需解析
        return {"parse": 0, "playUrl": "", "url": id}

    def searchContent(self, key, quick, pg=1):
        # 搜索功能直接复用分类逻辑，将关键词作为分类名（注意：实际搜索可能需要专用接口，这里保持原有逻辑）
        return self.categoryContent(key, pg, False, {})
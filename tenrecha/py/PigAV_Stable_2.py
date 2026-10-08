import json
import urllib.parse
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "PigAV_Stable"

    def init(self, extend=""):
        self.base_url = "https://pigav.ws"
        self.api_url = "https://pigav.ws/api/v1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://pigav.ws",
            "Referer": "https://pigav.ws/"
        }
        self.page_size = 24

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_id": "publishedAt", "type_name": "最近更新"},
                {"type_id": "hot", "type_name": "热门视频"},
                {"type_id": "views", "type_name": "最多观看"}
            ]
        }
        result["list"] = self.get_videos(f"{self.api_url}/videos?sort=-publishedAt&count={self.page_size}&start=0")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        sort_map = {"publishedAt": "-publishedAt", "hot": "-hot", "views": "-views"}
        sort = sort_map.get(tid, "-publishedAt")
        p = int(pg)
        start = (max(1, p) - 1) * self.page_size
        url = f"{self.api_url}/videos?sort={sort}&count={self.page_size}&start={start}"
        return {"list": self.get_videos(url)}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = f"{self.api_url}/videos/{vid}"
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            data = self.parse_json(res)
            if not data:
                return {"list": []}
            
            vod = {
                "vod_id": vid,
                "vod_name": data.get("name") or data.get("title") or "",
                "vod_pic": self.fix_url(data.get("thumbnailPath", "")),
                "vod_remarks": self.format_time(data.get("duration", 0)),
                "vod_actor": data.get("channel", {}).get("displayName", "") if isinstance(data.get("channel"), dict) else "",
                "vod_content": data.get("description", ""),
                "vod_play_from": "PigAV",
                "vod_play_url": f"播放正片${vid}"
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        p = int(pg)
        start = (max(1, p) - 1) * self.page_size
        # 修复：中文搜索必须 URL 编码，否则请求失败
        encoded_key = urllib.parse.quote(key)
        url = f"{self.api_url}/search/videos?search={encoded_key}&count={self.page_size}&start={start}"
        return {"list": self.get_videos(url)}

    def playerContent(self, flag, id, vipFlags):
        url = f"{self.api_url}/videos/{id}"
        
        # 修复：精简 Header，移除 Range 头。m3u8 索引文件不需要 Range，部分播放器内核会因此 403/断流
        play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": f"https://pigav.ws/videos/{id}",
            "Origin": "https://pigav.ws",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            data = self.parse_json(res)
            if not data:
                return {"parse": 0, "url": ""}
            
            play_url = ""
            
            # ===== 方案1: HLS (m3u8) =====
            streaming = data.get("streamingPlaylists", [])
            if streaming and isinstance(streaming, list):
                best_stream = None
                # 优先选 720p 左右，兼顾清晰度与加载速度
                for stream in streaming:
                    if not isinstance(stream, dict):
                        continue
                    res_h = stream.get("resolution", {})
                    height = res_h.get("height", 0) if isinstance(res_h, dict) else 0
                    if 680 <= height <= 800:
                        best_stream = stream
                        break
                
                # 次选 480p 或 1080p
                if not best_stream:
                    for stream in streaming:
                        if not isinstance(stream, dict):
                            continue
                        res_h = stream.get("resolution", {})
                        height = res_h.get("height", 0) if isinstance(res_h, dict) else 0
                        if 400 <= height <= 1100:
                            best_stream = stream
                            break
                
                # 兜底选第一个
                if not best_stream:
                    best_stream = streaming[0]
                
                if isinstance(best_stream, dict):
                    # 兼容多种可能的字段名
                    for field in ["playlistUrl", "url", "playlist_url", "hlsUrl"]:
                        play_url = best_stream.get(field, "")
                        if play_url:
                            break
            
            # ===== 方案2: MP4 / WebM 直链 =====
            if not play_url:
                files = data.get("files", [])
                if files and isinstance(files, list):
                    candidates = []
                    for f in files:
                        if not isinstance(f, dict):
                            continue
                        res_info = f.get("resolution", {})
                        height = res_info.get("height", 0) if isinstance(res_info, dict) else 0
                        candidates.append((height, f))
                    
                    # 按分辨率升序，优先取 720p 及以下的最高画质
                    candidates.sort(key=lambda x: x[0])
                    suitable = [f for h, f in candidates if 0 < h <= 720]
                    target = suitable[-1] if suitable else (candidates[-1][1] if candidates else None)
                    
                    if target:
                        for field in ["fileUrl", "fileDownloadUrl", "url", "downloadUrl", "src"]:
                            play_url = target.get(field, "")
                            if play_url:
                                break
            
            # ===== 方案3: 根级备用字段 =====
            if not play_url:
                for field in ["videoUrl", "streamUrl", "url", "source", "playbackUrl"]:
                    play_url = data.get(field, "")
                    if play_url:
                        break
            
            # 统一处理 URL
            play_url = self.fix_url(play_url)
            
            if play_url:
                is_m3u8 = ".m3u8" in play_url.lower()
                
                result = {
                    "parse": 0,
                    "url": play_url,
                    "header": play_headers
                }
                
                # 部分播放器内核需要显式标记 jx=0 才会走直链逻辑
                if is_m3u8:
                    result["jx"] = "0"
                
                return result
                
        except Exception:
            pass
        
        return {"parse": 0, "url": ""}

    def get_videos(self, url):
        videos = []
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            data = self.parse_json(res)
            if not data:
                return videos
            
            items = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                vid = item.get("shortUUID") or item.get("uuid") or item.get("id", "")
                if not vid:
                    continue
                videos.append({
                    "vod_id": vid,
                    "vod_name": item.get("name") or item.get("title") or "",
                    "vod_pic": self.fix_url(item.get("thumbnailPath", "")),
                    "vod_remarks": self.format_time(item.get("duration", 0))
                })
        except Exception:
            pass
        return videos

    def parse_json(self, res):
        """统一安全解析响应"""
        try:
            if hasattr(res, 'text'):
                text = res.text
            elif hasattr(res, 'content'):
                text = res.content.decode('utf-8', errors='ignore')
            else:
                text = str(res)
            return json.loads(text) if text else None
        except Exception:
            return None

    def fix_url(self, path):
        if not path:
            return ""
        path = str(path).strip()
        if path.startswith("http"):
            return path
        # 修复：正确处理缺少斜杠的相对路径，防止拼接成 https://pigav.wsthumbnails/...
        base = self.base_url.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"

    def format_time(self, seconds):
        try:
            sec = int(float(seconds))
            m, s = divmod(sec, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        except Exception:
            return ""
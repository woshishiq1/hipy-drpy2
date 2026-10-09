# coding=utf-8
"""
音乐库 (yinyueku.cn) TVBox 音乐爬虫
基于 MKOnlinePlayer api.php · 风格对齐 凤梨音乐.py
- 分类：站点配置歌单（抖音热歌/黑胶VIP等）
- 搜索：types=search
- 播放：types=url + id/source/sign 直出 mp3
"""
import sys
import re
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    host = "https://www.yinyueku.cn"
    api = host + "/api.php"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    PLAYLISTS = [
        {"id": "7785066739", "source": "netease", "name": "黑胶VIP热歌榜"},
        {"id": "music174723163081", "source": "my", "name": "抖音热歌"},
        {"id": "music17472336238", "source": "my", "name": "K歌金曲"},
        {"id": "music174723400571", "source": "my", "name": "影视金曲"},
        {"id": "music174723516789", "source": "my", "name": "动漫音乐"},
        {"id": "music174727005359", "source": "my", "name": "试音人声"},
        {"id": "music174723193145", "source": "my", "name": "一人一首成名曲"},
        {"id": "music174727210412", "source": "my", "name": "高效助眠"},
        {"id": "music174727460767", "source": "my", "name": "红歌经典"},
        {"id": "music174723266632", "source": "my", "name": "70后金曲"},
        {"id": "music174723290833", "source": "my", "name": "80后金曲"},
        {"id": "music174723312765", "source": "my", "name": "90后金曲"},
        {"id": "music174723333326", "source": "my", "name": "00后金曲"},
        {"id": "music174727341490", "source": "my", "name": "儿歌童谣"},
    ]

    def getName(self):
        return "音乐库"

    def init(self, extend=""):
        if extend and str(extend).startswith("http"):
            self.host = str(extend).rstrip("/")
            self.api = self.host + "/api.php"

    def destroy(self):
        pass

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.host + "/",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }

    def _api(self, data):
        try:
            r = self.post(self.api, data=data, headers=self._headers())
            if not r:
                return None
            text = r.text if hasattr(r, "text") else str(r)
            text = (text or "").strip()
            if not text:
                return None
            return json.loads(text)
        except Exception:
            return None

    def _artist(self, a):
        if isinstance(a, list):
            return " / ".join([str(x) for x in a if x])
        return str(a or "")

    def _song_vod(self, s):
        sid = str(s.get("id") or "")
        source = str(s.get("source") or "netease")
        sign = str(s.get("sign") or "")
        name = str(s.get("name") or sid)
        artist = self._artist(s.get("artist"))
        # play id 携带 source|sign，播放时再取直链
        play_id = sid + "|" + source + "|" + sign
        return {
            "vod_id": play_id,
            "vod_name": name,
            "vod_pic": "",
            "vod_remarks": artist,
            "vod_actor": artist,
        }

    def homeContent(self, filter):
        classes = [{"type_id": p["id"] + "@" + p["source"], "type_name": p["name"]} for p in self.PLAYLISTS]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        # 默认展示黑胶VIP热歌榜前20
        data = self._api({"types": "playlist", "id": "7785066739", "source": "netease"}) or []
        if not isinstance(data, list):
            data = []
        return {"list": [self._song_vod(s) for s in data[:20]]}

    def categoryContent(self, tid, pg, filter, ext):
        page = int(pg) if str(pg).isdigit() else 1
        tid = str(tid or "")
        source = "netease"
        lid = tid
        if "@" in tid:
            lid, source = tid.split("@", 1)
        data = self._api({"types": "playlist", "id": lid, "source": source}) or []
        if not isinstance(data, list):
            data = []
        # 简单分页
        size = 30
        start = (page - 1) * size
        chunk = data[start:start + size]
        return {
            "list": [self._song_vod(s) for s in chunk],
            "page": page,
            "pagecount": max(1, (len(data) + size - 1) // size),
            "limit": size,
            "total": len(data),
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        data = self._api({
            "types": "search",
            "count": 20,
            "pages": page,
            "name": key,
        }) or []
        if not isinstance(data, list):
            data = []
        return {
            "list": [self._song_vod(s) for s in data],
            "page": page,
            "pagecount": page + (1 if len(data) >= 20 else 0),
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else ids
        raw = str(raw)
        parts = raw.split("|")
        sid = parts[0] if parts else raw
        source = parts[1] if len(parts) > 1 else "netease"
        sign = parts[2] if len(parts) > 2 else ""
        name = sid
        artist = ""
        # 尝试用搜索补全元数据（可选）
        try:
            data = self._api({"types": "search", "count": 5, "pages": 1, "name": sid}) or []
            if isinstance(data, list):
                for s in data:
                    if str(s.get("id")) == sid:
                        name = s.get("name") or name
                        artist = self._artist(s.get("artist"))
                        source = s.get("source") or source
                        sign = s.get("sign") or sign
                        break
        except Exception:
            pass
        play_id = sid + "|" + source + "|" + sign
        vod = {
            "vod_id": play_id,
            "vod_name": name,
            "vod_pic": "",
            "vod_actor": artist,
            "vod_remarks": "可试听",
            "vod_content": ("歌手：" + artist) if artist else "",
            "vod_play_from": "音乐库",
            "vod_play_url": "试听$" + play_id,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        raw = str(id or "")
        if "$" in raw:
            raw = raw.split("$")[-1]
        if raw.startswith("http"):
            return {"parse": 0, "url": raw, "header": header}
        parts = raw.split("|")
        sid = parts[0] if parts else ""
        source = parts[1] if len(parts) > 1 else "netease"
        sign = parts[2] if len(parts) > 2 else ""
        if not sid:
            return {"parse": 0, "url": "", "header": header}
        data = self._api({"types": "url", "id": sid, "source": source, "sign": sign}) or {}
        url = ""
        if isinstance(data, dict):
            url = data.get("url") or ""
        if url and str(url).startswith("http"):
            return {"parse": 0, "url": url, "header": header}
        return {"parse": 0, "url": "", "header": header, "msg": "获取播放地址失败"}

    def localProxy(self, params):
        return None

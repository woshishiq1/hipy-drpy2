# coding=utf-8
# !/python
import sys
import re
import json
import requests
from urllib.parse import quote
from base.spider import Spider

sys.path.append('..')

HOST = "https://ddys.io"
API = HOST + "/api/v1"

HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": HOST + "/",
    "X-Requested-With": "XMLHttpRequest",
}

CATEGORIES = [
    {"type_id": "latest", "type_name": "最新更新"},
    {"type_id": "movie", "type_name": "电影"},
    {"type_id": "series", "type_name": "剧集"},
    {"type_id": "anime", "type_name": "动漫"},
    {"type_id": "variety", "type_name": "综艺"},
]

class Spider(Spider):
    def getName(self):
        return "低端影视"

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update(HEADER)
        self.session.get(HOST + "/", timeout=10)

    def _get(self, path, params=None):
        try:
            r = self.session.get(API + path, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except:
            return None

    def _parse_movie(self, item):
        return {
            "vod_id": item.get("slug", ""),
            "vod_name": item.get("title", ""),
            "vod_pic": item.get("poster", ""),
            "vod_remarks": str(item.get("rating", "")) if item.get("rating") else "",
            "vod_year": str(item.get("year", "")),
            "type_name": item.get("type", ""),
        }

    def homeContent(self, filter=False):
        result = {"class": []}
        for cat in CATEGORIES:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
        return result

    def homeVideoContent(self):
        data = self._get("/movies", {"limit": 24})
        if not data or not data.get("data"):
            return {"list": []}
        return {"list": [self._parse_movie(i) for i in data["data"]]}

    def categoryContent(self, tid, pg="1", filt=False, ext={}):
        page = int(pg) if pg else 1
        params = {"page": page, "limit": 24}
        if tid and tid != "latest":
            params["type"] = tid
        data = self._get("/movies", params=params)
        if not data or not data.get("data"):
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        meta = data.get("meta", {})
        items = [self._parse_movie(i) for i in data["data"]]
        return {
            "list": items,
            "page": page,
            "pagecount": meta.get("total_pages", 1),
            "limit": meta.get("per_page", 24),
            "total": meta.get("total", 0),
        }

    def _parse_online(self, online_list):
        """解析在线播放源，每个播放源作为一条独立线路"""
        result = []
        for i, src in enumerate(online_list):
            name = src.get("name", f"播放源{i+1}") or f"播放源{i+1}"
            url = src.get("url", "")
            if not url:
                continue
            # 多集格式: "第01集$https://...m3u8#第02集$https://...m3u8"
            if "$" in url and "#" in url:
                parts = url.split("#")
                ep_list = []
                for part in parts:
                    part = part.strip()
                    if "$" in part:
                        ep_name, ep_url = part.split("$", 1)
                        ep_list.append(f"{ep_name.strip()}${ep_url.strip()}")
                    else:
                        ep_list.append(f"播放${part}")
                result.append((name, "&".join(ep_list)))
            elif url and "http" in url:
                result.append((name, f"播放${url}"))
        return result

    def detailContent(self, ids):
        slug = str(ids[0]).strip() if ids else ""
        if not slug:
            return {"list": []}
        detail = self._get(f"/movies/{slug}")
        if not detail or not detail.get("data"):
            return {"list": []}
        d = detail["data"]
        sources = self._get(f"/movies/{slug}/sources")
        source_data = sources.get("data", {}) if sources else {}
        play_from = []
        play_url = []
        online_list = source_data.get("online", [])
        if online_list:
            eps = self._parse_online(online_list)
            for name, ep_url in eps:
                play_from.append(name)
                play_url.append(ep_url)
        if not play_from:
            play_from = ["在线播放"]
            play_url = ["播放$"]
        intro = re.sub(r'<[^>]+>', '', d.get("intro", "")).strip()
        actors = d.get("actors", [])
        directors = d.get("director", [])
        vod = {
            "vod_id": slug,
            "vod_name": d.get("title", ""),
            "vod_pic": d.get("poster", ""),
            "vod_year": str(d.get("year", "")),
            "vod_area": d.get("region", ""),
            "vod_actor": "/".join(actors) if actors else "",
            "vod_director": "/".join(directors) if directors else "",
            "vod_remarks": d.get("rating", "") and str(d["rating"]) or "",
            "vod_content": intro[:500],
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        url = id.strip()
        if not url:
            return {"parse": 0, "playUrl": "", "url": "", "header": HEADER}
        is_m3u8 = bool(re.search(r'\.m3u8(\?|$|#|&)', url))
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": HEADER if is_m3u8 else {},
        }

    def searchContent(self, key, quick=False, pg="1"):
        params = {"q": key, "page": int(pg) if pg else 1, "limit": 20}
        data = self._get("/search", params=params)
        if not data or not data.get("data"):
            return {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 20, "total": 0}
        items = [self._parse_movie(i) for i in data["data"]]
        meta = data.get("meta", {})
        return {
            "list": items,
            "page": int(pg) if pg else 1,
            "pagecount": meta.get("total_pages", 1),
            "limit": meta.get("per_page", 20),
            "total": meta.get("total", 0),
        }

    def localProxy(self, params):
        return None


if __name__ == "__main__":
    spider = Spider()
    spider.init("")
    print("=== home ===")
    print(json.dumps(spider.homeContent(), ensure_ascii=False, indent=2))
    print("\n=== homeVod ===")
    print(json.dumps(spider.homeVideoContent(), ensure_ascii=False, indent=2))
    print("\n=== cate movie ===")
    print(json.dumps(spider.categoryContent("movie", "1", False, {}), ensure_ascii=False, indent=2))
    print("\n=== search 凡人 ===")
    print(json.dumps(spider.searchContent("凡人", False, "1"), ensure_ascii=False, indent=2))
    print("\n=== detail 凡人修仙传 ===")
    print(json.dumps(spider.detailContent(["a-mortals-journey-to-immortality"]), ensure_ascii=False, indent=2))
    print("\n=== play ===")
    print(json.dumps(spider.playerContent("", "播放$https://test.m3u8", []), ensure_ascii=False, indent=2))

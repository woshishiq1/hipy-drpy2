import base64
import json
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    API = "https://xk211.xkgzs.xyz/api/vod/"
    AES_KEY = b"11320jkjksdkxxaw"
    PAGE_SIZE = 36

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "okhttp/4.12.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "App-Version-Code": "123",
            "App-Os-Type": "android",
            "App-Ui-Mode": "2",
            "App-Device-Id": "1234567890abcdef1234567890abcdef",
        })
        self._init_data = None
        self._init_time = 0

    def getName(self):
        return "星空4K"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return bool(url and any(x in url.lower() for x in (".m3u8", ".mp4", ".flv", ".mkv", ".mpd")))

    def manualVideoCheck(self):
        pass

    def destroy(self):
        self.session.close()

    def _decrypt(self, value):
        raw = base64.b64decode(value)
        cipher = AES.new(self.AES_KEY, AES.MODE_CBC, self.AES_KEY)
        return json.loads(unpad(cipher.decrypt(raw), AES.block_size).decode("utf-8"))

    def _post(self, endpoint, data=None):
        response = self.session.post(self.API + endpoint, data=data or {}, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("msg") or "API request failed")
        encrypted = payload.get("data")
        return self._decrypt(encrypted) if encrypted else {}

    def _get_init(self):
        if self._init_data is None or time.time() - self._init_time > 600:
            self._init_data = self._post("init")
            self._init_time = time.time()
        return self._init_data

    @staticmethod
    def _vod(item):
        return {
            "vod_id": str(item.get("vod_id", "")),
            "vod_name": item.get("vod_name", ""),
            "vod_pic": item.get("vod_pic", ""),
            "vod_remarks": item.get("vod_remarks", ""),
        }

    def homeContent(self, filter):
        data = self._get_init()
        classes = [
            {"type_id": str(item["type_id"]), "type_name": item.get("type_name", "")}
            for item in data.get("type_list", [])
            if item.get("type_id")
        ]
        videos = data.get("recommend_list") or data.get("hot_search_list") or []
        return {"class": classes, "list": [self._vod(v) for v in videos], "filters": {}}

    def homeVideoContent(self):
        data = self._get_init()
        videos = data.get("recommend_list") or data.get("hot_search_list") or []
        return {"list": [self._vod(v) for v in videos]}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(int(pg or 1), 1)
        params = {"type_id": tid, "page": page}
        for key in ("class", "area", "lang", "year", "sort", "by"):
            if extend and extend.get(key):
                params[key] = extend[key]
        data = self._post("typeFilterVodList", params)
        items = data.get("recommend_list", [])
        total = int(data.get("total") or 0)
        page_size = int(data.get("page_size") or self.PAGE_SIZE)
        pagecount = (total + page_size - 1) // page_size if total else page + (1 if len(items) >= page_size else 0)
        return {
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": page_size,
            "total": total,
            "list": [self._vod(v) for v in items],
        }

    def detailContent(self, ids):
        data = self._post("vodDetail", {"vod_id": ids[0]})
        vod = data.get("vod") or {}
        source_info = {}
        for source in data.get("player_source_list", []):
            source_info.setdefault(source.get("player_code"), source)
        play_from = []
        play_urls = []
        for source in data.get("vod_play_url_list", []):
            code = source.get("player_code", "")
            player = source_info.get(code) or {}
            source_id = player.get("id")
            if source_id is None:
                continue
            episodes = []
            for episode in source.get("urls", []):
                url = episode.get("url", "")
                if url and self.isVideoFormat(url):
                    play_id = url
                else:
                    play_id = "xk://{}/{}/{}".format(ids[0], source_id, episode.get("episode_index", 0))
                episodes.append(f'{episode.get("name") or "播放"}${play_id}')
            if episodes:
                play_from.append(player.get("player_name") or code or "播放")
                play_urls.append("#".join(episodes))
        item = self._vod(vod)
        item.update({
            "vod_actor": vod.get("vod_actor", ""),
            "vod_director": vod.get("vod_director", ""),
            "vod_content": vod.get("vod_content") or vod.get("vod_blurb", ""),
            "vod_year": vod.get("vod_year", ""),
            "vod_area": vod.get("vod_area", ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_urls),
        })
        return {"list": [item]}

    def searchContent(self, key, quick, pg="1"):
        page = max(int(pg or 1), 1)
        data = self._post("searchList", {"keywords": key, "page": page})
        items = data.get("search_list", [])
        return {"page": page, "pagecount": page + (1 if len(items) >= self.PAGE_SIZE else 0), "list": [self._vod(v) for v in items]}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        url = id
        if id.startswith("xk://"):
            vod_id, source_id, episode_index = id[5:].split("/", 2)
            data = self._post("vodParse", {
                "vod_id": vod_id,
                "player_source_id": source_id,
                "episode_index": episode_index,
                "scene": 0,
            })
            url = data.get("play_url", "")
        direct = self.isVideoFormat(url)
        return {
            "parse": 0 if direct else 1,
            "url": url,
            "header": json.dumps({"User-Agent": self.session.headers["User-Agent"]}, ensure_ascii=False),
        }

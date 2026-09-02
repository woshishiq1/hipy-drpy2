# -*- coding: utf-8 -*-
import json
import ssl
import urllib3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ai.dramarush.tv"
        self.api = self.host + "/api/trpc"
        self.name = "追剧狂飙"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16; PLA-AL10 Build/HUAWEIPLA-AL10) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/114.0.5735.196 Mobile Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": self.host + "/zh",
            "Origin": self.host
        }
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = TLSAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        self.class_cache = None
        # cursor 翻页状态缓存: { "tid_page": cursor_value }
        self.cursor_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("base_url") or self.host).rstrip("/")
                self.api = self.host + "/api/trpc"
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/zh"
                self.session.headers.update(self.headers)
            except Exception:
                pass

    def getName(self):
        return self.name

    # ==================== tRPC 请求核心 ====================

    def _trpc(self, proc, payload=None):
        url = f"{self.api}/{proc}"
        params = {}
        if payload is not None:
            params["input"] = json.dumps({"json": payload}, separators=(",", ":"))
        try:
            r = self.session.get(url, params=params, timeout=20, verify=False)
            if r.status_code == 200:
                data = r.json()
                return data.get("result", {}).get("data", {}).get("json", {})
            elif r.status_code == 400:
                err = r.json().get("error", {}).get("json", {}).get("message", "")
                print(f"[DramaRush] {proc} BAD_REQUEST: {err[:200]}")
            else:
                print(f"[DramaRush] {proc} HTTP {r.status_code}")
        except Exception as e:
            print(f"[DramaRush] {proc} exception: {e}")
        return {}

    # ==================== 播放地址解析 ====================

    def _resolve_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _get_episode_url(self, drama_id, episode_index):
        data = self._trpc("episode.watch", {"dramaId": drama_id, "episode": int(episode_index)})
        if isinstance(data, dict):
            ep = data.get("episode", {})
            return self._resolve_url(ep.get("hlsUrl", ""))
        return ""

    # ==================== 标准爬虫接口 ====================

    def homeContent(self, filter):
        data = self._trpc("feed.recommend", {"pageSize": 20})
        classes = self._classes()
        items = []
        if isinstance(data, dict):
            for it in data.get("items", []):
                drama = it.get("drama") or it
                if drama:
                    items.append(drama)
        return {
            "class": classes,
            "filters": self._filters(classes),
            "list": [self._vod(x) for x in items],
            "parse": 0,
            "jx": 0
        }

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        pg = int(pg or 1)
        items = []
        cursor_key = f"{tid}_{pg}"
        prev_key = f"{tid}_{pg - 1}" if pg > 1 else None

        if tid == "rank":
            tab = extend.get("tab", "hot")
            req = {"tab": tab, "pageSize": 30}
            if prev_key and prev_key in self.cursor_cache:
                req["cursor"] = self.cursor_cache[prev_key]
            data = self._trpc("rank.list", req)
            items = data.get("items", []) if isinstance(data, dict) else []
            # 缓存下一页 cursor
            if data.get("nextCursor"):
                self.cursor_cache[cursor_key] = data["nextCursor"]

        elif tid == "recommend":
            req = {"pageSize": 20}
            if prev_key and prev_key in self.cursor_cache:
                req["cursor"] = self.cursor_cache[prev_key]
            data = self._trpc("feed.recommend", req)
            if isinstance(data, dict):
                for it in data.get("items", []):
                    drama = it.get("drama") or it
                    if drama:
                        items.append(drama)
            if data.get("nextCursor"):
                self.cursor_cache[cursor_key] = data["nextCursor"]

        else:
            req = {"pageSize": 30}
            if extend.get("order"):
                req["order"] = extend.get("order")
            if extend.get("updateStatus"):
                req["updateStatus"] = extend.get("updateStatus")
            if extend.get("genre"):
                req["genre"] = extend.get("genre")
            if tid not in ("all", "recommend"):
                req["contentKind"] = tid
            if prev_key and prev_key in self.cursor_cache:
                req["cursor"] = self.cursor_cache[prev_key]
            data = self._trpc("drama.list", req)
            items = data.get("items", []) if isinstance(data, dict) else []
            if data.get("nextCursor"):
                self.cursor_cache[cursor_key] = data["nextCursor"]

        has_more = bool(data.get("nextCursor")) if isinstance(data, dict) else False
        return {
            "page": pg,
            "pagecount": pg + 1 if has_more else pg,
            "limit": 30,
            "total": 99999,
            "list": [self._vod(x) for x in items],
            "parse": 0,
            "jx": 0
        }

    def detailContent(self, ids):
        vid = str(ids[0]).replace("dr_", "")
        data = self._trpc("drama.byId", {"id": vid})
        if not isinstance(data, dict) or not data.get("id"):
            return {"list": []}

        name = data.get("title") or data.get("name") or vid
        total = data.get("totalEpisodes") or 0

        # 获取剧集列表（从 episode.watch 获取完整 episodes 信息）
        watch_data = self._trpc("episode.watch", {"dramaId": vid, "episode": 1})
        eps = []
        if isinstance(watch_data, dict):
            eps = watch_data.get("episodes", [])

        play = []
        for ep in eps:
            idx = ep.get("index") or 1
            title = ep.get("title") or f"第{idx}集"
            is_free = ep.get("isFree", False)
            locked = ep.get("locked", False)

            if is_free and not locked:
                url = self._get_episode_url(vid, idx)
                if url:
                    play.append(f"{title}${url}")
                else:
                    play.append(f"{title}${vid}|{idx}")
            else:
                # 付费集：标注需要解锁，但保留索引供 playerContent 尝试
                play.append(f"{title}[锁]${vid}|{idx}")

        if not play:
            # 单集剧兜底
            url = self._get_episode_url(vid, 1)
            if url:
                play = [f"第1集${url}"]
            else:
                play = [f"第1集${vid}|1"]

        vod = {
            "vod_id": "dr_" + vid,
            "vod_name": name,
            "vod_pic": self._pic(data),
            "type_name": self._kind_name(data.get("contentKind", "")),
            "vod_year": str(data.get("year") or ""),
            "vod_area": data.get("region") or "",
            "vod_remarks": data.get("releaseStatus") or f"全{total}集",
            "vod_actor": data.get("actor") or "",
            "vod_director": data.get("director") or "",
            "vod_content": data.get("description") or data.get("summary") or name,
            "vod_play_from": self.name,
            "vod_play_url": "#".join(play)
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        # search.query 不支持 cursor，但返回 20 条
        data = self._trpc("search.query", {"q": str(key), "pageSize": 20})
        items = data if isinstance(data, list) else []
        return {
            "page": pg,
            "pagecount": pg,
            "limit": 20,
            "total": len(items),
            "list": [self._vod(x) for x in items],
            "parse": 0,
            "jx": 0
        }

    def playerContent(self, flag, id, vipFlags):
        if str(id).startswith("http"):
            return self._build_result(id)
        parts = str(id).split("|")
        if len(parts) >= 2:
            vid = parts[0].replace("dr_", "")
            seq = int(parts[1])
        else:
            vid = str(id).replace("dr_", "")
            seq = 1
        url = self._get_episode_url(vid, seq)
        return self._build_result(url)

    # ==================== 内部工具 ====================

    def _build_result(self, url):
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "jx": 0,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/zh",
                "Origin": self.host
            }
        }

    def _classes(self):
        if self.class_cache:
            return self.class_cache
        self.class_cache = [
            {"type_id": "recommend", "type_name": "推荐"},
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "rank", "type_name": "排行榜"},
            {"type_id": "SHORT_DRAMA", "type_name": "短剧"},
            {"type_id": "SERIES", "type_name": "长剧"},
            {"type_id": "MOVIE", "type_name": "电影"},
            {"type_id": "VARIETY", "type_name": "综艺"},
            {"type_id": "ANIME", "type_name": "动漫"},
        ]
        return self.class_cache

    def _filters(self, classes):
        fs = {
            "rank": [
                {
                    "key": "tab",
                    "name": "榜单",
                    "value": [
                        {"n": "热播", "v": "hot"},
                        {"n": "新剧", "v": "new"},
                        {"n": "追剧", "v": "follow"},
                        {"n": "分类", "v": "category"},
                        {"n": "豆瓣高分", "v": "douban"},
                    ]
                }
            ],
            "all": [
                {
                    "key": "order",
                    "name": "排序",
                    "value": [
                        {"n": "默认", "v": ""},
                        {"n": "最新", "v": "new"},
                        {"n": "最热", "v": "hot"},
                    ]
                },
                {
                    "key": "updateStatus",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ONGOING"},
                        {"n": "已完结", "v": "COMPLETED"},
                    ]
                }
            ],
        }
        for c in classes:
            tid = c["type_id"]
            if tid not in fs:
                fs[tid] = fs["all"]
        return fs

    def _vod(self, item):
        item = item or {}
        vid = str(item.get("id") or item.get("drama_id") or "")
        return {
            "vod_id": "dr_" + vid,
            "vod_name": item.get("title") or item.get("name") or vid,
            "vod_pic": self._pic(item),
            "vod_remarks": item.get("releaseStatus")
                           or (f"全{item.get('totalEpisodes')}集" if item.get("totalEpisodes") else "")
                           or (f"{item.get('playCount', 0)}热度" if item.get("playCount") else ""),
        }

    def _pic(self, item):
        return item.get("cover") or item.get("poster") or item.get("img") or ""

    def _kind_name(self, k):
        mapping = {
            "SHORT_DRAMA": "短剧",
            "SERIES": "长剧",
            "MOVIE": "电影",
            "VARIETY": "综艺",
            "ANIME": "动漫",
        }
        return mapping.get(k, k)

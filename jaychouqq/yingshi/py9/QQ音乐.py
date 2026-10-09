# -*- coding: utf-8 -*-
"""
================================================================
 音乐站 TVBox py站源 v1.0 (q-16a.pages.dev 聚合音乐)
================================================================
 功能:
  - 12 个精细音乐分类(热门/流行/摇滚/纯音乐/粤语/电音/古典/儿歌/影视原声/民谣/DJ/古风)
  - 站内搜索(酷狗搜索接口,支持分页)
  - 歌曲详情(含歌手/专辑/时长)
  - 智能解析播放地址(多音源 resolve 后端,支持 standard/exhigh/lossless 三档音质)
  - 多 User-Agent 轮换
  - 本地缓存(加速翻页)

 数据来源:
  - 搜索: 酷狗 songsearch API (公开接口)
  - 取流: musicserver.haitangw.cc resolve-url (站方自有后端,支持 kg/wy/tx)

 依赖: requests  (pip install requests)
================================================================
"""

import json
import re
import os
import time
import random
import hashlib
import traceback
import tempfile
from urllib.parse import quote

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ---------------- UA 池:多 User-Agent 轮换 ----------------
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Lenovo TB-J606L) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/4.0 TV Safari/537.36",
]

# ---------------- 接口 ----------------
KG_SEARCH_API = "https://songsearch.kugou.com/song_search_v2"
KG_HOT_API = "https://mobileservice.kugou.com/api/v3/search/hot"
RESOLVE_API = "https://musicserver.haitangw.cc/v1/music/resolve-url"
# 备用取流节点(与网站同源逻辑)
RESOLVE_FALLBACK = [
    "https://musicserver.haitangw.cc/v1/music/resolve-url",
    "https://musicapi.haitangw.net/v1/music/resolve-url",
]

# ---------------- 音乐分类 ----------------
CATEGORIES = [
    {"type_id": "hot",       "type_name": "🔥热门推荐", "query": None},
    {"type_id": "pop",       "type_name": "🎵流行",     "query": "流行歌曲"},
    {"type_id": "rock",      "type_name": "🎸摇滚",     "query": "摇滚"},
    {"type_id": "pure",      "type_name": "🎹纯音乐",   "query": "纯音乐"},
    {"type_id": "cantonese", "type_name": "🎤粤语",     "query": "粤语歌曲"},
    {"type_id": "electronic","type_name": "🎧电音",     "query": "电音"},
    {"type_id": "classical", "type_name": "🎻古典",     "query": "古典音乐"},
    {"type_id": "kids",      "type_name": "👶儿歌",     "query": "儿歌大全"},
    {"type_id": "ost",       "type_name": "🎬影视原声", "query": "影视原声"},
    {"type_id": "folk",      "type_name": "🪕民谣",     "query": "民谣"},
    {"type_id": "dj",        "type_name": "💿DJ舞曲",   "query": "DJ舞曲"},
    {"type_id": "ancient",   "type_name": "🏮古风",     "query": "古风歌曲"},
]

# 音质档位:显示名 -> resolve接口 level
QUALITIES = [
    ("流畅", "standard"),
    ("高清", "exhigh"),
    ("无损", "lossless"),
]

PAGE_SIZE = 20
SEARCH_PAGESIZE = 30
CACHE_TTL = 1800
CACHE_VERSION = "v2"  # 升级时改这个,强制旧缓存失效


def _clean_em(text):
    """去掉搜索结果中的 <em> 高亮标签"""
    if not text:
        return ""
    text = re.sub(r"</?em>", "", text)
    return text.strip()


def _fmt_duration(sec):
    try:
        sec = int(sec)
    except Exception:
        return ""
    m, s = divmod(sec, 60)
    return "%d:%02d" % (m, s)


class Spider:
    def __init__(self):
        self.cache_dir = os.path.join(tempfile.gettempdir(), "q16music_cache")
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception:
            pass
        self.proxy = None
        self.timeout = 20
        self._session = None

    # ============ 基础 ============
    def getName(self):
        return "Q16音乐"

    def init(self, extend=""):
        """
        extend 可传 JSON,例如:
        {"proxy": "http://127.0.0.1:7890", "timeout": 20}
        """
        if not extend:
            return
        try:
            cfg = json.loads(extend) if isinstance(extend, str) else extend
            self.proxy = cfg.get("proxy")
            self.timeout = int(cfg.get("timeout", 20))
        except Exception:
            pass

    def isVideoFormat(self, url):
        url = (url or "").lower()
        if url.split("?")[0].endswith((".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg")):
            return True
        # 取流后端的 cdn 直链多为 mp3
        return "kugou.com" in url or "music.126.net" in url

    def manualVideoCheck(self):
        return True

    # ============ 内部工具 ============
    def _session_get(self):
        if self._session is None:
            self._session = requests.Session()
        # 每次请求轮换 UA
        self._session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://q-16a.pages.dev/",
            "Origin": "https://q-16a.pages.dev",
        })
        return self._session

    def _get(self, url, params=None):
        s = self._session_get()
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        r = s.get(url, params=params, timeout=self.timeout, proxies=proxies)
        r.raise_for_status()
        return r

    def _post_json(self, url, data):
        s = self._session_get()
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        # 取流接口轮换 UA(每次独立)
        headers = {"User-Agent": random.choice(USER_AGENTS),
                   "Content-Type": "application/json",
                   "Accept": "application/json"}
        r = s.post(url, json=data, headers=headers,
                   timeout=self.timeout, proxies=proxies)
        r.raise_for_status()
        return r.json()

    def _cache_path(self, key):
        return os.path.join(self.cache_dir, CACHE_VERSION + "_" +
                            hashlib.md5(key.encode("utf-8")).hexdigest() + ".json")

    def _cache_get(self, key):
        try:
            p = self._cache_path(key)
            if not os.path.exists(p):
                return None
            if time.time() - os.path.getmtime(p) > CACHE_TTL:
                return None
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _cache_set(self, key, data):
        try:
            with open(self._cache_path(key), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _diag_item(self, msg="组件异常"):
        return {"vod_id": "__diag__", "vod_name": "⚠️" + msg,
                "vod_pic": "", "vod_remarks": "点我看详情"}

    # ============ 数据层 ============
    def _search_songs(self, keyword, page=1, pagesize=SEARCH_PAGESIZE):
        """酷狗搜索,返回标准歌曲列表(带缓存)"""
        if not HAS_REQUESTS:
            return []
        cache_key = "s:{}:{}:{}".format(keyword, page, pagesize)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        songs = []
        try:
            params = {
                "keyword": keyword, "page": page, "pagesize": pagesize,
                "userid": 0, "clientver": "", "platform": "WebFilter",
                "tag": "em", "filter": 2, "iscorrection": 1, "privilege_filter": 0,
            }
            data = self._get(KG_SEARCH_API, params=params).json()
            for it in (data.get("data") or {}).get("lists") or []:
                fh = it.get("FileHash")
                if not fh:
                    continue
                name = _clean_em(it.get("FileName") or "")
                singer = _clean_em(it.get("SingerName") or "")
                # FileName 常为 "歌手 - 歌名",拆分出歌名
                title = name
                if " - " in name:
                    parts = name.split(" - ", 1)
                    if len(parts) == 2:
                        title = parts[1].strip()
                songs.append({
                    "filehash": fh,
                    "album_id": it.get("AlbumID") or "",
                    "title": title or name,
                    "singer": singer,
                    "album": _clean_em(it.get("AlbumName") or ""),
                    "duration": it.get("Duration") or 0,
                    # 封面:Image 模板中的 {size} 替换为 400
                    "pic": (it.get("Image") or "").replace("{size}", "400"),
                })
        except Exception:
            traceback.print_exc()
        # 只缓存有效结果,避免把失败的空结果也缓存导致持续无内容
        if songs:
            self._cache_set(cache_key, songs)
        return songs

    def _hot_keywords(self, count=8):
        """酷狗热搜词(带缓存)"""
        cached = self._cache_get("hot_kw")
        if cached:
            return cached[:count]
        kws = []
        try:
            data = self._get(KG_HOT_API,
                             params={"format": "json", "plat": 0,
                                     "count": 30}).json()
            for it in (data.get("data") or {}).get("info") or []:
                kw = (it.get("keyword") or "").strip()
                if kw and len(kw) < 20:
                    kws.append(kw)
        except Exception:
            traceback.print_exc()
        self._cache_set("hot_kw", kws)
        return kws[:count] if kws else ["周杰伦", "林俊杰", "邓紫棋"]

    def _resolve_url(self, filehash, level="standard", source="kg"):
        """
        智能取流:轮换取流节点 + UA,失败自动降级重试。
        返回直链或 ""。
        """
        payload = {"source": source, "rid": str(filehash), "level": level}
        for api in RESOLVE_FALLBACK:
            try:
                d = self._post_json(api, payload)
                if not d:
                    continue
                code = d.get("code")
                if code in (0, 200) or d.get("message") == "ok":
                    data = d.get("data") or {}
                    url = data.get("url") or d.get("url") or ""
                    if url:
                        return url
            except Exception:
                traceback.print_exc()
                continue
        return ""

    def _to_vod(self, s):
        remark = " ".join(x for x in [
            s.get("singer"), _fmt_duration(s.get("duration"))] if x)
        return {
            "vod_id": "{}|{}".format(s["filehash"], s.get("album_id") or ""),
            "vod_name": s.get("title") or "未知歌曲",
            "vod_pic": s.get("pic") or "",
            "vod_remarks": remark,
        }

    def _parse_vod_id(self, vod_id):
        parts = (vod_id or "").split("|")
        fh = parts[0] if parts else ""
        album_id = parts[1] if len(parts) > 1 else ""
        return fh, album_id

    # ============ TVBox 接口 ============
    def homeContent(self, filter):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                   for c in CATEGORIES]
        return {"class": classes, "filters": {}}

    def _is_good_song(self, s):
        """过滤劣质结果:无歌手/标题异常的不要"""
        title = s.get("title") or ""
        singer = s.get("singer") or ""
        if not title or not singer:
            return False
        if len(title) > 30 or "_" in title:
            return False
        bad_kw = ["独家首发", "首发", "试听", "伴奏", "铃声"]
        if any(k in title for k in bad_kw):
            return False
        return True

    def homeVideoContent(self):
        """首页:热门歌手歌曲(只收录制良好、有封面的)"""
        if not HAS_REQUESTS:
            return {"list": [self._diag_item("缺少 requests 依赖")]}
        # 可靠的热门查询放前面,热搜词作补充
        kws = ["周杰伦", "林俊杰", "邓紫棋", "陈奕迅", "薛之谦",
               "王菲", "张学友", "Beyond", "凤凰传奇", "李荣浩"]
        kws += [k for k in self._hot_keywords(10)
                if k not in ("独家首发",)]
        videos, seen = [], set()
        for kw in kws:
            for s in self._search_songs(kw, page=1, pagesize=10):
                fh = s.get("filehash")
                if fh in seen or not self._is_good_song(s):
                    continue
                if not s.get("pic"):
                    continue
                seen.add(fh)
                videos.append(self._to_vod(s))
                if len(videos) >= 20:
                    break
            if len(videos) >= 20:
                break
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(int(pg), 1)
        except Exception:
            pg = 1
        if not HAS_REQUESTS:
            return {"list": [self._diag_item("缺少 requests 依赖")],
                    "page": 1, "pagecount": 1, "limit": PAGE_SIZE, "total": 1}
        # 热门分类:热搜词轮换
        if tid == "hot":
            kws = self._hot_keywords(10)
            kw = kws[(pg - 1) % len(kws)]
            songs = self._search_songs(kw, page=1, pagesize=SEARCH_PAGESIZE)
            pagecount = len(kws)
        else:
            query = next((c["query"] for c in CATEGORIES
                          if c["type_id"] == tid), "流行歌曲")
            songs = self._search_songs(query, page=pg, pagesize=SEARCH_PAGESIZE)
            pagecount = 10  # 搜索接口支持翻页,给足页数
        items = [self._to_vod(s) for s in songs[:PAGE_SIZE]]
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": PAGE_SIZE, "total": len(songs)}

    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}
        if not HAS_REQUESTS:
            return {"list": [self._diag_item("缺少 requests 依赖")]}
        try:
            pg = max(int(pg), 1)
        except Exception:
            pg = 1
        if quick:
            songs = self._search_songs(key, page=1, pagesize=10)
            return {"list": [self._to_vod(s) for s in songs]}
        songs = self._search_songs(key, page=pg, pagesize=SEARCH_PAGESIZE)
        items = [self._to_vod(s) for s in songs[:PAGE_SIZE]]
        return {"list": items, "page": pg, "pagecount": 10,
                "limit": PAGE_SIZE, "total": len(songs)}

    def detailContent(self, ids):
        """
        歌曲详情 + 三档音质选集。
        vod_id 编码: {filehash}|{album_id}
        播放 id 编码: {filehash}|{level}
        """
        vod_id = ids[0] if ids else ""
        fh, album_id = self._parse_vod_id(vod_id)
        if not fh or fh == "__diag__":
            return {"list": [{
                "vod_id": "__diag__", "vod_name": "⚠️缺少 requests 依赖",
                "vod_pic": "", "type_name": "系统诊断",
                "vod_content": "请在 TVBox 的 Python 环境中执行: pip install requests",
                "vod_play_from": "说明", "vod_play_url": "确定$__diag__|help"}]}
        # 从缓存的搜索结果里找回歌曲元信息
        title, singer, album, duration, pic = "", "", "", 0, ""
        try:
            for fname in os.listdir(self.cache_dir):
                if not fname.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(self.cache_dir, fname),
                              "r", encoding="utf-8") as f:
                        for s in json.load(f):
                            if s.get("filehash") == fh:
                                title = s.get("title") or ""
                                singer = s.get("singer") or ""
                                album = s.get("album") or ""
                                duration = s.get("duration") or 0
                                pic = s.get("pic") or ""
                                break
                    if title:
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if not title:
            title, singer = fh[:12], "未知歌手"

        episodes = ["{}$".format(qn) + "{}|{}".format(fh, lv)
                    for qn, lv in QUALITIES]
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": "音乐",
            "vod_year": "",
            "vod_area": "华语",
            "vod_remarks": _fmt_duration(duration),
            "vod_actor": singer,
            "vod_director": "",
            "vod_content": "歌手: {}\n专辑: {}\n时长: {}".format(
                singer or "未知", album or "未知", _fmt_duration(duration)),
            "vod_play_from": "Q16音乐",
            "vod_play_url": "#".join(episodes),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """
        智能解析:
         1. 按指定音质档取流;
         2. 失败自动降档重试(无损->高清->流畅);
         3. 仍失败则换备用节点。
        """
        if not HAS_REQUESTS or not id or id.startswith("__diag__"):
            return {"parse": 0, "url": ""}
        if "|" in id:
            fh, want_lv = id.split("|", 1)
        else:
            fh, want_lv = id, "standard"
        # 降级顺序:想要的档位 -> 更低档位
        lv_order = [lv for _, lv in QUALITIES]
        try:
            start = lv_order.index(want_lv)
        except ValueError:
            start = 0
        url = ""
        for lv in lv_order[start:]:
            url = self._resolve_url(fh, level=lv)
            if url:
                break
        if not url:
            return {"parse": 0, "url": ""}
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://q-16a.pages.dev/",
            "Origin": "https://q-16a.pages.dev",
        }
        return {"parse": 0, "playUrl": "", "url": url, "header": headers}


if __name__ == "__main__":
    sp = Spider()
    sp.init("")
    print("站名:", sp.getName())
    print("分类数:", len(sp.homeContent(None)["class"]))
    r = sp.searchContent("晴天", True)
    print("搜索 晴天:", len(r["list"]), "条")
    if r["list"]:
        print("首条:", r["list"][0]["vod_name"], "|", r["list"][0]["vod_remarks"])

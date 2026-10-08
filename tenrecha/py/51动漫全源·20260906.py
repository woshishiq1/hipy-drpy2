# -*- coding: utf-8 -*-
# 51dm（无翼鸟/51动漫）T4 全分区视频源 — awXVideo/butterfly SDK 家族
# 逆向要点：
#  - 配置: GET /api/app/ping/config -> data.domain[{urls,type}] + homeCategory/shortCategory/comicsCategory/
#    cartoonCategory/novelCategory/liveCategory/photoCategory/pornGameCategory 全分类
#  - 游客登录: POST /api/app/login/guest {"DevID"} -> token(JWT)
#  - 长视频: /media/home + /media/play + /media/m3u8/{videoUrl}?token=&line=1/2/3 (三线路)
#  - 短视频: /media/short/hot(需token) + 同上播放
#  - 漫画: /comics/home(topic嵌套) + /comics/detail + /comics/chapter + /comicsChapter/pics(章节图)
#  - 里番: /comicsvideo/home + /comicsvideo/details{videoId} + 同漫画章节
#  - 小说: /novel/home + /novel/detail(desc正文开头, 章节全VIP游客6164)
#  - 直播: /live/home -> list[].stream(直连m3u8)
#  - 写真: /photo/list + /photo/detail -> pictures[]
#  - 色游: /porngame/list + /porngame/detail -> url(下载链接)
#  - 图片: 前100字节 XOR "2019ysapp7527" (WebP), localProxy 回传
import base64
import json
import random
import threading
import time
import urllib.parse
import urllib.request

try:
    from base.spider import Spider
except Exception:
    Spider = object

BASE = "https://dcnmzzpl7qfr2.cloudfront.net"
XOR_KEY = b"2019ysapp7527"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"

# kind -> (分类名前缀, 分类配置键)
KIND_LABEL = {
    "video": "视频", "short": "短视频", "comic": "里番",
    "live": "直播", "photo": "写真", "game": "色游",
}
CONFIG_KEY = {
    "video": "homeCategory", "short": "shortCategory",
    "comic": "cartoonCategory", "live": "liveCategory",
    "photo": "photoCategory", "game": "pornGameCategory",
}


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self._token = None
        self._cfg = None
        self._cfg_ts = 0
        self._live = {}       # liveId -> stream
        self._lock = threading.Lock()

    # ---------- 基础 ----------
    def _post(self, path, body=None, auth=True, retries=2):
        url = BASE + path
        h = {"User-Agent": UA, "Content-Type": "application/json", "Referer": BASE + "/"}
        if auth and self._token:
            h["Authorization"] = self._token
        data = json.dumps(body or {}).encode()
        for i in range(retries):
            try:
                req = urllib.request.Request(url, data=data, headers=h, method="POST")
                with urllib.request.urlopen(req, timeout=15) as r:
                    j = json.loads(r.read().decode("utf-8", "replace"))
                if isinstance(j, dict) and j.get("code") == 200:
                    return j.get("data")
                return j.get("data") if isinstance(j, dict) else None
            except Exception:
                time.sleep(0.3)
        return None

    def _get_raw(self, url, retries=2):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
        for i in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read()
            except Exception:
                time.sleep(0.3)
        return None

    def _get_config(self):
        if self._cfg and time.time() - self._cfg_ts < 600:
            return self._cfg
        try:
            req = urllib.request.Request(BASE + "/api/app/ping/config", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            d = j.get("data") if isinstance(j, dict) else None
            if d:
                self._cfg = d
                self._cfg_ts = time.time()
        except Exception:
            pass
        return self._cfg

    def _login(self):
        if self._token:
            return self._token
        devid = "h5_" + _g() + "_" + _g()[:4] + "_" + _g()[:4] + "_" + _g()[:4] + "_" + _g()
        d = self._post("/api/app/login/guest", {"DevID": devid}, auth=False)
        if d and d.get("token"):
            self._token = d["token"]
        return self._token

    def _img_domain(self):
        cfg = self._get_config()
        if cfg and isinstance(cfg.get("domain"), list):
            for it in cfg["domain"]:
                if it.get("type") == "IMAGE" and it.get("urls"):
                    return it["urls"][0].rstrip("/") + "/"
        return "https://sy02iz33.eygmso.cn/"

    def _img_bytes(self, rel):
        url = self._img_domain() + str(rel).lstrip("/")
        raw = self._get_raw(url)
        if raw:
            b = bytearray(raw)
            for i in range(min(100, len(b))):
                b[i] ^= XOR_KEY[i % len(XOR_KEY)]
            return bytes(b)
        return None

    def _pic(self, rel):
        if not rel:
            return ""
        return self.getProxyUrl() + "&ac=pic&path=" + urllib.parse.quote("img:" + str(rel))

    # ---------- 类型路由 ----------
    @staticmethod
    def _kind_of(tid):
        return str(tid).split(":", 1)[0] if ":" in str(tid) else "video"

    @staticmethod
    def _cid_of(tid):
        return str(tid).split(":", 1)[1] if ":" in str(tid) else str(tid)

    def getName(self):
        return "51动漫全源·20260906"

    def init(self, extend=""):
        self._get_config()
        self._login()
        return "51动漫·视频/漫画/小说/直播/写真/色游"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".ts" in url or "/m3u8/" in url

    def manualVideoCheck(self):
        return True

    # ---------- 首页 ----------
    def homeContent(self, filter):
        self._get_config()
        classes = []
        for kind, ckey in CONFIG_KEY.items():
            arr = (self._cfg or {}).get(ckey) or []
            for c in arr:
                cid = c.get("id")
                name = c.get("name")
                if cid is not None and name:
                    label = name if kind == "video" else KIND_LABEL[kind] + "·" + name
                    classes.append({"type_name": label, "type_id": kind + ":" + str(cid)})
        vlist = []
        try:
            d = self._post("/api/app/media/home", {"id": 123401, "pageNum": 1, "pageSize": 20}, auth=False)
            for v in (d or {}).get("mediaList") or []:
                it = self._vod_media(v, "video")
                if it:
                    vlist.append(it)
        except Exception:
            pass
        return {"class": classes, "list": vlist, "filters": {}}

    # ---------- 列表 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg or 1))
        kind = self._kind_of(tid)
        cid = self._cid_of(tid)
        if kind in ("video", "short"):
            path = "/api/app/media/home" if kind == "video" else "/api/app/media/short/hot"
            d = self._post(path, {"id": int(cid), "pageNum": pg, "pageSize": 30}, auth=(kind == "short"))
            arr = (d or {}).get("mediaList") or []
            return {"page": pg, "pagecount": pg + 1, "list": [self._vod_media(v, kind) for v in arr if self._vod_media(v, kind)]}
        if kind == "comic":
            d = self._post("/api/app/comicsvideo/home", {"id": int(cid), "pageNum": pg, "pageSize": 30})
            arr = (d or {}).get("comicsList") or []
            return {"page": pg, "pagecount": pg + 1, "list": [self._vod_comic(v) for v in arr if self._vod_comic(v)]}
        if kind == "live":
            d = self._post("/api/app/live/home", {"id": int(cid), "pageNum": pg, "pageSize": 30})
            arr = (d or {}).get("list") or []
            out = []
            for v in arr:
                it = self._vod_live(v)
                if it:
                    out.append(it)
            return {"page": pg, "pagecount": pg + 1, "list": out}
        if kind == "photo":
            d = self._post("/api/app/photo/list", {"id": int(cid), "pageNum": pg, "pageSize": 30})
            arr = (d or {}).get("list") or []
            return {"page": pg, "pagecount": pg + 1, "list": [self._vod_photo(v) for v in arr if self._vod_photo(v)]}
        if kind == "game":
            d = self._post("/api/app/porngame/list", {"id": int(cid), "pageNum": pg, "pageSize": 30})
            arr = (d or {}).get("list") or []
            return {"page": pg, "pagecount": pg + 1, "list": [self._vod_game(v) for v in arr if self._vod_game(v)]}
        return {"page": pg, "pagecount": 1, "list": []}

    # ---------- 各类列表项 ----------
    def _vod_media(self, v, kind):
        vid = v.get("id")
        if vid is None:
            return None
        pay = v.get("payType") or 0
        pt = v.get("playTime") or 0
        remark = ("VIP" if pay == 1 else ("金币" if pay == 2 else "免费"))
        if pt:
            remark += "·{}秒".format(pt)
        return {"vod_id": kind + ":" + str(vid), "vod_name": v.get("title") or "",
                "vod_pic": self._pic(v.get("coverImg")), "vod_remarks": remark}

    def _vod_comic(self, v):
        vid = v.get("videoId") or v.get("id")
        if vid is None:
            return None
        pay = v.get("comicsPayType") or 0
        remark = ("VIP" if pay == 1 else ("金币" if pay == 2 else "免费")) + "·{}话".format(v.get("chapterNum") or v.get("newChapter") or 0)
        return {"vod_id": "comic:" + str(vid), "vod_name": v.get("title") or "",
                "vod_pic": self._pic(v.get("coverImg")), "vod_remarks": remark}

    def _vod_live(self, v):
        lid = v.get("id")
        if lid is None:
            return None
        st = v.get("stream") or ""
        if st:
            self._live[str(lid)] = st
        return {"vod_id": "live:" + str(lid), "vod_name": v.get("username") or "",
                "vod_pic": v.get("snapshot") or v.get("avatarUrl") or "",
                "vod_remarks": "{}人观看".format(v.get("viewersCount") or 0)}

    def _vod_photo(self, v):
        pid = v.get("id")
        if pid is None:
            return None
        return {"vod_id": "photo:" + str(pid), "vod_name": v.get("name") or "",
                "vod_pic": self._pic(v.get("cover")), "vod_remarks": ("VIP" if v.get("isVip") else "免费")}

    def _vod_game(self, v):
        gid = v.get("id")
        if gid is None:
            return None
        return {"vod_id": "game:" + str(gid), "vod_name": v.get("title") or "",
                "vod_pic": "", "vod_remarks": v.get("format") or "游戏"}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        self._login()
        vid = str(ids[0])
        kind = self._kind_of(vid)
        rid = self._cid_of(vid)
        if kind in ("video", "short"):
            return self._detail_media(rid, kind)
        if kind == "comic":
            return self._detail_comic(rid)
        if kind == "live":
            return self._detail_live(rid)
        if kind == "photo":
            return self._detail_photo(rid)
        if kind == "game":
            return self._detail_game(rid)
        return {"list": []}

    def _detail_media(self, rid, kind):
        d = self._post("/api/app/media/play", {"id": int(rid)})
        if not d:
            return {"list": []}
        mi = d.get("mediaInfo") or {}
        pay = mi.get("payType") or 0
        pt = mi.get("playTime") or 0
        tags = ",".join([t.get("name", "") for t in (mi.get("tagInfoList") or []) if t.get("name")])
        pub = (mi.get("publisher") or {}).get("name") or ""
        remark = "VIP" if pay == 1 else ("金币" if pay == 2 else "免费")
        vu = mi.get("videoUrl") or ""
        # 三条线路
        plays = []
        if vu:
            for line in (1, 2, 3):
                plays.append(self._m3u8_url(vu, line))
        vod = {
            "vod_id": kind + ":" + str(mi.get("id") or rid),
            "vod_name": mi.get("title") or "",
            "vod_pic": self._pic(mi.get("coverImg")),
            "vod_year": (mi.get("addedTime") or "")[:4] or "2026",
            "vod_remarks": remark,
            "vod_content": "演员:{} · 标签:{} · 时长:{}秒 · 点赞:{}".format(pub, tags or "-", pt, mi.get("likes") or 0),
            "type_name": "视频" if kind == "video" else "短视频",
            "vod_play_from": "线路一$$$线路二$$$海外线路",
            "vod_play_url": "$$$".join(["正片$" + p for p in plays]),
        }
        return {"list": [vod]}

    def _m3u8_url(self, vu, line=1):
        return BASE + "/api/app/media/m3u8/" + urllib.parse.quote(vu, safe="") + "?token=" + urllib.parse.quote(self._token or "") + "&line=" + str(line)

    def _detail_comic(self, rid):
        d = self._post("/api/app/comicsvideo/details", {"videoId": int(rid)})
        data = (d or {}).get("comicsData") or {}
        comic_id = data.get("id") or rid
        if not data:
            return {"list": []}
        ch = self._post("/api/app/comics/chapter", {"id": int(comic_id)})
        chlist = (ch or {}).get("chapterList") or []
        pay = data.get("comicsPayType") or 0
        remark = "VIP" if pay == 1 else ("金币" if pay == 2 else "免费")
        eps = []
        for c in chlist:
            cid = c.get("id")
            n = c.get("chapterNum") or len(eps) + 1
            if cid is not None:
                eps.append("第{}话${}".format(n, cid))
        vod = {
            "vod_id": "comic:" + str(comic_id),
            "vod_name": data.get("title") or "",
            "vod_pic": self._pic(data.get("coverImg")),
            "vod_remarks": remark + "·{}话".format(data.get("chapterNum") or 0),
            "vod_content": "作者:{} · 标签:{}".format(",".join(data.get("author") or []), ",".join([t.get("name", "") for t in (data.get("tags") or [])]) or "-"),
            "type_name": "里番",
            "vod_play_from": "里番",
            "vod_play_url": "#".join(eps) if eps else "",
        }
        return {"list": [vod]}

    def _detail_live(self, rid):
        st = self._live.get(rid)
        if not st:
            d = self._post("/api/app/live/home", {"id": 10041, "pageNum": 1, "pageSize": 50})
            for v in (d or {}).get("list") or []:
                if str(v.get("id")) == str(rid) and v.get("stream"):
                    st = v["stream"]
                    self._live[rid] = st
                    break
        name = rid
        vod = {
            "vod_id": "live:" + str(rid),
            "vod_name": "直播间" + str(rid),
            "vod_pic": "",
            "vod_remarks": "直播",
            "type_name": "直播",
            "vod_play_from": "直播",
            "vod_play_url": "直播$" + (st or ""),
        }
        return {"list": [vod]}

    def _detail_photo(self, rid):
        d = self._post("/api/app/photo/detail", {"id": int(rid)})
        if not d:
            return {"list": []}
        pics = d.get("pictures") or []
        urls = "&&".join([self._pic(p) for p in pics if p])
        vod = {
            "vod_id": "photo:" + str(d.get("id") or rid),
            "vod_name": d.get("name") or "",
            "vod_pic": self._pic(d.get("cover")),
            "vod_remarks": ("VIP" if d.get("isVip") else "免费") + "·{}P".format(len(pics)),
            "vod_content": d.get("desc") or "",
            "type_name": "写真",
            "vod_play_from": "写真",
            "vod_play_url": "写真$" + urls,
        }
        return {"list": [vod]}

    def _detail_game(self, rid):
        d = self._post("/api/app/porngame/detail", {"id": int(rid)})
        if not d:
            return {"list": []}
        url = d.get("url") or ""
        vod = {
            "vod_id": "game:" + str(d.get("id") or rid),
            "vod_name": d.get("title") or "",
            "vod_pic": "",
            "vod_remarks": "下载",
            "vod_content": (d.get("manual") or d.get("desc") or "")[:500],
            "type_name": "色游",
            "vod_play_from": "下载",
            "vod_play_url": "下载$" + url,
        }
        return {"list": [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg=1):
        self._login()
        pg = max(1, int(pg))
        out = []
        for mt, parser in ((1, lambda v: self._vod_media(v, "video")),
                           (6, lambda v: self._vod_photo(v))):
            d = self._post("/api/app/search/details", {"mediaType": mt, "keyword": key, "pageNum": pg, "pageSize": 20})
            arr = None
            if d:
                arr = d.get("mediaList") or d.get("photoList")
            for v in arr or []:
                it = parser(v)
                if it:
                    out.append(it)
        return {"list": out}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        self._login()
        pid = str(id or "")
        header = {"User-Agent": UA, "Referer": BASE + "/"}
        # 漫画章节 -> pics
        if pid.isdigit() and flag == "漫画":
            ch = self._post("/api/app/comicsChapter/pics", {"id": int(pid)})
            pics = (ch or {}).get("chapter") or []
            urls = "&&".join([self._pic(p.get("comicsPic")) for p in pics if p.get("comicsPic")])
            return {"parse": 0, "playUrl": "type=manga", "url": "pics://" + urls}
        # 写真 -> pics
        if flag == "写真":
            urls = pid  # detailContent 已拼好 pics 列表
            if urls.startswith("pics://"):
                return {"parse": 0, "playUrl": "type=manga", "url": urls}
            return {"parse": 0, "playUrl": "type=manga", "url": "pics://" + urls}
        # 直播/视频 -> m3u8
        if pid.startswith("http"):
            return {"parse": 0, "playUrl": "", "url": pid, "header": header}
        # 视频 vod_id 兜底
        if ":" in pid and pid.split(":", 1)[0] in ("video", "short"):
            rid = pid.split(":", 1)[1]
            d = self._post("/api/app/media/play", {"id": int(rid)})
            vu = ((d or {}).get("mediaInfo") or {}).get("videoUrl") or ""
            if vu:
                return {"parse": 0, "playUrl": "", "url": self._m3u8_url(vu, 1), "header": header}
        return {"parse": 0, "playUrl": "", "url": pid, "header": header}

    # ---------- 图片代理 ----------
    def localProxy(self, param):
        p = param
        if isinstance(p, str):
            try:
                p = json.loads(p) if p.strip().startswith("{") else urllib.parse.parse_qs(p)
            except Exception:
                p = {}
        ac = path = ""
        if isinstance(p, dict):
            ac = p.get("ac") or ""
            path = p.get("path") or ""
        else:
            ac = (p.get("ac") or [""])[0]
            path = (p.get("path") or [""])[0]
        if ac != "pic":
            return [404, "text/plain", b""]
        if not str(path).startswith("img:"):
            path = urllib.parse.unquote(str(path))
        if not str(path).startswith("img:"):
            return [404, "text/plain", b""]
        data = self._img_bytes(str(path)[4:])
        if not data:
            return [404, "text/plain", b""]
        mime = "image/jpeg"
        if data[:4] == b"\x89PNG":
            mime = "image/png"
        elif data[:3] == b"GIF":
            mime = "image/gif"
        elif data[:4] == b"RIFF":
            mime = "image/webp"
        return [200, mime, data]


def _g():
    return hex(random.randint(0, 2 ** 32 - 1))[2:].zfill(8)

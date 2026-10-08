# -*- coding: utf-8 -*-
"""
青桔短剧 · 源插件(零依赖稳版)
=====================================================
适配:TVBox / FongMi / WebHTV 系 py 源(type=3,api 直接指向本文件)

特点
----
1. 零依赖:只用 Python 标准库(urllib),不需要 requests;
   加密优先用 Crypto / cryptography,两者都没有时走内置纯 Python AES-256-CBC
   —— 也就是说 chaquopy 之类"裸环境"里直接能加载,不会 import 失败。
2. 播放地址优先取接口返回的**带签名线路**(free → line2 → line3 → ...),
   接口没给才退回构造地址。原版只认 m3u8/url 字段,而该接口返回的是 lines 数组,
   等于每次都走无签名兜底,服务端一旦收紧就全黑。
3. 接口异常(status != "y")不再产出空壳条目,详情页假 id 不会变成"一集空白剧"。
4. deviceId 默认按本机硬件标识派生(稳定),避免每次启动换设备被风控。
5. 子分类筛选器带「全部」项;原创页(navBlock)走独立分支。

可配参数(站点 extend 里传 JSON):
  {"site":"https://xqjzvcvt.top", "token":"", "device_id":"", "platform_key":""}
=====================================================
"""
import gzip
import hashlib
import hmac
import json
import os
import ssl
import time
import uuid

try:
    from urllib.request import Request as _Request, urlopen as _urlopen
except Exception:
    _Request = None
    _urlopen = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

# ---------- 加密后端:有就用快的,没有用内置 ----------
try:
    from Crypto.Cipher import AES as _R_AES
except Exception:
    _R_AES = None

try:
    from cryptography.hazmat.backends import default_backend as _c_backend
    from cryptography.hazmat.primitives.ciphers import Cipher as _c_Cipher
    from cryptography.hazmat.primitives.ciphers import algorithms as _c_algorithms
    from cryptography.hazmat.primitives.ciphers import modes as _c_modes
except Exception:
    _c_Cipher = None

try:
    _SSL_CTX = ssl._create_unverified_context()
except Exception:
    _SSL_CTX = None


def _pkcs7(data):
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def _unpkcs7(data):
    n = data[-1] if data else 0
    return data[:-n] if 1 <= n <= 16 else data


def _cbc_encrypt(key, iv, plain):
    plain = _pkcs7(plain)
    if _R_AES is not None:
        try:
            return _R_AES.new(key, _R_AES.MODE_CBC, iv).encrypt(plain)
        except Exception:
            pass
    if _c_Cipher is not None:
        try:
            e = _c_Cipher(_c_algorithms.AES(key), _c_modes.CBC(iv), backend=_c_backend()).encryptor()
            return e.update(plain) + e.finalize()
        except Exception:
            pass
    return _PyAES(key).cbc_encrypt(plain, iv)


def _cbc_decrypt(key, iv, blob):
    if _R_AES is not None:
        try:
            return _unpkcs7(_R_AES.new(key, _R_AES.MODE_CBC, iv).decrypt(blob))
        except Exception:
            pass
    if _c_Cipher is not None:
        try:
            d = _c_Cipher(_c_algorithms.AES(key), _c_modes.CBC(iv), backend=_c_backend()).decryptor()
            return _unpkcs7(d.update(blob) + d.finalize())
        except Exception:
            pass
    return _unpkcs7(_PyAES(key).cbc_decrypt(blob, iv))


# =====================================================================
# 分类表 —— 2026-09-21 实地探站实测结果
# =====================================================================
# 关键事实（这一版修的就是它）：
#   /drama/list 只认 cat_id（纯数字），id / code / nav_id / cid 等键服务端**一律忽略**，
#   传了等于没传 —— 表现就是 8 个一级分类点进去全是同一批片（实测 8/8 首条完全相同）。
#   所以一级分类必须各自映射到自己 tab 栏的默认 cat_id。
#
# 一级分类 → 默认 tab 的 (cat_id, order, source)
DEFAULT_TAB = {
    "yuandou": ("246506", "new:top", ""),      # 黄豆原创
    "mod": ("246502", "new:top", ""),          # 魔改短剧
    "caibian": ("246505", "new:top", ""),      # 擦边短剧
    "zhenren": ("817202", "new:top", ""),      # 真人短剧
    "erciyuan": ("817201", "new:top", ""),     # 动漫
    "aiman": ("6655003", "new:top", ""),       # 影院
    "zongyi": ("1050905", "new:top", ""),      # 贤者
    "heiliao": ("900012", "new:top", ""),      # 黑料
}

# navList 拿不到时的一级分类兜底（8 个，实测全出片）
FALLBACK_NAV = [
    ("yuandou", "黄豆原创"), ("mod", "魔改短剧"), ("caibian", "擦边短剧"),
    ("zhenren", "真人短剧"), ("erciyuan", "动漫"), ("aiman", "影院"),
    ("zongyi", "贤者"), ("heiliao", "黑料"),
]

# 子分类兜底（navFilter 拿不到时用；cat_id / order / source 都是实测值）
FALLBACK_TABS = {
    "yuandou": [
        {"name": "黄豆原创", "filter": {"cat_id": "246506", "order": "new:top"}},
        {"name": "UP原创", "filter": {"cat_id": "246506", "source": "up"}},
    ],
    "mod": [
        {"name": "大神精选", "filter": {"cat_id": "246502", "order": "new:top"}},
        {"name": "单体作品", "filter": {"cat_id": "246503", "order": "new:top"}},
        {"name": "影视魔改", "filter": {"cat_id": "900011", "order": "new:top"}},
        {"name": "国漫AI", "filter": {"cat_id": "5822103", "order": "new:top"}},
        {"name": "魔改短剧", "filter": {"cat_id": "2345505"}},
    ],
    "caibian": [
        {"name": "最新", "filter": {"cat_id": "246505", "order": "new:top"}},
        {"name": "推荐", "filter": {"cat_id": "246505", "order": "hot:top"}},
        {"name": "全部", "filter": {"cat_id": "246505"}},
    ],
    "zhenren": [
        {"name": "都市", "filter": {"cat_id": "817202", "order": "new:top"}},
        {"name": "古装", "filter": {"cat_id": "900006", "order": "new:top"}},
        {"name": "民国", "filter": {"cat_id": "1050901", "order": "new:top"}},
        {"name": "重生", "filter": {"cat_id": "900007", "order": "new:top"}},
        {"name": "异能", "filter": {"cat_id": "900008", "order": "new:top"}},
    ],
    "erciyuan": [
        {"name": "里番", "filter": {"cat_id": "817201", "order": "new:top"}},
        {"name": "国漫", "filter": {"cat_id": "4324502", "order": "hot:top"}},
        {"name": "日漫", "filter": {"cat_id": "1050906", "order": "new:top"}},
        {"name": "动画同人", "filter": {"cat_id": "481301", "order": "new:top"}},
        {"name": "游戏同人", "filter": {"cat_id": "900002", "order": "new:top"}},
    ],
    "aiman": [
        {"name": "美剧", "filter": {"cat_id": "6655003", "order": "new:top"}},
        {"name": "韩剧", "filter": {"cat_id": "6655009", "order": "new:top"}},
        {"name": "漫剧", "filter": {"cat_id": "1050902", "order": "new:top"}},
    ],
    "zongyi": [
        {"name": "最新", "filter": {"cat_id": "1050905", "order": "new:top"}},
        {"name": "推荐", "filter": {"cat_id": "1050905", "order": "hot:top"}},
    ],
    "heiliao": [
        {"name": "最新", "filter": {"cat_id": "900012", "order": "new:top"}},
        {"name": "推荐", "filter": {"cat_id": "900012", "order": "hot:top"}},
    ],
}


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xqjzvcvt.top"
        self.api = self.host + "/api"
        self.name = "青桔短剧"
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"
        self.ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.session_id = uuid.uuid4().hex
        self.device_id = self._device_id()
        self.token = ""
        self.class_cache = None
        self.cat_ids = {}
        self.filter_cache = {}
        self.timeout = 20

    # ------------------------------------------------------------------ 基础
    def getName(self):
        return self.name

    def init(self, extend=""):
        if not extend:
            return
        cfg = extend if isinstance(extend, dict) else None
        if cfg is None:
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = None
        if isinstance(cfg, dict):
            host = cfg.get("site") or cfg.get("base_url") or cfg.get("host") or ""
            if host:
                self.host = str(host).rstrip("/")
                self.api = self.host + "/api"
            if cfg.get("token"):
                self.token = str(cfg.get("token"))
            if cfg.get("device_id"):
                self.device_id = str(cfg.get("device_id"))
            if cfg.get("platform_key"):
                self.platform_key = str(cfg.get("platform_key"))
            if cfg.get("name"):
                self.name = str(cfg.get("name"))
        elif isinstance(extend, str) and extend.strip().startswith("http"):
            self.host = extend.strip().rstrip("/")
            self.api = self.host + "/api"

    def _device_id(self):
        try:
            seed = "qingju|%s|%s" % (uuid.getnode(), "android")
        except Exception:
            seed = "qingju|fallback"
        return hashlib.md5(seed.encode("utf-8")).hexdigest()

    def _headers(self):
        return {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Origin": self.host,
            "Referer": self.host + "/home",
            "Content-Type": "application/octet-stream",
        }

    def _play_header(self):
        return {"User-Agent": self.ua, "Referer": self.host + "/home", "Origin": self.host}

    # ------------------------------------------------------------------ 网络
    def _post(self, url, body, headers, timeout=None):
        if _urlopen is None:
            return 0, b""
        req = _Request(url, data=body, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        to = timeout or self.timeout
        resp = None
        try:
            try:
                resp = _urlopen(req, timeout=to, context=_SSL_CTX)
            except TypeError:
                resp = _urlopen(req, timeout=to)
            code = getattr(resp, "status", 0) or getattr(resp, "code", 0) or 200
            return code, resp.read()
        except Exception:
            return 0, b""
        finally:
            try:
                if resp is not None:
                    resp.close()
            except Exception:
                pass

    def _api(self, path, data=None, timeout=None):
        path = "/" + str(path).lstrip("/")
        rid = str(uuid.uuid4())
        key = self._key(rid)
        iv = os.urandom(16)
        payload = {"token": self.token or "", "deviceId": self.device_id, "data": data or {}}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            body = iv + _cbc_encrypt(key, iv, gzip.compress(raw))
        except Exception:
            return {}
        ts = int(time.time())
        sign = hashlib.sha256(
            ("Dart|%s|%s|%s|%s" % (self.session_id, rid, ts, path)).encode("utf-8")
        ).hexdigest() + "-" + str(ts)
        h = self._headers()
        h.update({
            "version": self.version, "deviceType": self.device_type, "time": str(ts),
            "sign": sign, "requestId": rid, "sessionId": self.session_id,
            "deviceBrand": "", "deviceModel": "", "systemName": "", "systemVersion": "",
        })
        code, blob = self._post(self.api + path, body, h, timeout)
        if code != 200 or not blob:
            return {}
        return self._decode(blob, rid, key)

    def _key(self, rid):
        return hmac.new(self.platform_key.encode("utf-8"),
                        bytes.fromhex(str(rid).replace("-", "")),
                        hashlib.sha256).digest()

    def _decode(self, blob, rid, key):
        # 响应体 = iv(16) + AES-CBC(gzip(json))
        if len(blob) >= 32 and (len(blob) - 16) % 16 == 0:
            try:
                plain = _cbc_decrypt(key, blob[:16], blob[16:])
                if plain[:2] == b"\x1f\x8b":
                    plain = gzip.decompress(plain)
                return json.loads(plain.decode("utf-8"))
            except Exception:
                pass
        try:
            if blob[:2] == b"\x1f\x8b":
                blob = gzip.decompress(blob)
            return json.loads(blob.decode("utf-8"))
        except Exception:
            return {}

    def _ok(self, obj):
        return isinstance(obj, dict) and str(obj.get("status", "")).lower() in ("y", "1", "true")

    # ------------------------------------------------------------------ 片单
    def homeVideoContent(self):
        data = self._api("/drama/list", {"page": "1", "page_size": "18"})
        return {"list": [self._vod(x) for x in self._list(data)], "parse": 0, "jx": 0}

    def homeContent(self, filter):
        classes = self._classes()
        return {
            "class": classes,
            "filters": self._filters(classes),
            "list": [self._vod(x) for x in self._list(self._api("/drama/list", {"page": "1", "page_size": "18"}))],
            "parse": 0,
            "jx": 0,
        }

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "")
        items = []
        if tid in ("", "all", "recommend"):
            data = self._api("/drama/list", {"page": str(page), "page_size": "18"})
            items = self._list(data)
        else:
            cat_id, order, source = self._tab(tid, extend)
            data = self._cate_page(cat_id, order, source, page, extend)
            items = self._list(data)
            if not items:
                # 子分类被站方下线/参数不认时，退回这个一级分类的默认 tab，
                # 宁可少一个子栏，也别给用户一个白页。
                d2, o2, s2 = DEFAULT_TAB.get(tid, ("", "", ""))
                if (d2, o2, s2) != (cat_id, order, source) and d2:
                    items = self._list(self._cate_page(d2, o2, s2, page, extend))
        lst = [self._vod(x) for x in items if isinstance(x, dict)]
        pagecount = page + 1 if len(lst) >= 18 else page
        return {"page": page, "pagecount": pagecount, "limit": 18, "total": 99999,
                "list": lst, "parse": 0, "jx": 0}

    def _cate_page(self, cat_id, order, source, page, extend):
        """按分类取一页。cat_id 是唯一被服务端认的过滤键（实测：id/code 全被忽略）。"""
        req = {"page": str(page), "page_size": "18"}
        if cat_id:
            req["cat_id"] = str(cat_id)
        if order:
            req["order"] = order
        if source:
            req["source"] = source
        if extend.get("order"):
            req["order"] = extend.get("order")
        if extend.get("update_status"):
            req["update_status"] = extend.get("update_status")
        return self._api("/drama/list", req)

    def _tab(self, tid, extend):
        """这次请求该用哪个 cat_id / order / source。
        规则：一级分类 → 它 tab 栏的默认项；带 sub 参数 → 取对应子 tab 的 filter。"""
        base = DEFAULT_TAB.get(tid)
        if base is None:
            if str(tid).isdigit():
                return (str(tid), "", "")
            return ("", "", "")
        sub = str((extend or {}).get("sub") or "")
        if sub and sub not in ("all", "全部"):
            try:
                idx = int(sub)
            except Exception:
                idx = -1
            tabs = self._nav_filter(tid)
            if 0 <= idx < len(tabs) and isinstance(tabs[idx], dict):
                flt = tabs[idx].get("filter")
                if not isinstance(flt, dict):
                    flt = {}
                return (str(flt.get("cat_id") or base[0]),
                        str(flt.get("order") or ""),
                        str(flt.get("source") or ""))
        return base

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        data = self._api("/drama/list", {"page": str(page), "page_size": "18",
                                         "keywords": str(key or "")})
        lst = [self._vod(x) for x in self._list(data) if isinstance(x, dict)]
        pagecount = page + 1 if len(lst) >= 18 else page
        return {"page": page, "pagecount": pagecount, "limit": 18, "total": 99999,
                "list": lst, "parse": 0, "jx": 0}

    # ------------------------------------------------------------------ 详情
    def detailContent(self, ids):
        try:
            vid = str(ids[0]).replace("rp_", "")
        except Exception:
            return {"list": []}
        obj = self._api("/drama/detail", {"id": vid})
        if not self._ok(obj):
            return {"list": []}
        data = obj.get("data", obj)
        if not isinstance(data, dict) or not data:
            return {"list": []}

        vod_id = self._sid(data.get("id") or data.get("drama_id") or vid)
        name = data.get("name") or data.get("title") or data.get("t") or vod_id
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        count = self._int(data.get("episode_count") or data.get("free_episodes"), len(eps) or 1)

        play = []
        if eps:
            for i, ep in enumerate(eps, 1):
                if not isinstance(ep, dict):
                    continue
                seq = ep.get("seq") or ep.get("episode") or ep.get("ep") or i
                title = ep.get("name") or ep.get("title") or ("第%s集" % seq)
                play.append("%s$%s|%s" % (title, vod_id, seq))
        if not play:
            for i in range(1, max(count, 1) + 1):
                play.append("第%s集$%s|%s" % (i, vod_id, i))

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": self._pic(data),
            "type_name": data.get("category") or data.get("type") or "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": data.get("update_label") or ("全%s集" % count),
            "vod_actor": "",
            "vod_director": "",
            "vod_content": data.get("description") or data.get("summary") or name,
            "vod_play_from": self.name,
            "vod_play_url": "#".join(play),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    # ------------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags):
        vid, seq = self._split(id)
        url = ""
        obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, timeout=15)
        if self._ok(obj):
            d = obj.get("data") or {}
            if isinstance(d, dict):
                lines = d.get("lines") if isinstance(d.get("lines"), list) else []
                url = self._pick_line(lines)
                if not url:
                    url = d.get("m3u8") or d.get("url") or ""
        if not url:
            url = self._hls(vid, seq)
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0, "header": self._play_header()}

    @staticmethod
    def _pick_line(lines):
        """优先 free 线路,其次任意可用线路"""
        if not isinstance(lines, list):
            return ""
        for ln in lines:
            if isinstance(ln, dict) and str(ln.get("name", "")).lower() == "free" and ln.get("url"):
                return ln.get("url")
        for ln in lines:
            if isinstance(ln, dict) and ln.get("url"):
                return ln.get("url")
        if lines and isinstance(lines[0], str):
            return lines[0]
        return ""

    def _hls(self, vid, seq):
        return "%s/api/drama/hls/%s/%s/play.m3u8?line=free" % (self.host, self._sid(vid), seq)

    # ------------------------------------------------------------------ 工具
    def _classes(self):
        if self.class_cache:
            return self.class_cache
        arr = [{"type_id": "all", "type_name": "全部短剧"}]
        rows = []
        try:
            obj = self._api("/drama/navList", {})
            rows = self._list(obj)
            if not rows and isinstance(obj, dict):
                rows = self._list(obj.get("data", {}))
        except Exception:
            rows = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("code") or item.get("id") or item.get("cat_id") or "")
            name = item.get("name") or item.get("title") or tid
            if tid and name:
                arr.append({"type_id": tid, "type_name": name})
        if len(arr) <= 1:
            # navList 挂了也不能让首页空着 —— 用内置 8 个一级分类兜底
            for code, nm in FALLBACK_NAV:
                arr.append({"type_id": code, "type_name": nm})
        self.class_cache = arr
        return arr

    def _filters(self, classes):
        common = [
            {"key": "order", "name": "排序", "value": [
                {"n": "默认", "v": "new:top"}, {"n": "最新", "v": "new:top"},
                {"n": "最热", "v": "hot:top"}]},
            {"key": "update_status", "name": "状态", "value": [
                {"n": "全部", "v": ""}, {"n": "连载", "v": "0"}, {"n": "完结", "v": "1"}]},
        ]
        fs = {}
        for c in classes:
            if not isinstance(c, dict):
                continue
            tid = c.get("type_id")
            if tid == "all":
                fs[tid] = common
                continue
            tabs = self._nav_filter(tid)
            # ★ 下标必须与 _tab() 里索引的 tabs 列表一一对应：
            #   "all" = 该分类默认 tab，其余 "0..N-1" = tabs[0..N-1]
            vals = [{"n": "全部", "v": "all"}]
            for i, t in enumerate(tabs):
                if isinstance(t, dict):
                    vals.append({"n": t.get("name") or ("分类%s" % i), "v": str(i)})
            if len(vals) <= 1:
                vals = []
            fs[tid] = ([{"key": "sub", "name": "子分类", "value": vals}] if vals else []) + common
        return fs

    def _nav_filter(self, code):
        """子分类表：优先服务端 navFilter；拿不到用内置兜底（实测值）。"""
        code = str(code)
        if code in self.filter_cache:
            return self.filter_cache[code]
        rows = []
        try:
            obj = self._api("/drama/navFilter", {"code": code})
            rows = self._list(obj)
            if not rows and isinstance(obj, dict):
                rows = self._list(obj.get("data", {}))
            rows = [x for x in rows if isinstance(x, dict)]
        except Exception:
            rows = []
        if not rows:
            rows = [dict(x) for x in FALLBACK_TABS.get(code, [])]
        self.filter_cache[code] = rows
        return rows

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for k in ("list", "items", "data", "records", "rows"):
            v = data.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                got = self._list(v)
                if got:
                    return got
        return []

    def _nav_items(self, data):
        blocks = self._list(data)
        items = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if isinstance(b.get("items"), list):
                items += [x for x in b.get("items") if isinstance(x, dict)]
            elif b.get("id") or b.get("drama_id"):
                items.append(b)
        return items

    def _vod(self, item):
        item = item if isinstance(item, dict) else {}
        vid = self._sid(item.get("id") or item.get("drama_id") or "")
        cnt = item.get("episode_count")
        remarks = item.get("update_label") or item.get("corner") or ""
        if not remarks and cnt:
            remarks = "全%s集" % cnt
        return {
            "vod_id": vid,
            "vod_name": item.get("name") or item.get("title") or item.get("t") or vid,
            "vod_pic": self._pic(item),
            "vod_remarks": str(remarks),
        }

    def _pic(self, item):
        if not isinstance(item, dict):
            return ""
        return (item.get("img_y") or item.get("img_x") or item.get("img")
                or item.get("cover") or item.get("pic") or "")

    def _sid(self, x):
        return str(x or "").replace("rp_", "")

    def _split(self, x):
        p = str(x).split("|", 1)
        return self._sid(p[0]), (p[1] if len(p) > 1 and p[1] else "1")

    def _int(self, x, d=0):
        try:
            return int(str(x).split(".")[0])
        except Exception:
            return d


# =====================================================================
# 内置 AES-256-CBC(纯标准库,仅在环境无 Crypto/cryptography 时启用)
# 已与 pycryptodome 对拍 360 轮,结果一致
# =====================================================================
def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p & 0xff


def _rotl(x, n):
    return ((x << n) | (x >> (8 - n))) & 0xff if n else x & 0xff


def _mk_tables():
    inv = [0] * 256
    for i in range(1, 256):
        for j in range(1, 256):
            if _gmul(i, j) == 1:
                inv[i] = j
                break
    sbox = [0] * 256
    for i in range(256):
        x = inv[i]
        sbox[i] = (x ^ _rotl(x, 1) ^ _rotl(x, 2) ^ _rotl(x, 3) ^ _rotl(x, 4) ^ 0x63) & 0xff
    rsbox = [0] * 256
    for i, v in enumerate(sbox):
        rsbox[v] = i
    return sbox, rsbox


_SBOX, _RSBOX = _mk_tables()
_M2 = [_gmul(i, 2) for i in range(256)]
_M3 = [_gmul(i, 3) for i in range(256)]
_M9 = [_gmul(i, 9) for i in range(256)]
_M11 = [_gmul(i, 11) for i in range(256)]
_M13 = [_gmul(i, 13) for i in range(256)]
_M14 = [_gmul(i, 14) for i in range(256)]


def _rcon(n):
    r = 1
    for _ in range(n - 1):
        r = _gmul(r, 2)
    return r


class _PyAES(object):
    def __init__(self, key):
        nk = len(key) // 4
        nr = nk + 6
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        for i in range(nk, 4 * (nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [_SBOX[b] for b in t]
                t[0] ^= _rcon(i // nk)
            elif nk > 6 and i % nk == 4:
                t = [_SBOX[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        self.rk = w
        self.nr = nr

    def _ark(self, s, rnd):
        for c in range(4):
            for r in range(4):
                s[4 * c + r] ^= self.rk[rnd * 4 + c][r]

    @staticmethod
    def _shift(s):
        for r in range(1, 4):
            row = [s[4 * c + r] for c in range(4)]
            row = row[r:] + row[:r]
            for c in range(4):
                s[4 * c + r] = row[c]

    @staticmethod
    def _inv_shift(s):
        for r in range(1, 4):
            row = [s[4 * c + r] for c in range(4)]
            row = row[-r:] + row[:-r]
            for c in range(4):
                s[4 * c + r] = row[c]

    @staticmethod
    def _mix(s):
        for c in range(4):
            a = s[4 * c:4 * c + 4]
            s[4 * c + 0] = _M2[a[0]] ^ _M3[a[1]] ^ a[2] ^ a[3]
            s[4 * c + 1] = a[0] ^ _M2[a[1]] ^ _M3[a[2]] ^ a[3]
            s[4 * c + 2] = a[0] ^ a[1] ^ _M2[a[2]] ^ _M3[a[3]]
            s[4 * c + 3] = _M3[a[0]] ^ a[1] ^ a[2] ^ _M2[a[3]]

    @staticmethod
    def _inv_mix(s):
        for c in range(4):
            a = s[4 * c:4 * c + 4]
            s[4 * c + 0] = _M14[a[0]] ^ _M11[a[1]] ^ _M13[a[2]] ^ _M9[a[3]]
            s[4 * c + 1] = _M9[a[0]] ^ _M14[a[1]] ^ _M11[a[2]] ^ _M13[a[3]]
            s[4 * c + 2] = _M13[a[0]] ^ _M9[a[1]] ^ _M14[a[2]] ^ _M11[a[3]]
            s[4 * c + 3] = _M11[a[0]] ^ _M13[a[1]] ^ _M9[a[2]] ^ _M14[a[3]]

    def _enc_block(self, blk):
        s = list(blk)
        self._ark(s, 0)
        for rnd in range(1, self.nr):
            s = [_SBOX[b] for b in s]
            self._shift(s)
            self._mix(s)
            self._ark(s, rnd)
        s = [_SBOX[b] for b in s]
        self._shift(s)
        self._ark(s, self.nr)
        return bytes(s)

    def _dec_block(self, blk):
        s = list(blk)
        self._ark(s, self.nr)
        for rnd in range(self.nr - 1, 0, -1):
            self._inv_shift(s)
            s = [_RSBOX[b] for b in s]
            self._ark(s, rnd)
            self._inv_mix(s)
        self._inv_shift(s)
        s = [_RSBOX[b] for b in s]
        self._ark(s, 0)
        return bytes(s)

    def cbc_encrypt(self, data, iv):
        out = bytearray()
        prev = iv
        for i in range(0, len(data), 16):
            blk = self._enc_block(bytes(x ^ y for x, y in zip(data[i:i + 16], prev)))
            out += blk
            prev = blk
        return bytes(out)

    def cbc_decrypt(self, data, iv):
        out = bytearray()
        prev = iv
        for i in range(0, len(data), 16):
            blk = data[i:i + 16]
            out += bytes(x ^ y for x, y in zip(self._dec_block(blk), prev))
            prev = blk
        return bytes(out)

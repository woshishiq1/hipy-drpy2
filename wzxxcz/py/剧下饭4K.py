# coding=utf-8
"""
剧下饭 manian.juxiafan.com | TVBox Python 爬虫 (豆花类式规范)
站点: http://manian.juxiafan.com/  (内置 8 个备用域名自动轮换)
接口: JSON API, AES-256-ECB(PKCS7/base64) 签名
包含: 分类、筛选(类型/地区/年份)、多线路播放顺序及解析、详情页、副标题、搜索、直播兜底
"""
import json
import time
import base64
from base64 import b64encode
from urllib.request import Request, urlopen
from urllib.parse import quote_plus, unquote

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = object

HOST = "http://manian.juxiafan.com"

BASE_URLS = [
    "http://manian.juxiafan.com",
    "http://195.225.24.128:6213",
    "http://jugaoqing.com",
    "http://jumianfei.com",
    "http://juyongjiu.com",
    "http://kuailezhuiju2.com",
    "http://zhuiju666.com",
    "http://194.147.100.155:7744",
]

AES_KEY = b"kZ6fT8oF6oM8eX6lF7eH2rJ3pW7gW0kC"
UA = "okhttp/4.12.0"

LIVE_TYPE_ID = 22023  # 隐藏直播分类(服务端不下发, 手动补进分类栏)

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


# ======================= AES-256-ECB =======================

def _build_sbox():
    sbox = [0] * 256
    p = q = 1
    while True:
        p = p ^ ((p << 1) ^ (0x1B if p & 0x80 else 0)) & 0xFF
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q ^= 0x09 if (q & 0x80) else 0
        q &= 0xFF
        xformed = q ^ ((q << 1) | (q >> 7)) & 0xFF
        xformed = (xformed ^ ((q << 2) | (q >> 6))) & 0xFF
        xformed = (xformed ^ ((q << 3) | (q >> 5))) & 0xFF
        xformed = (xformed ^ ((q << 4) | (q >> 4))) & 0xFF
        sbox[p] = xformed ^ 0x63
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]


def _xtime(a):
    return ((a << 1) ^ (0x1B if a & 0x80 else 0)) & 0xFF


_COL2 = [_xtime(i) for i in range(256)]
_COL3 = [_xtime(i) ^ i for i in range(256)]


def _expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def _encrypt_block(block, w, nr):
    def _rk(r):
        return [x for word in w[r * 4:(r * 4) + 4] for x in word]

    s = list(block)
    rk0 = _rk(0)
    for j in range(16):
        s[j] ^= rk0[j]
    for r in range(1, nr):
        s = [_SBOX[b] for b in s]
        s = [s[0], s[5], s[10], s[15],
             s[4], s[9], s[14], s[3],
             s[8], s[13], s[2], s[7],
             s[12], s[1], s[6], s[11]]
        t = [0] * 16
        for c in range(4):
            i = c * 4
            a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
            t[i] = _COL2[a0] ^ _COL3[a1] ^ a2 ^ a3
            t[i + 1] = a0 ^ _COL2[a1] ^ _COL3[a2] ^ a3
            t[i + 2] = a0 ^ a1 ^ _COL2[a2] ^ _COL3[a3]
            t[i + 3] = _COL3[a0] ^ a1 ^ a2 ^ _COL2[a3]
        s = t
        rk = _rk(r)
        s = [s[j] ^ rk[j] for j in range(16)]
    s = [_SBOX[b] for b in s]
    s = [s[0], s[5], s[10], s[15],
         s[4], s[9], s[14], s[3],
         s[8], s[13], s[2], s[7],
         s[12], s[1], s[6], s[11]]
    rk = _rk(nr)
    s = [s[j] ^ rk[j] for j in range(16)]
    return bytes(s)


def _aes256_ecb_encrypt(plain, key):
    w, nr = _expand_key(key)
    out = bytearray()
    for i in range(0, len(plain), 16):
        out += _encrypt_block(bytes(plain[i:i + 16]), w, nr)
    return bytes(out)


def _aes_encrypt(plaintext, key=AES_KEY):
    """PKCS7 填充 + AES-256-ECB -> base64 (多后端, 输出一致)"""
    data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    pad = 16 - len(data) % 16
    data = data + bytes([pad]) * pad
    try:
        from Crypto.Cipher import AES
        return b64encode(AES.new(key, AES.MODE_ECB).encrypt(data)).decode()
    except Exception:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher as _C
            from cryptography.hazmat.primitives.ciphers.algorithms import AES as _AES
            from cryptography.hazmat.primitives.ciphers.modes import ECB as _ECB
            from cryptography.hazmat.backends import default_backend as _B
            enc = _C(_AES(key), _ECB(), backend=_B()).encryptor()
            return b64encode(enc.update(data) + enc.finalize()).decode()
        except Exception:
            return b64encode(_aes256_ecb_encrypt(data, key)).decode()


# ======================= 类式爬虫 =======================

class Spider(_BaseSpider):

    def __init__(self, *args, **kwargs):
        self._host = BASE_URLS[0]
        self.extend = {}
        if kwargs.get("host"):
            self._host = self._fix_host(kwargs["host"])
        if kwargs.get("extend") is not None:
            self.init(kwargs["extend"])

    # ---------- 基础 ----------

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {} if not isinstance(extend, dict) else extend
        if isinstance(self.extend, dict) and self.extend.get("site"):
            self._host = self._fix_host(self.extend["site"])
        elif isinstance(extend, str) and extend.strip().startswith("http"):
            self._host = self._fix_host(extend.strip())
        elif isinstance(extend, str) and extend.strip().startswith("base="):
            self._host = self._fix_host(extend.strip()[5:])

    def getName(self):
        return "剧下饭4K影视"

    def _fix_host(self, host):
        if host is None or (isinstance(host, str) and host.strip() == ""):
            return BASE_URLS[0]
        return str(host).rstrip("/")

    def _http(self, method, url, body=None, content_type=None, timeout=12):
        headers = {"User-Agent": UA}
        data = None
        if body is not None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            headers["Content-Length"] = str(len(data))
        if content_type:
            headers["Content-Type"] = content_type
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    def _post(self, path, body=None, content_type=None):
        urls = []
        h = self._fix_host(self._host)
        if h not in urls:
            urls.append(h)
        for b in BASE_URLS:
            if b not in urls:
                urls.append(b)
        last = "{}"
        for u in urls:
            try:
                last = self._http("POST", u + path, body, content_type)
                if '"code"' in last:
                    return last
            except Exception:
                continue
        return last

    def _get(self, url, timeout=12):
        try:
            return self._http("GET", url, timeout=timeout)
        except Exception:
            return "{}"

    def _post_form(self, path, params):
        ts = str(int(time.time()))
        params["timestamp"] = ts
        items = sorted(params.items())
        concat = "&".join(k + "=" + quote_plus(str(v)) for k, v in items)
        ds = _aes_encrypt(concat)
        form = "&".join(k + "=" + quote_plus(str(v)) for k, v in items)
        form += "&datasign=" + quote_plus(ds)
        return self._post(path, form, "application/x-www-form-urlencoded")

    def _post_json(self, path, params):
        params["timestamp"] = str(int(time.time()))
        items = sorted(params.items())
        concat = "&".join(k + "=" + str(v) for k, v in items)
        ds = _aes_encrypt(concat)
        obj = dict(items)
        obj["datasign"] = ds
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return self._post(path, body, "application/json;charset=UTF-8")

    # ---------- 分类 / 筛选 ----------

    @staticmethod
    def _split_options(text):
        if not text:
            return []
        return [x.strip() for x in str(text).split(",") if x.strip()]

    def _build_filters(self, ext):
        """按分类下发的 extend 构造筛选: 类型(classify)/地区(area)/年份(year)"""
        filters = []
        class_opts = self._split_options(ext.get("class"))
        area_opts = self._split_options(ext.get("area"))
        year_opts = self._split_options(ext.get("year"))

        def _opts(opts):
            return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in opts]

        if class_opts:
            filters.append({"key": "classify", "name": "类型", "value": _opts(class_opts)})
        if area_opts:
            filters.append({"key": "area", "name": "地区", "value": _opts(area_opts)})
        if year_opts:
            filters.append({"key": "year", "name": "年份", "value": _opts(year_opts)})
        return filters

    def _home(self):
        resp = self._post("/api/v1/video/classifies")
        try:
            data = json.loads(resp).get("data") or []
        except Exception:
            data = []
        cls = []
        filters = {}
        for c in data:
            if not c.get("id") or not c.get("name"):
                continue
            tid = str(c.get("id"))
            ext = c.get("extend") or {}
            cls.append({"type_id": tid, "type_name": c.get("name")})
            filters[tid] = self._build_filters(ext)
        # 按 type_id 升序, 与 App 首页顺序一致
        cls.sort(key=lambda x: int(x["type_id"]) if str(x["type_id"]).isdigit() else 10 ** 9)
        # 服务端不下发隐藏直播分类(22023), 手动追加到分类栏末尾
        if str(LIVE_TYPE_ID) not in [str(c.get("type_id")) for c in cls]:
            cls.append({"type_id": str(LIVE_TYPE_ID), "type_name": "直播"})
            filters[str(LIVE_TYPE_ID)] = []
        return {"class": cls, "filters": filters}

    def homeContent(self, filter=False):
        return self._home()

    def homeVideoContent(self):
        # 首页推荐: 电视剧(22016)第一页, 失败返回空墙
        try:
            res = self._category(str(22016), "1", {})
            return {"list": res.get("list") or []}
        except Exception:
            return {"list": []}

    # ---------- 列表 ----------

    def _build_list(self, resp, page=1, id_desc=False):
        try:
            data = json.loads(resp).get("data") or {}
        except Exception:
            data = {}
        lst = []
        for v in data.get("list") or []:
            if not v.get("id"):
                continue
            lst.append({
                "vod_id": str(v.get("id")),
                "vod_name": v.get("name") or "",
                "vod_pic": v.get("videoPic") or "",
                "vod_remarks": v.get("remarks") or "",
            })
        # 本地按 id 降序: 搜索时 id 大=收录晚=越新, 最新的排在头部
        if id_desc and lst:
            try:
                lst.sort(key=lambda v: int(v.get("vod_id") or 0), reverse=True)
            except Exception:
                pass
        try:
            pg = int(page) or 1
        except (ValueError, TypeError):
            pg = 1
        try:
            pagecount = int(data.get("totalPage") or 1)
        except (ValueError, TypeError):
            pagecount = 1
        if pagecount < pg:
            pagecount = pg
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": data.get("limit") or 20,
            "total": data.get("totalCount") or 0,
            "list": lst,
        }

    def _category(self, tid, pg, extend):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            pass
        try:
            type_id = int(tid)
        except Exception:
            type_id = 0

        # ---- 直播分类 22023: 服务端不下发, 走 liveVideo 接口返回直播分组 ----
        if type_id == LIVE_TYPE_ID:
            lst = []
            try:
                r = self._get(self._fix_host(self._host) + "/api/v1/video/liveVideo")
                data = (json.loads(r).get("data") or {})
                for v in data.get("list") or []:
                    if not v.get("id"):
                        continue
                    lst.append({
                        "vod_id": str(v.get("id")),
                        "vod_name": v.get("name") or "",
                        "vod_pic": v.get("videoPic") or "",
                        "vod_remarks": v.get("remarks") or ("直播" if v.get("typeId") else ""),
                    })
            except Exception:
                pass
            return {"page": 1, "pagecount": 1, "limit": len(lst), "total": len(lst), "list": lst}

        # 筛选参数: 类型 classify / 地区 area / 年份 year (空值/全部忽略)
        params = {"pageNum": page, "typeId": type_id}
        active_filter = False
        if isinstance(extend, dict):
            for k in ("classify", "area", "year"):
                val = extend.get(k)
                if val and str(val) not in ("", "全部", "null", "None"):
                    params[k] = str(val)
                    active_filter = True

        resp = self._post_json("/api/v1/video/index", params)
        res = self._build_list(resp, page, False)

        # 服务端把部分分类降级为只返回 2 条(limit=2), 此时自动改用 /video/search
        # 空关键词+typeId 兜底, 拿完整列表(40条/页, 最新在前)。
        # 注意: 仅在无筛选条件时回退; 带筛选时搜索接口不认这些条件, 不能回退以免丢条件。
        if not active_filter and len(res.get("list") or []) < 10:
            fb = {"keyword": "", "typeId": type_id, "pageNum": page}
            resp2 = self._post_json("/api/v1/video/search", fb)
            res = self._build_list(resp2, page, True)
        return res

    def categoryContent(self, tid, pg="1", filter=None, extend=None):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]
        return self._category(tid, pg, extend)

    # ---------- 搜索 ----------

    def _search(self, key, pg="1"):
        key = (key or "").strip().strip('"').strip("'")
        if not key:
            return {"page": 1, "pagecount": 0, "limit": 20, "total": 0, "list": []}
        # 兼容播放器传入 URL 编码关键词, 服务端 % 会当通配符, 必须先解码回原文
        if "%" in key:
            try:
                dec = unquote(key)
                if dec and dec != key:
                    key = dec.strip()
            except Exception:
                pass
        # 兼容 \uXXXX 转义形态的关键词
        if key and "\\u" in key and all(ord(ch) < 128 for ch in key):
            try:
                dec = key.encode("ascii").decode("unicode_escape")
                if dec and dec != key:
                    key = dec
            except Exception:
                pass
        try:
            page = int(pg or 1)
        except (ValueError, TypeError):
            page = 1
        if page < 1:
            page = 1
        resp = self._post_json("/api/v1/video/search", {"keyword": key, "pageNum": page})
        return self._build_list(resp, page, True)

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        try:
            return self._search(key, pg)
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    # ---------- 详情 ----------

    def _fetch_detail(self, vid):
        resp = self._post_form("/api/v1/video/videoDetails", {"id": str(vid)})
        try:
            return json.loads(resp).get("data") or {}
        except Exception:
            return {}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        data = self._fetch_detail(ids[0])
        if not data:
            return {"list": []}

        sources = data.get("playerSource") or []
        from_names, from_urllists = [], []
        seen = {}
        for src in sources:
            eps = src.get("episodes") or []
            if not eps:
                continue
            name = src.get("sourceName") or "剧下饭"
            if name in seen:  # 同名线路加序号区分
                seen[name] += 1
                name = name + str(seen[name])
            else:
                seen[name] = 1
            segs = []
            for i, ep in enumerate(eps, 1):
                ep_name = (ep.get("episodeName") or "") or ("第" + str(i) + "集")
                ep_name = ep_name.replace("$", "_").replace("#", "_")
                segs.append(ep_name + "$" + str(ids[0]) + "_" + str(i))
            from_names.append(name)
            from_urllists.append("#".join(segs))

        if not from_urllists:
            return {"list": []}

        content = data.get("content") or ""
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        play_from = "$$$".join(from_names)      # 多线路: 名字用 $$$ 分隔
        play_url = "$$$".join(from_urllists)    # 线路内集数用 # 分隔

        return {"list": [{
            "vod_id": str(data.get("id") or ids[0]),
            "vod_name": data.get("name") or "",
            "vod_pic": data.get("videoPic") or "",
            "vod_content": content,
            "vod_actor": data.get("actor") or "",
            "vod_director": data.get("director") or "",
            "vod_score": str(data.get("score") or ""),
            "vod_remarks": data.get("remarks") or "",
            "vod_type": data.get("classify") or "",
            "vod_area": data.get("area") or "",
            "vod_year": data.get("year") or "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }]}

    # ---------- 播放 ----------

    def _analysis_url(self, source_code, pc):
        """调用服务端 analysisUrl 把加密 playerCode 解析成真实播放地址。
        返回解析成功后的 URL 字符串, 失败返回空串。"""
        if not source_code or not pc:
            return ""
        try:
            r = self._post_form("/api/v1/player/analysisUrl", {"from": source_code, "code": pc})
            u = (json.loads(r).get("data") or "")
            if str(u).startswith("http"):
                return str(u)
        except Exception:
            pass
        return ""

    def playerContent(self, flag, id, vipFlags=""):
        try:
            vid, ep = id.rsplit("_", 1)
            ep = int(ep)
        except Exception:
            return {"parse": 0, "url": id, "header": {"User-Agent": UA}}

        data = self._fetch_detail(vid)
        sources = data.get("playerSource") or []
        flag_s = str(flag or "").strip()
        # 优先用户当前选中的线路, 其余线路作为备选
        ordered = [src for src in sources if str(src.get("sourceName") or "").strip() == flag_s]
        for src in sources:
            if src not in ordered:
                ordered.append(src)

        for src in ordered:
            eps = src.get("episodes") or []
            if not eps or ep > len(eps):
                continue
            pc = (eps[ep - 1] or {}).get("playerCode") or ""
            parse_url = src.get("parseUrl") or ""
            source_code = src.get("sourceCode") or ""

            # 1) 线路自带解析接口: parseUrl + playerCode -> json.url
            if parse_url and pc:
                j = self._get(parse_url + pc)
                try:
                    u = json.loads(j).get("url") or ""
                except Exception:
                    u = ""
                if u:
                    return {"parse": 0, "url": u, "header": {"User-Agent": UA}}

            # 2) 加密 code: 走服务端 analysisUrl 秒播解析
            if pc and not str(pc).startswith("http"):
                u = self._analysis_url(source_code, pc)
                if u:
                    headers = {"User-Agent": UA}
                    if source_code == "huya":
                        headers["Referer"] = "https://www.huya.com/"
                    return {"parse": 0, "url": u, "header": headers}
                # 解析失败: 仍把 code 原样返回, 交由播放器自行尝试
                return {"parse": 0, "url": pc, "header": {"User-Agent": UA}}
            elif pc:
                # 3) 直链 m3u8/mp4/网页
                return {"parse": 0, "url": pc, "header": {"User-Agent": UA}}

        return {"parse": 0, "url": "", "header": {"User-Agent": UA}}

    # ---------- 其它契约 ----------

    def localProxy(self, param):
        return {"list": [], "parse": 0, "url": ""}

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url or str(url).startswith("http"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()


# ======================= 本地自测 =======================

if __name__ == "__main__":
    def show(label, s, n=260):
        txt = json.dumps(s, ensure_ascii=False) if not isinstance(s, str) else s
        print("== " + label + " ==")
        print(txt if len(txt) <= n else txt[:n])
        print()

    sp = Spider()
    show("homeContent", sp.homeContent(False))
    show("category 电视剧", sp.categoryContent("22016", "1", False, None))
    show("category 电视剧+地区内地", sp.categoryContent("22016", "1", False, {"area": "内地"}))
    show("category 电视剧+年份2026", sp.categoryContent("22016", "1", False, {"year": "2026"}))
    show("category 直播", sp.categoryContent("22023", "1", False, None))
    show("search 逐玉", sp.searchContent("逐玉", True))
    show("detail 621119", sp.detailContent(["621119"]))
    show("player ep1", sp.playerContent("剧下饭极速专线", "621119_1", None))
    show("live detail", sp.detailContent(["366473"]))
    show("live play", sp.playerContent("直播频道", "366473_1", None))
    show("huya play", sp.playerContent("虎牙直播", "370855_1", None))

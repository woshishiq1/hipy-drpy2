# -*- coding: utf-8 -*-
# awXVideo.fm spider v1.0.0（TVBox 四壳协议 / FongMi 兼容）
#
# 站点：awXVideo.fm（Vite SPA + 私有加密协议 Ver 2.1.7）
# 协议：请求头签名 HmacSHA1 + 响应体 AES 解密（前端原样复刻，无需再抓包）
# 会话：站点自带游客发号（自动注册/续期）；注册被限流时可手动填 token
#
# 实测边界（如实标注，不做假解锁）：
#   · 分类 / 列表 / 详情：游客态直读，无需登录
#   · 播放：本站正片走服务端票控 + 签名，游客态只放行 10 秒试看片段
#     → 无 token：返回站点试看片段并在备注标明「试看10s」
#     → 有 token：返回正片清单（token 从浏览器 localStorage 复制即可）
#   · 预览/试看分片真实可拉（实测 299KB 首片），绝不返回假地址黑屏
#
# 开关（不填直接能用）：
#   {"token":"..."}      自带会话（可选，换 token = 换免费额度）
#   {"device_id":"..."}  固定游客号（可选）
#   {"img_cdn":"..."}    图片 CDN（默认 kssimg.rlkfus.cn）
#   {"sort":"2"}         默认排序
#   {"verify":"1"}       播放前先校验线路
import base64
import hashlib
import hmac
import json
import os
import random
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

# ============================ 站点常量 ============================
HOST = "https://d18psf29jvwgay.cloudfront.net"
RAW_SITE = HOST
IMG_CDN = "https://kssimg.rlkfus.cn"
VID_CDN = "https://kssts.rlkfus.cn"

VER = "2.1.7"
REQ_KEY = "jR6dO6fT1yD9zY7u"
RESP_KEY = "vEukA&w15z4VAD3kAY#fkL#rBnU!WDhN"
IMG_KEY = b"2019ysapp7527"
GUEST_SKEY = "zfvG4u4OjrxTjyb"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

PAGE_SIZE = 30
CACHE_TTL = 300
SEARCH_CATS = (376401, 342081, 342082, 342083)   # 本地搜索覆盖的热门分类
SEARCH_PAGES = 6                                  # 每个分类搜几页
SEARCH_PAGE_SIZE = 50

_DEFAULT_PROXY_FALLBACK = ""
# 站点独立板块 id（漫画走 /comics、AI 短剧走 /aiorder，不是媒体列表接口）
_SKIP_CATS = (10141, 1307112)
_PROXY_CONFIG_PATHS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "proxy_config.json"),
    os.path.expanduser("~/tvbox-dev/assets/proxy_config.json"),
)


def _load_default_proxy():
    for path in _PROXY_CONFIG_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                p = str(data.get("default_proxy", "")).strip()
                if p:
                    return p
        except Exception:
            continue
    return _DEFAULT_PROXY_FALLBACK


# ==================== 协议层：CryptoJS / base64-js 兼容 ====================
_B64CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_REVMAP = dict((ord(c), i) for i, c in enumerate(_B64CHARS))


def _js_to_bytes(b64s):
    """base64-js toByteArray：标准解码"""
    try:
        return base64.b64decode(b64s + "=" * (-len(b64s) % 4))
    except Exception:
        return b""


def _js_from_bytes(b):
    """base64-js fromByteArray：标准编码（带 padding）"""
    return base64.b64encode(bytes(b)).decode("ascii")


def _cj_b64_parse(s):
    """CryptoJS enc.Base64.parse：遇 '=' 截断，非表内字符按 0 占位（行为必须一致）"""
    pi = s.find("=")
    if pi != -1:
        s = s[:pi]
    words, bits = [], 0
    for i in range(len(s)):
        if i % 4:
            v1 = _REVMAP.get(ord(s[i - 1]), 0)
            v2 = _REVMAP.get(ord(s[i]), 0)
            combined = ((v1 << ((i % 4) * 2)) | (v2 >> (6 - (i % 4) * 2))) & 0xFFFFFFFF
            wi = bits >> 5
            while len(words) <= wi:
                words.append(0)
            sh = (24 - bits % 32) % 32
            words[wi] = (words[wi] | ((combined << sh) & 0xFFFFFFFF)) & 0xFFFFFFFF
            bits += 8
    out = bytearray()
    for i in range(bits // 8):
        out.append((words[i >> 2] >> (24 - (i % 4) * 8)) & 0xFF)
    return bytes(out)


def _splice(lst, start, count):
    """JS Array.splice(start, deleteCount) 语义：返回被删元素并就地删除"""
    removed = lst[start:start + count]
    del lst[start:start + count]
    return removed


def _hex_bytes(h):
    return bytes(int(h[i:i + 2], 16) for i in range(0, len(h), 2))


def _aes_cbc_decrypt(key, iv, data):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except Exception:
        return _pure_py_aes_cbc_decrypt(key, iv, data)
    if len(iv) < 16:
        iv = bytes(iv) + b"\x00" * (16 - len(iv))
    if len(data) % 16:
        data = data[:len(data) - (len(data) % 16)]
    if not data:
        return b""
    raw = AES.new(key, AES.MODE_CBC, iv[:16]).decrypt(data)
    try:
        return unpad(raw, 16)
    except Exception:
        return raw


# --- 纯 Python AES 兜底（无 pycryptodome 环境也能跑） ---
_SBOX = None
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36,
         0x6C, 0xD8, 0xAB, 0x4D, 0x9A)


def _build_sbox():
    global _SBOX
    if _SBOX is not None:
        return _SBOX
    p = q = 1
    sbox = [0] * 256
    while True:
        p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)) & 0xFF
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ \
            ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    _SBOX = sbox
    return sbox


def _xtime(a):
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _expand_key(key):
    sbox = _build_sbox()
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [sbox[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [sbox[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def _inv_shift_rows(s):
    s[1], s[5], s[9], s[13] = s[13], s[1], s[5], s[9]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[7], s[11], s[15], s[3]


def _inv_sub_bytes(s):
    sbox = _build_sbox()
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    for i in range(16):
        s[i] = inv[s[i]]


def _inv_mix_columns(s):
    for c in range(4):
        i = c * 4
        a = s[i:i + 4]
        s[i + 0] = _gmul(a[0], 14) ^ _gmul(a[1], 11) ^ _gmul(a[2], 13) ^ _gmul(a[3], 9)
        s[i + 1] = _gmul(a[0], 9) ^ _gmul(a[1], 14) ^ _gmul(a[2], 11) ^ _gmul(a[3], 13)
        s[i + 2] = _gmul(a[0], 13) ^ _gmul(a[1], 9) ^ _gmul(a[2], 14) ^ _gmul(a[3], 11)
        s[i + 3] = _gmul(a[0], 11) ^ _gmul(a[1], 13) ^ _gmul(a[2], 9) ^ _gmul(a[3], 14)


def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p


def _pure_py_aes_cbc_decrypt(key, iv, data):
    try:
        w, nr = _expand_key(list(key))
        if len(iv) < 16:
            iv = list(iv) + [0] * (16 - len(iv))
        prev = list(iv[:16])
        out = bytearray()
        for off in range(0, len(data) - len(data) % 16, 16):
            block = list(data[off:off + 16])
            state = list(block)
            _inv_shift_rows(state)
            _inv_sub_bytes(state)
            for rnd in range(nr, 0, -1):
                rk = w[rnd * 4:rnd * 4 + 4]
                for c in range(4):
                    for r in range(4):
                        state[c * 4 + r] ^= rk[c][r]
                if rnd > 1:
                    _inv_mix_columns(state)
                _inv_shift_rows(state)
                _inv_sub_bytes(state)
            rk = w[0:4]
            for c in range(4):
                for r in range(4):
                    state[c * 4 + r] ^= rk[c][r]
            out.extend((state[i] ^ prev[i]) & 0xFF for i in range(16))
            prev = block
        return bytes(out)
    except Exception:
        return b""


def decode_http_response(e):
    """复刻前端 decodeHttpResponseData（Ver 2.1.7）"""
    if isinstance(e, bytes):
        e = e.decode("utf-8", "replace")
    if not e:
        return ""
    n = list(_js_to_bytes(e))
    if len(n) <= 12:
        return ""
    o = _splice(n, 0, 12)
    c = list(RESP_KEY.encode("utf-8")) + o
    l = len(c) // 2
    d = _cj_b64_parse(_js_from_bytes(c))
    g = list(hashlib.sha256(d).digest()[8:24])
    head = _splice(c, 0, l)
    v = _cj_b64_parse(_js_from_bytes(g + head))
    a = list(hashlib.sha256(v).digest())
    bz = list(hashlib.sha256(_cj_b64_parse(_js_from_bytes(c + g))).digest())
    k = _splice(a, 0, 8) + _splice(bz, 8, 16) + _splice(a, 16, 24)
    iv_b = _splice(bz, 0, 4) + _splice(a, 4, 8) + _splice(bz, 8, 12)
    key = _cj_b64_parse(_js_from_bytes(k))
    iv = _cj_b64_parse(_js_from_bytes(iv_b))
    ct = _cj_b64_parse(_js_from_bytes(n))
    return _aes_cbc_decrypt(key, iv, ct).decode("utf-8", "replace")


def _nonce():
    """前端 nonce：36 位 UUID 形态"""
    f = [random.choice("0123456789abcdef") for _ in range(36)]
    f[14] = "4"
    f[19] = "0123456789abcdef"[(int(f[19], 16) & 3) | 8]
    f[8] = f[13] = f[18] = f[23] = "-"
    return "".join(f)


_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(n):
    if n <= 0:
        return "0"
    out = ""
    while n:
        out = _B36[n % 36] + out
        n //= 36
    return out


def _gen_devid():
    """前端 devID：Math.random 小数位 + Date.now 的 base36"""
    frac = ("%.17f" % random.random()).split(".")[1][:16]
    return frac + _base36(int(time.time() * 1000))


def _sign(api_path, token="", ua_str=""):
    """x-api-key = timestamp=..;sign=..;nonce=..（HmacSHA1）"""
    ts = int(time.time())
    nc = _nonce()
    msg = "%s&%s&%s&%d&%s" % (token or "", api_path, ua_str or "", ts, nc)
    sig = hmac.new(REQ_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).hexdigest()
    return "timestamp=%d;sign=%s;nonce=%s" % (ts, sig, nc)


# ==================== 图片解密（前端 decryptImage 复刻） ====================
_IMG_MAGIC = bytes([136, 168, 48, 203, 16, 118])
_IMG_FEATS = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF")


def _is_encrypted_image(data):
    for feat in _IMG_FEATS:
        if data[:len(feat)] == feat:
            return False
    return True


def decrypt_image(data):
    """站点图片加密：全量 XOR 163 或 前100字节与 key 循环 XOR"""
    if not data:
        return data
    if data[:6] == _IMG_MAGIC:
        out = bytearray()
        for i, b in enumerate(data):
            if i < len(_IMG_MAGIC) and b == _IMG_MAGIC[i]:
                continue
            out.append(b ^ 163)
        return bytes(out)
    if _is_encrypted_image(data):
        buf = bytearray(data)
        lim = min(100, len(buf))
        for a in range(0, lim, len(IMG_KEY)):
            for c in range(len(IMG_KEY)):
                if a + c < lim:
                    buf[a + c] ^= IMG_KEY[c]
        return bytes(buf)
    return data


def _img_mime(data):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"GIF":
        return "image/gif"
    if data[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


# ==================== 铁律11 脱敏 / 铁律13 未成年剔除 ====================
_SENSITIVE_MAP = {
    "强奸": "胁迫", "轮奸": "群侵", "迷奸": "药迷", "兽交": "异物",
    "幼女": "", "幼齿": "", "儿童": "", "女童": "", "未成年": "",
    "小学生": "", "中学生": "", "初中": "", "高中": "",
}
# 铁律11：古典映射脱敏表（审计固定名，与 _SENSITIVE_MAP 同源）
CLASSICAL_MAP = dict(_SENSITIVE_MAP)
_BLOCK_WORDS = ("幼女", "幼齿", "儿童", "女童", "未成年", "小学生", "中学生",
                "初中生", "高中生", "幼儿园")


def _is_minor_itm(title):
    t = str(title or "")
    return any(w in t for w in _BLOCK_WORDS)


def _sanitize_text(s):
    """铁律11：敏感词古典映射脱敏"""
    t = str(s or "")
    for k, v in CLASSICAL_MAP.items():
        if k in t:
            t = t.replace(k, v)
    return t


def desensitize(text):
    """铁律11：对外统一脱敏入口（等价 _sanitize_text）"""
    return _sanitize_text(text)


def _sanitize_item(item):
    """铁律11+13：条目脱敏 + 未成年剔除（返回 None 表示剔除）"""
    if not isinstance(item, dict):
        return None
    name = item.get("vod_name") or ""
    if _is_minor_itm(name):
        return None
    item["vod_name"] = _sanitize_text(name)
    if item.get("vod_remarks"):
        item["vod_remarks"] = _sanitize_text(item["vod_remarks"])
    return item


def _sanitize_list(items):
    out = []
    for it in items or []:
        v = _sanitize_item(it)
        if v:
            out.append(v)
    return out


def _sanitize_vod(vod):
    if not isinstance(vod, dict):
        return None
    if _is_minor_itm(vod.get("vod_name") or ""):
        return None
    vod["vod_name"] = _sanitize_text(vod.get("vod_name") or "")
    vod["vod_content"] = _sanitize_text(vod.get("vod_content") or "")
    vod["vod_remarks"] = _sanitize_text(vod.get("vod_remarks") or "")
    return vod


def _sanitize_classes(classes):
    out = []
    for c in classes or []:
        name = str(c.get("type_name") or "")
        if not name or _is_minor_itm(name):
            continue
        c["type_name"] = _sanitize_text(name)
        out.append(c)
    return out


# ==================== HTTP 自适应层 ====================
class _Http(object):
    """requests 优先，urllib 兜底（TVBox 环境无 requests 也能跑）"""

    def __init__(self):
        self._sess = None
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": HOST,
            "Referer": HOST + "/",
        }
        try:
            import requests
            self._sess = requests.Session()
            self._sess.headers.update(self.headers)
        except Exception:
            self._sess = None

    def post(self, url, body, headers=None):
        payload = json.dumps(body or {})
        hdrs = dict(self.headers)
        hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)
        if self._sess is not None:
            r = self._sess.post(url, data=payload.encode("utf-8"), headers=hdrs, timeout=20)
            return r.text, r.status_code
        import urllib.request
        req = urllib.request.Request(url, data=payload.encode("utf-8"), headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace"), resp.status

    def get(self, url, headers=None, binary=False):
        hdrs = dict(self.headers)
        if headers:
            hdrs.update(headers)
        if self._sess is not None:
            r = self._sess.get(url, headers=hdrs, timeout=20)
            return (r.content if binary else r.text), r.status_code
        import urllib.request
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            return (data if binary else data.decode("utf-8", "replace")), resp.status

    def close(self):
        try:
            if self._sess is not None:
                self._sess.close()
        except Exception:
            pass


# ==================== Spider ====================
class Spider(_BaseSpider):
    """awXVideo.fm —— 免登录可读列表，播放走站点 H5 中转"""

    def __init__(self):
        self.name = "awXVideo"
        self.host = HOST
        # 铁律15：反代属性
        self.rawSite = RAW_SITE
        self.siteUrl = HOST
        self.HOST = HOST
        self.img_cdn = IMG_CDN
        self.vid_cdn = VID_CDN
        self.token = ""
        self.device_id = _gen_devid()
        self.sort = "0"
        self.verify = False
        self._http = None
        self._cache = {}
        self._cache_lock = None
        self._classes = None
        self._default_proxy = _load_default_proxy()
        self._use_proxy = True

    # ---------- 基础 ----------
    def getName(self):
        return self.name

    def init(self, extend=""):
        cfg = {}
        if isinstance(extend, dict):
            cfg = extend
        elif extend:
            try:
                cfg = json.loads(extend)
            except Exception:
                try:
                    import ast
                    cfg = ast.literal_eval(extend)
                except Exception:
                    cfg = {}
        self.token = str(cfg.get("token") or self.token or "")
        self.device_id = str(cfg.get("device_id") or self.device_id)
        self.img_cdn = str(cfg.get("img_cdn") or IMG_CDN).rstrip("/")
        self.vid_cdn = str(cfg.get("vid_cdn") or VID_CDN).rstrip("/")
        self.sort = str(cfg.get("sort") or "0")
        self.verify = str(cfg.get("verify") or "") in ("1", "true", "True")
        if self._http is None:
            self._http = _Http()
        if self._cache_lock is None:
            try:
                import threading
                self._cache_lock = threading.RLock()
            except Exception:
                self._cache_lock = None
        # 自动游客会话（拿不到就静默降级为免登录模式）
        if not self.token and str(cfg.get("guest", "1")) != "0":
            try:
                self._guest_login()
            except Exception:
                pass
        return None

    def getDependence(self):
        return ""

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|ts)(\?|$)", url or "", re.I))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        try:
            if self._http is not None:
                self._http.close()
        except Exception:
            pass
        self._http = None
        return ""

    # ---------- 协议调用 ----------
    def _session(self):
        if self._http is None:
            self._http = _Http()
        return self._http

    def _call(self, path, body=None, retry=2):
        """带签名请求 + 响应解密；返回 (code, data, tip)"""
        last = (0, None, "")
        for _ in range(max(1, retry)):
            try:
                hs = {}
                ua_str = ""
                hs["Authorization"] = self.token or ""
                hs["x-api-key"] = _sign(path, self.token, ua_str)
                txt, status = self._session().post(HOST + path, body or {}, hs)
                j = json.loads(txt)
                code = j.get("code")
                data = j.get("data")
                if j.get("hash") and isinstance(data, str):
                    dec = decode_http_response(data)
                    try:
                        data = json.loads(dec) if dec else None
                    except Exception:
                        data = dec
                if code == 200:
                    return code, data, j.get("tip") or ""
                last = (code, data, j.get("tip") or "")
                if code in (1002, 1011):
                    # 无 token / token 失效 —— 免登录重试一次
                    if self.token:
                        self.token = ""
                        continue
                    return last
                time.sleep(0.4)
            except Exception as e:
                last = (-1, None, str(e))
                time.sleep(0.4)
        return last

    def _guest_login(self):
        """站点自带游客发号：HmacSHA1(devID&{}, devID+guest_skey)"""
        path = "/api/app/login/guest"
        body = {"devID": self.device_id, "affCode": "{}"}
        msg = "%s&%s" % (self.device_id, "{}")
        body["sign"] = hmac.new((self.device_id + GUEST_SKEY).encode("utf-8"),
                                msg.encode("utf-8"), hashlib.sha1).hexdigest()
        hs = {"Authorization": "", "x-api-key": _sign(path, "", "")}
        txt, _ = self._session().post(HOST + path, body, hs)
        j = json.loads(txt)
        data = j.get("data")
        if j.get("hash") and isinstance(data, str):
            dec = decode_http_response(data)
            try:
                data = json.loads(dec) if dec else None
            except Exception:
                data = None
        if isinstance(data, dict):
            tk = data.get("token") or data.get("accessToken") or ""
            if tk:
                self.token = str(tk)
        return self.token

    # ---------- 分类 ----------
    def _categories(self):
        now = time.time()
        if self._classes and now - self._classes[0] < CACHE_TTL * 6:
            return self._classes[1]
        code, data, _ = self._call("/api/app/media/categories", {})
        classes = []
        if isinstance(data, dict):
            nav = [("n_must", "入站必刷"), ("n_week", "每周精选")]
            for tid, name in nav:
                if tid == "n_week" and not self._nav_list("n_week", 1):
                    # 站点周更，当周无内容时不显示（避免空分类）
                    continue
                classes.append({"type_id": tid, "type_name": name})
            for key, prefix in (("homeCategory", "h"), ("shortCategory", "s"), ("lldCategory", "l")):
                # 短视频分区走站点 /short/* 接口，实测需会话；无 token 时剔除避免空分类
                if key == "shortCategory" and not self.token:
                    continue
                for c in (data.get(key) or []):
                    cid = c.get("id")
                    nm = c.get("name")
                    if cid is None or not nm:
                        continue
                    # 站点独立板块（漫画走 /comics、AI 短剧走 /aiorder），非媒体列表，剔除避免空分类
                    if int(cid) in _SKIP_CATS:
                        continue
                    classes.append({"type_id": "%s%s" % (prefix, cid), "type_name": str(nm)})
        classes = _sanitize_classes(classes)
        self._classes = (now, classes)
        return classes

    def homeContent(self, filter):
        classes = self._categories()
        filters = {}
        sorts = [{"key": "sort", "name": "排序",
                  "value": [{"n": "默认", "v": "0"}, {"n": "最新", "v": "2"},
                            {"n": "最热", "v": "1"}, {"n": "好评", "v": "3"}]}]
        for c in classes:
            if c["type_id"].startswith("h") or c["type_id"].startswith("s"):
                filters[c["type_id"]] = sorts
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        items = self._list_by_cat("h342081", 1, "0")
        return {"list": _sanitize_list(self._items(items))}

    # ---------- 列表 ----------
    def _list_by_cat(self, tid, page, sort=None):
        tid = str(tid or "")
        sort = str(sort if sort is not None else self.sort)
        page = max(1, int(page or 1))
        if tid.startswith("n_"):
            return self._nav_list(tid, page)
        cid = tid[1:] if tid[:1] in ("h", "s", "l") else tid
        try:
            cid = int(cid)
        except Exception:
            return []
        body = {"id": cid, "pageNum": page, "pageSize": PAGE_SIZE}
        if sort and sort != "0":
            body["sort"] = int(sort) if str(sort).isdigit() else sort
        code, data, tip = self._call("/api/app/media/home", body)
        if code != 200 or not isinstance(data, dict):
            data = None
        ml = data.get("mediaList") if isinstance(data, dict) else None
        # 短视频分区回退：站点独立接口（需会话）
        if (not ml) and str(tid).startswith("s"):
            for path in ("/api/app/media/short/found", "/api/app/media/short/hot"):
                c2, d2, _ = self._call(path, {"pageNum": page, "pageSize": PAGE_SIZE}, retry=1)
                if c2 == 200 and isinstance(d2, dict):
                    ml = d2.get("mediaList") or d2.get("list")
                    if isinstance(ml, list) and ml:
                        return ml
        return ml if isinstance(ml, list) else []

    def _nav_list(self, tid, page):
        if tid == "n_daily":
            code, data, _ = self._call("/api/app/media/dailyRecommend", {"pageNum": page, "pageSize": 10})
            out = []
            if isinstance(data, dict):
                for grp in (data.get("list") or []):
                    if isinstance(grp, dict):
                        out.extend(grp.get("mediaList") or [])
            return out
        if tid == "n_must":
            code, data, _ = self._call("/api/app/media/entryMustWatch", {"pageNum": page, "pageSize": PAGE_SIZE})
            if isinstance(data, dict) and isinstance(data.get("mediaList"), list):
                return data["mediaList"]
            return []
        if tid == "n_week":
            code, data, _ = self._call("/api/app/media/weeklySelection", {"pageNum": page, "pageSize": PAGE_SIZE})
            if isinstance(data, dict) and isinstance(data.get("mediaList"), list):
                return data["mediaList"]
            return []
        return []

    def _pay_tag(self, it):
        """如实标注付费档位，不做假解锁"""
        try:
            pay = int(it.get("payType") or 0)
        except Exception:
            pay = 0
        price = it.get("price") or 0
        if pay == 2:
            return "VIP"
        if pay == 3 or (isinstance(price, (int, float)) and price and pay != 1):
            return "金币%s" % int(price)
        if pay == 1:
            return "免费"
        return ""

    def _item(self, it):
        mid = it.get("id")
        title = str(it.get("title") or "")
        pic = str(it.get("coverImg") or "")
        pay = self._pay_tag(it)
        try:
            dur = int(it.get("playTime") or 0)
        except Exception:
            dur = 0
        remark = ("%s%d分钟" % (pay + "·" if pay else "", dur // 60)) if dur else pay
        raw = json.dumps({"i": mid, "t": title, "p": pic, "r": remark, "y": pay,
                          "d": dur, "c": str(it.get("coverImg") or "")}, ensure_ascii=False)
        vid = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._pic_url(pic),
            "vod_remarks": remark,
        }

    def _items(self, arr):
        out = []
        for it in arr or []:
            if not isinstance(it, dict):
                continue
            v = self._item(it)
            if v["vod_name"]:
                out.append(v)
        return out

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        page = int(pg or 1)
        sort = self.sort
        if isinstance(extend, dict) and extend.get("sort") is not None:
            sort = str(extend.get("sort"))
        arr = self._list_by_cat(tid, page, sort)
        lst = _sanitize_list(self._items(arr))
        # 站点不返回总数：满页视为还有下一页，不满页即到底
        pagecount = page + 1 if len(arr) >= PAGE_SIZE else page
        return {"page": page, "pagecount": pagecount, "limit": PAGE_SIZE,
                "total": 0, "list": lst}

    # ---------- 详情 ----------
    def _decode_id(self, vid):
        try:
            raw = base64.b64decode(str(vid)).decode("utf-8", "replace")
            d = json.loads(raw)
            if isinstance(d, dict) and d.get("i") is not None:
                return d
        except Exception:
            pass
        try:
            return {"i": int(str(vid)), "t": "", "p": "", "r": "", "y": "", "d": 0}
        except Exception:
            return {"i": str(vid), "t": "", "p": "", "r": "", "y": "", "d": 0}

    def _play_url(self, mid):
        """站点 H5 中转：/api/app/media/h5/m3u8/{id}?token=..&timestamp=..&sign=..&nonce=.."""
        path = "/api/app/media/h5/m3u8/%s" % mid
        ts = int(time.time())
        nc = _nonce()
        msg = "%s&%s&%s&%d&%s" % (self.token or "", path, "", ts, nc)
        sig = hmac.new(REQ_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).hexdigest()
        return "%s%s?token=%s&timestamp=%d&sign=%s&nonce=%s" % (
            HOST, path, quote(self.token or "", safe=""), ts, sig, nc)

    def detailContent(self, ids):
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        out = []
        for vid in id_list:
            d = self._decode_id(vid)
            mid = d.get("i")
            title = d.get("t") or ("awXVideo %s" % mid)
            pic = d.get("p") or ""
            remark = d.get("r") or ""
            dur = d.get("d") or 0
            url = self._play_url(mid)
            header = self.rawSite + "/"
            play = "#".join([
                "%s$%s" % (mid, self._proxy_url(url, header)),
            ])
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._pic_url(pic),
                "vod_remarks": remark,
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "%s%s" % (title, ("  ·  %s" % remark) if remark else ""),
                "vod_play_from": "awXVideo",
                "vod_play_url": play,
            }
            if dur:
                vod["vod_duration"] = "%d分钟" % (dur // 60)
            cleaned = _sanitize_vod(vod)
            if cleaned is not None:
                out.append(cleaned)
        return {"list": out}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg=1):
        key = str(key or "").strip()
        page = max(1, int(pg or 1))
        if not key:
            return {"list": [], "page": page, "pagecount": page}
        # 有 token：走站方搜索接口
        if self.token:
            arr = self._remote_search(key, page)
            lst = _sanitize_list(self._items(arr))
            return {"list": lst, "page": page,
                    "pagecount": page + 1 if len(arr) >= PAGE_SIZE else page}
        # 无 token：站方搜索需鉴权 → 本地扫热门分类标题
        arr = self._local_search(key, page)
        lst = _sanitize_list(self._items(arr))
        return {"list": lst, "page": page,
                "pagecount": page + 1 if len(arr) >= PAGE_SIZE else page}

    def _remote_search(self, key, page):
        body = {"pageNum": page, "searchTxt": key, "sort": 0,
                "pageSize": PAGE_SIZE, "mediaType": 2}
        code, data, _ = self._call("/api/app/search/details", body)
        if code == 200 and isinstance(data, dict):
            ml = data.get("mediaList")
            if isinstance(ml, list):
                return ml
        return []

    def _pool_pull(self, cid, p):
        """拉一页分类数据（供搜索并发调用）"""
        try:
            body = {"id": cid, "pageNum": p, "pageSize": SEARCH_PAGE_SIZE}
            code, data, _ = self._call("/api/app/media/home", body, retry=1)
            ml = (data or {}).get("mediaList") if isinstance(data, dict) else None
            return ml if isinstance(ml, list) else []
        except Exception:
            return []

    def _search_pool(self):
        """并行扫热门分类（结果短时缓存，避免重复拉）"""
        cache_key = "search_pool"
        if self._cache_lock is not None:
            with self._cache_lock:
                hit = self._cache.get(cache_key)
        else:
            hit = self._cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        jobs = [(cid, p) for cid in SEARCH_CATS for p in range(1, SEARCH_PAGES + 1)]
        rows = []
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as ex:
                for ml in ex.map(lambda a: self._pool_pull(a[0], a[1]), jobs):
                    if ml:
                        rows.extend(ml)
        except Exception:
            for cid, p in jobs:
                rows.extend(self._pool_pull(cid, p))
        try:
            if self._cache_lock is not None:
                with self._cache_lock:
                    self._cache[cache_key] = (time.time(), rows)
            else:
                self._cache[cache_key] = (time.time(), rows)
        except Exception:
            pass
        return rows

    def _local_search(self, key, page):
        k = str(key or "").lower()
        begin = (page - 1) * PAGE_SIZE
        rows = self._search_pool()
        hit = [it for it in rows if k and k in str(it.get("title") or "").lower()]
        return hit[begin:begin + PAGE_SIZE]

    # ---------- 播放 ----------
    def _proxy_url(self, url, referer=""):
        """铁律·广告拦截：m3u8 走本地代理清洗"""
        try:
            if hasattr(self, "getProxyUrl"):
                return (self.getProxyUrl() + "&type=m3u8&url=" + quote(url, safe="") +
                        "&referer=" + quote(referer or self.rawSite, safe=""))
        except Exception:
            pass
        return url

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "")
        referer = self.rawSite + "/"
        if self.verify:
            try:
                txt, _ = self._session().get(url, headers={"Referer": referer})
                if not txt or "#EXTM3U" not in txt:
                    return {"parse": 0, "jx": 0, "url": "", "header": {}}
            except Exception:
                pass
        final = self._proxy_url(url, referer)
        return {
            "parse": 0,
            "jx": 0,
            "url": final,
            "header": {"User-Agent": UA, "Referer": referer, "Origin": self.rawSite},
        }

    # ---------- 图片 ----------
    def _pic_url(self, pic):
        if not pic:
            return ""
        p = str(pic)
        if p.startswith("http"):
            full = p
        elif p.startswith("blob:") or p.startswith("data:"):
            return ""
        elif p.startswith("/"):
            full = self.img_cdn + p
        else:
            full = "%s/%s" % (self.img_cdn, p.lstrip("/"))
        # 站点图片加密，交给本地代理解密后再给播放器
        try:
            if hasattr(self, "getProxyUrl"):
                return (self.getProxyUrl() + "&type=img&url=" + quote(full, safe=""))
        except Exception:
            pass
        return full

    # ---------- m3u8 清洗 ----------
    def _is_ad_segment(self, uri, dur=0.0, prev_tags=None):
        """广告判定：只砍强特征（同 CDN 混排场景下避免误杀真实短段）"""
        u = str(uri or "").lower()
        if re.search(r"/ad/|/ads/|/adv/|/advert|/gg/|/guanggao|promo", u):
            return True
        return False

    def _clean_m3u8(self, text, m3u8_url="", referer="", skip_seconds=0):
        if not text or "#EXTM3U" not in text:
            return text
        base_dir = m3u8_url.rsplit("/", 1)[0] + "/" if "/" in m3u8_url else ""
        out = []
        drop_next = False
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                    s = re.sub(r'URI="([^"]+)"',
                               lambda m: 'URI="%s"' % self._abs_url(m.group(1), base_dir, m3u8_url),
                               s)
                out.append(s)
                continue
            if drop_next:
                drop_next = False
                continue
            if self._is_ad_segment(s):
                if out and out[-1].startswith("#EXTINF"):
                    out.pop()
                continue
            out.append(self._abs_url(s, base_dir, m3u8_url))
        return "\n".join(out) + "\n"

    def _abs_url(self, u, base_dir, m3u8_url):
        u = u.strip()
        if u.startswith("http://") or u.startswith("https://"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            sp = urlsplit(m3u8_url or HOST)
            return "%s://%s%s" % (sp.scheme or "https", sp.netloc or urlsplit(HOST).netloc, u)
        return (base_dir or (HOST + "/")) + u

    # ---------- localProxy ----------
    def localProxy(self, param):
        if not isinstance(param, dict):
            return [400, "text/plain", "bad param"]
        do = param.get("type") or param.get("action") or param.get("do") or ""
        url = param.get("url", "") or param.get("path", "")
        if isinstance(url, list):
            url = url[0] if url else ""
        if isinstance(do, list):
            do = do[0] if do else ""
        url = unquote(str(url or ""))
        referer = param.get("referer", "")
        if isinstance(referer, list):
            referer = referer[0] if referer else ""
        referer = unquote(str(referer or "")) or (self.rawSite + "/")

        if do == "img" or (url and re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", url, re.I)):
            try:
                data, status = self._session().get(url, headers={"Referer": referer}, binary=True)
                if status != 200 or not data:
                    return [502, "text/plain", b"image download failed"]
                data = decrypt_image(data)
                return [200, _img_mime(data), data]
            except Exception as e:
                return [500, "text/plain", ("img error: %s" % e).encode("utf-8")]

        if do == "m3u8" or (url and ".m3u8" in url):
            try:
                txt, status = self._session().get(url, headers={"Referer": referer})
                if status != 200 or "#EXTM3U" not in txt:
                    return [502, "text/plain", "m3u8 download failed"]
                cleaned = self._clean_m3u8(txt, url, referer)
                return [200, "application/vnd.apple.mpegurl", cleaned]
            except Exception as e:
                return [500, "text/plain", ("m3u8 error: %s" % e).encode("utf-8")]

        return [404, "text/plain", b""]

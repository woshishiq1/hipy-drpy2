# coding=utf-8
"""
玖月影视 rhwf.cn | TVBox Python 爬虫
关键:
  - easy_slide 滑块守卫闭环：piece 原图块带掩码模板匹配定位缺口，RC4(key=guard[:8]) 加密 x"x"y 写 guardret
  - MacCMS style/26 移动模板，pej 前缀路由：详情 /pej/、分类 /pejtype/、筛选 /pejshow/、播放 /pejplay/、搜索 /search/
  - 分类筛选对齐站点：类型 / 字母 / 年份（页面行序），12 段槽位（段0 类型、段4 年份、段5 字母）
  - 简介只留剧情正文：剥评论卡 / 配图 AI 综述 / SEO 堆砌；空走 meta 兜底；固定前缀
  - player_aaaa 括号配平取 JSON，master 首条子流 urljoin；直链 parse:0，不可还原回退 parse:1
  - 主备域名轮换，强制 IPv4
"""
import re
import sys
import json
import time
import base64
import socket
import struct
import zlib
import threading
import urllib.parse

sys.path.append('..')

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# 云端出口 IPv6 不通/国内 IPv6 不稳：强制 IPv4 解析（壳子本地网络正常时不影响）
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        res = _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        v4 = [x for x in res if x[0] == socket.AF_INET]
        return v4 or res
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[rhwf]", *a)
            except Exception:
                pass

        # 离线/老基类无持久化缓存时的空桩，脚本侧 try 兜底跳过
        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "failed"

        def delCache(self, key):
            return "failed"

    Spider = _BaseSpider


# 主备域名（HOSTS 顺序即轮换顺序；www 域偶发 503，根域优先）
HOSTS = ["https://rhwf.cn", "https://www.rhwf.cn"]
HOST = HOSTS[0]
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
DEFAULT_PIC = ""

# 守卫令牌持久化缓存（热启动复用）：过盾成功后落盘，下次启动先读缓存试，失效自动回退重解
_GUARD_CACHE_KEY = "rhwf_guard"
_GUARD_TTL = 1800  # 秒，30 分钟内复用

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航，线上实证）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "9",  "type_name": "短视频"},
    {"type_id": "51", "type_name": "即将上映"},
]

# 筛选维度选项（年份 / 字母，线上实证全量）
_YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
          "2018", "2017", "2016"]
_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
            "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

# 各频道子类型选项（槽0=类型 tid，线上实证）
_TYPE_MAP = {
    "1": [("35", "喜剧片"), ("36", "动作片"), ("37", "爱情片"), ("38", "科幻片"),
          ("39", "恐怖片"), ("40", "剧情片"), ("41", "战争片")],
    "2": [("42", "国产剧"), ("43", "港台剧"), ("44", "日韩剧"), ("45", "欧美剧")],
    "3": [("46", "国内综艺"), ("47", "海外综艺")],
    "4": [("48", "国内动漫"), ("49", "海外动漫")],
    "9": [("57", "动画短片"), ("58", "短剧")],
    "51": [],
}


def _opts(values):
    items = []
    for it in values:
        if isinstance(it, (tuple, list)):
            v, n = it[0], it[1]
        else:
            v = n = it
        items.append({"n": n, "v": v})
    return [{"n": "全部", "v": ""}] + items


def _build_filters(tid):
    dims = []
    types = _TYPE_MAP.get(tid, [])
    if types:
        dims.append({"key": "class", "name": "类型", "value": _opts(types)})
    # 展示顺序对齐站点页面行序：类型 → 字母 → 年份（URL 槽位仍为段4年份、段5字母）
    dims.append({"key": "letter", "name": "字母", "value": _opts(_LETTERS)})
    dims.append({"key": "year", "name": "年份", "value": _opts(_YEARS)})
    return dims


FILTERS = {c["type_id"]: _build_filters(c["type_id"]) for c in CLASSES}

# ===================== 正则 =====================
# 卡片列表
_RE_HREF = re.compile(r'href="(/pej/\d+\.html)"', re.I)
_RE_IMG = re.compile(r'<img[^>]*>', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_DSRC = re.compile(r'data-src="([^"]*)"', re.I)
_RE_SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
_RE_NAME6 = re.compile(r'<div[^>]*class="ys-name6"[^>]*>([\s\S]*?)</div>', re.I)
_RE_FILMNAME = re.compile(r'<div[^>]*class="filmName"[^>]*>([\s\S]*?)</div>', re.I)
_RE_CARD = re.compile(r'<a[^>]*href="/pej/\d+\.html"[\s\S]*?</a>', re.I)

# 详情字段
_RE_H1 = re.compile(r'<div[^>]*class="ys-name18"[^>]*>([\s\S]*?)</div>', re.I)
_RE_YEAR1 = re.compile(r'<div[^>]*class="year1"[^>]*>([\s\S]*?)</div>', re.I)
_RE_ACTOR = re.compile(r'<div[^>]*class="main-actors2"[^>]*>([\s\S]*?)</div>', re.I)
_RE_STYLE = re.compile(r'<div[^>]*class="ys-style8"[^>]*>([\s\S]*?)</div>', re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SPAN = re.compile(r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_MORE = re.compile(r'<span[^>]*class="more-actor"[^>]*>[\s\S]*?</span>', re.I)
_RE_POSTER = re.compile(r'<a[^>]*class="poster5"[^>]*>([\s\S]*?)</a>', re.I)

# 简介（多层兜底）
_RE_INTRO_P = re.compile(r'Synopsis-word[\s\S]*?<p[^>]*>([\s\S]*?)</p>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路 / 选集（标题块 + 紧跟选集块）
_RE_LINE_TITLE = re.compile(
    r'<div[^>]*class="list-name23"[^>]*>([\s\S]*?)</div>\s*</div>', re.I)
_RE_LINE_NAME = re.compile(r'<div[^>]*class="name17"[^>]*>([\s\S]*?)</div>', re.I)
_RE_EP_BLOCK = re.compile(r'<div[^>]*class="list-number1"[^>]*>([\s\S]*?)</div>', re.I)
_RE_EP = re.compile(r'href="(/pejplay/[^"]+)"[^>]*>\s*<div[^>]*>([\s\S]*?)</div>', re.I)

# 分页 / 总页：pager2 块内 <span class="now">1</span>/<span class="total">133</span>
_RE_SEARCH_PAGE = re.compile(r'/search/[^"]*?-(\d+)-+\.html', re.I)
_RE_TYPE_PAGE = re.compile(r'/pejtype/[^"]*-(\d+)\.html', re.I)
_RE_SHOW_PAGE = re.compile(r'/pejshow/[^"]*-(\d+)\.html', re.I)
_RE_TOTAL = re.compile(r'<span class="now">\d+</span>/<span class="total">(\d+)</span>', re.I)


# ===================== 守卫：RC4 / PNG 解码 / 缺口定位 =====================
def _rc4(data, key):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + ord(key[i % len(key)])) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for b in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(b ^ S[(S[i] + S[j]) % 256])
    return bytes(out)


def _decode_png(data):
    """纯标准库解码调色板索引 PNG(非隔行, 8bit colortype 3) → (W,H,plte,trns,img)。"""
    off = 8
    idat = b""
    plte = []
    trns = set()
    W = H = 0
    while off < len(data):
        ln = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8].decode("latin1")
        ch = data[off + 8:off + 8 + ln]
        if typ == "IHDR":
            W, H, bd, ct, _, _, _ = struct.unpack(">IIBBBBB", ch)
        elif typ == "PLTE":
            plte = [tuple(ch[i:i + 3]) for i in range(0, len(ch), 3)]
        elif typ == "tRNS":
            trns = set(ch)
        elif typ == "IDAT":
            idat += ch
        elif typ == "IEND":
            break
        off += 12 + ln
    raw = zlib.decompress(idat)
    stride = W
    prev = [0] * stride
    img = []
    pos = 0
    for y in range(H):
        f = raw[pos]
        pos += 1
        row = list(raw[pos:pos + stride])
        pos += stride
        for x in range(stride):
            a = row[x]
            left = row[x - 1] if x >= 1 else 0
            up = prev[x]
            ul = prev[x - 1] if x >= 1 else 0
            if f == 1:
                row[x] = (a + left) & 255
            elif f == 2:
                row[x] = (a + up) & 255
            elif f == 3:
                row[x] = (a + ((left + up) >> 1)) & 255
            elif f == 4:
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else ul)
                row[x] = (a + pr) & 255
        img.append(row)
        prev = row
    return W, H, plte, trns, img


def _png_feat(plte, trns, img, x, y):
    i = img[y][x]
    if i in trns:
        return None
    r, g, b = plte[i]
    return ((r + g + b) / 3.0, max(r, g, b) - min(r, g, b))


def _gap_x_pure(data, gw, k_sat=0.6):
    """纯标准库兜底：piece 形状掩码约束下, 背景窄带内找暗/低饱和拼图块, 返回缺口 x。"""
    W, H, plte, trns, img = _decode_png(data)
    xs = [x for y in range(H) for x in range(345, W) if img[y][x] not in trns]
    ys = [y for y in range(H) for x in range(345, W) if img[y][x] not in trns]
    if not xs:
        return 0
    px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
    mask = [(y - py0, x - px0) for y in range(py0, py1 + 1)
            for x in range(px0, px1 + 1) if img[y][x] not in trns]
    tw = px1 - px0 + 1
    BG = [[_png_feat(plte, trns, img, x, y) for x in range(340)] for y in range(H)]
    y0 = max(0, gw)
    best = (1e18, 0)
    for x in range(0, max(1, 340 - tw)):
        lum, sat, n = 0.0, 0.0, 0
        for dy, dx in mask:
            by, bx = y0 + dy, x + dx
            if by < H and bx < 340 and BG[by][bx]:
                lum += BG[by][bx][0]
                sat += BG[by][bx][1]
                n += 1
        if n == 0:
            continue
        score = lum / n + k_sat * sat / n
        if score < best[0]:
            best = (score, x)
    return best[1]


def _gap_x_cv2(data, gw):
    """运行环境有 cv2/numpy 时: 右侧 piece 浮层即从背景原位抠出的原图块,
    带掩码在左半背景做归一化相关匹配, 相关系数最高处即缺口原位。不可用返回 None。"""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    try:
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.shape[2] == 4:
            b, g, bl, al = cv2.split(img)
            bgra = cv2.merge([b, g, bl])
        else:
            bgra = img[:, :, :3]
            al = np.full(img.shape[:2], 255, np.uint8)
        pm = al[:, 345:] > 20
        ys, xs = np.where(pm)
        if len(xs) == 0:
            return None
        px0, px1, py0, py1 = xs.min(), xs.max(), ys.min(), ys.max()
        mask = (pm[py0:py1 + 1, px0:px1 + 1].astype(np.uint8)) * 255
        tpl = bgra[py0:py1 + 1, 345 + px0:345 + px1 + 1]
        bg = bgra[:, :340]
        res = cv2.matchTemplate(bg, tpl, cv2.TM_CCOEFF_NORMED, mask=mask)
        _, _, _, ml = cv2.minMaxLoc(res)
        return ml[0]
    except Exception:
        return None


class Spider(Spider):

    def getName(self):
        return "rhwf.cn"

    def getDependence(self):
        # 框架 init 阶段反射调用（app.getDependence → ru.getDependence）；
        # 本脚本无额外依赖模块，返回空列表，避免属性缺失在初始化窗口抛异常。
        return []

    def log(self, *a, **kw):
        # 壳子基类 log 为单参签名，多参调用需在此拼接一行，避免 TypeError 吞掉成功路径
        try:
            print("[rhwf]", " ".join(str(x) for x in a))
        except Exception:
            pass

    def init(self, extend=""):
        # 初始化只做本地字段装配，不在此发网络请求：
        # init 在框架单例缓存(computeIfAbsent)窗口内同步执行，一旦在此抛异常，
        # 实例会被永久缓存成空壳 SpiderNull，后续分类/首页请求不再重试 init；
        # 会话与过盾推迟到首次列表请求惰性建立，遇壳由 _http_get 自愈重放。
        try:
            try:
                self.extend = json.loads(extend) if extend else {}
            except Exception:
                self.extend = {}
            self.hosts = list(self.extend.get("hosts") or HOSTS)
            self.host_idx = 0
            self.site_url = (self.extend.get("site") or self.hosts[0]).rstrip("/")
            self.headers = {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": self.site_url + "/",
                "Upgrade-Insecure-Requests": "1",
            }
            self.default_pic = DEFAULT_PIC
            self._play_cache = {}
            # 守卫会话：自建 session 保留 guard/guardret Cookie；基类 fetch 不持 jar, 双保险写请求头
            self._guard_session = None
            self._guard_cookie = ""
            self._guard_ok = False
            self._guard_lock = threading.Lock()
            # 热启动：先回填持久化的守卫令牌，失效/不可用则跳过，后续遇壳再解
            self._cache_load()
        except Exception as e:
            self.log("init 初始化异常(已兜底, 不阻断)", e)

    def _switch_host(self):
        """主备域名轮换：切到下一 host，清守卫会话与 Cookie，后续请求重解盾。"""
        if len(self.hosts) <= 1:
            return False
        self.host_idx = (self.host_idx + 1) % len(self.hosts)
        self.site_url = self.hosts[self.host_idx].rstrip("/")
        self.headers["Referer"] = self.site_url + "/"
        self._guard_session = None
        self._guard_cookie = ""
        self._guard_ok = False
        self._cache_clear()
        self.headers.pop("Cookie", None)
        self.log("切换域名 →", self.site_url)
        return True

    # ---------------- 守卫会话 ----------------
    def _guard_sess(self):
        if self._guard_session is None:
            try:
                import requests as rq
                sess = rq.Session()
                sess.verify = False
                adapter = rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                sess.mount('https://', adapter)
                sess.mount('http://', adapter)
            except Exception:
                sess = None
            self._guard_session = sess
        return self._guard_session

    def _cache_load(self):
        """从持久化缓存回填守卫 Cookie；host 不符/过期/代理不可用则跳过，不阻断。"""
        try:
            data = self.getCache(_GUARD_CACHE_KEY)
            if not isinstance(data, dict):
                return False
            if data.get("host") != self.site_url:
                return False
            ck = data.get("cookies") or {}
            if not ck:
                return False
            sess = self._guard_sess()
            if sess is not None:
                for k, v in ck.items():
                    sess.cookies.set(k, v, path="/")
            self._guard_cookie = (data.get("cookie_header")
                                  or "; ".join("%s=%s" % (k, v) for k, v in ck.items()))
            self._guard_ok = True
            self.log("守卫令牌缓存已复用")
            return True
        except Exception as e:
            self.log("缓存读跳过", e)
            return False

    def _cache_save(self):
        """过盾成功后持久化守卫令牌；代理不可用则跳过，不阻断。"""
        try:
            sess = self._guard_session
            ck = sess.cookies.get_dict() if sess is not None else {}
            if not ck:
                return
            data = {
                "host": self.site_url,
                "cookies": ck,
                "cookie_header": self._guard_cookie,
                "expiresAt": int(time.time()) + _GUARD_TTL,
            }
            self.setCache(_GUARD_CACHE_KEY, data)
        except Exception as e:
            self.log("缓存写跳过", e)

    def _cache_clear(self):
        """清除持久化守卫令牌（切域/令牌失效时调用）。"""
        try:
            self.delCache(_GUARD_CACHE_KEY)
        except Exception:
            pass

    @staticmethod
    def _is_shell(text, status=200):
        if not text or len(text) < 80:
            return True
        try:
            if status and int(status) != 200:
                return True
        except Exception:
            pass
        return "_guard/html.js" in text

    def _solve_guard(self, retries=3):
        """解滑块守卫：加锁串行，单轮失败换图重试；成功返回 True。"""
        with self._guard_lock:
            for attempt in range(retries):
                try:
                    if self._solve_once():
                        return True
                except Exception as e:
                    self.log("守卫求解异常", e)
                if attempt < retries - 1:
                    time.sleep(0.8)
        self._guard_ok = False
        return False

    def _solve_once(self):
        """单轮：首访落会话→取拼图→识别缺口→RC4 种 guardret→验证放行。"""
        sess = self._guard_sess()
        h = dict(self.headers)
        # 1. 首访落会话 Cookie
        if sess is not None:
            sess.get(self.site_url + "/", headers=h, timeout=(10, 20))
            rp = sess.get(self.site_url + "/_guard/easy_slide.png?t=%d" % int(time.time() * 1000),
                          headers=dict(h, Referer=self.site_url + "/"), timeout=(10, 20))
            body = rp.content
            ck = sess.cookies.get_dict()
        else:
            self.fetch(self.site_url + "/", headers=h, timeout=(10, 20))
            rp = self.fetch(self.site_url + "/_guard/easy_slide.png?t=%d" % int(time.time() * 1000),
                            headers=dict(h, Referer=self.site_url + "/"), timeout=(10, 20))
            body = rp.content
            ck = {}
            for c in getattr(rp, "cookies", []):
                ck[c.name] = c.value
        guard = ck.get("guard", "")
        guardword = ck.get("guardword", "")
        if not guard or not guardword:
            self.log("守卫缺 guard/guardword")
            return False
        gw = int(guardword)

        gx = _gap_x_cv2(body, gw)
        if gx is None:
            gx = _gap_x_pure(body, gw)
        gx = int(round(gx))
        gy = gw

        secret = guard[:8]
        plain = ("%dx%d" % (gx, gy)).encode("utf-8")
        guardret = base64.b64encode(_rc4(plain, secret)).decode("utf-8")
        ck["guardret"] = guardret

        if sess is not None:
            sess.cookies.set("guardret", guardret, path="/")
            sess.cookies.set("guard", guard, path="/")
            sess.cookies.set("guardword", guardword, path="/")
        self._guard_cookie = "; ".join("%s=%s" % (k, v) for k, v in ck.items())

        # 验证一次
        if sess is not None:
            rv = sess.get(self.site_url + "/", headers=dict(h, Referer=self.site_url + "/"),
                          timeout=(10, 20))
            ok = not self._is_shell(rv.text, getattr(rv, "status_code", 200))
        else:
            rv = self.fetch(self.site_url + "/", headers=dict(h, Referer=self.site_url + "/"),
                            timeout=(10, 20))
            ok = not self._is_shell(rv.text)
        self._guard_ok = ok
        if ok:
            self._cache_save()
        self.log("守卫求解 gx=%d gw=%d 放行=%s" % (gx, gy, ok))
        return ok

    def _http_get(self, url, headers=None, timeout=15):
        """本站 GET：优先守卫 session 复用 Cookie；遇壳重解后重放一次。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._guard_sess()
        rsp = None
        try:
            if sess is not None:
                rsp = sess.get(url, headers=h, timeout=timeout)
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("GET 异常", url, e)
            rsp = None
        text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200) if rsp is not None else 0

        if self._is_shell(text, status):
            self.log("遇守卫壳, 重新求解")
            for _ in range(2):
                if not self._solve_guard():
                    break
                try:
                    if sess is not None:
                        # 有守卫 session：Cookie 由 jar 自动携带，不再发手工头避免覆盖
                        rsp = sess.get(url, headers=h, timeout=timeout)
                    else:
                        h["Cookie"] = self._guard_cookie
                        rsp = self.fetch(url, headers=h, timeout=timeout)
                    text = rsp.text if hasattr(rsp, "text") else ""
                    status = getattr(rsp, "status_code", 200)
                except Exception as e:
                    self.log("重放异常", e)
                    text, status = "", 0
                    break
                if not self._is_shell(text, status):
                    break
                self.log("重放仍为壳, 再次求解")
        return rsp

    def _fetch(self, url, headers=None, tries=3):
        last = ""
        for attempt in range(tries):
            try:
                rsp = self._http_get(url, headers=headers, timeout=(10, 30))
                status = getattr(rsp, "status_code", 200) if rsp is not None else 0
                text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
                if not self._is_upstream_error(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, e)
                last = ""
            if attempt < tries - 1:
                if self._switch_host():
                    url = self._rebase_url(url)
                time.sleep(1.2)
        return last

    @staticmethod
    def _is_upstream_error(text, status=200):
        if not text or len(text) < 200:
            return True
        try:
            if status and int(status) != 200:
                return True
        except Exception:
            pass
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "error code", "web server is down"))

    # ---------------- 基础工具 ----------------
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _rebase_url(self, url):
        """域名轮换后，把绝对 URL 的 scheme/netloc 替换为当前 site_url 域。"""
        if not url or not url.startswith("http"):
            return self._fix_url(url)
        try:
            parts = urllib.parse.urlsplit(url)
            base = urllib.parse.urlsplit(self.site_url)
            return urllib.parse.urlunsplit((
                base.scheme, base.netloc, parts.path, parts.query, parts.fragment))
        except Exception:
            return url

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = _RE_MORE.sub("", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    @staticmethod
    def _is_placeholder_pic(pic):
        if not pic:
            return True
        low = pic.lower()
        return any(k in low for k in ("load1.png", "load.png", "blank", "logo",
                                      "placeholder", "default", "loading"))

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for block in _RE_CARD.findall(html):
            mh = _RE_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            seen.add(href)

            # 片名：img alt 优先（全名），div.filmName / div.ys-name6 文本兜底
            name = ""
            mi = _RE_IMG.search(block)
            if mi:
                ma = _RE_ALT.search(mi.group(0))
                if ma:
                    name = self._clean(ma.group(1))
            if not name:
                mt = _RE_FILMNAME.search(block) or _RE_NAME6.search(block)
                if mt:
                    name = self._clean(mt.group(1))
            if not name:
                continue

            pic = ""
            if mi:
                md = _RE_DSRC.search(mi.group(0))
                if md:
                    pic = md.group(1)
                if not pic:
                    ms = _RE_SRC.search(mi.group(0))
                    if ms:
                        pic = ms.group(1)
            if self._is_placeholder_pic(pic):
                pic = ""

            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
                "vod_score": "",
            })
        return videos

    # ---------------- 列表 / 搜索 URL ----------------
    def _list_url(self, tid, extend, page=1):
        extend = extend or {}
        def _val(k):
            v = (extend.get(k) or "").strip()
            return "" if v in ("全部", "none") else v
        cls = _val("class")
        year = _val("year")
        letter = _val("letter")
        page = int(page) if page else 1
        slot0 = cls or tid
        if not any([cls, year, letter]) and page <= 1:
            return "%s/pejtype/%s.html" % (self.site_url, tid)
        if any([cls, year, letter]):
            seg = [slot0, "", "", "", year, letter, "", "", "", "", "", ""]
            seg = "-".join(urllib.parse.quote(x) if not x.isascii() else x for x in seg)
            return "%s/pejshow/%s.html" % (self.site_url, seg)
        return "%s/pejtype/%s-%d.html" % (self.site_url, slot0, page)

    def _page_count(self, html, page):
        if not html:
            return 1
        # 优先分页块内 span.total（当前页/总页）；无分页块再兜底页码链接
        mt = _RE_TOTAL.search(html)
        if mt:
            return max(1, int(mt.group(1)))
        pages = [int(x) for x in _RE_TYPE_PAGE.findall(html)]
        pages += [int(x) for x in _RE_SHOW_PAGE.findall(html)]
        pages += [int(x) for x in _RE_SEARCH_PAGE.findall(html)]
        return max(pages) if pages else max(1, page)

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            # 空列表兜底：疑似撞壳/未解盾导致，清守卫态重解重拉一次（与分类对齐）
            if not videos:
                self.log("  首页为空, 清守卫态重拉一次")
                self._guard_session = None
                self._guard_cookie = ""
                self._guard_ok = False
                html = self._fetch(self.site_url + "/")
                self.log("  重拉 HTML 长度: %d" % len(html))
                videos = self._parse_cards(html)
            return {"list": videos}
        except Exception as e:
            self.log("homeVideoContent 异常", e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            extend = extend or {}

            url = self._list_url(tid, extend, page)
            self.log("category: %s" % url)
            html = self._fetch(url)
            self.log("  HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            # 空列表兜底：疑似撞壳/未解盾导致，清守卫态重解重拉一次
            if not videos:
                self.log("  列表为空, 清守卫态重拉一次")
                self._guard_session = None
                self._guard_cookie = ""
                self._guard_ok = False
                html = self._fetch(url)
                self.log("  重拉 HTML 长度: %d" % len(html))
                videos = self._parse_cards(html)
            pagecount = self._page_count(html, page)
            self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": 36, "total": pagecount * 36,
            }
        except Exception as e:
            self.log("categoryContent 异常", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 36, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            kw = urllib.parse.quote(str(key or "").strip())
            if page <= 1:
                url = "%s/search/%s-------------.html" % (self.site_url, kw)
            else:
                url = "%s/search/%s--%d-----------.html" % (self.site_url, kw, page)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._parse_cards(html)
            pagecount = self._page_count(html, page)
            self.log("  搜索: %d 条, 总页数: %d" % (len(videos), pagecount))
            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": 30, "total": pagecount * 30,
            }
        except Exception as e:
            self.log("searchContent 异常", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _extract_intro(self, html):
        """提取剧情正文：剥离网友评论卡、配图 AI 综述段、相关搜索 SEO 堆砌；
        普通 <p> 正文保留，综述 p 之后吐出的裸摘要丢弃，前置占位文本保留。
        bs4 不可用时回退首段正则。"""
        if BeautifulSoup is not None:
            try:
                soup = BeautifulSoup(html, "html.parser")
                box = soup.find(class_="Synopsis-word")
                if box is None:
                    return ""
                # 1) 剥离网友评论卡（背景/渐变/圆角样式或含“网友评论”）
                for tag in list(box.find_all(True)):
                    style = ((tag.attrs or {}).get("style") or "").lower()
                    txt = tag.get_text()
                    if ("网友评论" in txt) or any(
                            k in style for k in ("background", "linear-gradient", "border-radius")):
                        tag.decompose()
                # 2) 先扫描含配图的 AI 综述段（剥 img 前打标），再剥图片/SEO 链接
                review_ps = set()
                for p in box.find_all("p"):
                    if p.find("img"):
                        review_ps.add(id(p))
                for img in box.find_all("img"):
                    img.decompose()
                for a in box.find_all("a"):
                    a.decompose()
                # 3) 按 DOM 顺序收集正文：综述 p 后裸摘要丢弃，普通正文/前置占位保留
                parts = []
                after_review = False
                for ch in box.children:
                    nm = getattr(ch, "name", None)
                    if nm is None:
                        t = self._clean(str(ch))
                        if t and not after_review:
                            parts.append(t)
                        continue
                    if nm not in ("p", "div"):
                        continue
                    if id(ch) in review_ps:
                        after_review = True
                        continue
                    style = ((ch.attrs or {}).get("style") or "").lower()
                    if any(k in style for k in ("background", "linear-gradient", "border-radius")):
                        continue
                    t = self._clean(ch.get_text())
                    if t:
                        after_review = False
                        parts.append(t)
                txt = "\n".join(parts)
                txt = re.split(r"相关搜索[:：]", txt)[0]
                return txt.strip()
            except Exception as e:
                self.log("简介解析异常", e)
        mf = _RE_INTRO_P.search(html)
        return self._clean(mf.group(1)) if mf else ""

    def _info_field(self, html, label):
        """在 main-actors2 / ys-style8 块中提取指定标签后的链接文本(逗号拼接)。"""
        for blk in list(_RE_ACTOR.finditer(html)) + list(_RE_STYLE.finditer(html)):
            seg = blk.group(1)
            if ("%s：" % label) not in seg and ("%s:" % label) not in seg:
                continue
            after = re.split(r'%s[：:]' % re.escape(label), seg, 1)[-1]
            links = [self._clean(a) for a in _RE_A.findall(after)]
            links = [x for x in links if x]
            if links:
                return ",".join(links)
            sp = _RE_SPAN.search(after)
            if sp:
                return self._clean(sp.group(1))
            return self._clean(after)
        return ""

    def _parse_lines(self, html):
        """线路分组保 DOM 顺序：name17 标题就近配对其后的 list-number1 选集块；
        演员表/资讯/推荐等复用 name17 但无选集块, 自然不落盘。"""
        html = re.sub(r"<style[\s\S]*?</style>", "", html)
        html = re.sub(r"<script[\s\S]*?</script>", "", html)

        tokens = []
        for m in _RE_LINE_NAME.finditer(html):
            tokens.append((m.start(), "title", self._clean(m.group(1))))
        for m in _RE_EP.finditer(html):
            tokens.append((m.start(), "ep", (m.group(1), self._clean(m.group(2)))))
        tokens.sort(key=lambda t: t[0])

        play_from, play_url = [], []
        cur_line = None
        cur_eps = []
        for _, kind, payload in tokens:
            if kind == "title":
                if cur_line and cur_eps:
                    play_from.append(cur_line)
                    play_url.append("#".join("%s$%s" % (n, h) for n, h in cur_eps))
                cur_line, cur_eps = payload, []
            else:
                if cur_line is None:
                    continue
                href, ep_name = payload
                if not ep_name:
                    ep_name = "第%02d集" % (len(cur_eps) + 1)
                cur_eps.append((ep_name, href))
        if cur_line and cur_eps:
            play_from.append(cur_line)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in cur_eps))
        return play_from, play_url

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 片名
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
            if not name:
                mt = re.search(r"<title>(.*?)</title>", html, re.S)
                if mt:
                    name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        except Exception:
            pass
        name = name or vod_id

        # 海报
        pic = ""
        try:
            mp = _RE_POSTER.search(html)
            if mp:
                mi = _RE_DSRC.search(mp.group(1)) or _RE_SRC.search(mp.group(1))
                if mi:
                    pic = mi.group(1)
        except Exception:
            pass
        if self._is_placeholder_pic(pic):
            pic = ""
        pic = self._fix_url(pic) or self.default_pic

        # 简介：Synopsis-word 正文（剥评论/综述/SEO）优先，meta description 兜底
        content = ""
        try:
            content = self._extract_intro(html)
        except Exception:
            content = ""
        if not content:
            try:
                mm = _RE_META_DESC.search(html)
                if mm:
                    content = self._clean(mm.group(1))
            except Exception:
                pass
        content = re.sub(r"^(?:影片介绍|简介|剧情介绍)\s*[:：]?\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        actor = director = classify = area = ""
        try:
            actor = self._info_field(html, "主演")
        except Exception:
            pass
        try:
            director = self._info_field(html, "导演")
        except Exception:
            pass
        try:
            classify = self._info_field(html, "类型")
        except Exception:
            pass
        try:
            area = self._info_field(html, "地区")
        except Exception:
            pass

        # 更新时间（副标兜底）
        remarks = ""
        try:
            my = _RE_YEAR1.search(html)
            if my:
                upd = self._clean(my.group(1))
                if upd:
                    remarks = "更新：" + upd
        except Exception:
            pass

        # 线路与选集（保 DOM 顺序）
        play_from, play_url = self._parse_lines(html)
        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": area,
            "vod_year": "",
            "vod_classify": classify,
            "type_name": classify,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        html = self._fetch(play_page, headers=header)
        stream = self._extract_stream(html)

        if stream:
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    @staticmethod
    def _player_json(html):
        """括号深度配对精确截取 player_aaaa JSON（正确处理嵌套对象）。"""
        i = html.find("player_aaaa")
        if i < 0:
            return ""
        j = html.find("{", i)
        if j < 0:
            return ""
        depth, instr, esc = 0, False, False
        for k in range(j, len(html)):
            c = html[k]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                instr = not instr
                continue
            if instr:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return html[j:k + 1]
        return ""

    def _extract_stream(self, html):
        if not html:
            return ""
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw.replace("\\/", "/"))
                if str(aa.get("encrypt", "0")) not in ("0", ""):
                    return ""
                if aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    return m2.group(1).replace("\\/", "/")
        m2 = re.search(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', html, re.I)
        return m2.group(0) if m2 else ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率：取首条子 m3u8 并 urljoin；已是含分片媒体列表/mp4 原样返回。"""
        if not url or ".mp4" in url.lower():
            return url

        def _get(target):
            last = None
            for _ in range(2):
                try:
                    rs = self.fetch(target, headers=header, timeout=10)
                    if getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?"))
                except Exception as e:
                    last = e
            return None, last

        try:
            rm, err = _get(url)
            if err is not None:
                self.log("  master 拉取重试后失败: %s" % err)
                return url
            text = rm.text if hasattr(rm, "text") else (
                rm.content.decode("utf-8", "ignore") if hasattr(rm, "content") else "")
            if "#EXT-X-STREAM-INF" not in text:
                return url
            lines = [ln.strip().replace("\\/", "/") for ln in text.splitlines()]
            for i, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF"):
                    if i + 1 < len(lines):
                        sub = lines[i + 1].strip()
                        if sub and not sub.startswith("#"):
                            sub = urllib.parse.urljoin(url, sub)
                            rs, sub_err = _get(sub)
                            if rs is not None:
                                self.log("  master 解析子流 %s" % sub[:120])
                                return sub
                            self.log("  子流重试后失败: %s" % sub_err)
                            break
        except Exception as e:
            self.log("  子流解析回退: %s" % e)
        return url

    # ---------------- 其余契约 ----------------
    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"})
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, rsp.content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._play_cache = {}

    def close(self):
        self.destroy()

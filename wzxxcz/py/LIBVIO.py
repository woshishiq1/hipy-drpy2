# coding=utf-8
"""
LIBVIO libvio.io | TVBox Python 爬虫 
关键机关(全部死磕源码+实测破解):
  1. CDN 盾: JS PoW 挑战(403) → sha256(SIG+nonce) 前缀匹配 DIFF
     → 同一 TCP 连接带 __cdn_pow 重放 → 302 下发 __cdn_verified(30 分钟通行证)
     ⚠️ 挑战/重放/通行证全部绑定同一 TLS 连接 — 必须单连接复用(标准库 http.client)
  2. maccms.url = www.libvio.me(io 域为当前主站, 双域备援)
  3. show 12 段路由: page 在索引 8、year 在索引 11(与豆花系完全同款)
  4. 搜索 5 秒频率限制("请不要频繁操作"提示页 → 等待重试)
  5. 播放: player_aaaa(encrypt=3) → from=yd189 线路 url 为密文
     → /vid/yd.php 页面 LIBVIO_YD_CFG.parseUrl(服务端签名) → GET 返回 JSON 真实直链
     from=kuake/xunlei2 等网盘线路为明文网盘链接 → parse:1 交壳子嗅探
  6. 设备端铁律: 全标准库(无 requests/cv2), init 零网络零线程, homeContent 纯本地
"""
import re
import sys
import json
import time
import gzip
import ssl
import base64
import hashlib
import threading
import http.client
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    class _BaseSpider:
        def log(self, *a, **kw):
            try:
                print("[libvio]", *a)
            except Exception:
                pass

        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "failed"

        def delCache(self, key):
            return "failed"

    Spider = _BaseSpider


HOST = "https://www.libvio.io"
HOSTS = ["https://www.libvio.io", "https://www.libvio.me"]
UA = ("Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点导航 + 首页板块, 线上实证） =====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "剧集"},
    {"type_id": "4",  "type_name": "番剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "15", "type_name": "日韩"},
    {"type_id": "16", "type_name": "欧美"},
]

_YEARS = [str(y) for y in range(2026, 2014, -1)]  # 2026..2015(站点筛选实测)

# 各频道筛选维度（剧情/地区/年份, 逐项对齐站点 screenbox 实测值）
_FILTER_MAP = {
    "1": (
        ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
         "犯罪", "动画", "奇幻", "武侠", "冒险"],
        ["中国大陆", "中国香港", "中国台湾", "美国", "法国", "英国",
         "日本", "韩国", "德国", "泰国", "印度", "意大利", "西班牙"],
    ),
    "2": (
        ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
         "奇幻", "剧情", "历史", "经典", "乡村", "情景"],
        ["中国大陆", "中国台湾", "中国香港", "韩国", "日本", "美国",
         "泰国", "英国", "新加坡", "其他"],
    ),
    "4": (
        ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉",
         "校园", "动作", "机战", "运动", "战争", "少年"],
        ["中国", "日本", "欧美", "其他"],
    ),
    "3": (
        ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食",
         "纪实", "曲艺", "生活", "游戏互动", "财经", "求职"],
        ["内地", "港台", "日韩", "欧美"],
    ),
    "15": (
        ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
         "奇幻", "剧情", "历史", "经典", "乡村", "情景"],
        ["日本", "韩国"],
    ),
    "16": (
        ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
         "奇幻", "剧情", "历史", "经典", "乡村", "情景"],
        ["美国", "英国", "德国", "加拿大", "其他"],
    ),
}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


def _build_filters(tid):
    classes, areas = _FILTER_MAP.get(tid, ([], []))
    return [
        {"key": "class", "name": "剧情", "value": _opts(classes)},
        {"key": "area",  "name": "地区", "value": _opts(areas)},
        {"key": "year",  "name": "年份", "value": _opts(_YEARS)},
    ]


FILTERS = {c["type_id"]: _build_filters(c["type_id"]) for c in CLASSES}


# ===================== 正则 =====================
# 列表卡片(stui 模板): thumb a(href,title,data-original) + pic-text(备注) + pic-tag(评分)
_RE_CARD = re.compile(
    r'<a class="stui-vodlist__thumb[^"]*"[^>]*?href="(/detail/\d+\.html)"'
    r'[^>]*?title="([^"]*)"'
    r'[^>]*?data-original="([^"]*)"'
    r'([\s\S]{0,600}?)</a>', re.S | re.I)
_RE_PIC_TEXT = re.compile(r'class="pic-text[^"]*">([^<]*)<', re.I)
_RE_PIC_TAG = re.compile(r'class="pic-tag[^"]*">([^<]*)<', re.I)

# 简易卡片(无 data-original 兜底)
_RE_HREF = re.compile(r'href="(/detail/\d+\.html)"', re.I)

# 分页: <li class="active num"><a>1/267</a></li>
_RE_PAGE = re.compile(r'class="active num"[^>]*>\s*<a[^>]*>\s*(\d+)\s*/\s*(\d+)', re.S | re.I)
_RE_PAGE_LINKS = re.compile(r'/type/\d+-(\d+)\.html', re.I)
_RE_PAGE_SHOW = re.compile(r'/show/[^"]*?-(\d+)(?:-{1,10})\.html', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_META = re.compile(r'<div class="vod-meta">([\s\S]*?)</div>', re.S | re.I)
_RE_META_ITEM = re.compile(r'<span class="meta-item">([^<]*)</span>', re.I)
_RE_ACTOR = re.compile(r'主演：([^<]*)</span>', re.I)
_RE_DIRECTOR = re.compile(r'导演：([^<]*)</span>', re.I)
_RE_SCORE = re.compile(r'class="score">([\d.]+)分', re.I)
_RE_POSTER = re.compile(r'id="js-poster-img"[^>]*?(?:data-original|src)="([^"]+)"', re.I)
_RE_POSTER_BG = re.compile(r'id="js-backdrop"[^>]*?data-src="([^"]+)"', re.I)
_RE_DESC = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.S | re.I)
_RE_DESC2 = re.compile(r'<span class="detail-sketch">([\s\S]*?)</span>', re.S | re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([^<]*)</title>', re.I)

# 线路面板(排除 netdisk 网盘面板): <h3>线路名</h3> ... <ul class="stui-content__playlist...">
_RE_PANEL = re.compile(
    r'<h3>([^<]{1,24}播放[^<]{0,10})</h3>'
    r'(?:(?!<h3>)[\s\S])*?'
    r'<ul class="stui-content__playlist[^"]*">([\s\S]*?)</ul>', re.I)
_RE_EP = re.compile(r'<a href="(/w/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>', re.I)

# 播放页
_RE_PLAYER_AA = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</', re.I)
_RE_VID_IFRAME = re.compile(r'<iframe[^>]*src="(/vid/[a-z0-9_]+\.php\?[^"]+)"', re.I)
_RE_PARSE_CFG = re.compile(r'window\.LIBVIO_\w+_CFG\s*=\s*(\{[\s\S]*?\});\s*<', re.I)
_RE_PARSE_URL = re.compile(r'"parseUrl"\s*:\s*"([^"]+)"', re.I)

# 搜索频率限制提示
_RE_SEARCH_LIMIT = re.compile(r'请不要频繁操作|搜索时间间隔', re.I)


# ===================== 标准库网络层（设备端零第三方依赖·单连接过盾） =====================
# CDN 盾机制(实测): 403 挑战页 → sha256(SIG+nonce) 前缀=DIFF → 同一 TCP 连接
# 带 __cdn_pow 重放 → 302 + Set-Cookie __cdn_verified(30 分钟) → 该连接内放行。
# 挑战/重放/通行证全部绑定同一 TLS 连接 → 必须单连接复用 + 断线自动重过盾。
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class _Net(object):
    """单连接会话: 同一 TLS 连接跑全部请求, 403 自动 PoW 过盾, 断线重连重过盾。
    自动吸收全部响应 Set-Cookie(__cdn_verified / _lvs 等)并在后续请求携带 —
    parse_yd.php 需要 yd.php 下发的 _lvs 会话 Cookie 才返回真实直链(否则 notice 诱饵)。"""

    def __init__(self, host):
        self.host = host
        self.conn = None
        self.cookies = {}     # 全部会话 cookie(全站同域, 统一携带)
        self.lock = threading.RLock()  # 壳子可能并发调用接口(清缓存重入), 防连接串线

    def _newconn(self):
        self.conn = http.client.HTTPSConnection(
            self.host, context=_SSL_CTX, timeout=30)
        self.cookies = {}

    def _absorb(self, sc_header):
        """吸收 Set-Cookie(支持多条, 仅取 kv 部分)。"""
        if not sc_header:
            return
        try:
            lines = sc_header if isinstance(sc_header, list) else [sc_header]
            for line in lines:
                kv = line.split(";", 1)[0]
                k, _, v = kv.partition("=")
                k = k.strip()
                if k:
                    self.cookies[k] = v.strip()
        except Exception:
            pass

    def close(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass
        self.conn = None

    def _send(self, path, referer=None):
        c = self.conn
        c.putrequest("GET", path, skip_accept_encoding=True)
        for k, v in (("User-Agent", UA),
                     ("Accept-Encoding", "gzip, deflate"),
                     ("Accept", "text/html,application/xhtml+xml,*/*;q=0.8"),
                     ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
                     ("Connection", "keep-alive")):
            c.putheader(k, v)
        if referer:
            c.putheader("Referer", referer)
        if self.cookies:
            try:
                c.putheader("Cookie", "; ".join(
                    "%s=%s" % (k, v) for k, v in self.cookies.items()))
            except Exception:
                pass
        c.endheaders()
        r = c.getresponse()
        data = r.read()
        try:
            if (r.getheader("Content-Encoding") or "").lower() == "gzip":
                data = gzip.decompress(data)
        except Exception:
            pass
        try:
            self._absorb(r.msg.get_all("Set-Cookie"))
        except Exception:
            self._absorb(r.getheader("Set-Cookie"))
        return (r.status, r.getheader("Location") or "",
                data.decode("utf-8", "ignore"), "")

    def _solve_pow(self, html):
        """解 PoW: sha256(SIG+nonce) 前缀=DIFF, 期望 ~65536 次, Python <1s。"""
        try:
            m_ts = re.search(r'\bTS\s*=\s*"(\d+)"', html)
            m_sig = re.search(r'\bSIG\s*=\s*"([a-f0-9]{64})"', html)
            m_diff = re.search(r'\bDIFF\s*=\s*"([0-9a-f]+)"', html)
            m_mode = re.search(r'\bMODE\s*=\s*"(\w+)"', html)
            if not (m_ts and m_sig and m_diff and m_mode):
                return ""
            ts, sig, diff, mode = (m_ts.group(1), m_sig.group(1),
                                   m_diff.group(1), m_mode.group(1))
            sig_b = sig.encode()
            n = len(diff)
            for i in range(2100000):
                if hashlib.sha256(sig_b + str(i).encode()).hexdigest()[:n] == diff:
                    return "__cdn_pow=%s_%s_%d_%s" % (ts, mode, i, sig)
        except Exception:
            pass
        return ""

    def get(self, path, tries=3, referer=None):
        """带自动过盾的 GET(线程安全: 壳子清缓存可能并发重入)。成功返回 html; 失败返回 ''。"""
        with self.lock:
            return self._get_locked(path, tries, referer)

    def _get_locked(self, path, tries=3, referer=None):
        for _ in range(tries):
            try:
                if self.conn is None:
                    self._newconn()
                st, loc, body, _ = self._send(path, referer)
            except Exception:
                # 连接断开/超时 → 重连重来(通行证绑连接, 作废)
                try:
                    self.close()
                except Exception:
                    pass
                self.conn = None
                continue
            if st == 200:
                return body
            if st == 403 and ("DIFF" in body or "__cdn_pow" in body):
                pow_ck = self._solve_pow(body)
                if not pow_ck:
                    return ""
                try:
                    # 同连接重放挑战答案 → 302 下发 __cdn_verified(自动吸收)
                    st2, loc2, body2, _ = self._send("/", referer=None)
                    self._absorb_manual(pow_ck)
                except Exception:
                    try:
                        self.close()
                    except Exception:
                        pass
                    self.conn = None
                    continue
                if "__cdn_verified" not in self.cookies:
                    continue
                # 重放原目标(同连接, 已放行)
                try:
                    st3, loc3, body3, _ = self._send(path, referer)
                except Exception:
                    try:
                        self.close()
                    except Exception:
                        pass
                    self.conn = None
                    continue
                if st3 == 200:
                    return body3
                continue
            # 其它状态码(5xx 等): 视为失败重试
        return ""

    def _absorb_manual(self, pow_ck):
        """把 PoW 答案注入 cookie(服务端 302 校验需要)。"""
        try:
            for kv in pow_ck.split(";"):
                k, _, v = kv.strip().partition("=")
                if k:
                    self.cookies[k] = v
        except Exception:
            pass


# 模块级共享会话（exec 抢跑与 Spider 实例共用同一连接/通行证）
_NET = _Net("www.libvio.io")


# ===================== exec 抢跑（冷启动决胜） =====================
# 壳子 exec 加载 py 时同步完成: 过盾 + 抓首页解析卡片。
# 接口计时开始前数据已就绪 — homeVideoContent 零网络秒回。
_MODULE_DATA = {"videos": None}


def _parse_cards(html):
    """解析 stui 列表卡片(备注 pic-text + 评分 pic-tag)。"""
    videos = []
    seen = set()
    if not html:
        return videos
    for m in _RE_CARD.finditer(html):
        href, title, pic, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        if href in seen:
            continue
        seen.add(href)
        remarks = ""
        mt = _RE_PIC_TEXT.search(tail)
        if mt:
            remarks = mt.group(1).strip()
        ms = _RE_PIC_TAG.search(tail)
        score = ms.group(1).strip() if ms else ""
        if score and score not in ("0.0",) and remarks:
            remarks = remarks + " " + score
        elif score and score not in ("0.0",):
            remarks = score
        videos.append({
            "vod_id": href,
            "vod_name": _clean(title)[:100],
            "vod_pic": _fix_url(pic),
            "vod_remarks": remarks,
        })
    if not videos:
        # 兜底: 只有 href 的极简卡片
        for href in _RE_HREF.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": href.rstrip("/").split("/")[-1].replace(".html", ""),
                "vod_pic": DEFAULT_PIC,
                "vod_remarks": "",
            })
    return videos


def _clean(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
          .replace("&amp;", "&").replace("&quot;", '"')
          .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def _fix_url(url):
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return HOST + url
    return url


_WARM_EVENT = threading.Event()


def _warm_once():
    """单次抓首页并填充 _MODULE_DATA。成功返回 True。"""
    try:
        html = _NET.get("/")
        if html and "stui-vodlist__thumb" in html:
            vids = _parse_cards(html)
            if vids:
                _MODULE_DATA["videos"] = vids[:60]
                return True
    except Exception:
        pass
    return False


def _warm_thread():
    """后台预热: 失败自动断线重连重过盾, 约 60s 窗口内不停重试 —
    网络晚就绪(开机/切网)也能自愈, 保证清缓存后 exec 数据仍在场。
    成功或窗口耗尽后放行全部等待者。"""
    for _ in range(24):
        if _warm_once():
            break
        try:
            _NET.close()
        except Exception:
            pass
        try:
            time.sleep(2.5)
        except Exception:
            break
    _WARM_EVENT.set()


def _module_warm():
    """exec 阶段: 启动后台预热线程, 主线程最多等 3 秒 —
    exec 永不长阻塞(防壳子超时杀模块), 慢网由接口侧等待兜底。"""
    try:
        t = threading.Thread(target=_warm_thread)
        t.daemon = True
        t.start()
    except Exception:
        _WARM_EVENT.set()
        return
    _WARM_EVENT.wait(3.0)


# ===================== Spider =====================
class Spider(Spider):

    def getName(self):
        return "LIBVIO"

    def init(self, extend=""):
        # 铁律: init 只做本地装配, 零网络零线程 —
        # 实例异常会被壳子永久缓存成空壳, 后续接口不再重试。
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # -------- 持久缓存(首页数据, 冷启动保险) --------
    _HOME_CACHE_KEY = "libvio_home"
    _HOME_CACHE_TTL = 1800

    def _home_cache_get(self, ignore_ttl=False):
        try:
            data = self.getCache(self._HOME_CACHE_KEY)
            if isinstance(data, dict):
                videos = data.get("videos") or []
                ts = int(data.get("t") or 0)
                if videos and (ignore_ttl or int(time.time()) - ts < self._HOME_CACHE_TTL):
                    return videos
        except Exception:
            pass
        return None

    def _home_cache_put(self, videos):
        try:
            self.setCache(self._HOME_CACHE_KEY,
                          {"t": int(time.time()), "videos": videos[:60]})
        except Exception:
            pass

    def _fetch(self, path_or_url, tries=3, referer=None):
        """统一入口: 绝对 URL → 换算 path 走单连接会话。"""
        url = path_or_url
        if url.startswith("http"):
            try:
                p = urllib.parse.urlsplit(url)
                url = p.path + (("?" + p.query) if p.query else "")
            except Exception:
                pass
        if not url.startswith("/"):
            url = "/" + url
        return _NET.get(url, tries=tries, referer=referer)

    def _page_count(self, html):
        try:
            m = _RE_PAGE.search(html)
            if m:
                return int(m.group(2))
            pages = _RE_PAGE_LINKS.findall(html)
            if pages:
                return max(int(p) for p in pages)
            ps = re.findall(r'page=(\d+)', html)
            if ps:
                return max(int(p) for p in ps) + 1
        except Exception:
            pass
        return 1

    # -------- 首页 --------
    def homeContent(self, filter=False):
        # 铁律: 纯本地秒回, 壳子对分类超时容忍度极低
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            # 0) 持久缓存: 上次会话数据直接秒回(宁旧勿空)
            cached = self._home_cache_get()
            if cached:
                self.log("home 命中持久缓存 %d 条" % len(cached))
                return {"list": cached}
            # 0.5) exec 抢跑数据; 不在场则等预热线程(最多 5s, 数据一到立即放行)
            mv = _MODULE_DATA.get("videos")
            if not mv:
                self.log("home 预热未就绪, 等待最多 5s")
                for _ in range(25):
                    if _WARM_EVENT.wait(0.2):
                        break
                    mv = _MODULE_DATA.get("videos")
                    if mv:
                        break
                mv = _MODULE_DATA.get("videos")
            if mv:
                self.log("home 使用 exec 抢跑数据 %d 条" % len(mv))
                self._home_cache_put(mv)
                return {"list": mv}
            # 1) 现场抓取: 两轮, 第二轮强制断线重连重过盾(单轮异常不逃逸)
            videos = []
            for _round in range(2):
                try:
                    html = self._fetch("/")
                    videos = _parse_cards(html)
                except Exception:
                    videos = []
                if videos:
                    self.log("home 现场抓取 %d 条(第%d轮)" % (len(videos), _round + 1))
                    break
                try:
                    _NET.close()  # 断线重连(通行证绑连接, 重过盾)
                except Exception:
                    pass
            if videos:
                _MODULE_DATA["videos"] = videos[:60]  # 回写: 下次清缓存 exec 数据在场
                self._home_cache_put(videos)
                return {"list": videos}
            # 2) 兜底: 各分类第一页合并(单类异常不逃逸)
            seen, merged = set(), []
            for tid in ("1", "2", "4", "3"):
                try:
                    th = self._fetch("/type/%s.html" % tid)
                    for v in _parse_cards(th):
                        if v["vod_id"] not in seen:
                            seen.add(v["vod_id"])
                            merged.append(v)
                except Exception:
                    pass
                if len(merged) >= 40:
                    break
            videos = merged[:60]
            self.log("home 分类合并 %d 条" % len(videos))
            if videos:
                _MODULE_DATA["videos"] = videos
                self._home_cache_put(videos)
            return {"list": videos}
        except Exception as e:
            self.log("homeVideoContent 异常", e)
            stale = self._home_cache_get(ignore_ttl=True)
            return {"list": stale or []}

    # -------- 分类/筛选 --------
    def _build_show_path(self, tid, page, cls="", area="", year=""):
        """12 段 show 路由(实测): 索引 0=tid, 1=area, 3=class, 8=page, 11=year。
        中文段需 URL 编码(站点链接即 %E4%BD.. 形式)。"""
        q = urllib.parse.quote
        segs = [str(tid), q(area), "", q(cls), "", "", "", "",
                str(page) if str(page) != "1" else "", "", "", q(year)]
        return "/show/" + "-".join(segs) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if not isinstance(extend, dict):
                extend = {}

            cls = extend.get("class") or ""
            area = extend.get("area") or ""
            year = extend.get("year") or ""
            for v in (cls, area, year):
                if v in ("全部",):
                    v = ""
            cls = "" if cls == "全部" else cls
            area = "" if area == "全部" else area
            year = "" if year == "全部" else year

            path = self._build_show_path(tid, page, cls, area, year)
            html = self._fetch(path)
            self.log("category: %s → %d bytes" % (path, len(html)))
            videos = _parse_cards(html)
            pagecount = self._page_count(html)

            # 兜底: show 无结果时回退 type 分页路由
            if not videos:
                html = self._fetch("/type/%s-%d.html" % (tid, page))
                videos = _parse_cards(html)
                pagecount = self._page_count(html)

            return {
                "list": videos, "page": page, "pagecount": int(pagecount),
                "limit": 12, "total": int(pagecount) * 12,
            }
        except Exception as e:
            self.log("categoryContent 异常", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 12, "total": 0}

    # -------- 搜索 --------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            kw = urllib.parse.quote(str(key or "").strip())
            path = "/search/%s-------------.html" % kw
            html = self._fetch(path)
            # 搜索 5 秒频率限制: 提示页 → 等待后重试一次
            if html and _RE_SEARCH_LIMIT.search(html):
                self.log("search 触发 5 秒频率限制, 等待重试")
                time.sleep(5.2)
                html = self._fetch(path)
            self.log("search: %s → %d bytes" % (path, len(html)))
            videos = _parse_cards(html)
            return {
                "list": videos, "page": page,
                "pagecount": self._page_count(html),
                "limit": 12, "total": len(videos),
            }
        except Exception as e:
            self.log("searchContent 异常", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 12, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # -------- 详情 --------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else _fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = _clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = _RE_TITLE_TAG.search(html)
                if m:
                    name = _clean(m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = DEFAULT_PIC
        try:
            m = _RE_POSTER.search(html)
            if m:
                pic = self._fix_pic(m.group(1))
            else:
                m = _RE_POSTER_BG.search(html)
                if m:
                    pic = self._fix_pic(m.group(1))
        except Exception:
            pass

        # 元信息 vod-meta: [类型, 地区, 年份, 上映.., 共N集, 更新..]
        metas = []
        try:
            for mm in _RE_META.finditer(html):
                metas.extend(_RE_META_ITEM.findall(mm.group(1)))
        except Exception:
            pass
        remark_ep = ""
        update_date = ""
        for it in metas:
            if it.startswith("共 ") or it.startswith("共"):
                remark_ep = it
            if it.startswith("更新"):
                update_date = it

        # 备注(副标题): 详情"共 N 集"优先, 否则用列表卡备注
        remarks = remark_ep or ""

        # 简介: detail-content(完整版, display:none) 优先, sketch 缩略兜底
        content = ""
        try:
            m = _RE_DESC.search(html)
            if m:
                content = _clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_DESC2.search(html)
                if m:
                    content = _clean(m.group(1))
            except Exception:
                pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = _clean(m.group(1))
            except Exception:
                pass
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 主演/导演
        actor = ""
        try:
            m = _RE_ACTOR.search(html)
            if m:
                actor = re.sub(r"\s*,\s*", ", ", _clean(m.group(1)))
        except Exception:
            pass
        director = ""
        try:
            m = _RE_DIRECTOR.search(html)
            if m:
                director = _clean(m.group(1))
        except Exception:
            pass

        # 豆瓣评分
        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        # ===== 线路与剧集(按站点 HTML 顺序 = 站点线路顺序, 排除网盘面板) =====
        play_from = []
        play_url = []
        try:
            for pm in _RE_PANEL.finditer(html):
                line_name = _clean(pm.group(1))
                eps = _RE_EP.findall(pm.group(2))
                if not line_name or not eps:
                    continue
                play_from.append(line_name)
                play_url.append("#".join(
                    "%s$%s" % (_clean(n), h) for h, _s, _n, _e, n in eps))
        except Exception as e:
            self.log("剧集解析异常", e)

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks,
            "type_name": metas[0] if metas else "",
            "vod_area": metas[1] if len(metas) > 1 else "",
            "vod_year": metas[2] if len(metas) > 2 else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _fix_pic(self, url):
        return _fix_url(url) or DEFAULT_PIC

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else _fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        m = _RE_PLAYER_AA.search(html) if html else None
        if not m:
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res
        try:
            aa = json.loads(m.group(1))
        except Exception:
            try:
                aa = json.loads(m.group(1).replace("\\/", "/"))
            except Exception:
                aa = {}
        real_url = (aa.get("url") or "").replace("\\/", "/").replace("&amp;", "&")
        frm = aa.get("from") or ""
        vid = aa.get("id") or ""
        nid = aa.get("nid") or "1"
        self.log("  from=%s encrypt=%s url=%s" % (frm, aa.get("encrypt"), real_url[:80]))

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # 情况 A: 明文直链 m3u8/mp4
        if real_url.startswith("http") and (".m3u8" in real_url.lower() or ".mp4" in real_url.lower()):
            self.log("  => 直链: %s" % real_url[:120])
            res = {"parse": 0, "playUrl": "", "url": real_url, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 情况 B: 网盘线路(url 明文网盘链接) → 交壳子嗅探(与站点行为一致: 网盘引导页)
        if real_url.startswith("http"):
            self.log("  => 网盘线路, 交壳子嗅探")
            res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 情况 C: 在线线路(url 密文) → /vid/{from}解析.php?url=密文
        # (⚠️ 必须带播放页 Referer, 否则返回首页诱饵)
        # → 页面内 LIBVIO_YD_CFG.parseUrl(服务端已签名) → GET → JSON 真实直链
        parse_src = ""
        if real_url:
            php = "yd" if "yd" in frm.lower() else frm.rstrip("0123456789").lower()
            parse_src = "/vid/%s.php?url=%s&next=&id=%s&nid=%s" % (
                php, urllib.parse.quote(real_url), vid, nid)
        if parse_src:
            yd_html = self._fetch(parse_src, referer=play_page)
            cfgm = _RE_PARSE_CFG.search(yd_html)
            parse_url = ""
            if cfgm:
                try:
                    cfg = json.loads(cfgm.group(1))
                    parse_url = cfg.get("parseUrl", "")
                except Exception:
                    mu = _RE_PARSE_URL.search(cfgm.group(1))
                    parse_url = mu.group(1) if mu else ""
            if not parse_url:
                mu = _RE_PARSE_URL.search(yd_html)
                if mu:
                    parse_url = mu.group(1)
            if parse_url:
                parse_url = parse_url.replace("\\u0026", "&").replace("\\/", "/").replace("&amp;", "&")
                if parse_url.startswith("/"):
                    parse_url = self.site_url + parse_url
                pj = self._fetch(parse_url, referer=self.site_url + parse_src.split("?")[0])
                jm = re.search(r'"url"\s*:\s*"([^"]+)"', pj)
                if jm:
                    real = jm.group(1).replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
                    if real.startswith("http"):
                        self.log("  => parse 直链: %s" % real[:120])
                        res = {"parse": 0, "playUrl": "", "url": real, "header": header}
                        self._play_cache[play_page] = (now, res)
                        return res

        # 兜底: 交 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    # -------- 其它 --------
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
            url = _fix_url(url)
            html = self._fetch(url)
            return [200, "image/jpeg", html.encode("utf-8", "ignore"), ""]
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


# exec 阶段抢跑: 过盾 + 抓首页(接口计时开始前数据就绪, 冷启动零等待)
_module_warm()

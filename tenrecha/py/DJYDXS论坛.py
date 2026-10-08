# -*- coding: utf-8 -*-
"""
TVBox 爬虫 —— DJYDXS论坛
============================================================
站点: https://4kzimu.top
类型: Discuz X5.0 论坛 (爱电影-爱字幕-4K-REMUX)

原理说明
--------
本论坛帖子详情里，百度网盘 / 115 网盘 / ed2k 等下载源不是明写的 <a> 链接，
而是通过插件 nimba_tanchuanjilu 用 JS 变量注入：
    <script>window._NTCJ_BOXES=[{"type":"baidu","url":"https://pan.baidu.com/s/...?pwd=xxx","pwd":"xxx"},{"type":"ed2k","url":"ed2k://|file|...|HASH|/", "pwd":""}];</script>
所以不用模拟登录或点 AJAX，只要抓到 thread-{tid}-1-1.html 就能拿到全部下载链接。
Cookies 用来解锁会员可见的版块/帖子（如 4K.SDR.REMUX、4K剧集.115网盘），没登录态
直接访问会被跳到 member.php 登录页。

★★★ 内置配置区：直接改下面两个值即可，其他一律不要动 ★★★
    BASE    : 站点根地址（一般不动）
    COOKIES : 浏览器登录后复制的完整 Cookie 字符串（换账号/过期时替换这里）

★★★ 硬性约定（改动会导致站点完全加载不出来）★★★
    1. 主类必须叫 Spider —— TVBox 的 python 加载器只认这个名字，
       改名后现象就是「一片空白、什么都没有」，且不报任何错。
    2. 必须实现 init(extend) / getName() 这两个生命周期方法。
============================================================
用法
----
1. 把本文件放到 TVBox 的 spider/ 目录（例如 /spider/DJYDXS.py）。
2. 打开 TVBox 设置 -> 配置路径 -> 爬虫配置，选择本文件所在 JSON。
3. 如果不想每次改文件，可以在 TVBox 的 extend 里配：
       {"cookies": "cTo3_2132_saltkey=..."}
   extend 的 cookies 优先级高于本文件里的 COOKIES 常量。
4. 命令行自检：
       python DJYDXS.py                # 交互式跑通全流程
       python DJYDXS.py --home         # 只看首页
       python DJYDXS.py --cat fid:112  # 看 4K.SDR.REMUX 第 1 页
       python DJYDXS.py --detail 35236 # 看单帖详情
       python DJYDXS.py --search 星球   # 关键词搜索

下载链接一律走 push:// 协议（USE_PUSH=True），配合本地/云盘代理使用；
设 USE_PUSH=False 则直接把原始网盘 URL 交给播放器。
"""

# ==================================================================
# ★★★ 内置配置区（直接改这里）★★★
# ==================================================================

BASE = "https://4kzimu.top"

# Cookie 复制方法：
#   1. 浏览器登录 https://4kzimu.top
#   2. 按 F12 -> Network 面板 -> 刷新页面
#   3. 点第一个请求 -> Request Headers -> 找到 Cookie: 字段
#   4. 冒号后面一整串字符复制粘贴到下面两个引号之间（含分号）
#   5. 保存文件，重启 TVBox
#
# 过期症状：进任何资源版块都被跳回 member.php 登录页，或 _NTCJ_BOXES 抓不到
COOKIES = """cTo3_2132_saltkey=LT8prnHZ;cTo3_2132_lastvisit=1786540756;cTo3_2132_d_i18n=1;cTo3_2132_auth=9a78u8lqMEXHcRmxDZNME8RdODrNj7EGVDPztAMw0acbfosCY%2BwDHkZzuResPPmCxMgYICq33ahy%2FPIAoIStwVjl;cTo3_2132_lastcheckfeed=1410%7C1786544367;cTo3_2132_nofavfid=1;cTo3_2132_smile=5D1;cTo3_2132_visitedfid=112D2;cTo3_2132_member_login_status=1;cTo3_2132_movmod_112=liebiao;cTo3_2132_st_t=1410%7C1788883036%7C45167182f20df932a09c05ea4e2e8eaa;cTo3_2132_forum_lastvisit=D_2_1787903684D_112_1788883036;cTo3_2132_sid=F0TW8w;cTo3_2132_lip=104.28.211.46%2C1788883024;cTo3_2132_onlineusernum=34;cTo3_2132_ulastactivity=5df3hv1yM3mnCkPeJS4JTPJMoqRackSdYz3hxkDo2gpoky2WRZXY;cTo3_2132_lastact=1788940692%09plugin.php%09"""

# 资源版块（Discuz 的 fid + 中文名）。要增删只改这个列表。
# 排序：按用户浏览习惯（4K/REMUX 优先，剧集次之，1080P 最后）
CATEGORIES = [
    (112, "4KSDR.Remux"),
    (119, "1080P.Remux"),
    (58,  "1080P高码版"),
    (37,  "1080P最新剧集"),
    (2,   "最新1080P电影"),
    (115, "4K剧集.115网盘"),
    (116, "国语特效MKV"),
    (86,  "转载资源区"),
    (78,  "资源补档"),
]

# 资源版块 fid 集合，供搜索过滤「求片热线」等非下载版块
_KNOWN_FIDS = set(fid for fid, _n in CATEGORIES)

# 列表页排序方式：
#   latest  = 最新回复（默认，Discuz 首页默认）
#   lastpost= 最新主题
#   heat    = 热门
#   hot     = 热帖
#   digest  = 精华
DEFAULT_ORDER = "latest"

# 是否统一把下载链接走 push:// 协议（默认开）。
# True  -> playerContent 返回 {"url":"push://pan.baidu.com/s/xxx"}
# False -> playerContent 返回 {"url":"https://pan.baidu.com/s/xxx"}
USE_PUSH = True

# 详情页里保留多少个下载线路（一个帖子可能有 baidu + 115 + ed2k 多个）
MAX_BOXES = 6

# ------------------------------------------------------------------
# 海报 / 卡片显示
# ------------------------------------------------------------------

# 列表页强制用「海报墙」模式（forumdisplay 的 movmod=haibao）。
# 论坛默认是表格列表（fid 86/78/112/116），那种布局里没有海报图，
# 打开后 9 个版块都能拿到 dstmdb 的海报；关掉则回到各版块自己的布局。
USE_HAIBAO = True

# 卡片样式（TVBox 的 Vod.Style）。
#   type : rect=直角矩形 / round=圆角 / oval=椭圆
#   ratio: 宽高比（宽/高）。电影竖版海报约 0.75，横版剧照用 1.33
# 只想要直角、不改比例，就写 {"type": "rect"}。
CARD_STYLE = {"type": "rect", "ratio": 0.75}

# 列表页是否并发补抓每帖详情，用来补「完整日期 + 片长」。
#   开：海报上能显示 2026-9-9 · 117分钟，首屏多等 2~4 秒，之后走内存缓存秒开
#   关：海报只显示版块列表页能拿到的信息，不额外发请求
PREFETCH_DETAIL = True
PREFETCH_WORKERS = 12     # 并发线程数（越大首屏越快，别超过 16）
PREFETCH_MAX = 40         # 单页最多补抓多少条（防止卡顿）

# ------------------------------------------------------------------
# 搜索（走论坛自带的 Discuz 搜索，不要改成遍历版块，那样会超时）
# ------------------------------------------------------------------

# 搜索结果缓存时长（秒）。Discuz 有防刷限制（10 秒一次），
# 缓存能避免 TVBox 边打字边联想搜索把额度打满。
SEARCH_CACHE_TTL = 600

# 论坛两次「新搜索」之间的最小间隔（秒）。
# 站方限制是 10 秒，这里留 11 秒余量。翻页（复用 searchid）不受此限制。
SEARCH_COOLDOWN = 11

# 联想搜索（quick=True）时，关键词至少几个字才真的发请求。
# 设 2 可以避免 TVBox 每敲一个字母都打一次站方搜索。
SEARCH_MIN_LEN = 2

# 是否只保留 CATEGORIES 里列出的版块的结果。
# 关掉的话会混进「求片热线」(fid 56) 这类无下载链接的求助帖。
SEARCH_ONLY_KNOWN_FID = True

# 搜索结果是否并发补抓详情（拿海报 + 片长）。
#   开：结果有海报，但每条一个详情请求，一页最多 36 条 → 约慢 3~6 秒（12 线程并发）
#   关：秒出，海报留空（标题/日期照常有，点进去详情页才加载海报）
# 原生搜索页本身没有海报图，想要搜索结果带海报必须开这个
SEARCH_PREFETCH = True

# 请求超时（秒）
TIMEOUT = 20

# ==================================================================
# 依赖
# ==================================================================

import json
import os
import re
import sys
import time
import html as _html
from urllib.parse import quote, urlparse

try:
    from requests import Session
except Exception:
    Session = None

try:
    import threading as _threading
except Exception:
    _threading = None

try:
    from concurrent.futures import ThreadPoolExecutor as _Pool
except Exception:
    _Pool = None

try:
    from base.spider import Spider as _Spider  # TVBox 环境
except Exception:
    class _Spider:  # 独立运行时
        def __init__(self, *a, **kw):
            pass


# ==================================================================
# 通用工具
# ==================================================================

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": BASE + "/",
}


def _unescape(s):
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return _html.unescape(s)


def _clean_title(s):
    s = _unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _b64_encode(s):
    import base64
    return base64.b64encode(str(s or "").encode("utf-8")).decode("utf-8")


def _b64_decode(s):
    import base64
    try:
        return base64.b64decode(str(s or "").encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def _fid_from_tid(tid):
    """tid 编码：'fid:112' -> 112；'fid:112###35236' -> (112, 35236)"""
    tid = str(tid or "").strip()
    if "###" in tid:
        head, _, tail = tid.partition("###")
        m = re.match(r"fid:(\d+)", head)
        return (int(m.group(1)) if m else 0, tail.strip())
    m = re.match(r"fid:(\d+)", tid)
    return int(m.group(1)) if m else 0


# ==================================================================
# 每帖补充信息缓存（日期 / 片长 / 海报）
# ==================================================================
# key = tid，value = {"date": "2026-9-9", "runtime": "117分钟", "pic": "..."}
# 详情页抓到后写进来，列表页直接复用；抓过一次后同进程内不再重复请求。
_TID_INFO = {}
_TID_LOCK = _threading.Lock() if _threading else None


def _tid_info_get(tid):
    tid = str(tid or "")
    if not tid:
        return {}
    if _TID_LOCK:
        with _TID_LOCK:
            return dict(_TID_INFO.get(tid) or {})
    return dict(_TID_INFO.get(tid) or {})


def _tid_info_put(tid, **kw):
    """只覆盖非空值，避免后一次的抓取把已有的信息冲掉。"""
    tid = str(tid or "")
    if not tid:
        return
    def _do():
        cur = _TID_INFO.setdefault(tid, {})
        for k, v in kw.items():
            if v:
                cur[k] = v
    if _TID_LOCK:
        with _TID_LOCK:
            _do()
    else:
        _do()


# ==================================================================
# 搜索缓存（Discuz 站方限制 10 秒一次新搜索，必须缓存）
# ==================================================================
# _SEARCH_SID   : keyword -> searchid（翻页复用，免得每次都算新搜索）
# _SEARCH_CACHE : (keyword, page) -> (时间戳, items, total, pagecount)
# _SEARCH_TS    : 上一次「新搜索」的时间戳
_SEARCH_SID = {}
_SEARCH_CACHE = {}
_SEARCH_TS = [0.0]
_SEARCH_LOCK = _threading.Lock() if _threading else None


def _search_cache_get(k, pg, ttl):
    ent = _SEARCH_CACHE.get((k, pg))
    if not ent:
        return None
    if ttl > 0 and (time.time() - ent[0]) > ttl:
        return None
    return ent[1], ent[2], ent[3]


def _search_cache_put(k, pg, items, total, pagecount):
    _SEARCH_CACHE[(k, pg)] = (time.time(), items, total, pagecount)


def _search_wait_slot(cooldown):
    """距离上次新搜索不足 cooldown 秒就等着，返回实际等待秒数。"""
    last = _SEARCH_TS[0]
    if last <= 0:
        return 0.0
    gap = cooldown - (time.time() - last)
    if gap <= 0:
        return 0.0
    time.sleep(gap)
    return gap


def _search_mark_used():
    _SEARCH_TS[0] = time.time()


def _fmt_date(s):
    """'2026-09-09 13:20' / '2026-9-9 13:20' -> '2026-9-9'（去掉时分、去掉前导零）。"""
    s = str(s or "").strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if not m:
        return ""
    return "%d-%d-%d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _fmt_runtime(s):
    """'117' / '117分钟' / '◎片 长 117分钟' -> '117分钟'。"""
    s = str(s or "")
    m = re.search(r"(\d{1,3})\s*分钟", s)
    if m:
        return "%d分钟" % int(m.group(1))
    m2 = re.match(r"^\s*(\d{1,3})\s*$", s)
    if m2:
        return "%d分钟" % int(m2.group(1))
    return ""


# ==================================================================
# Spider
# ==================================================================

# ★★★ 类名必须是 Spider ★★★
# TVBox 的 python 加载器（base.spider / hipy）只认模块里名为 "Spider" 的类，
# 换成 DJYDXSSpider 之类的名字会导致站点完全加载不出来（一片空白、无任何输出）。
class Spider(_Spider):
    """TVBox 标准 Spider 实现。"""

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            pass
        # 允许 extend 里的 cookies 覆盖内置常量
        self.cookies = COOKIES.strip()
        self.ext_headers = dict(HEADERS)
        self._session = None
        self._last_picture = ""

    # --------------------------------------------------------------
    # 生命周期接口（TVBox 加载器会主动调用）
    # --------------------------------------------------------------

    def init(self, extend=""):
        """TVBox 实例化后立刻调用，extend 是 JSON 字符串或 dict。"""
        try:
            self._apply_extend(extend)
        except Exception as e:
            print("[DJYDXS] init 异常: %s" % e)
        return True

    def getName(self):
        return "DJYDXS论坛"

    def isVideoFormat(self, url):
        """让 TVBox 对每个外链都走 playerContent，不做格式过滤。"""
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass
        self._session = None

    def localProxy(self, param):
        return None

    # --------------------------------------------------------------
    # Session / HTTP
    # --------------------------------------------------------------

    def _apply_extend(self, extend):
        """从 TVBox 传入的 extend 里读取 cookies。"""
        if not extend:
            return
        if isinstance(extend, str):
            s = extend.strip()
            if not s or s.lower() in ("true", "false", "null", "none"):
                return
            try:
                extend = json.loads(s)
            except Exception:
                return
        if not isinstance(extend, dict):
            return
        ck = extend.get("cookies") or extend.get("cookie")
        if ck:
            self.cookies = str(ck).strip()
        ua = extend.get("ua") or extend.get("user_agent")
        if ua:
            self.ext_headers["User-Agent"] = str(ua)
        referer = extend.get("referer")
        if referer:
            self.ext_headers["Referer"] = str(referer)

    def _sess(self):
        if self._session is None:
            if Session is None:
                return None
            s = Session()
            s.headers.update(self.ext_headers)
            # 关键：把 cookie 写进 jar，而不是手动设 header["Cookie"]。
            # 原生搜索 search.php 第一跳（srchtxt）会 302 并下发新的 sid cookie，
            # 必须走 jar 才能在重定向/后续请求里带上它；写死 header 会覆盖 jar，
            # 导致 searchid 第二跳鉴权失败被跳回登录页。
            host = urlparse(BASE).hostname or "4kzimu.top"
            for kv in self.cookies.split(";"):
                kv = kv.strip()
                if not kv or "=" not in kv:
                    continue
                k, v = kv.split("=", 1)
                try:
                    s.cookies.set(k.strip(), v.strip(), domain=host)
                except Exception:
                    pass
            self._session = s
        return self._session

    def _get(self, url):
        s = self._sess()
        if s is not None:
            try:
                r = s.get(url, timeout=TIMEOUT)
                r.encoding = "utf-8"
                return r.text
            except Exception as e:
                print("[DJYDXS] requests 异常 %s: %s" % (url, e))
                return ""
        # 兜底：stdlib
        try:
            import urllib.request
            fh = dict(self.ext_headers)
            fh["Cookie"] = self.cookies
            req = urllib.request.Request(url, headers=fh)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print("[DJYDXS] urllib 异常 %s: %s" % (url, e))
            return ""

    @staticmethod
    def _looks_like_login_page(html):
        """判定返回的页面是不是 Discuz 登录页（未登录 / Cookie 失效）。

        可靠信号：<title>登录 - ...</title> 且出现登录表单按钮 name="loginsubmit"。
        单看 "member.php?mod=logging" 不可靠，登录页链接在登录态页面里也会出现。
        """
        if not html:
            return False
        # 前 2KB 检查 <title>，快速短路
        head = html[:2048]
        if not re.search(r"<title>\s*登录", head, re.I):
            return False
        return 'name="loginsubmit"' in html

    # --------------------------------------------------------------
    # 解析：版块列表
    # --------------------------------------------------------------

    # Discuz pretty URL: thread-{tid}-{fid_or_1}-{page}.html
    # 第 3 段实际是"当前列表页码"，随翻页变化（page1 是 -1.html，page2 是 -2.html）
    _RE_THREAD_ROW = re.compile(
        r'<a href="thread-(\d+)-1-\d+\.html"[^>]*class="s xst"[^>]*>(.*?)</a>',
        re.S,
    )
    # 海报墙布局 —— 覆盖 forum 2/37/58/115/119 的多种变体：
    #   1. haibao-movie-card + list_cmi_txt + haibao-card-title (论坛 2/37/58/119)
    #   2. portal_block + img22 + p (论坛 115 顶部推荐位)
    #   3. fm-trend-card + fm-trend-title + img alt 存完整标题
    # 统一策略：以 <a href="thread-TID-1-PAGE.html" ...> ... </a> 为边界，
    # 在锚点内提取 img src / alt 和标题类 <p>
    _RE_ANCHOR_THREAD = re.compile(
        r'<a href="thread-(\d+)-1-\d+\.html"[^>]*>(.*?)</a>',
        re.S | re.I,
    )
    _RE_IMG_SRC = re.compile(r'<img[^>]*?src="([^"]+)"', re.I)
    _RE_IMG_ALT = re.compile(r'<img[^>]*?alt="([^"]+)"', re.I)
    _RE_CARD_TITLE = re.compile(
        r'<p[^>]*class="[^"]*(?:haibao-card-title|fm-trend-title)[^"]*"[^>]*>(.*?)</p>',
        re.S | re.I,
    )
    _RE_CARD_META = re.compile(
        r'<p[^>]*class="[^"]*(?:haibao-card-sub|haibao-card-year|fm-trend-sub)[^"]*"[^>]*>(.*?)</p>',
        re.S | re.I,
    )
    _RE_TOTAL = re.compile(r"threads=(\d+)", re.I)
    # Discuz 分页栏常见形式："共 N 页" 或 pages=N 或 最后一个 forum-fid-N.html 链接
    _RE_PAGES_CN = re.compile(r"共\s*(\d+)\s*页", re.I)
    _RE_PAGES_EN = re.compile(r'pages=(\d+)', re.I)
    _RE_LAST_PAGE_LINK = re.compile(r'forum-(\d+)-(\d+)\.html', re.I)

    # ---- 原生搜索（search.php）结果页解析 ----
    # 结果页：<li class="pbw" id="TID"> <h3 class="xs3"><a href="..." target="_blank">标题(含高亮font)</a>
    #   每行还带 <p> <span>YYYY-M-D H:M</span> - <span>作者</span> - <span><a href="forum-FID-1.html" class="xi1">版块名</a></span> </p>
    # 注意：a 开标签用 <a[^>]*> 整体跳过（它带 href/target 等属性），(.*?) 只捕获标签内文。
    _RE_SEARCH_ITEM = re.compile(
        r'<li[^>]*class="pbw"[^>]*id="(\d+)"[^>]*>\s*'
        r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>\s*</h3>\s*'
        r'(.*?)</li>',
        re.S | re.I,
    )
    _RE_SEARCH_TID = re.compile(r'tid=(\d+)')
    _RE_SEARCH_FID = re.compile(r'forum-(\d+)-\d+\.html|forumdisplay&amp;fid=(\d+)')
    _RE_SEARCH_DATE = re.compile(r'<span>\s*(\d{4}-\d{1,2}-\d{1,2})\b')
    _RE_SEARCH_TOTAL = re.compile(r'相关内容\s*(\d+)\s*个', re.I)
    _RE_SEARCH_SID = re.compile(r'searchid=(\d+)')
    _RE_SEARCH_PGS = re.compile(r'共\s*(\d+)\s*页')
    #     <a href="thread-36030-1-1.html" target="_blank">
    #       <div class="list_common_movie_in">
    #         <div class="list_cmi_pic"><img src="https://dstmdb.../1433367.jpg"></div>
    #         <div class="list_cmi_txt">
    #           <p class="haibao-card-title">一夜限定</p>
    #           <p class="haibao-card-year">2026</p>   （或 haibao-card-sub）
    # --------------------------------------------------------------
    _RE_HAIBAO_CARD = re.compile(
        r'<li class="haibao-movie-card">(.*?)</li>', re.S | re.I
    )
    _RE_HB_TID = re.compile(r'href="thread-(\d+)-1-\d+\.html"', re.I)
    _RE_HB_PIC = re.compile(r'<img[^>]*?src="([^"]+)"', re.I)
    _RE_HB_TITLE = re.compile(
        r'<p[^>]*class="[^"]*haibao-card-title[^"]*"[^>]*>(.*?)</p>', re.S | re.I
    )
    _RE_HB_SUB = re.compile(
        r'<p[^>]*class="[^"]*haibao-card-(?:sub|year)[^"]*"[^>]*>(.*?)</p>',
        re.S | re.I,
    )

    # 表格布局里每行的时间（最后回复时间），形如 2026-9-9 13:20
    _RE_TBODY = re.compile(
        r'<tbody id="(?:normalthread|stickthread)_(\d+)">(.*?)</tbody>', re.S | re.I
    )
    _RE_ROW_DATE = re.compile(
        r'<em[^>]*>(?:<span[^>]*>)?\s*(?:发表于\s*)?(\d{4}-\d{1,2}-\d{1,2})',
        re.I,
    )

    # 详情页：发表时间 / 片长
    _RE_POSTED = re.compile(
        r'<em id="authorposton\d+">[^<]*?(\d{4}-\d{1,2}-\d{1,2})', re.I
    )
    _RE_RUNTIME = re.compile(r"片\s*长[^0-9]{0,8}(\d{1,3})\s*分钟")
    _RE_RUNTIME_LOOSE = re.compile(r"(?<!\d)(\d{2,3})\s*分钟")

    @staticmethod
    def _list_url(fid, page, order, haibao=False):
        """拼版块列表页 URL。

        haibao=True 时强制海报墙模式（forumdisplay&movmod=haibao），
        这样所有版块都能拿到海报图；排序参数照常带上。
        """
        fid = int(fid)
        page = max(1, int(page or 1))
        if haibao:
            params = {"mod": "forumdisplay", "fid": fid, "page": page,
                      "movmod": "haibao"}
        elif order == "latest":
            return "%s/forum-%d-%d.html" % (BASE, fid, page)
        else:
            params = {"mod": "forumdisplay", "fid": fid, "page": page}
        if order == "lastpost":
            params["filter"] = "lastpost"
            params["orderby"] = "lastpost"
        elif order == "heat":
            params["filter"] = "heat"
            params["orderby"] = "heats"
        elif order == "hot":
            params["filter"] = "hot"
        elif order == "digest":
            params["filter"] = "digest"
            params["digest"] = "1"
        return "%s/forum.php?%s" % (
            BASE, "&".join("%s=%s" % kv for kv in params.items()))

    # --------------------------------------------------------------
    # 原生 Discuz 搜索（search.php）
    # --------------------------------------------------------------

    def _search_url(self, kw, page, sid):
        """拼原生搜索 URL。

        第 1 页（没有 sid）用 srchtxt=kw；翻页（有 sid）用 searchid=sid&kw=kw。
        Discuz 把结果存进 session，后续翻页必须带同一个 searchid，
        否则会重新算一次「新搜索」触发 10 秒防刷限制。
        """
        page = max(1, int(page or 1))
        if sid:
            q = ("mod=forum&searchid=%s&orderby=lastpost&ascdesc=desc"
                 "&searchsubmit=yes&kw=%s" % (sid, quote(kw)))
        else:
            q = ("mod=forum&srchtxt=%s&searchsubmit=yes" % quote(kw))
        if page > 1:
            q += "&page=%d" % page
        return "%s/search.php?%s" % (BASE, q)

    def _parse_search(self, html, sid_holder):
        """解析原生搜索页，返回 (items, total, pagecount, sid)。

        items: [{vod_id, vod_name, fid, tid, date}]
        """
        items = []
        seen = set()

        # 结果里的 fid 行：<a href="forum-112-1.html" class="xi1">4K.SDR.REMUX</a>
        # 只有已知资源版块才收（过滤「求片热线」等求助帖）
        for m in self._RE_SEARCH_ITEM.finditer(html):
            tid = m.group(1).strip()
            title_raw = m.group(2) or ""
            rest = m.group(3) or ""
            if not tid or tid in seen:
                continue

            title = _clean_title(title_raw)
            if not title:
                m_t = self._RE_SEARCH_TID.search(title_raw)
                if m_t:
                    title = m_t.group(1)
            if not title or len(title) < 2:
                continue

            # 提取该行所属版块 fid
            fid = 0
            mf = self._RE_SEARCH_FID.search(rest)
            if mf:
                fid = int(mf.group(1) or mf.group(2))
            if SEARCH_ONLY_KNOWN_FID and fid and fid not in _KNOWN_FIDS:
                continue

            date = ""
            md = self._RE_SEARCH_DATE.search(rest)
            if md:
                date = _fmt_date(md.group(1))

            # 补 tid 缓存（日期），供海报角标/详情页复用
            if date:
                _tid_info_put(tid, date=date)

            seen.add(tid)
            items.append({
                "vod_id": "fid:%s###%s" % (fid, tid),
                "vod_name": title,
                "fid": fid,
                "tid": tid,
                "date": date,
                "vod_pic": "",
            })

        total = 0
        mt = self._RE_SEARCH_TOTAL.search(html)
        if mt:
            try:
                total = int(mt.group(1))
            except Exception:
                total = 0

        # searchid（翻页用）：优先从页面里取当前 searchid
        sid = None
        ms = self._RE_SEARCH_SID.search(html)
        if ms:
            sid = ms.group(1)

        # 总页数
        pagecount = 0
        if total > 0:
            # Discuz 每页固定 36 条（同版块列表页的每页条数）
            pagecount = (total + 35) // 36
        mp = self._RE_SEARCH_PGS.search(html)
        if mp:
            try:
                pagecount = int(mp.group(1))
            except Exception:
                pass

        return items, total, pagecount, sid

    def _native_search(self, kw, page, quick):
        """走原生搜索。返回 (items, total, pagecount)。"""
        key = kw.strip().lower()

        # 联想搜索（quick）且关键词太短：不发请求（避免每敲一字打一次站方）
        if quick and len(key) < SEARCH_MIN_LEN:
            return [], 0, 1

        # 该页命中缓存？
        if not quick:
            hit = _search_cache_get(key, page, SEARCH_CACHE_TTL)
            if hit is not None:
                items, total, pagecount = hit
                return items, total, pagecount

        # 取本页 searchid（翻页复用）。第 1 页没 sid。
        sid = _SEARCH_SID.get(key)
        use_sid = sid if page > 1 else None

        # 有缓存就免防刷；没有且这次是「新搜索」（无 sid 或第 1 页要重算）就等槽
        cached = _search_cache_get(key, page, SEARCH_CACHE_TTL) is not None
        if not cached:
            wait = _search_wait_slot(SEARCH_COOLDOWN)
            if wait:
                print("[DJYDXS] 搜索防刷等待 %.1fs" % wait)

        url = self._search_url(kw, page, use_sid)
        html = self._get(url)
        if not html:
            # 网络失败：给空结果，别卡住
            return [], 0, 1

        if self._looks_like_login_page(html):
            print("[DJYDXS] 搜索页疑似 Cookie 失效")
            return [], 0, 1

        # 命中「10 秒内只能搜索一次」→ 结果页会带提示且无内容
        if "抱歉" in html and ("只能进行一次搜索" in html or "search" in html.lower()):
            print("[DJYDXS] 触发搜索防刷，本次空结果")
            return [], 0, 1

        sid_holder = {}
        items, total, pagecount, sid_new = self._parse_search(html, sid_holder)

        # 记下 sid 供翻页
        if sid_new:
            _SEARCH_SID[key] = sid_new
        # 第 1 页也算用过一次搜索额度
        _search_mark_used()

        # 写缓存
        if items is not None:
            _search_cache_put(key, page, items, total, pagecount)

        return items, total, pagecount

    @staticmethod
    def _main_region(html):
        """截取主列表区域（id="threadlist" ~ id="ft"）。

        版块顶部有 fm-trend-card「本月最热」推荐位，指向的是别的版块，
        整页扫会把它们混进列表里。
        """
        idx_start = html.find('id="threadlist"')
        idx_end = html.find('id="ft"', idx_start) if idx_start >= 0 else -1
        if idx_start >= 0 and idx_end > idx_start:
            div_start = html.rfind('<div', 0, idx_start)
            if div_start >= 0:
                return html[div_start:idx_end]
        return html

    def _parse_haibao_cards(self, html, fid):
        """海报墙卡片 -> [(tid, pic, title, sub)]。"""
        main = self._main_region(html)
        out = []
        seen = set()
        for m in self._RE_HAIBAO_CARD.finditer(main):
            body = m.group(1)
            mt = self._RE_HB_TID.search(body)
            if not mt:
                continue
            tid = mt.group(1)
            if tid in seen:
                continue
            pic = ""
            mp = self._RE_HB_PIC.search(body)
            if mp:
                p = mp.group(1).strip()
                # 过滤站点模板图 / 占位图
                if p and "nophoto" not in p and not p.startswith("template/") \
                        and not p.startswith("static/"):
                    pic = p
            mt2 = self._RE_HB_TITLE.search(body)
            title = _clean_title(mt2.group(1)) if mt2 else ""
            if not title or len(title) < 1:
                continue
            ms = self._RE_HB_SUB.search(body)
            sub = _clean_title(ms.group(1)) if ms else ""
            seen.add(tid)
            out.append((tid, pic, title, sub))
        return out

    def _parse_list(self, html, fid):
        """解析列表页 -> (items, dates)

        items: [{"tid", "vod_name", "vod_pic"}]
        dates: {tid: "2026-9-9"}
        """
        main = self._main_region(html)
        items = []
        dates = {}
        seen = set()

        # 表格布局里每行自带时间（最后回复时间）
        for m in self._RE_TBODY.finditer(main):
            tid = m.group(1)
            md = self._RE_ROW_DATE.search(m.group(2))
            if md:
                dates[tid] = _fmt_date(md.group(1))

        # 布局 1：标准表格布局（fid 86/78/112/116）—— 有 class="s xst"
        for m in self._RE_THREAD_ROW.finditer(main):
            tid = m.group(1)
            if tid in seen:
                continue
            title = _clean_title(m.group(2))
            if not title or len(title) < 2:
                continue
            seen.add(tid)
            items.append({"tid": tid, "vod_name": title, "vod_pic": ""})

        # 布局 2：海报墙卡片（haibao 模式 / 默认就是海报墙的版块）
        if not items:
            for tid, pic, title, sub in self._parse_haibao_cards(html, fid):
                if tid in seen:
                    continue
                seen.add(tid)
                full = (title + " " + sub).strip() if sub else title
                items.append({"tid": tid, "vod_name": full, "vod_pic": pic})

        # 布局 3：其它海报墙变体（逐锚点兜底）
        if not items:
            for m in self._RE_ANCHOR_THREAD.finditer(main):
                tid = m.group(1)
                if tid in seen:
                    continue
                body = m.group(2) or ""
                pic = ""
                mi_src = self._RE_IMG_SRC.search(body)
                if mi_src:
                    p = mi_src.group(1).strip()
                    if p and "nophoto" not in p and not p.startswith("template/"):
                        pic = p
                alt = ""
                mi_alt = self._RE_IMG_ALT.search(body)
                if mi_alt:
                    alt = _clean_title(mi_alt.group(1))
                title = ""
                mi_t = self._RE_CARD_TITLE.search(body)
                if mi_t:
                    title = _clean_title(mi_t.group(1))
                meta = ""
                mi_m = self._RE_CARD_META.search(body)
                if mi_m:
                    meta = _clean_title(mi_m.group(1))
                if alt and len(alt) > len(title):
                    full = alt
                elif title and meta:
                    full = (title + " " + meta).strip()
                else:
                    full = title
                if not full or len(full) < 2:
                    continue
                seen.add(tid)
                items.append({"tid": tid, "vod_name": full, "vod_pic": pic})

        return items, dates

    def _fetch_tid_info(self, fid, tid):
        """抓帖子详情，补「发表日期 + 片长」，结果写进全局缓存。"""
        cached = _tid_info_get(tid)
        if cached.get("date") and cached.get("runtime"):
            return cached
        html = self._get("%s/thread-%s-1-1.html" % (BASE, tid))
        if not html or self._looks_like_login_page(html):
            return cached
        info = dict(cached)
        mp = self._RE_POSTED.search(html)
        if mp:
            info["date"] = _fmt_date(mp.group(1))
        # 片长只在首楼正文里找，避免抓到推荐位标题里的「162分钟」之类
        scope = html
        mpost = self._RE_FIRST_POST.search(html)
        if mpost:
            scope = mpost.group(1)
        m2 = self._RE_RUNTIME.search(scope)
        if m2:
            info["runtime"] = _fmt_runtime(m2.group(1))
        elif not mpost:
            m3 = self._RE_RUNTIME_LOOSE.search(html)
            if m3:
                info["runtime"] = _fmt_runtime(m3.group(1))
        # 海报：表格布局的版块（fid 86/78/116）列表页没有图，只能从首楼取
        if not info.get("pic"):
            m_img = self._RE_IMAGE.search(scope)
            if m_img:
                p = m_img.group(1)
                if p and "nophoto" not in p:
                    info["pic"] = p
            if not info.get("pic"):
                m_p = self._RE_POSTER.search(scope)
                if m_p:
                    info["pic"] = m_p.group(1)
        _tid_info_put(tid, **info)
        return info

    def _prefetch(self, items, fid):
        """并发补抓列表项缺的日期 / 片长。"""
        def _one(it):
            try:
                info = self._fetch_tid_info(fid, it.get("tid"))
            except Exception as e:
                print("[DJYDXS] 补抓 tid=%s 失败: %s" % (it.get("tid"), e))
                return
            if not it.get("date") and info.get("date"):
                it["date"] = info["date"]
            if not it.get("runtime") and info.get("runtime"):
                it["runtime"] = info["runtime"]
            if not it.get("vod_pic") and info.get("pic"):
                it["vod_pic"] = info["pic"]

        if _Pool and len(items) > 1:
            try:
                with _Pool(max_workers=max(1, int(PREFETCH_WORKERS))) as ex:
                    list(ex.map(_one, items))
                return
            except Exception as e:
                print("[DJYDXS] 并发补抓异常，退回串行: %s" % e)
        for it in items:
            _one(it)

    def _parse_category(self, fid, page, order="latest", prefetch=True):
        """抓取一个版块的列表页，返回 (items, pagecount, total)。

        流程：
          1. 抓默认布局页（表格版块能拿到完整标题 + 日期）
          2. 抓 movmod=haibao 海报墙页拿海报图，按 tid 合并
          3. 用缓存 / 并发补抓补齐「完整日期 + 片长」
        """
        fid = int(fid)
        page = max(1, int(page or 1))

        html = self._get(self._list_url(fid, page, order))
        if not html:
            return [], 0, 0
        # 登录失效自检：Discuz 会把未登录用户跳到 member.php 登录页
        if self._looks_like_login_page(html):
            print("[DJYDXS] 疑似 Cookie 失效（登录页被跳）: fid=%s page=%s" % (fid, page))
            return [], 0, 0

        items, dates = self._parse_list(html, fid)
        pagecount, total = self._parse_pager(html, fid)

        # ---- 海报：默认布局经常没有图，再抓一次海报墙模式补上 ----
        if USE_HAIBAO:
            need = [it for it in items if not it.get("vod_pic")]
            if need or not items:
                hb_html = self._get(self._list_url(fid, page, order, haibao=True))
                if hb_html and not self._looks_like_login_page(hb_html):
                    cards = self._parse_haibao_cards(hb_html, fid)
                    hb_map = {t: (p, ti, s) for t, p, ti, s in cards}
                    if not items:
                        # 默认页一条都没解析出来，整份用海报墙结果
                        for t, p, ti, s in cards:
                            items.append({
                                "tid": t,
                                "vod_name": (ti + " " + s).strip() if s else ti,
                                "vod_pic": p,
                            })
                    else:
                        for it in items:
                            hb = hb_map.get(it.get("tid"))
                            if not hb:
                                continue
                            if hb[0]:
                                it["vod_pic"] = hb[0]
                            # 标题取更详细的那个
                            hb_full = (hb[1] + " " + hb[2]).strip() if hb[2] else hb[1]
                            if len(hb_full) > len(it.get("vod_name") or ""):
                                it["vod_name"] = hb_full
                    if not pagecount:
                        pagecount, total = self._parse_pager(hb_html, fid)

        # ---- 日期 / 片长：先吃缓存 ----
        for it in items:
            c = _tid_info_get(it.get("tid"))
            if not it.get("date"):
                it["date"] = dates.get(it.get("tid")) or c.get("date") or ""
            if not it.get("runtime") and c.get("runtime"):
                it["runtime"] = c["runtime"]
            if not it.get("vod_pic") and c.get("pic"):
                it["vod_pic"] = c["pic"]

        # ---- 还缺的并发补抓 ----
        if prefetch and PREFETCH_DETAIL:
            todo = [it for it in items
                    if not it.get("date") or not it.get("runtime")
                    or not it.get("vod_pic")][:PREFETCH_MAX]
            if todo:
                self._prefetch(todo, fid)

        # 统一补上 fid / vod_id
        for it in items:
            it["fid"] = fid
            it["vod_id"] = "fid:%d###%s" % (fid, it.get("tid"))

        return items, pagecount, total

    def _parse_pager(self, html, fid):
        """从列表页底部抽总页数 / 总帖数。"""
        pagecount = 0
        m_cn = self._RE_PAGES_CN.search(html)
        if m_cn:
            try:
                pagecount = int(m_cn.group(1))
            except Exception:
                pass
        if pagecount <= 0:
            m_en = self._RE_PAGES_EN.search(html)
            if m_en:
                try:
                    pagecount = int(m_en.group(1))
                except Exception:
                    pass
        if pagecount <= 0:
            max_link_page = 0
            for m in self._RE_LAST_PAGE_LINK.finditer(html):
                if int(m.group(1)) == fid:
                    p = int(m.group(2))
                    if p > max_link_page:
                        max_link_page = p
            if max_link_page > 0:
                pagecount = max_link_page

        total = 0
        m_total = self._RE_TOTAL.search(html)
        if m_total:
            try:
                total = int(m_total.group(1))
            except Exception:
                pass
        return pagecount, total

    # --------------------------------------------------------------
    # 解析：帖子详情
    # --------------------------------------------------------------

    _RE_SUBJECT = re.compile(
        r'<span id="thread_subject"[^>]*>(.*?)</span>', re.S
    )
    _RE_NTCJ_BOXES = re.compile(
        r'window\._NTCJ_BOXES=(\[[^\r\n]*\]);', re.S
    )
    _RE_POSTER = re.compile(
        r'file="(https?://[^"\s]+?(?:posters|DSXintu|dstmdb)[^"\s]*)"',
        re.I,
    )
    _RE_IMAGE = re.compile(
        r'<img[^>]*?file="(https?://[^"\s]+)"',
        re.I,
    )
    # 帖子正文：抓第一个 postmessage 里的纯文本（作为简介）
    _RE_FIRST_POST = re.compile(
        r'<td class="t_f" id="postmessage_\d+">(.*?)</td>\s*</tr>',
        re.S,
    )

    # type -> 展示名称
    _BOX_NAME = {
        "baidu":   "百度网盘",
        "115":     "115网盘",
        "ed2k":    "电驴ed2k",
        "thunder": "迅雷thunder",
        "quark":   "夸克网盘",
        "lanzou":  "蓝奏云",
        "aliyun":  "阿里云盘",
        "magnet":  "磁力链接",
        "m3u8":    "直连M3U8",
        "mp4":     "直连MP4",
        "http":    "直连HTTP",
    }

    def _parse_detail(self, fid, tid):
        """抓 thread-{tid}-1-1.html，解析出 subject / poster / boxes / content。"""
        fid = int(fid)
        url = "%s/thread-%s-1-1.html" % (BASE, tid)
        html = self._get(url)
        if not html:
            return None

        # 登录失效自检
        if self._looks_like_login_page(html):
            print("[DJYDXS] 帖子详情页疑似 Cookie 失效: %s" % url)
            return None

        # 标题
        title = ""
        m_sub = self._RE_SUBJECT.search(html)
        if m_sub:
            title = _clean_title(m_sub.group(1))

        # 简介（取第一楼正文，剥离标签）
        content = ""
        m_post = self._RE_FIRST_POST.search(html)
        post_html = m_post.group(1) if m_post else ""
        if post_html:
            raw = post_html
            raw = re.sub(r"<img[^>]*>", " ", raw, flags=re.I)
            raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
            raw = re.sub(r"<[^>]+>", "", raw)
            raw = _unescape(raw)
            content = re.sub(r"\s+", " ", raw).strip()[:600]

        # 海报：优先首楼正文里的图（<img ... file="...">）。
        # 不能全页扫，否则会抓到推荐位 / 轮播横幅的图。
        pic = ""
        m_img = self._RE_IMAGE.search(post_html) if post_html else None
        if m_img:
            pic = m_img.group(1)
        if not pic:
            m_pic = self._RE_POSTER.search(post_html or html)
            if m_pic:
                pic = m_pic.group(1)
        self._last_picture = pic

        # 日期 + 片长（顺手写进缓存，列表页下次直接用）
        # 列表页给的是「最后回复时间」，详情页这里取到的是「发表时间」。
        # 缓存里已有列表日期时以列表为准，避免同一条目前后两个日期。
        date = (_tid_info_get(tid).get("date") or "")
        if not date:
            m_pd = self._RE_POSTED.search(html)
            if m_pd:
                date = _fmt_date(m_pd.group(1))
        runtime = ""
        m_rt = self._RE_RUNTIME.search(post_html or html)
        if m_rt:
            runtime = _fmt_runtime(m_rt.group(1))
        elif not post_html:
            m_rt2 = self._RE_RUNTIME_LOOSE.search(html)
            if m_rt2:
                runtime = _fmt_runtime(m_rt2.group(1))
        _tid_info_put(tid, date=date, runtime=runtime, pic=pic)

        # 下载源 _NTCJ_BOXES
        boxes = []
        m_box = self._RE_NTCJ_BOXES.search(html)
        if m_box:
            try:
                arr = json.loads(m_box.group(1))
                for b in arr:
                    if not isinstance(b, dict):
                        continue
                    t = str(b.get("type") or "").lower().strip()
                    u = str(b.get("url") or "").strip()
                    p = str(b.get("pwd") or "").strip()
                    if not u:
                        continue
                    boxes.append({"type": t, "url": u, "pwd": p})
            except Exception as e:
                print("[DJYDXS] 解析 _NTCJ_BOXES 失败 tid=%s: %s" % (tid, e))

        # 兜底：如果 _NTCJ_BOXES 拿不到，扫正文里的常规网盘 / 磁力链接
        if not boxes:
            boxes = self._fallback_extract_links(html)

        return {
            "vod_id": "fid:%d###%s" % (fid, tid),
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "boxes": boxes,
            "detail_url": url,
            "date": date,
            "runtime": runtime,
        }

    def _fallback_extract_links(self, html):
        """_NTCJ_BOXES 抓不到时的兜底：从正文里挖网盘 / 磁力 / ed2k 直链。

        只在插件失效时才启用，正常情况下不会走到这里。
        """
        found = []
        patterns = [
            (r"https?://pan\.baidu\.com/s/[A-Za-z0-9_\-]+(?:\?pwd=[A-Za-z0-9]+)?", "baidu"),
            (r"https?://(?:115\.cn|115cdn\.com)/s/[A-Za-z0-9_\-]+(?:\?password=[A-Za-z0-9]+)?", "115"),
            (r"https?://(?:www\.)?pan\.quark\.cn/s/[A-Za-z0-9_\-]+(?:\?pwd=[A-Za-z0-9]+)?", "quark"),
            (r"https?://www\.lanzoux\.com/[A-Za-z0-9]+\.htm", "lanzou"),
            (r"ed2k://\|file\|[^\s]+", "ed2k"),
            (r"thunder://[^\s\"'<>]+", "thunder"),
            (r"magnet:\?xt=urn:btih:[A-Za-z0-9]+", "magnet"),
            (r"https?://[^\s\"'<>]+\.(?:mp4|mkv|m3u8)(?:\?[^\s\"'<>]*)?", "http"),
        ]
        for pat, kind in patterns:
            for m in re.finditer(pat, html, re.I):
                u = m.group(0).strip()
                # 剔除明显的 JS 变量、图片、样式链接
                if u.endswith((".js", ".css", ".png", ".jpg", ".gif")):
                    continue
                # 剔除论坛自身
                if BASE in u:
                    continue
                # 剔除已记录
                if any(u == f["url"] for f in found):
                    continue
                pwd = ""
                pm = re.search(r"(?:pwd|password)=([A-Za-z0-9]+)", u)
                if pm:
                    pwd = pm.group(1)
                found.append({"type": kind, "url": u, "pwd": pwd})
                if len(found) >= MAX_BOXES:
                    break
            if len(found) >= MAX_BOXES:
                break
        return found

    # --------------------------------------------------------------
    # TVBox 标准接口
    # --------------------------------------------------------------

    def homeContent(self, filter):
        """首页：返回所有资源版块 + 首页列表（默认第一个版块）。"""
        self._apply_extend(filter if isinstance(filter, dict) else {})
        classes = []
        for fid, name in CATEGORIES:
            classes.append({"type_id": "fid:%d" % fid, "type_name": name})
        # 首页显示第一个版块的列表，作为快速入口
        first_fid = CATEGORIES[0][0] if CATEGORIES else 0
        listing = {"list": []}
        if first_fid:
            try:
                listing = self.categoryContent("fid:%d" % first_fid, 1, {}, {})
            except Exception as e:
                print("[DJYDXS] homeContent 首页列表异常: %s" % e)
        return {
            "class": classes,
            "list": listing.get("list", []),
            "page": listing.get("page", 1),
            "pagecount": listing.get("pagecount", 0),
        }

    def homeVideoContent(self):
        return self.categoryContent(
            "fid:%d" % (CATEGORIES[0][0] if CATEGORIES else 0), 1, {}, {}
        )

    def getFilter(self, tid):
        return [
            {"key": "order", "name": "排序", "value": [
                {"n": "最新回复", "v": "latest"},
                {"n": "最新主题", "v": "lastpost"},
                {"n": "热门",     "v": "heat"},
                {"n": "热帖",     "v": "hot"},
                {"n": "精华",     "v": "digest"},
            ]},
        ]

    def categoryContent(self, tid, pg, filter, extend):
        self._apply_extend(extend)
        # 合并 filter/extend 提取 order
        order = DEFAULT_ORDER
        for src in (filter, extend):
            if isinstance(src, str):
                s = src.strip()
                if s and s.lower() not in ("true", "false", "null", "none"):
                    try:
                        src = json.loads(s)
                    except Exception:
                        src = None
            if isinstance(src, dict):
                v = src.get("order") or src.get("orderby")
                if v:
                    order = str(v).strip()
        fid = _fid_from_tid(tid)
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        if fid <= 0:
            return {"list": [], "page": pg, "pagecount": 0, "total": 0}

        items, pagecount, total = self._parse_category(fid, pg, order)
        vods = [self._to_vod(x) for x in items]
        # 没有 total 就用 list 长度兜底；没有 pagecount 用 9999
        if total <= 0:
            total = len(items)
        if pagecount <= 0:
            pagecount = 9999 if len(items) else 1
        return {
            "list": vods,
            "page": pg,
            "pagecount": pagecount,
            "total": total,
            "limit": max(len(items), 1),
        }

    @staticmethod
    def _marks(item):
        """海报角标：完整日期 + 片长，如 "2026-9-9 · 117分钟"。"""
        date = item.get("date") or ""
        runtime = item.get("runtime") or ""
        return " · ".join([x for x in (date, runtime) if x])

    def _to_vod(self, item):
        """把内部解析的 item 转为 TVBox 的 Vod 对象。"""
        fid = item.get("fid") or _fid_from_tid(item.get("vod_id"))
        tid = item.get("tid") or ""
        name = item.get("vod_name") or ""
        date = item.get("date") or ""
        vod = {
            "vod_id": "fid:%s###%s" % (fid, tid),
            "vod_name": name,
            "vod_pic": item.get("vod_pic") or "",
            "vod_remarks": self._marks(item),
            "vod_class": item.get("category", ""),
            "type_id": "fid:%s" % fid,
            # 有完整日期时 vod_year 留空：皮肤会同时渲染 vod_year(上方) 和
            # vod_remarks(下方)，若都放日期会出现「上面一个孤立日期 + 下面一个日期·时长」
            # 重复。日期已经放进下方 remarks，上方就不再多显。拿不到日期才退回标题年份。
            "vod_year": "" if date else self._year_from_title(name),
        }
        if CARD_STYLE:
            vod["style"] = dict(CARD_STYLE)
        return vod

    @staticmethod
    def _year_from_title(title):
        m = re.search(r"\b(19[89]\d|20[0-4]\d)\b", str(title or ""))
        return m.group(1) if m else ""

    def detailContent(self, ids):
        try:
            vid = str(ids[0]) if ids else ""
        except Exception:
            vid = ""
        fid, tid = _fid_from_tid(vid)
        if not fid or not tid:
            return {"list": []}

        info = self._parse_detail(fid, tid)
        if not info:
            return {"list": []}

        self._last_picture = info.get("vod_pic") or ""

        # 拼装 vod_play_from / vod_play_url
        play_from = []
        play_url = []
        boxes = info.get("boxes") or []
        if not boxes:
            play_from.append("0")
            play_url.append("无可用下载链接$__ACK__")
        else:
            # 按下载类型分组：同类型（如 8 个 ed2k 分集）合成一条线路，
            # 而不是拆成 8 条线路，TVBox 里选集体验更好。
            groups = []          # [(type, [box, ...])]
            gmap = {}            # type -> groups 里的下标
            for b in boxes[:MAX_BOXES]:
                key = (b.get("type") or "下载").lower()
                if key not in gmap:
                    gmap[key] = len(groups)
                    groups.append((key, []))
                groups[gmap[key]][1].append(b)

            for key, blist in groups:
                name = self._BOX_NAME.get(key, key or "下载")
                play_from.append(name)
                eps = []
                for i, b in enumerate(blist):
                    label = self._box_label(b)
                    # 同类型多条时为每条加序号，方便选集
                    if len(blist) > 1:
                        fn = self._box_filename(b)
                        label = fn if fn else "%s 第%d个" % (label, i + 1)
                    # id 用 base64 存原始 URL，避免 $ 等字符被 TVBox 解析器吃掉
                    eps.append("%s$%s" % (label.replace("$", " "), _b64_encode(b["url"])))
                play_url.append("#".join(eps))
        name = info.get("vod_name") or ""
        date = info.get("date") or ""
        runtime = info.get("runtime") or ""
        vod = {
            "vod_id": info["vod_id"],
            "vod_name": name,
            "vod_pic": info.get("vod_pic") or "",
            "vod_remarks": " · ".join([x for x in (date, runtime) if x]),
            "vod_content": info.get("vod_content") or "",
            "vod_class": "",
            # 与 _to_vod 一致：有完整日期时 vod_year 留空，避免皮肤同时渲染
            # vod_year + vod_remarks 造成「孤立日期 + 日期·时长」重复显示
            "vod_year": "" if date else self._year_from_title(name),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        if CARD_STYLE:
            vod["style"] = dict(CARD_STYLE)
        return {"list": [vod]}

    @staticmethod
    def _box_filename(b):
        """从 ed2k / 磁力 URL 里提取文件名，用作选集名（比乱码 hash 好看）。"""
        url = str(b.get("url") or "")
        name = ""
        if url.lower().startswith("ed2k://"):
            parts = url.split("|")
            if len(parts) > 2:
                name = parts[2]
        elif url.lower().startswith("magnet:"):
            import urllib.parse as _up
            q = _up.parse_qs(_up.urlparse(url).query)
            if q.get("dn"):
                name = q["dn"][0]
        if not name:
            return ""
        # 解 URL 编码 + 去掉扩展名
        try:
            import urllib.parse as _up
            name = _up.unquote(name)
        except Exception:
            pass
        name = re.sub(r"\.(mkv|mp4|iso|ts|avi|rmvb|mov|wmv|ass|srt|zip|rar|7z|torrent)$",
                      "", name, flags=re.I)
        name = name.strip()
        if not name:
            return ""

        # 优先压成「集数 + 集标题」，例如：
        #   Star.Wars...S01E01.A.New.Threat.2160p.DSNP.WEB-DL  ->  "E01 A New Threat"
        m = re.search(r"S(\d{1,2})E(\d{1,3})", name, re.I)
        if m:
            tail = name[m.end():]
            # 截到分辨率/压制组标签为止
            tail = re.split(
                r"(?i)\.?(2160p|1080p|720p|480p|2160i|1080i|4k|web-?dl|webrip|bluray|"
                r"bdrip|remux|h\.?26[45]|x26[45]|xvid|hdr|dv|dolby|truehd|atmos|ddp?5|"
                r"ddp?7|aac|flac|dts|nf|dsnp|hmax|atvp|hulu|amzn|max|10bit|hdr10|sdr)",
                tail,
            )[0]
            ep_title = tail.strip(" .-_[]()").replace(".", " ").strip()
            label = "E%s" % (m.group(2).lstrip("0") or m.group(2))
            if ep_title:
                label += " " + ep_title
            if len(label) > 40:
                label = label[:40] + "…"
            return label

        # 非剧集：去掉冗长的分辨率/编码尾巴后截断
        short = re.split(
            r"(?i)\.?(2160p|1080p|720p|480p|web-?dl|webrip|bluray|bdrip|remux|h\.?26[45]|x26[45])",
            name,
        )[0].strip(" .-_")
        short = (short or name).replace(".", " ").strip()
        if len(short) > 40:
            short = short[:40] + "…"
        return short

    @staticmethod
    def _box_label(b):
        """下载线路的显示名：带上类型 + 密码提示。"""
        kind = b.get("type") or ""
        pwd = b.get("pwd") or ""
        tag = {"baidu": "百度网盘", "115": "115网盘", "ed2k": "ed2k",
               "thunder": "迅雷", "quark": "夸克", "lanzou": "蓝奏云",
               "aliyun": "阿里云盘", "magnet": "磁力", "m3u8": "直连M3U8",
               "mp4": "直连MP4", "http": "直连HTTP"}.get(kind, kind or "下载")
        if pwd:
            return "%s(密码:%s)" % (tag, pwd[:8])
        return tag

    # --------------------------------------------------------------
    # 搜索（走论坛原生 Discuz 搜索，带缓存 + 防刷）
    # --------------------------------------------------------------

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        key = str(key or "").strip()
        if not key:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}

        items, total, pagecount = self._native_search(key, pg, bool(quick))

        # 可选：并发补抓详情拿海报（SEARCH_PREFETCH 默认关，避免搜索变慢）
        if SEARCH_PREFETCH and items:
            try:
                self._prefetch(items, 0)
            except Exception:
                pass

        return {
            "list": [self._to_vod(x) for x in items],
            "page": pg,
            "pagecount": pagecount,
            "total": total,
        }

    # --------------------------------------------------------------
    # 播放
    # --------------------------------------------------------------

    def playerContent(self, flag, id, vipFlags):
        id = str(id or "")
        if id == "__ACK__" or flag in ("0", "提示"):
            return {"parse": 0, "playUrl": "", "url": self._ack_url(),
                    "header": self.ext_headers,
                    "pic": self._last_picture}
        # id 是 base64 编码的原始下载 URL
        raw = _b64_decode(id)
        if not raw:
            raw = id
        if USE_PUSH and not raw.startswith("push://"):
            url = "push://" + raw
        else:
            url = raw
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": self.ext_headers,
            "pic": self._last_picture,
        }

    @staticmethod
    def _ack_url():
        # 空 URL，让播放器不报错
        return ""


# ==================================================================
# TVBox 加载入口
# ==================================================================

def create():
    """兼容部分加载器（走 create() 而不是直接实例化类）。"""
    return Spider()


# 命令行自检用的别名，方便外部 import 后按老名字取
DJYDXSSpider = Spider


# ==================================================================
# 命令行自检（TVBox 加载时不会执行到）
# ==================================================================

if __name__ == "__main__":
    import pprint
    s = DJYDXSSpider()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    def _show(obj, width=120):
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        for line in text.splitlines():
            print(line[:width])

    if cmd == "--home":
        _show(s.homeContent(None))
    elif cmd.startswith("--cat="):
        _show(s.categoryContent(cmd.split("=", 1)[1], 1, {}, {}))
    elif cmd == "--cat" and len(sys.argv) > 2:
        _show(s.categoryContent(sys.argv[2], 1, {}, {}))
    elif cmd.startswith("--detail="):
        _show(s.detailContent([cmd.split("=", 1)[1]]))
    elif cmd == "--detail" and len(sys.argv) > 2:
        vid = sys.argv[2]
        # 允许传 "fid:112###36030" 或直接 "36030"（后者默认 fid=112）
        if "###" in vid:
            vid = vid
        elif vid.isdigit():
            vid = "fid:112###" + vid
        _show(s.detailContent([vid]))
    elif cmd.startswith("--search="):
        _show(s.searchContent(cmd.split("=", 1)[1], 1, 1))
    elif cmd == "--search" and len(sys.argv) > 2:
        _show(s.searchContent(sys.argv[2], 1, 1))
    elif cmd == "--player" and len(sys.argv) > 2:
        # 用法：--player 115网盘1 fid:112###35236
        _show(s.playerContent(sys.argv[2], _b64_encode("https://example.com"), []))
    else:
        print("DJYDXS 论坛爬虫自检模式")
        print("用法：")
        print("  python DJYDXS.py                          交互式跑通全流程")
        print("  python DJYDXS.py --home                    首页（版块 + 第一版块列表）")
        print("  python DJYDXS.py --cat fid:112             指定版块列表页")
        print("  python DJYDXS.py --detail fid:112###35236  指定帖子详情")
        print("  python DJYDXS.py --search 星球              关键词搜索")
        print()
        print("开始自检，先抓首页...")
        home = s.homeContent(None)
        print("  版块数: %d" % len(home.get("class", [])))
        for c in home.get("class", [])[:5]:
            print("   - %s  (%s)" % (c["type_name"], c["type_id"]))
        lst = home.get("list", [])
        print("  首页列表条数: %d" % len(lst))
        for v in lst[:5]:
            print("   - %s" % (v.get("vod_name") or "")[:44])
            print("     角标=%-22s 海报=%s  style=%s" % (
                v.get("vod_remarks") or "(空)",
                "有" if v.get("vod_pic") else "无",
                v.get("style") or "-"))
        nopic = sum(1 for v in lst if not v.get("vod_pic"))
        print("  无海报条数: %d / %d" % (nopic, len(lst)))
        if lst:
            print("  首条: %s" % lst[0].get("vod_name"))
            detail = s.detailContent([lst[0]["vod_id"]])
            if detail.get("list"):
                v = detail["list"][0]
                print("  详情标题: %s" % v.get("vod_name"))
                print("  详情海报: %s" % (v.get("vod_pic") or "(无)")[:80])
                pf = v.get("vod_play_from", "")
                pu = v.get("vod_play_url", "")
                print("  播放线路: %s" % pf)
                print("  播放地址: %s" % pu[:120])

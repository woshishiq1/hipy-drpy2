# coding=utf-8
"""
快乐影院 tspnd.cc | TVBox Python 爬虫 
关键:
  - 网络层 100% Python 标准库 (urllib), 零第三方依赖, TVBox 任何环境可跑
  - 模块级初始化全部防御式+懒加载, 任何环境均可加载成功 (分类永不丢失)
  - 自动破解 _guard 滑块验证 (RC4 + guardret cookie), 手动管理 cookie
  - 分类筛选: 子分类 / 类型 / 年份 / 首字母 / 语言 (与站点 tspnbdshow 一致)
  - 详情页: 导演/主演/类型/地区/更新时间/剧情介绍
  - 线路顺序与网站完全一致 (线路N 由站点数据顺序决定)
  - 播放页解析 player_aaaa 直取 m3u8 直链
  - 全程写调试日志, 便于现场排查
"""
import re
import sys
import os
import json
import time
import base64
import struct
import zlib
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except Exception:
    class _BaseSpider(object):
        pass
    Spider = _BaseSpider

# 其余标准库逐一防御导入 (任何一项失败都不影响模块加载)
ssl = None
tempfile = None
urllib_request = None
http_cookiejar = None
try:
    import ssl as ssl
except Exception:
    pass
try:
    import tempfile as tempfile
except Exception:
    pass
try:
    import urllib.request as urllib_request
except Exception:
    pass
try:
    import http.cookiejar as http_cookiejar
except Exception:
    pass

HOST = "https://tspnd.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/style/26/static/images/load7.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


class _Rsp(object):
    """轻量响应对象 (兼容 .text/.content/.headers 用法)"""
    def __init__(self, text, content, headers, url):
        self.text = text
        self.content = content
        self.headers = headers
        self.url = url


# ===================== 懒加载: 日志 / cookie / opener =====================
_LOG_PATH = None
_LOG_CHECKED = False
_COOKIE_JAR = None
_OPENER = None


def _get_log_path():
    """懒定位日志文件, 找不到就放弃, 绝不抛异常"""
    global _LOG_PATH, _LOG_CHECKED
    if _LOG_CHECKED:
        return _LOG_PATH
    _LOG_CHECKED = True
    cands = []
    try:
        if tempfile is not None:
            cands.append(os.path.join(tempfile.gettempdir(), "kuaile_debug.log"))
    except Exception:
        pass
    cands.append("/sdcard/快乐影院_debug.log")
    cands.append("kuaile_debug.log")
    for _p in cands:
        try:
            with open(_p, "a", encoding="utf-8") as f:
                f.write("==== %s 爬虫加载 V2.1 ====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            _LOG_PATH = _p
            break
        except Exception:
            continue
    return _LOG_PATH


def _get_jar():
    global _COOKIE_JAR
    if _COOKIE_JAR is None:
        if http_cookiejar is None:
            raise RuntimeError("http.cookiejar 不可用")
        _COOKIE_JAR = http_cookiejar.CookieJar()
    return _COOKIE_JAR


def _get_opener():
    global _OPENER
    if _OPENER is None:
        handlers = []
        try:
            handlers.append(urllib_request.HTTPCookieProcessor(_get_jar()))
        except Exception:
            pass
        try:
            handlers.append(urllib_request.HTTPRedirectHandler())
        except Exception:
            pass
        try:
            if ssl is not None:
                handlers.append(urllib_request.HTTPSHandler(
                    context=ssl._create_unverified_context()))
        except Exception:
            pass
        _OPENER = urllib_request.build_opener(*handlers)
    return _OPENER


def _cookie_get(name):
    try:
        for c in _get_jar():
            if c.name == name:
                return c.value
    except Exception:
        pass
    return None


def _cookie_set(name, value):
    try:
        ck = http_cookiejar.Cookie(
            0, name, value, None, False, "tspnd.cc", True, False,
            "/", True, secure=False, expires=None, discard=True,
            comment=None, comment_url=None, rest={}, rfc2109=False)
        _get_jar().set_cookie(ck)
    except Exception:
        pass

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "9",  "type_name": "短视频"},
    {"type_id": "51", "type_name": "即将上映"},
]

# 与网站筛选栏完全一致: 栏1 子分类(tid), 栏2 首字母, 栏3 年份
_SUBCLASS = {
    "1": [("1", "全部"), ("35", "喜剧片"), ("36", "动作片"), ("37", "爱情片"),
          ("38", "科幻片"), ("39", "恐怖片"), ("40", "剧情片"), ("41", "战争片")],
    "2": [("2", "全部"), ("42", "国产剧"), ("43", "港台剧"), ("44", "日韩剧"),
          ("45", "欧美剧")],
    "3": [("3", "全部"), ("46", "国内综艺"), ("47", "海外综艺")],
    "4": [("4", "全部"), ("48", "国内动漫"), ("49", "海外动漫")],
    "9": [("9", "全部"), ("57", "动画短片"), ("58", "短剧")],
    "51": [("51", "全部")],
}

_LETTERS = ([("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E"),
             ("F", "F"), ("G", "G"), ("H", "H"), ("I", "I"), ("J", "J"),
             ("K", "K"), ("L", "L"), ("M", "M"), ("N", "N"), ("O", "O"),
             ("P", "P"), ("Q", "Q"), ("R", "R"), ("S", "S"), ("T", "T"),
             ("U", "U"), ("V", "V"), ("W", "W"), ("X", "X"), ("Y", "Y"),
             ("Z", "Z")])
_YEARS = [(str(y), str(y)) for y in range(2026, 2015, -1)]
_LANGS = [("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"), ("日语", "日语")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    flt = [
        {"key": "sub", "name": "分类",
         "value": [{"n": n, "v": v} for v, n in _SUBCLASS.get(tid, [(tid, "全部")])]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in _YEARS]},
        {"key": "letter", "name": "字母",
         "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in _LETTERS]},
        {"key": "lang", "name": "语言",
         "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in _LANGS]},
    ]
    FILTERS[tid] = flt


# ===================== 正则 =====================
# img 标签先整段抓取, 再优先取 data-src (站点懒加载: src="" data-src=真图)
_RE_CARD = re.compile(
    r'<a href="(/tspnbd/\d+\.html)">\s*(<img[^>]*>)',
    re.S | re.I)
# 首页推荐卡 (ys-poster)
_RE_HOME_CARD = re.compile(
    r'<a href="(/tspnbd/\d+\.html)">\s*'
    r'<div class="ys-poster">\s*(<img[^>]*>)',
    re.S | re.I)
# 首页轮播
_RE_SWIPER = re.compile(
    r'<a href="(/tspnbd/\d+\.html)">\s*(<img[^>]*>)\s*'
    r'<div class="filmName">([^<]*)</div>',
    re.S | re.I)


def _img_pic(tag):
    """从 img 标签取图片地址: data-src 优先, src 兜底"""
    if not tag:
        return ""
    m = re.search(r'data-src="([^"]*)"', tag, re.I)
    if not m or not m.group(1):
        m = re.search(r'src="([^"]*)"', tag, re.I)
    return m.group(1) if m else ""
# 详情页线路块: 线路名 + 其后剧集
_RE_LINE_BLOCK = re.compile(
    r'name17">(线路\d+)</div>\s*</div>\s*</div>\s*'
    r'<div class="list-number1"[^>]*>([\s\S]*?)</div>\s*(?:<div class="list-name23"|<div class="link")',
    re.S | re.I)
_RE_EP = re.compile(
    r'<a href="(/tspnbdplay/[^"]+)"><div>([^<]*)</div></a>', re.I)
_RE_TOTAL = re.compile(r'class="total">(\d+)')
_RE_H1_TITLE = re.compile(r'<title>([^<]*)</title>')
_RE_NAME18 = re.compile(r'<div class="ys-name18">([^<]*)</div>')
_RE_YEAR1 = re.compile(r'<div class="year1">([^<]*)</div>')
_RE_DIRECTOR = re.compile(
    r'director1">导演：((?:<a[^>]*>[^<]*</a>\s*)+)', re.S)
_RE_ACTORS = re.compile(
    r'main-actors2">\s*主演：((?:<a[^>]*>[^<]*</a>\s*)+)', re.S)
_RE_STYLE = re.compile(r'ys-style8">类型：<span>(.*?)</span>', re.S)
_RE_AREA = re.compile(r'ys-style8">地区：<span>(.*?)</span>', re.S)
_RE_ROLE = re.compile(r'<div class="role">([^<]*)</div>')
# 剧情: Synopsis-word 到 相关搜索 / 网友评论 前
_RE_SYN = re.compile(
    r'Synopsis-word[^>]*>\s*(.*?)(?:相关搜索|网友评论|</div>\s*</div>\s*</div>)', re.S)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name="description"[^>]*content="([^"]*)"', re.I)
# 播放数据
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)


class Spider(Spider):

    def getName(self):
        return "快乐影院"

    def log(self, *args, **kw):
        try:
            line = "[%s] %s" % (time.strftime("%H:%M:%S"),
                                " ".join(str(a) for a in args))
            print("[快乐影院]", line)
            lp = _get_log_path()
            if lp:
                with open(lp, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            pass

    def _http_get(self, url, headers=None, timeout=15, **kw):
        """自带 HTTP GET: 纯标准库 urllib, 零第三方依赖"""
        h = {"User-Agent": UA, "Accept": "*/*",
             "Accept-Language": "zh-CN,zh;q=0.9"}
        if headers:
            h.update(headers)
        req = urllib_request.Request(url, headers=h)
        rsp = _get_opener().open(req, timeout=timeout)
        data = rsp.read()
        try:
            charset = rsp.headers.get_content_charset() or "utf-8"
        except Exception:
            charset = "utf-8"
        try:
            text = data.decode(charset, "ignore")
        except Exception:
            text = data.decode("utf-8", "ignore")
        return _Rsp(text, data, rsp.headers, rsp.geturl())

    def init(self, extend=""):
        self.log("init 开始, extend=%s" % (extend or ""))
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        try:
            self.site_url = (self.extend.get("site") or HOST).rstrip("/")
            self.headers = {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": self.site_url + "/",
            }
            self.default_pic = DEFAULT_PIC
            self._play_cache = {}
            self._warmed = False
        except Exception as e:
            self.log("init 异常: %s" % e)
        self.log("init: site=%s, 日志文件=%s" % (
            getattr(self, "site_url", HOST), _get_log_path() or "不可用"))

    # ===================== 滑块破解 =====================
    @staticmethod
    def _rc4(text, key):
        s = list(range(256))
        j = 0
        for i in range(256):
            j = (j + s[i] + ord(key[i % len(key)])) % 256
            s[i], s[j] = s[j], s[i]
        i = j = 0
        out = []
        for ch in text:
            i = (i + 1) % 256
            j = (j + s[i]) % 256
            s[i], s[j] = s[j], s[i]
            out.append(chr(ord(ch) ^ s[(s[i] + s[j]) % 256]))
        return ''.join(out)

    @staticmethod
    def _png_to_gray(data):
        """纯 Python 解码 PNG 为灰度二维列表 (无 PIL/numpy 依赖)"""
        import struct, zlib
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        pos = 8
        width = height = bitdepth = ctype = None
        plte = None
        idat = b''
        while pos + 8 <= len(data):
            ln, = struct.unpack('>I', data[pos:pos + 4])
            typ = data[pos + 4:pos + 8]
            chunk = data[pos + 8:pos + 8 + ln]
            pos += 12 + ln
            if typ == b'IHDR':
                width, height, bitdepth, ctype = struct.unpack('>IIBB', chunk[:10])
            elif typ == b'PLTE':
                plte = chunk
            elif typ == b'IDAT':
                idat += chunk
            elif typ == b'IEND':
                break
        if width is None or bitdepth != 8:
            return None
        raw = zlib.decompress(idat)
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype, 3)
        stride = width * channels
        # 反滤波
        out = []
        prev = [0] * stride
        p = 0
        for y in range(height):
            f = raw[p]; p += 1
            line = list(raw[p:p + stride]); p += stride
            if f == 1:
                for i in range(channels, stride):
                    line[i] = (line[i] + line[i - channels]) & 0xFF
            elif f == 2:
                for i in range(stride):
                    line[i] = (line[i] + prev[i]) & 0xFF
            elif f == 3:
                for i in range(stride):
                    left = line[i - channels] if i >= channels else 0
                    line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
            elif f == 4:
                for i in range(stride):
                    a_ = line[i - channels] if i >= channels else 0
                    b_ = prev[i]
                    c_ = prev[i - channels] if i >= channels else 0
                    pp = a_ + b_ - c_
                    pa, pb, pc = abs(pp - a_), abs(pp - b_), abs(pp - c_)
                    pr = a_ if (pa <= pb and pa <= pc) else (b_ if pb <= pc else c_)
                    line[i] = (line[i] + pr) & 0xFF
            out.append(line)
            prev = line
        # 转灰度
        gray = []
        for y in range(height):
            row = out[y]
            g = []
            if ctype == 3 and plte:
                for x in range(width):
                    idx = row[x] * 3
                    g.append(int(0.299 * plte[idx] + 0.587 * plte[idx + 1] + 0.114 * plte[idx + 2]))
            elif ctype == 0:
                g = list(row[:width])
            elif ctype == 2:
                for x in range(width):
                    i = x * 3
                    g.append(int(0.299 * row[i] + 0.587 * row[i + 1] + 0.114 * row[i + 2]))
            elif ctype == 6:
                for x in range(width):
                    i = x * 4
                    if row[i + 3] < 40:
                        g.append(255)  # 透明→白(绿底近似)
                    else:
                        g.append(int(0.299 * row[i] + 0.587 * row[i + 1] + 0.114 * row[i + 2]))
            elif ctype == 4:
                for x in range(width):
                    i = x * 2
                    if row[i + 1] < 40:
                        g.append(255)
                    else:
                        g.append(row[i])
            else:
                return None
            gray.append(g)
        return gray

    def _solve_guard(self):
        """破解 _guard 滑块验证, 成功返回 True"""
        try:
            st = time.time()
            rsp = self._http_get(
                self.site_url + "/_guard/easy_slide.png?t=%d" % (time.time() * 1000),
                headers={"User-Agent": UA, "Referer": self.site_url + "/"},
                timeout=20)
            guard = _cookie_get("guard")
            word = _cookie_get("guardword")
            if not guard or not word:
                self.log("guard: 缺少 cookie")
                return False
            word = int(word)

            try:
                gray = self._png_to_gray(rsp.content)
                if gray is None:
                    # 兜底: PIL+numpy
                    from PIL import Image
                    import numpy as np
                    import io
                    arr = np.array(Image.open(io.BytesIO(rsp.content)).convert('L')).astype(float)
                    gray = arr.tolist()
                # 缺口 = 半透明暗块, 顶部 y = guardword
                # 在 y∈[word+2, word+42] 检测"比同列上下文暗"的列 → 缺口暗带
                a = gray
                W = len(a[0])
                # 列均值
                def colmean(r0, r1):
                    r0 = max(0, r0); r1 = min(len(a), r1)
                    if r1 <= r0:
                        return [0.0] * W
                    out = []
                    for x in range(W):
                        s = 0.0
                        for y in range(r0, r1):
                            s += a[y][x]
                        out.append(s / (r1 - r0))
                    return out
                band = colmean(word + 2, word + 42)
                ref_top = colmean(max(0, word - 25), max(1, word - 5))
                bot0, bot1 = min(word + 50, 170), min(word + 80, 200)
                ref_bot = colmean(bot0, bot1)
                cols = []
                for x in range(340):
                    ref = (ref_top[x] + ref_bot[x]) / 2
                    if ref - band[x] > 20:
                        cols.append(x)
                if not cols:
                    self.log("guard: 未检测到缺口暗带")
                    return False
                # 连续段
                segs = []
                stx, prev = cols[0], cols[0]
                for c in cols[1:]:
                    if c - prev <= 3:
                        prev = c
                    else:
                        segs.append((stx, prev))
                        stx = prev = c
                segs.append((stx, prev))
                # 候选: 每段中心-27 (块宽54)
                cands = []
                for x0, x1 in segs[:4]:
                    if x1 - x0 < 20:
                        continue
                    cx = (x0 + x1) / 2
                    cands.append(int(round(cx - 27)))
                if not cands:
                    cands = [int(round((cols[0] + cols[-1]) / 2 - 27))]
                self.log("guard: 候选 %s y=%d (耗时%.1fs)" % (cands, word, time.time() - st))
            except Exception as e:
                self.log("guard: 图像处理失败 %s" % e)
                return False

            for gx in cands:
                for off in (0, -1, 1, -2, 2):
                    enc = base64.b64encode(
                        self._rc4("%dx%d" % (gx + off, word), guard[:8]).encode('latin-1')).decode()
                    _cookie_set("guardret", enc)
                    rsp2 = self._http_get(self.site_url + "/")
                    if len(rsp2.text) > 1000:
                        self.log("guard: 破解成功 x=%d" % (gx + off))
                        return True
            self.log("guard: 破解失败 (候选已穷尽)")
            return False
        except Exception as e:
            self.log("guard: 异常 %s" % e)
            return False

    def _warm_up(self):
        if self._warmed:
            return
        try:
            rsp = self._http_get(self.site_url + "/")
            if len(rsp.text) > 1000:
                self._warmed = True
                self.log("预热完成")
                return
            self.log("遇到滑块验证, 开始破解...")
            if self._solve_guard():
                self._warmed = True
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=30, headers=None):
        text = ""
        for attempt in range(3):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self._http_get(url, headers=h, timeout=timeout)
                text = ""
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)

                # 命中滑块验证页
                if "_guard/html.js" in text or len(text) < 200:
                    self.log("⚠️ 触发滑块验证 (attempt %d): %s" % (attempt + 1, url))
                    if self._solve_guard():
                        continue
                    return text
                return text
            except Exception as e:
                # 网络/限流异常: 等待后重试, 不直接放弃
                self.log("fetch FAIL (attempt %d) %s -> %s" % (attempt + 1, url, e))
                try:
                    time.sleep(1.5)
                except Exception:
                    pass
        return text

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

    def _clean(self, s):
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

    # ===================== 列表解析 =====================
    def _extract_videos(self, html, remarks_map=None):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos
        matches = _RE_CARD.findall(html)
        self.log("  卡片: %d 条" % len(matches))
        for href, img_tag in matches:
            if href in seen:
                continue
            seen.add(href)
            alt = ""
            m = re.search(r'alt="([^"]*)"', img_tag, re.I)
            if m:
                alt = m.group(1)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100],
                "vod_pic":     self._fix_url(_img_pic(img_tag)) or self.default_pic,
                "vod_remarks": (remarks_map or {}).get(href, ""),
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_TOTAL.search(html)
        if m:
            total = int(m.group(1))
            return max(1, (total + 23) // 24)
        return 1

    # ===================== TVBox 接口 =====================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def _parse_home(self, html):
        videos = []
        seen = set()
        # 轮播
        for href, img_tag, name in _RE_SWIPER.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(name)[:100],
                "vod_pic":     self._fix_url(_img_pic(img_tag)) or self.default_pic,
                "vod_remarks": "推荐",
            })
        # 各板块推荐
        for href, img_tag in _RE_HOME_CARD.findall(html):
            if href in seen:
                continue
            seen.add(href)
            alt = ""
            m = re.search(r'alt="([^"]*)"', img_tag, re.I)
            if m:
                alt = m.group(1)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100],
                "vod_pic":     self._fix_url(_img_pic(img_tag)) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def homeVideoContent(self):
        # 空结果自动重试: 首次调用可能早于滑块破解完成, 避免 TVBox 缓存空列表
        for attempt in range(3):
            self._warm_up()
            html = self._fetch(self.site_url + "/")
            videos = self._parse_home(html)
            self.log("home 第%d次: HTML %d 字节, %d 条" % (attempt + 1, len(html), len(videos)))
            if videos:
                return {"list": videos}
            # 没拿到 → 重置预热状态, 强制重新破解滑块
            self.log("  空结果, 重置滑块状态后重试")
            self._warmed = False
            try:
                time.sleep(1)
            except Exception:
                pass
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        sub = extend.get("sub") or tid
        year = extend.get("year") or ""
        letter = extend.get("letter") or ""
        lang = extend.get("lang") or ""

        # URL 槽位: [0]=子分类tid [2]=类型 [4]=年份 [5]=首字母 [6]=语言 [11]=页码
        slots = [""] * 12
        slots[0] = str(sub)
        if year:
            slots[4] = str(year)
        if letter:
            slots[5] = str(letter)
        if lang:
            slots[6] = str(lang)
        slots[11] = str(page)
        path = "-".join(slots)
        url = "%s/tspnbdshow/%s.html" % (self.site_url, urllib.parse.quote(path))
        self.log("category: %s" % url)
        for attempt in range(3):
            html = self._fetch(url)
            videos = self._extract_videos(html)
            pagecount = self._page_count(html)
            self.log("  第%d次: HTML %d 字节, %d 条, 总页数: %d"
                     % (attempt + 1, len(html), len(videos), pagecount))
            if videos or not html:
                break
            # 有响应但没解析到内容 → 重置滑块状态重试
            self.log("  空结果, 重置滑块状态后重试")
            self._warmed = False
            try:
                time.sleep(1)
            except Exception:
                pass

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        # /search/-{关键词}-{页码}-----------.html
        slots = [""] * 12
        slots[1] = key
        slots[2] = str(page)
        path = "-".join(slots)
        url = "%s/search/%s.html" % (self.site_url, urllib.parse.quote(path))
        self.log("search: %s" % url)
        for attempt in range(3):
            html = self._fetch(url)
            videos = self._extract_videos(html)
            self.log("  第%d次: HTML %d 字节, %d 条" % (attempt + 1, len(html), len(videos)))
            if videos or not html:
                break
            self.log("  空结果, 重置滑块状态后重试")
            self._warmed = False
            try:
                time.sleep(1)
            except Exception:
                pass
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            for attempt in range(2):
                self.log("  详情空响应, 重置滑块状态后重试")
                self._warmed = False
                self._warm_up()
                html = self._fetch(url)
                if html:
                    break
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题 (与网站一致: ys-name18 / title)
        name = ""
        m = _RE_NAME18.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_H1_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("》")[0].replace("《", ""))
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = re.search(
            r'class="poster5"><img\s+src=""\s+data-src="([^"]+)"', html)
        if not m:
            m = re.search(r'class="poster5"><img[^>]*(?:data-src|src)="([^"]+)"', html)
        if m:
            pic = self._fix_url(m.group(1))

        # 更新时间 (副标题, 网站显示于标题下)
        year_info = ""
        m = _RE_YEAR1.search(html)
        if m:
            year_info = self._clean(m.group(1))

        # 导演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        # 主演
        actor = ""
        m = _RE_ACTORS.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        # 类型 / 地区
        vtype = ""
        m = _RE_STYLE.search(html)
        if m:
            vtype = self._clean(m.group(1))
        area = ""
        m = _RE_AREA.search(html)
        if m:
            area = self._clean(m.group(1))

        # 剧情 (与网站一致: Synopsis-word 区块, 去掉图片/评论/相关搜索)
        content = ""
        m = _RE_SYN.search(html)
        if m:
            body = m.group(1)
            body = re.sub(r"<img[^>]*>", "", body)
            # 去掉残留的内联样式片段
            body = re.sub(r'[a-zA-Z-]+\s*:\s*[^;"\'>]+;?', "", body)
            content = self._clean(body)
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ===== 线路 + 剧集 (顺序与网站完全一致) =====
        play_from = []
        play_url = []
        try:
            for m in _RE_LINE_BLOCK.finditer(html):
                line_name = self._clean(m.group(1)) or "线路"
                eps_html = m.group(2)
                eps = _RE_EP.findall(eps_html)
                if not eps:
                    continue
                play_from.append(line_name)
                play_url.append("#".join(
                    "%s$%s" % (self._clean(en), urllib.parse.quote(href, safe=""))
                    for href, en in eps))
        except Exception as e:
            self.log("  线路解析失败: %s" % e)

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        # 备注 (副标题): 类型·地区 + 更新时间
        remarks_parts = []
        if vtype:
            remarks_parts.append(vtype)
        if area:
            remarks_parts.append(area)
        remarks = "·".join(remarks_parts)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_type": vtype,
            "vod_remarks": remarks or (year_info or ("%d条线路" % len(play_from))),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ===================== 播放 =====================
    def playerContent(self, flag, id, vipFlags):
        play_page = urllib.parse.unquote(id)
        if not play_page.startswith("http"):
            play_page = self._fix_url(play_page)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        m3u8 = ""
        m = _RE_PLAYER.search(html)
        if m:
            try:
                data = json.loads(m.group(1))
                m3u8 = data.get("url", "") or ""
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                if m2:
                    m3u8 = m2.group(1)

        if m3u8:
            m3u8 = m3u8.replace("\\/", "/")
            self.log("  => 直链 m3u8: %s" % m3u8[:160])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            # 兜底: 交给 TVBox 嗅探
            self.log("  => 未解析到直链, 嗅探播放页")
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        self._play_cache[play_page] = (now, res)
        return res

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
            rsp = self._http_get(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

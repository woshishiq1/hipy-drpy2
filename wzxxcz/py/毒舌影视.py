# coding=utf-8
"""
毒舌影视 www.cssgm.com.cn | TVBox Python 爬虫
站点模板: MacCMS stui / hl048

路由（实证自列表/搜索/详情/播放源码）:
  - 首页:   /
  - 主分类: /cat/<tid>.html；分页 /cat/<tid>-<page>.html（第 1 页无 -1）
  - 子类型: /list/id/<subtype>.html
  - 剧情:   /list/class/<URL编码中文>/id/<tid>.html
  - 地区:   /list/area/<URL编码中文>/id/<tid>.html（地区+剧情: /list/area/<a>/class/<c>/id/<tid>.html）
  - 年份:   /list/id/<tid>/year/<年>.html（叠加剧情: /list/class/<c>/id/<tid>/year/<年>.html）
  - 语言:   /list/class/<c>/id/<tid>/lang/<URL编码中文>.html（裸分类: /list/id/<tid>/lang/<中文>.html）
  - 字母:   /list/class/<c>/id/<tid>/letter/<A-Z 或 0-9>.html
  - 排序:   /list/by/time|hits|score/class/<c>/id/<tid>.html
  - 筛选分页: /list/class/<c>/id/<tid>/page/<page>.html
  - 详情:   /cinema/<id>.html
  - 播放:   /view/<vid>/<sid>/<nid>.html
  - 搜索:   /so.html?wd=<关键词>；分页 /so/page/<page>/wd/<编码关键词>.html

列表/搜索卡片:
  - 主列表: ul.stui-vodlist > li > a.stui-vodlist__thumb.lazyload
  - 搜索主结果: ul.stui-vodlist__media > li.active > a.v-thumb.stui-vodlist__thumb.lazyload
  - 侧边热门(必须排除): a.m-thumb / .detail-side / ul.stui-vodlist__text，背景图 style 封面
  - 锚点 href/title/data-original；span.pic-text.text-right = 副标；h4/h3.title a = 片名兜底

详情字段:
  - 片名 h1.title；海报 img.lazyload[data-original]（src 为 load.gif 占位）
  - 简介 span.detail-content（完整版,display:none）优先，span.detail-sketch（截断版）兜底
  - 主演/导演: p.data > span.text-muted 标签之后的一串 <a>，逗号拼接；无 <a> 取纯文本
  - 类型/地区/年份: p.data 内 span.text-muted(.hidden-xs) 标签之后文本
  - 线路: div.stui-pannel-box.b.playlist.mb；h3.title 线路名（DOM 顺序即站点顺序，编号与 URL 段不一致时以 DOM/URL 为准）；
          ul.stui-content__playlist > li > a[href]，a 文本=集名

播放直链: 播放页内联 player_aaaa JSON，encrypt:0 时取 url 直出 m3u8；
          直链 CDN 域名各线路不同，不写死；保留 master 多码率首条子流拆分兜底，失败回退 parse:1 客户端嗅探。
"""
import re
import sys
import json
import time
import socket
import urllib.parse

sys.path.append('..')

# 云端出口 IPv6 不通：强制 IPv4 解析（壳子环境正常时不影响）
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
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
                print("[cssgm]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.cssgm.com.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# ---- 各频道子类型（/list/id/<subtype>.html）----
_MOVIE_SUBTYPE = [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
                  ("10", "剧情片"), ("11", "战争片"), ("41", "动画片"), ("12", "记录片"),
                  ("39", "恐怖片")]
_TV_SUBTYPE = [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
               ("22", "台湾剧"), ("21", "日本剧"), ("20", "泰国剧"), ("23", "海外剧")]
_ZY_SUBTYPE = [("25", "大陆综艺"), ("26", "日韩综艺"), ("27", "港台综艺"), ("28", "欧美综艺")]
_DM_SUBTYPE = [("29", "国产动漫"), ("30", "日本动漫"), ("42", "港台动漫"),
               ("31", "欧美动漫"), ("43", "海外动漫")]
_DJ_SUBTYPE = [("40", "短剧大全"), ("44", "AI漫剧")]

# ---- 剧情 class ----
_MOVIE_CLASS = ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
                "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
                "儿童", "网络电影"]
_TV_CLASS = ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
             "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"]
_ZY_CLASS = ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
             "曲艺", "生活", "游戏互动", "财经", "求职"]
_DM_CLASS = ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
            "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
            "亲子", "益智", "励志", "其他"]

# ---- 地区 area ----
_MOVIE_AREA = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
               "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]
_TV_AREA = ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
            "新加坡", "其他"]
_ZY_AREA = ["内地", "港台", "日韩", "欧美"]
_DM_AREA = ["国产", "日本", "欧美", "其他"]

# ---- 年份 year（站点实证，电影缺 2011）----
_MOVIE_YEAR = ["2010", "2012", "2013", "2014", "2015", "2016", "2017", "2018",
               "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]
_TV_YEAR = [str(y) for y in range(2026, 2009, -1)]
_ZY_YEAR = [str(y) for y in range(2018, 2003, -1)]
_DM_YEAR = [str(y) for y in range(2018, 2003, -1)]

# ---- 语言 lang ----
_LANG_MOVIE = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]
_LANG_7 = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]

# ---- 字母 letter：A-Z + 0-9 ----
_LETTERS = ["0-9"] + [chr(c) for c in range(65, 91)]

# ---- 排序 sort（站点 by/time|hits|score）----
_SORT = [("time", "最新"), ("hits", "最热"), ("score", "评分")]


def _class_opts(items):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in items]


def _subtype_opts(pairs):
    return [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in pairs]


def _lang_opts(items):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in items]


def _letter_opts():
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _LETTERS]


def _sort_opts():
    return [{"n": "默认", "v": ""}] + [{"n": n, "v": v} for v, n in _SORT]


FILTERS = {
    "1": [
        {"key": "subtype", "name": "类型", "value": _subtype_opts(_MOVIE_SUBTYPE)},
        {"key": "class",   "name": "剧情", "value": _class_opts(_MOVIE_CLASS)},
        {"key": "area",    "name": "地区", "value": _class_opts(_MOVIE_AREA)},
        {"key": "year",    "name": "年份", "value": _class_opts(_MOVIE_YEAR)},
        {"key": "lang",    "name": "语言", "value": _lang_opts(_LANG_MOVIE)},
        {"key": "letter",  "name": "字母", "value": _letter_opts()},
        {"key": "sort",    "name": "排序", "value": _sort_opts()},
    ],
    "2": [
        {"key": "subtype", "name": "类型", "value": _subtype_opts(_TV_SUBTYPE)},
        {"key": "class",   "name": "剧情", "value": _class_opts(_TV_CLASS)},
        {"key": "area",    "name": "地区", "value": _class_opts(_TV_AREA)},
        {"key": "year",    "name": "年份", "value": _class_opts(_TV_YEAR)},
        {"key": "lang",    "name": "语言", "value": _lang_opts(_LANG_7)},
        {"key": "letter",  "name": "字母", "value": _letter_opts()},
        {"key": "sort",    "name": "排序", "value": _sort_opts()},
    ],
    "3": [
        {"key": "subtype", "name": "类型", "value": _subtype_opts(_ZY_SUBTYPE)},
        {"key": "class",   "name": "剧情", "value": _class_opts(_ZY_CLASS)},
        {"key": "area",    "name": "地区", "value": _class_opts(_ZY_AREA)},
        {"key": "year",    "name": "年份", "value": _class_opts(_ZY_YEAR)},
        {"key": "lang",    "name": "语言", "value": _lang_opts(_LANG_7)},
        {"key": "letter",  "name": "字母", "value": _letter_opts()},
        {"key": "sort",    "name": "排序", "value": _sort_opts()},
    ],
    "4": [
        {"key": "subtype", "name": "类型", "value": _subtype_opts(_DM_SUBTYPE)},
        {"key": "class",   "name": "剧情", "value": _class_opts(_DM_CLASS)},
        {"key": "area",    "name": "地区", "value": _class_opts(_DM_AREA)},
        {"key": "year",    "name": "年份", "value": _class_opts(_DM_YEAR)},
        {"key": "lang",    "name": "语言", "value": _lang_opts(_LANG_7)},
        {"key": "letter",  "name": "字母", "value": _letter_opts()},
        {"key": "sort",    "name": "排序", "value": _sort_opts()},
    ],
    # 短剧：站点仅有“类型”一组有效筛选；剧情/地区/年份为空壳，无语言/字母组
    "24": [
        {"key": "subtype", "name": "类型", "value": _subtype_opts(_DJ_SUBTYPE)},
    ],
}

# ===================== 正则 =====================
# 列表/搜索卡片锚点（class 顺序可能为 v-thumb / m-thumb 在前）；
# 主列表/搜索主结果锚点均带 lazyload；侧边背景图热门锚点无 lazyload，据此排除
_RE_CARD_A = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*lazyload[^"]*"[^>]*>'
    r'([\s\S]*?)</a>', re.I)
_RE_HREF = re.compile(r'href="([^"]+)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_ORIG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_PIC_TEXT = re.compile(r'<span[^>]*class="pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_H_NAME = re.compile(
    r'<h[34][^>]*>\s*<a[^>]*(?:title="([^"]*)")?[^>]*>([\s\S]*?)</a>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<img[^>]*class="lazyload"[^>]*data-original="([^"]*)"', re.I)
_RE_INTRO_FULL = re.compile(
    r'<span[^>]*class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_SKETCH = re.compile(
    r'<span[^>]*class="detail-sketch"[^>]*>([\s\S]*?)</span>', re.I)
_RE_LABEL = re.compile(
    r'<span[^>]*class="text-muted[^"]*"[^>]*>({lab}：)</span>\s*'
    r'([\s\S]*?)(?=<span[^>]*class="(?:split-line|text-muted)|<p|</p|$)',
    re.I)
_RE_LINK = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 线路分组（DOM 顺序即站点顺序）
_RE_PLAY_BLOCK = re.compile(
    r'<div[^>]*class="stui-pannel-box[^"]*playlist[^"]*"[^>]*>'
    r'([\s\S]*?)(?=<div[^>]*class="stui-pannel-box[^"]*playlist[^"]*"|<!--\s*播放地址|$)',
    re.I)
_RE_LINE_NAME = re.compile(r'<h3[^>]*class="title"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_EP = re.compile(
    r'<li[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 分页总页：<span class="num">当前/总页</span>
_RE_PAGE_NUM = re.compile(r'<span[^>]*class="num"[^>]*>\s*(\d+)\s*/\s*(\d+)', re.I)


class Spider(Spider):

    def getName(self):
        return "毒舌影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ---------------- 基础工具 ----------------
    @staticmethod
    def _is_upstream_error(text, status=200):
        """识别上游/网关错误空壳、Cloudflare 错误页与非 200 响应；正常业务页一律放行。"""
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
            "error code", "ray id", "web server is down",
            "sorry, you have been blocked"))

    def _fetch(self, url, headers=None, tries=3):
        last = ""
        for _ in range(tries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self.fetch(url, headers=h, timeout=(10, 30))
                status = getattr(rsp, "status_code", 200)
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)
                if not self._is_upstream_error(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, e)
                last = ""
            time.sleep(1.2)
        return last

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
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析 ----------------
    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        return any(k in pic.lower() for k in ("load.png", "load.gif",
                                              "placeholder", "blank", "default"))

    def _is_side_block(self, block):
        # 侧边热播榜：m-thumb 缩略榜 / detail-side 容器 / 文字榜，必须排除
        return ("m-thumb" in block or "detail-side" in block
                or "stui-vodlist__text" in block)

    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_CARD_A.finditer(html):
            block = m.group(0)
            if self._is_side_block(block):
                continue
            mh = _RE_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            if "/cinema/" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)

            mt = _RE_TITLE.search(block)
            name = self._clean(mt.group(1)) if mt else ""
            mo = _RE_ORIG.search(block)
            pic = mo.group(1) if mo else ""
            if self._is_placeholder_pic(pic):
                pic = ""

            mp = _RE_PIC_TEXT.search(block)
            remarks = self._clean(mp.group(1)) if mp else ""

            # 片名兜底：锚点 title 缺失时取 h3/h4 文本
            if not name:
                mn = _RE_H_NAME.search(block)
                if mn:
                    name = self._clean(mn.group(1) or mn.group(2))
            if not name:
                continue

            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return max(1, int(m.group(2)))
            except Exception:
                pass
        nums = [int(x) for x in re.findall(r'-(\d+)\.html', html)]
        return max(1, max(nums)) if nums else 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def _category_path(self, tid, extend, page):
        subtype = extend.get("subtype") or ""
        klass = extend.get("class") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""
        lang = extend.get("lang") or ""
        letter = extend.get("letter") or ""
        sort = extend.get("sort") or ""

        # 无任何筛选：主分类导航路由；分页 /cat/<tid>-<page>.html
        if not any([subtype, klass, area, year, lang, letter, sort]):
            if page and page > 1:
                base = "/cat/%s-%d.html" % (tid, page)
            else:
                base = "/cat/%s.html" % tid
            return self.site_url + base

        idval = subtype or tid
        segs = []
        if sort:
            segs.append("by/%s" % sort)
        if area:
            segs.append("area/%s" % urllib.parse.quote(area))
        if klass:
            segs.append("class/%s" % urllib.parse.quote(klass))
        segs.append("id/%s" % idval)
        if year:
            segs.append("year/%s" % year)
        if lang:
            segs.append("lang/%s" % urllib.parse.quote(lang))
        if letter:
            segs.append("letter/%s" % letter)
        if page and page > 1:
            segs.append("page/%d" % page)
        return self.site_url + "/list/" + "/".join(segs) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._category_path(str(tid), extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        if page <= 1:
            url = "%s/so.html?wd=%s" % (self.site_url, keyword)
        else:
            url = "%s/so/page/%d/wd/%s.html" % (self.site_url, page, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._parse_cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 30, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _label_seg(self, html, label):
        pat = _RE_LABEL.pattern.replace("{lab}", re.escape(label))
        m = re.search(pat, html.replace("\n", " "), re.I)
        return m.group(2) if m else ""

    def _label_field(self, html, label):
        """纯文本标签字段（类型/地区/年份）。"""
        seg = self._label_seg(html, label)
        return self._clean(seg)

    def _links_field(self, html, label):
        """主演/导演：标签后一串 <a> 逗号拼接；无 <a> 取纯文本。"""
        seg = self._label_seg(html, label)
        if not seg:
            return ""
        links = [self._clean(a) for a in _RE_LINK.findall(seg)]
        links = [x for x in links if x]
        if links:
            return ",".join(links)
        return self._clean(seg)

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
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报
        pic = ""
        mp = _RE_DETAIL_PIC.search(html)
        if mp:
            pic = mp.group(1)
        pic = self._fix_url(pic) or self.default_pic

        # 简介：完整版优先，截断版兜底
        content = ""
        mf = _RE_INTRO_FULL.search(html)
        if mf:
            content = self._clean(mf.group(1))
        if not content:
            ms = _RE_INTRO_SKETCH.search(html)
            if ms:
                content = self._clean(ms.group(1))
        content = re.sub(r"^(剧情简介|简介)[：:]\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        actor = self._links_field(html, "主演")
        director = self._links_field(html, "导演")
        classify = self._label_field(html, "类型")
        area = self._label_field(html, "地区")
        year_raw = self._label_field(html, "年份")
        my = re.search(r"(\d{4})", year_raw)
        year = my.group(1) if my else year_raw

        # 详情页副标（全1集/HD…）
        remarks = ""
        mr = _RE_PIC_TEXT.search(html)
        if mr:
            remarks = self._clean(mr.group(1))

        # ===== 线路与选集（DOM 顺序）=====
        play_from, play_url = [], []
        for block in _RE_PLAY_BLOCK.findall(html):
            mn = _RE_LINE_NAME.search(block)
            line_name = self._clean(mn.group(1)) if mn else ""
            eps = []
            seen_ep = set()
            for ma in _RE_EP.finditer(block):
                ep_href, ep_inner = ma.group(1), ma.group(2)
                ep_href = ep_href.replace("&amp;", "&")
                if ep_href in seen_ep:
                    continue
                seen_ep.add(ep_href)
                ep_name = self._clean(ep_inner)
                if not ep_name:
                    ep_name = "第%02d集" % (len(eps) + 1)
                eps.append((ep_name, ep_href))
            if not eps:
                continue
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

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
            "vod_year": year,
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

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    @staticmethod
    def _player_json(html):
        """括号深度配对精确截取 player_aaaa JSON（正确处理嵌套的 vod_data 对象）。"""
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
        # 1) MacCMS player_aaaa JSON（深度配对截取）
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw.replace("\\/", "/"))
                # encrypt 非 0 视为未直出，交兜底链路
                if str(aa.get("encrypt", "0")) not in ("0", ""):
                    return ""
                if aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    return m2.group(1).replace("\\/", "/")
        # 2) 页面内裸 m3u8/mp4
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
                return url  # 已是含分片的媒体播放列表
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
        pass

    def close(self):
        self.destroy()

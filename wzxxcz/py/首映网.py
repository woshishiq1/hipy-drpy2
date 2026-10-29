# coding=utf-8
"""
首映网 jiyaogroup.com | TVBox Python 爬虫 
关键:
  - 苹果CMS V10 + stui 主题，纯 HTML 解析，无需 PoW / 无需 JS 解密
  - 分类走 /vodshow/{id}{-area}{-order}{-class}{-lang}{-letter}...{page}...{year}.html
  - 播放页直接内置 player_aaaa JSON，可拿到真实 m3u8 直链（bfzym3u8）
  - 搜索页为 media 版式（stui-vodlist__media），与列表页分开处理
"""
import re
import sys
import json
import time
import urllib.parse

sys.path.append('..')

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
                print("[jiyao]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://jiyaogroup.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/statics/img/favicon.ico"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",    "type_name": "电影"},
    {"type_id": "dianshiju",   "type_name": "电视剧"},
    {"type_id": "zongyi",      "type_name": "综艺"},
    {"type_id": "dongman",     "type_name": "动漫"},
    {"type_id": "donghuapian", "type_name": "动画片"},
    {"type_id": "duanju",      "type_name": "短剧"},
]

# ============ 页面真实筛选项（与站点 vodshow 页一一对应） ============
# 排序：站点 vodshow 页的 order 段实际不生效（hits/score 会 404 或忽略），
# 这里保留“按时间”一项以对齐站点默认行为。
_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_LANGS = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]

_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
            "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]

# 各分类“类型”(第二分类，落在 URL 的 id 段) —— 站点用独立 slug
_TYPE_MAP = {
    "dianying": [
        ("dongzuopian", "动作电影"), ("xijupian", "喜剧电影"),
        ("aiqingpian", "爱情电影"), ("kehuanpian", "科幻电影"),
        ("kongbupian", "恐怖电影"), ("juqingpian", "剧情电影"),
        ("zhanzhengpian", "战争电影"), ("jilupian", "纪录电影"),
    ],
    "dianshiju": [
        ("guochanju", "国产剧"), ("xianggangju", "香港剧"),
        ("taiwanju", "台湾剧"), ("ribenju", "日本剧"),
        ("taiguoju", "泰国剧"), ("hanguoju", "韩国剧"),
        ("oumeiju", "欧美剧"), ("haiwaiju", "海外剧"),
    ],
    "zongyi": [
        ("daluzongyi", "大陆综艺"), ("gangtaizongyi", "港台综艺"),
        ("rihanzongyi", "日韩综艺"), ("oumeizongyi", "欧美综艺"),
    ],
    "dongman": [
        ("guochandongman", "国产动漫"), ("rihandongman", "日韩动漫"),
        ("gangtaidongman", "港台动漫"), ("oumeidongman", "欧美动漫"),
        ("haiwaidongman", "海外动漫"),
    ],
    "donghuapian": [],
    "duanju": [
        ("nvpinlianai", "女频恋爱"), ("fanzhuanshuangju", "反转爽剧"),
        ("niandaichuanyue", "年代穿越"), ("naodongxuanyi", "脑洞悬疑"),
        ("xiandaidushi", "现代都市"), ("guzhuangxianxia", "古装仙侠"),
        ("rexuejuqing", "热血剧情"),
    ],
}

# 各分类“剧情”(落在 URL 的第 4 段)
_GENRE_MAP = {
    "dianying": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                 "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
                 "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
                 "儿童", "网络电影"],
    "dianshiju": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
                  "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "zongyi": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
               "曲艺", "生活", "游戏互动", "财经", "求职"],
    "dongman": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
                "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
                "亲子", "益智", "励志", "其他"],
    "donghuapian": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
                    "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "duanju": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
               "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
}

# 各分类“地区”(落在 URL 的第 2 段)
_AREA_MAP = {
    "dianying": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                 "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "dianshiju": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                  "新加坡", "其他"],
    "zongyi": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
               "新加坡", "其他"],
    "dongman": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                "新加坡", "其他"],
    "donghuapian": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                    "新加坡", "其他"],
    "duanju": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
               "新加坡", "其他"],
}


def _opt(names):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in names]


FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "subtype", "name": "类型",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": v} for v, n in _TYPE_MAP.get(_tid, [])]},
        {"key": "class", "name": "剧情", "value": _opt(_GENRE_MAP.get(_tid, []))},
        {"key": "area", "name": "地区", "value": _opt(_AREA_MAP.get(_tid, []))},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _opt(_LANGS)},
        {"key": "letter", "name": "字母", "value": _opt(_LETTERS)},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 卡片：<a class="stui-vodlist__thumb lazyload" href="..." title="..." data-original="...">
#       ... <span class="pic-text text-right">更新至xx</span>
_RE_CARD = re.compile(
    r'<a[^>]+?class="[^"]*stui-vodlist__thumb[^"]*"[^>]*?'
    r'href="(/voddetail/[^"]+)"[^>]*?'
    r'title="([^"]*)"[^>]*?'
    r'(?:data-original|data-src|src)="([^"]*)"([\s\S]*?)</a>',
    re.S | re.I)

# 兜底：仅有 href 的卡片
_RE_HREF = re.compile(r'href="(/voddetail/[^"]+\.html)"', re.I)

# 侧栏排行榜（stui-vodlist__text / bottom-line-dot）需排除，否则空结果会被误判
_RE_RANK_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-vodlist__text[^"]*"[^>]*>[\s\S]*?</ul>', re.I)

# 主列表区（stui-vodlist 也可能是空的 <ul class="stui-vodlist clearfix"></ul>）
_RE_MAIN_LIST = re.compile(
    r'<ul[^>]*class="[^"]*\bstui-vodlist\b[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)

# 备注（更新至xx / 完结）
_RE_REMARKS = re.compile(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)

# 搜索页媒体版式
_RE_MEDIA = re.compile(
    r'<a[^>]+?class="[^"]*stui-vodlist__thumb[^"]*"[^>]*?'
    r'href="(/voddetail/[^"]+)"[^>]*?'
    r'title="([^"]*)"[^>]*?'
    r'(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
# 详情页封面：站点用 src=load.gif 占位，真图在 data-original，必须优先取
_RE_COVER = re.compile(
    r'class="[^"]*stui-vodlist__thumb[^"]*picture[^"]*"[^>]*>'
    r'\s*<img[^>]*?data-original="([^"]+)"', re.S | re.I)
_RE_COVER_ANY = re.compile(
    r'<img[^>]*?class="[^"]*lazyload[^"]*"[^>]*?data-original="([^"]+)"', re.I)
_RE_INTRO_DESC = re.compile(
    r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_INTRO_FULL = re.compile(
    r'<div[^>]*id="desc"[\s\S]*?<p[^>]*class="[^"]*col-pd[^"]*"[^>]*>([\s\S]*?)</p>',
    re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S | re.I)

# 元信息
_RE_INFO = re.compile(
    r'<p[^>]*class="[^"]*data[^"]*"[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_SCORE = re.compile(r'<span[^>]*class="[^"]*score[^"]*"[^>]*>([\d.]+)</span>', re.I)

# 播放列表：tab 名称 + tab-pane 内容
_RE_TAB_NAME = re.compile(
    r'data-toggle="tab"\s+href="#([^"]+)"[^>]*>([^<]+)</a>', re.I)
_RE_TAB_PANE = re.compile(
    r'<div[^>]*class="[^"]*tab-pane[^"]*"[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</div>',
    re.S | re.I)
_RE_PLAY_A = re.compile(
    r'<a[^>]*href="(/vodplay/[^"]+)"[^>]*?(?:title="([^"]*)")?[^>]*>([^<]*)</a>',
    re.S | re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.S)

# 分页
_RE_PAGE_INFO = re.compile(r'<span class="num">\s*(\d+)\s*/\s*(\d+)\s*</span>', re.I)
_RE_TAIL_PAGE = re.compile(r'<a href="[^"]*?(\d+)-{3}\.html"[^>]*>\s*尾页', re.I)

# 站方搜索频控页（“请不要频繁操作，搜索时间间隔为3秒”）
_BLOCK_MARK = "请不要频繁操作"

_LINE_ALIAS = {
    "bfzym3u8": "暴风资源",
    "lzm3u8": "量子M3U8",
    "ffm3u8": "非凡M3U8",
    "wjm3u8": "无尽M3U8",
    "1080zyk": "1080资源",
    "dyttm3u8": "电影天堂",
    "vip": "VIP线路",
}
_LINE_PRIORITY = ["bfzym3u8", "lzm3u8", "ffm3u8", "1080zyk",
                  "wjm3u8", "dyttm3u8", "vip"]


class Spider(Spider):

    def getName(self):
        return "首映网"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础 ----------------
    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fetch_guarded(self, url, tries=4, wait=3.2, timeout=20, headers=None):
        """
        带频控保护的抓取。
        站方搜索接口限制“3 秒内只能搜一次”，超限会返回
        “请不要频繁操作，搜索时间间隔为3秒前”提示页，这里自动等待重试。
        """
        for i in range(tries):
            text = self._fetch(url, timeout=timeout, headers=headers)
            if text and _BLOCK_MARK not in text:
                return text
            self.log("  ⚠️ 触发站方频控，等待 %.1fs 后重试 (%d/%d)" % (wait, i + 1, tries))
            time.sleep(wait)
        return text if text else ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
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

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  卡片: %d 条" % len(matches))

        for href, title, pic, tail in matches:
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            remarks = ""
            mr = _RE_REMARKS.search(tail)
            if mr:
                remarks = self._clean(mr.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        if videos:
            return videos

        # 兜底：只有链接的情况。必须排除侧栏排行榜，否则「无结果」页会
        # 把排行榜条目误当成搜索结果。
        body = _RE_RANK_BLOCK.sub("", html)

        # 优先只在主列表 <ul class="stui-vodlist"> 内找
        mains = _RE_MAIN_LIST.findall(body)
        scope = "".join(mains) if mains else body

        hrefs = _RE_HREF.findall(scope)
        if not hrefs and mains:
            # 主列表为空 → 这就是真的没有结果
            self.log("  主列表为空，判定无结果")
            return videos

        self.log("  兜底 href=%d" % len(hrefs))
        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    href.split("/")[-1].replace(".html", ""),
                "vod_pic":     self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_info(self, html):
        """返回 (当前页, 总页数)"""
        if not html:
            return 1, 1
        m = _RE_PAGE_INFO.search(html)
        if m:
            try:
                return int(m.group(1)), int(m.group(2))
            except Exception:
                pass
        m = _RE_TAIL_PAGE.search(html)
        if m:
            try:
                return 1, int(m.group(1))
            except Exception:
                pass
        return 1, 1

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)

        # 去重（首页同一影片可能出现在轮播 + 最近更新）
        out = []
        seen = set()
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            # 轮播图的 pic-text 写的是片名本身，视作无效备注
            if v.get("vod_remarks") == v.get("vod_name"):
                v["vod_remarks"] = ""
            if not v.get("vod_remarks"):
                v["vod_remarks"] = "最近更新"
            out.append(v)
        self.log("home 影片: %d" % len(out))
        return {"list": out[:60]}

    # ---------------- 分类 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        year = extend.get("year") or ""
        area = extend.get("area") or ""
        order = extend.get("sort_field") or ""
        genre = extend.get("class") or ""
        lang = extend.get("lang") or ""
        letter = extend.get("letter") or ""
        subtype = extend.get("subtype") or ""

        # 站点 order 段只有 time 可用；hits/score 在纯分类下会 404，仅在无其它
        # 筛选时保留 time，其余情况留空，避免 System Error。
        if order not in ("time", "hits", "score"):
            order = ""
        if order and (year or area or genre or lang or letter):
            order = ""

        # 站点限制：year 与 area / genre 组合会返回空页，故只保留 year 单独生效
        if year and (area or genre or lang or letter):
            if genre:
                genre = ""
            if area:
                area = ""
            if lang:
                lang = ""
            if letter:
                letter = ""

        lid = subtype if subtype else tid

        segs = [
            lid,                                  # 1 分类（或子分类 slug）
            urllib.parse.quote(area, safe=""),    # 2 地区
            order,                                # 3 排序
            urllib.parse.quote(genre, safe=""),   # 4 剧情
            urllib.parse.quote(lang, safe=""),    # 5 语言
            urllib.parse.quote(letter, safe=""),  # 6 字母
            "", "",                               # 7-8
            str(page),                            # 9 页码
            "", "",                               # 10-11
            year,                                 # 12 年份
        ]

        url = "%s/vodshow/%s.html" % (self.site_url, "-".join(segs))
        self.log("category: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        if not html or "System Error" in html[:2000]:
            self.log("  页面异常，降级为纯分类首页")
            url = "%s/vodshow/%s-----------.html" % (self.site_url, tid)
            html = self._fetch(url)
            page = 1

        videos = self._extract_videos(html)
        cur, total = self._page_info(html)
        if page > 1:
            total = max(total, page)

        self.log("  最终: %d 条, 页码: %d/%d" % (len(videos), cur, total))

        return {
            "list": videos,
            "page": page,
            "pagecount": total,
            "limit": len(videos) if videos else 36,
            "total": total * (len(videos) if videos else 36),
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        keyword = urllib.parse.quote(key)

        if page == 1:
            url = "%s/vodsearch/%s-------------.html" % (self.site_url, keyword)
        else:
            url = "%s/vodsearch/%s----------%d---.html" % (self.site_url, keyword, page)

        self.log("search: %s" % url)
        html = self._fetch_guarded(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        if not videos:
            videos = self._extract_media(html)

        cur, total = self._page_info(html)
        if page > 1:
            total = max(total, page)

        self.log("  搜索命中: %d 条, 页码: %d/%d" % (len(videos), cur, total))

        return {
            "list": videos,
            "page": page,
            "pagecount": total,
            "limit": len(videos) if videos else 36,
            "total": total * (len(videos) if videos else 36),
        }

    def _extract_media(self, html):
        """搜索页 media 版式：li.detail 内 h3.title > a"""
        videos = []
        seen = set()
        if not html:
            return videos

        for href, title, pic in _RE_MEDIA.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            remarks = ""
            # 该条目的备注在 img 后的 span
            idx = html.find(href)
            if idx > 0:
                mr = _RE_REMARKS.search(html[idx:idx + 1200])
                if mr:
                    remarks = self._clean(mr.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        self.log("  media 版式: %d 条" % len(videos))
        return videos

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def _pick_info(self, html, label):
        """
        stui 模板里「类型/地区/年份」挤在同一个 <p class="data"> 内，
        「导演」「主演」各自独立成段。
        先用 split-line 切开，再按标签定位，避免标签自身 <span> 干扰。
        """
        if not html:
            return ""
        key = label.rstrip("：:")
        for m in _RE_INFO.finditer(html):
            blk = m.group(1)
            if key not in blk:
                continue

            # 该段可能是「类型/地区/年份」并列，先只保留本标签之后的部分
            parts = re.split(r'<span[^>]*class="[^"]*split-line[^"]*"[^>]*>', blk)
            chosen = None
            for p in parts:
                if key in p:
                    chosen = p
                    break
            if chosen is None:
                chosen = blk

            # 去掉标签本身的 span，再取 <a> 文本
            body = re.sub(
                r'<span[^>]*class="[^"]*text-muted[^"]*"[^>]*>[\s\S]*?</span>',
                "", chosen, count=1, flags=re.I)

            names = re.findall(r'<a[^>]*>([^<]+)</a>', body)
            names = [self._clean(n) for n in names]
            names = [n for n in names if n and n != "未知"]
            if names:
                return ", ".join(names)

            txt = self._clean(body).strip("：: ,，")
            if txt and txt != "未知":
                return txt
        return ""

    def _pick_region_year(self, html):
        """从「类型/地区/年份」同段里分别取地区与年份"""
        area = ""
        year = ""
        for m in _RE_INFO.finditer(html):
            blk = m.group(1)
            if "地区" not in blk and "年份" not in blk:
                continue

            ma = re.search(
                r'地区[：:]\s*</span>\s*<a[^>]*>([^<]+)</a>', blk, re.I)
            if ma:
                area = self._clean(ma.group(1))

            my = re.search(
                r'年份[：:]\s*</span>\s*<a[^>]*>([^<]+)</a>', blk, re.I)
            if my:
                year = self._clean(my.group(1))
            break
        return area, year

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # ---- 标题 ----
        name = ""
        m = _RE_H1.search(html) or _RE_H1_ANY.search(html)
        if m:
            name = self._clean(re.sub(r'<span[^>]*class="[^"]*score[^"]*"[\s\S]*?</span>',
                                      "", m.group(1), flags=re.I))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # ---- 封面 ----
        pic = ""
        m = _RE_COVER.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic or "load.gif" in pic or "lazy" in pic:
            m = _RE_COVER_ANY.search(html)
            if m:
                p2 = self._fix_url(m.group(1))
                if p2 and "load.gif" not in p2:
                    pic = p2
        if not pic:
            pic = self.default_pic

        # ---- 评分 ----
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # ---- 导演 / 主演 / 地区 / 年份 ----
        director = self._pick_info(html, "导演：")
        actor = self._pick_info(html, "主演：")
        area, year = self._pick_region_year(html)

        # ---- 备注 ----
        remarks = ""
        m = re.search(r'上次更新[：:]\s*</span>\s*<font[^>]*>([\s\S]*?)</font>', html, re.I)
        if m:
            remarks = self._clean(m.group(1))

        # ---- 简介 ----
        content = ""
        m = _RE_INTRO_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))

        # 去掉站方在简介末尾拼接的广告尾巴
        content = re.sub(r"想看更多的.*?请关注我们的网站[：:]?\s*\S*", "", content).strip()
        content = re.sub(r"详情\s*$", "", content).strip()

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ---- 播放线路 ----
        groups = self._extract_play_groups(html)
        self.log("  线路: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            self.log("  未解析到播放列表")
            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_area": area,
                "vod_year": year,
                "vod_score": score,
                "vod_remarks": remarks or "",
            }]}

        # 线路排序：已知线路优先
        def _key(item):
            k = item[0]
            for i, p in enumerate(_LINE_PRIORITY):
                if p in k:
                    return i
            return 999

        ordered = sorted(groups.items(), key=_key)

        play_from = []
        play_url = []
        for key, eps in ordered:
            if not eps:
                continue
            alias = _LINE_ALIAS.get(key, key)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _extract_play_groups(self, html):
        """
        返回 {线路标识: [(集名, 播放页url), ...]}
        站点的线路标识藏在播放页 player_aaaa.from 里，详情页只有 tab 名，
        因此这里用 tab 序号 + tab 名做 key，播放时再取真实 from。
        """
        groups = {}
        if not html:
            return groups

        # tab 名称表： down1 -> 高清云播
        tab_names = {}
        for tid, tname in _RE_TAB_NAME.findall(html):
            tab_names[tid] = self._clean(tname)

        for tid, inner in _RE_TAB_PANE.findall(html):
            eps = []
            seen = set()
            for href, ttl, text in _RE_PLAY_A.findall(inner):
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                ep = self._clean(ttl) or self._clean(text)
                if not ep:
                    ep = "第%d集" % (len(eps) + 1)
                eps.append((ep, self._fix_url(href)))
            if eps:
                key = tab_names.get(tid) or tid
                groups[key] = eps

        # 兜底：没有 tab-pane 时直接扫所有 vodplay 链接
        if not groups:
            eps = []
            seen = set()
            for href, ttl, text in _RE_PLAY_A.findall(html):
                href = href.replace("&amp;", "&")
                if ("/vodplay/" not in href) or (href in seen):
                    continue
                # 排除“立即播放”等无关按钮（无集名的一律跳过）
                ep = self._clean(ttl) or self._clean(text)
                if not ep:
                    continue
                seen.add(href)
                eps.append((ep, self._fix_url(href)))
            if eps:
                groups["播放线路"] = eps

        return groups

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        self.log("  HTML 长度: %d" % len(html))

        info = self._parse_player(html)
        if not info:
            # 兜底：交给 TVBox 嗅探
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        vurl = (info.get("url") or "").replace("\\/", "/")
        encrypt = info.get("encrypt", 0)

        self.log("  from=%s encrypt=%s url=%s" %
                 (info.get("from"), encrypt, vurl[:160]))

        if not vurl:
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        # 站点目前 encrypt=0 且直接给出 m3u8；加密线路交给嗅探
        if encrypt not in (0, "0", None):
            self.log("  encrypt≠0，交给 TVBox 解析")
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        if vurl.startswith("//"):
            vurl = "https:" + vurl
        elif vurl.startswith("/"):
            vurl = self.site_url + vurl

        ref = self.site_url + "/"
        try:
            p = urllib.parse.urlparse(vurl)
            ref = "%s://%s/" % (p.scheme, p.netloc)
        except Exception:
            pass

        res = {
            "parse": 0,
            "playUrl": "",
            "url": vurl,
            "header": {
                "User-Agent": UA,
                "Referer": ref,
            },
        }
        self._play_cache[play_page] = (now, res)
        return res

    def _parse_player(self, html):
        if not html:
            return None
        m = _RE_PLAYER.search(html)
        if not m:
            return None
        raw = m.group(1).strip()
        try:
            return json.loads(raw)
        except Exception:
            # 容错：手工替换转义
            try:
                raw2 = raw.replace("\\/", "/")
                return json.loads(raw2)
            except Exception:
                u = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                f = re.search(r'"from"\s*:\s*"([^"]+)"', raw)
                e = re.search(r'"encrypt"\s*:\s*"?(\d+)"?', raw)
                if u:
                    return {
                        "url": u.group(1),
                        "from": f.group(1) if f else "",
                        "encrypt": int(e.group(1)) if e else 0,
                    }
                return None

    # ---------------- 其它 ----------------
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

# coding=utf-8
"""
追影猫（追剧猫） www.movienuke.com | TVBox Python 爬虫
站点结构（服务端渲染 HTML，模板 conch，苹果 CMS 风格）:
  - 首页:   /
  - 分类:   /zjm/<tid>.html                        （第 1 页、无筛选直连，不触发校验）
            /search.php?searchtype=5&tid=<tid>&page=<p>&jq=&area=&year=&yuyan=&letter=&order=
            （第 2 页起 / 带筛选走 search.php）
  - 搜索:   /search.php?searchword=<关键词>&page=<p>
  - 详情:   /zhuijumao/<id>.html
      · 片名 h2.title；海报 content 顶部 a.vodlist_thumb[data-original]
      · 评分 #rating data-score / .star_tips 文本
      · 年份/地区/类型：首个 li.data 内 a（年份：/地区：/类型：）
      · 状态：li.data 内 span.data_style（已完结 / 更新至第35集 / HD）
      · 主演 / 导演：各自 li.data 内 a 文本列表
      · 简介：.content_desc.full_text span 优先，.content_desc.context span 兜底
      · 线路：ul.nav1 li a[href="#playlistN"]，文本即线路名，顺序即站点按钮顺序
      · 选集：div#playlistN 内 a[href=/play/<vid>-<sid>-<nid>.html]，按集号正序、去重
  - 播放:   /play/<vid>-<sid>-<nid>.html
      · 内联脚本 var now="<裸 m3u8/mp4 直链>"，直接 parse=0 播放；
        兜底页面裸链；再不行交客户端嗅探 parse=1。

站点防护（线上实证）:
  search.php（分类分页/筛选/搜索）首次访问返回轻量 JS 校验页（733 字节「请稍候」），
  页面脚本下发 cookie idc_search_browser=<hex>，种入 cookie 后 URL 追加 _idc_pass=<hex>
  重放即放行；放行标记随 cookie 保留（Max-Age=1800），同会话后续请求直接 200。
  爬虫内置「取校验页 → 提取 hash 种 cookie → 加重放参数重放」闭环，不依赖浏览器 JS。
"""
import re
import sys
import json
import time
import random
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

        def reset_session(self):
            """关闭并丢弃复用坏连接的会话，下次请求重建新连接。"""
            try:
                if self._session is not None:
                    self._session.close()
            except Exception:
                pass
            self._session = None

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print(["zhuiyingmao"], *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.movienuke.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航：电影/电视剧/综艺/动漫 + 短剧）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "29", "type_name": "短剧"},
]

# ===== 站点真实筛选选项（取自放行分类页快照，值与站点原值逐字、顺序一致）=====
_JQ = ["解密", "乡村", "都市", "少儿", "对话", "搞笑", "恐怖", "宫廷", "剧情", "言情",
       "家庭", "励志", "偶像", "时装", "年代", "悬疑", "古装", "热血", "同人", "耽美"]
_AREA = ["大陆", "香港", "台湾", "日本", "韩国", "欧美", "泰国", "其他"]
# 站点年份序列（站点本身缺 2011；more 为展开按钮，无实际取值，不纳入）
_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
         "2017", "2016", "2015", "2014", "2013", "2012", "2010"]
_YUYAN = ["国语", "粤语", "英语", "日语", "韩语", "泰语", "法语"]
_LETTER = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]
_ORDER = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hit"}, {"n": "评分", "v": "score"}]

# 各大类下的二级分类（站点 hl01 行，子 tid）；仅作为筛选维度，不进一级分类墙
_SUB = {
    "1":  [("动作片", "5"), ("喜剧片", "6"), ("爱情片", "7"), ("科幻片", "8"),
           ("恐怖片", "9"), ("剧情片", "10"), ("战争片", "11"), ("纪录片", "12")],
    "2":  [("国产剧", "13"), ("香港剧", "14"), ("台湾剧", "15"), ("欧美剧", "16"),
           ("韩国剧", "25"), ("日本剧", "26"), ("泰国剧", "27"), ("海外剧", "28"), ("短剧", "29")],
    "3":  [("大陆综艺", "30"), ("港台综艺", "31"), ("日韩综艺", "32"), ("欧美综艺", "33")],
    "4":  [("大陆动漫", "34"), ("日本动漫", "35"), ("欧美动漫", "36"), ("海外动漫", "37"), ("动画片", "38")],
    "29": [("国产剧", "13"), ("香港剧", "14"), ("台湾剧", "15"), ("欧美剧", "16"),
           ("韩国剧", "25"), ("日本剧", "26"), ("泰国剧", "27"), ("海外剧", "28"), ("短剧", "29")],
}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    rows = []
    if _SUB.get(tid):
        rows.append({
            "key": "tid", "name": "分类",
            "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": t} for n, t in _SUB[tid]],
        })
    rows += [
        {"key": "jq",     "name": "类型", "value": _opts(_JQ)},
        {"key": "area",   "name": "地区", "value": _opts(_AREA)},
        {"key": "year",   "name": "年份", "value": _opts(_YEAR)},
        {"key": "yuyan",  "name": "语言", "value": _opts(_YUYAN)},
        {"key": "letter", "name": "字母", "value": _opts(_LETTER)},
        {"key": "order",  "name": "排序", "value": _ORDER},
    ]
    FILTERS[tid] = rows

# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<li class="(?:vodlist_item|searchlist_item)[\s\S]*?</li>', re.I)
_RE_CARD_HREF = re.compile(r'href="(/zhuijumao/(\d+)\.html)"', re.I)
_RE_IMG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_PICTEXT = re.compile(r'<span class="pic_text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_TITLE = re.compile(
    r'<(?:p|h4) class="vodlist_title"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SUB = re.compile(r'<p class="vodlist_sub"[^>]*>([\s\S]*?)</p>', re.I)

_RE_H2 = re.compile(r'<h2[^>]*class="title"[^>]*>([\s\S]*?)</h2>', re.I)
_RE_SCORE = re.compile(r'data-score="([0-9]+(?:\.[0-9]+)?)"', re.I)
_RE_SCORE_TXT = re.compile(r'<span class="star_tips">([0-9.]+)</span>', re.I)
_RE_LI = re.compile(r'<li class="data"[\s\S]*?</li>', re.I)
_RE_LI_LABEL = re.compile(
    r'<span[^>]*>(年份|地区|类型|状态|主演|导演)：</span>([\s\S]*?)</li>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_INTRO_FULL = re.compile(
    r'<div class="content_desc full_text[^"]*"[^>]*>\s*<span>([\s\S]*?)</span>', re.I)
_RE_INTRO_CTX = re.compile(
    r'<div class="content_desc context[^"]*"[^>]*>\s*<span>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

_RE_TAB = re.compile(
    r'<li[^>]*>\s*<a[^>]*href="#playlist(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_BOX = re.compile(
    r'<div id="playlist(\d+)"[^>]*>([\s\S]*?)(?=<div id="playlist|$)', re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/play/\d+-(\d+)-(\d+)\.html)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_NOW = re.compile(r'var now="([^"]*)"', re.I)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)
_RE_PAGE = re.compile(r'[?&]page=(\d+)')


class Spider(Spider):

    def getName(self):
        return "追影猫"

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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._idc_ok = False
        # IDC 浏览器校验放行标记：hash 与额外会话 cookie 均显式带到请求头，
        # 不依赖底层会话 cookie jar 是否暴露给爬虫（兼容框架基类 fetch）。
        self._idc_browser = ""
        self._idc_cookies = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _low_session(self):
        s = getattr(self, "_session", None)
        if s is None and hasattr(self, "_sess"):
            try:
                s = self._sess
            except Exception:
                s = None
        return s

    def _is_idc_page(self, text):
        if not text:
            return False
        return ("idc_search_browser=" in text or "正在验证浏览器" in text
                or "请稍候" in text)

    def _is_upstream_error(self, text):
        if not text:
            return True
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "<title>503", "<title>502", "<title>429"))

    def _reset_session(self):
        self._idc_ok = False
        self._idc_browser = ""
        self._idc_cookies = {}
        try:
            if hasattr(self, "reset_session"):
                self.reset_session()
                return
            sess = getattr(self, "_session", None) or getattr(self, "_sess", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            self._session = None
        except Exception:
            pass

    @staticmethod
    def _b36(n):
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'
        if n == 0:
            return '0'
        s = ''
        while n:
            n, r = divmod(n, 36)
            s = digits[r] + s
        return s

    def _idc_pass(self):
        # 对齐浏览器：Date.now().toString(36) + Math.random().toString(36).slice(2,8)
        return self._b36(int(time.time() * 1000)) + ''.join(
            random.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(6))

    def _cookie_header(self):
        """把放行 hash 与服务端会话 cookie 合并成 Cookie 请求头（显式携带，不依赖 jar）。"""
        pairs = []
        if self._idc_browser:
            pairs.append("idc_search_browser=" + self._idc_browser)
        for k, v in self._idc_cookies.items():
            pairs.append("%s=%s" % (k, v))
        return "; ".join(pairs)

    def _store_set_cookie(self, rsp):
        """best-effort 记录响应 Set-Cookie 中的会话键值，供后续请求显式带回。"""
        try:
            sc = rsp.headers.get("Set-Cookie") or rsp.headers.get("set-cookie")
            if not sc:
                return
            for part in sc.split(","):
                kv = part.split(";")[0].strip()
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    k = k.strip()
                    if k and k.lower() not in ("idc_search_browser",):
                        self._idc_cookies[k] = v.strip()
        except Exception:
            pass

    def _solve_idc(self, url, text):
        """从校验页提取 hash，显式 Cookie 头 + _idc_pass 重放放行。
        返回 (是否成功, 重放响应正文)；成功时正文即放行后的目标页。
        hash 同时写入底层会话 jar 作双保险；放行后的会话 cookie 一并记录，
        后续请求通过显式 Cookie 头带回，不依赖框架会话是否对外暴露 cookie jar。"""
        m = re.search(r'idc_search_browser=([a-f0-9]+)', text or "")
        if not m:
            return False, ""
        self._idc_browser = m.group(1)

        # 双保险：底层会话若可写则种入
        sess = self._low_session()
        if sess is not None:
            try:
                sess.cookies.set("idc_search_browser", self._idc_browser,
                                 domain="www.movienuke.com", path="/")
            except Exception:
                pass

        sep = '&' if '?' in url else '?'
        replay = url + sep + "_idc_pass=" + self._idc_pass()
        h = dict(self.headers)
        ck = self._cookie_header()
        if ck:
            h["Cookie"] = ck
        try:
            rsp = self.fetch(replay, headers=h, timeout=12)
            body = rsp.text if hasattr(rsp, "text") else (
                rsp.content.decode("utf-8", "ignore") if hasattr(rsp, "content") else str(rsp))
            body = body or ""
            self._store_set_cookie(rsp)
            if not self._is_idc_page(body):
                self._idc_ok = True
                self.log("浏览器校验通过")
                return True, body
        except Exception as e:
            self.log("校验重放异常: %s" % e)
        return False, ""

    def _fetch(self, url, timeout=15, headers=None):
        def _once():
            h = dict(self.headers)
            if headers:
                h.update(headers)
            # 显式带回 IDC 放行 hash 与会话 cookie（不依赖框架会话 jar）
            ck = self._cookie_header()
            if ck:
                old = h.get("Cookie") or h.get("cookie")
                h["Cookie"] = (old + "; " + ck) if old else ck
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)

        text = ""
        for attempt in range(3):
            try:
                text = _once()
            except Exception as e:
                self.log("fetch FAIL %s -> %s" % (url, e))
                text = ""

            # 命中浏览器校验页：种 cookie 加重放参数重放，成功直接复用重放正文
            if text and self._is_idc_page(text):
                ok, body = self._solve_idc(url, text)
                if ok:
                    text = body
                else:
                    self.log("浏览器校验未能通过，本列表返回空")
                    return ""

            if text and not self._is_upstream_error(text):
                return text
            self._reset_session()
            time.sleep(0.8 * (attempt + 1))
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
        s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        # 去掉图标私有区字符与多余空白
        s = re.sub(r"[\ue000-\uf8ff]", "", s)
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif", "load.svg"):
            if bad in low:
                return True
        return False

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for block in _RE_CARD.findall(html):
            mh = _RE_CARD_HREF.search(block)
            if not mh:
                continue
            href, vid = mh.group(1), mh.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            pic = ""
            mp = _RE_IMG.search(block)
            if mp:
                pic = mp.group(1)

            title = ""
            mt = _RE_TITLE.search(block)
            if mt:
                # 搜索页锚文本前缀带 <span class="info_right">分类标签</span>，剥离
                raw = re.sub(r'<span class="info_right"[^>]*>[\s\S]*?</span>',
                              "", mt.group(1), flags=re.I)
                title = self._clean(raw)
            if not title:
                mt2 = re.search(r'title="([^"]*)在线观看"', block)
                if mt2:
                    title = self._clean(mt2.group(1))
            if not title:
                mt3 = re.search(r'<a[^>]*class="vodlist_thumb[^"]*"[^>]*title="([^"]*)"', block, re.I)
                if mt3:
                    title = self._clean(mt3.group(1))
            if not title:
                ma = re.search(r'<img[^>]*?alt="([^"]*)"', block, re.I)
                if ma:
                    title = self._clean(ma.group(1))

            remarks = ""
            mr = _RE_PICTEXT.search(block)
            if mr:
                remarks = self._clean(mr.group(1))

            # 副标题：搜索页取 info_right 分类标签；分类页取 vodlist_sub 更新时间
            subtitle = ""
            mi = re.search(r'<span class="info_right"[^>]*>([\s\S]*?)</span>', block, re.I)
            if mi:
                subtitle = self._clean(mi.group(1))
            if not subtitle:
                ms = _RE_SUB.search(block)
                if ms:
                    subtitle = self._clean(ms.group(1))

            pic = self._fix_url(pic)
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

            if not title:
                continue
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in _RE_PAGE.findall(html)]
        if pages:
            return max(1, max(pages))
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._parse_cards(html)
        self.log("home: %d 条" % len(videos))
        return {"list": videos}

    def _category_url(self, tid, page, extend):
        # 子分类（hl01）筛选优先于大类 tid；无筛选第 1 页直连 /zjm/<tid>.html
        sub_tid = extend.get("tid") if isinstance(extend, dict) else None
        if not extend and page == 1:
            return "%s/zjm/%s.html" % (self.site_url, str(tid))
        params = {"searchtype": "5", "tid": str(sub_tid or tid), "page": str(page)}
        for k in ("jq", "area", "year", "yuyan", "letter", "order"):
            if extend.get(k):
                params[k] = str(extend[k])
        return self.site_url + "/search.php?" + urllib.parse.urlencode(params)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
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

        url = self._category_url(tid, page, extend)
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 35, "total": pagecount * 35,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        params = {"searchword": str(key or "").strip(), "page": str(page)}
        url = self.site_url + "/search.php?" + urllib.parse.urlencode(params)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        self.log("  搜索结果: %d 条" % len(videos))
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) or 1,
            "limit": 35, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段提取 ----------------
    def _field_a(self, html, label):
        """定位“标签：</span>”后紧邻的第一个 <a> 文本（年份/地区/类型同行分列）。"""
        m = re.search(
            r'<span[^>]*>' + label + r'：</span>\s*<a[^>]*>([\s\S]*?)</a>', html, re.I)
        return self._clean(m.group(1)) if m else ""

    def _li_fields(self, html):
        """解析详情：年份/地区/类型/状态/主演/导演。"""
        out = {"year": self._field_a(html, "年份"),
               "area": self._field_a(html, "地区"),
               "classify": self._field_a(html, "类型"),
               "remarks": "", "actor": "", "director": ""}

        # 状态：状态：</span> 后的 data_style
        ms = re.search(
            r'<span>状态：</span>\s*<span class="data_style"[^>]*>([\s\S]*?)</span>', html, re.I)
        if ms:
            out["remarks"] = self._clean(ms.group(1))

        # 站点未填年份时存为占位 "0"，清洗为空
        if out["year"] in ("0", "0.0"):
            out["year"] = ""

        # 主演 / 导演：各自 li.data 内全部 <a>
        for li in _RE_LI.findall(html):
            ml = _RE_LI_LABEL.search(li)
            if not ml:
                continue
            label, body = ml.group(1), ml.group(2)
            if label in ("主演", "导演"):
                names = [self._clean(a) for a in _RE_A_TEXT.findall(body)]
                names = [x for x in names if x]
                out["actor" if label == "主演" else "director"] = ", ".join(names)
        return out

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
        mh = _RE_H2.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报
        pic = self.default_pic
        mp = _RE_IMG.search(html)
        if mp:
            pic = self._fix_url(mp.group(1))
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

        # 评分：data-score 优先，star_tips 文本兜底
        score = ""
        msc = _RE_SCORE.search(html)
        if msc:
            score = msc.group(1)
        if not score:
            mst = _RE_SCORE_TXT.search(html)
            if mst:
                score = mst.group(1)
        if score in ("0", "0.0"):
            score = ""

        # 年份 / 地区 / 类型 / 状态 / 主演 / 导演
        meta = self._li_fields(html)
        year, area, classify = meta["year"], meta["area"], meta["classify"]
        remarks, actor, director = meta["remarks"], meta["actor"], meta["director"]

        # 简介：完整折叠文本优先，摘要兜底，再兜底 meta description
        content = ""
        mint = _RE_INTRO_FULL.search(html)
        if mint:
            content = self._clean(mint.group(1))
        if not content:
            mint = _RE_INTRO_CTX.search(html)
            if mint:
                content = self._clean(mint.group(1))
        if not content:
            mdesc = _RE_META_DESC.search(html)
            if mdesc:
                content = self._clean(mdesc.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 线路（nav1 顺序即站点顺序）=====
        tabs = []  # (playlist 序号, 线路名)
        for mt in _RE_TAB.finditer(html):
            tabs.append((mt.group(1), self._clean(mt.group(2))))

        # ===== 选集分组（容器 playlistN），按集号正序、去重 =====
        groups = {}
        box_order = []
        for mb in _RE_EP_BOX.finditer(html):
            pid, box = mb.group(1), mb.group(2)
            if pid not in box_order:
                box_order.append(pid)
            eps = []
            seen_nid = set()
            for ma in _RE_EP_A.finditer(box):
                href, sid, nid, ep_name = (ma.group(1), ma.group(2),
                                           ma.group(3), self._clean(ma.group(4)))
                if nid in seen_nid:
                    continue
                seen_nid.add(nid)
                # 容器外的“立即播放”按钮不纳入（容器内本就为选集链接）
                if ep_name in ("立即播放", ""):
                    continue
                eps.append((int(nid), ep_name, href))
            eps.sort(key=lambda x: x[0])  # 正序
            groups[pid] = eps

        # 线路顺序：tab 顺序优先，其次容器出现顺序
        tab_map = {pid: name for pid, name in tabs}
        sid_order = [pid for pid, _ in tabs]
        for pid in box_order:
            if pid not in sid_order:
                sid_order.append(pid)

        play_from, play_url = [], []
        for pid in sid_order:
            eps = groups.get(pid)
            if not eps:
                continue
            line_name = tab_map.get(pid) or ("线路%s" % pid)
            lines = ["%s$%s" % (ep_name, href) for _, ep_name, href in eps]
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join(lines))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": area,
            "vod_year": year,
            "vod_lang": "",
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": "",
            "vod_update": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def _extract_stream(self, html):
        if not html:
            return ""
        m = _RE_NOW.search(html)
        if m:
            url = m.group(1).replace("\\/", "/")
            if url.startswith("http"):
                return url
        # 兜底：页面直接出现裸 m3u8/mp4
        m = _RE_STREAM.search(html.replace("\\/", "/"))
        if m:
            url = m.group(0)
            if "movienuke.com" not in url:
                return url
        return ""

    def _resolve_sub_stream(self, url, header):
        """若为多码率 master 列表，解析第一条子 m3u8 补全返回；
        已是媒体播放列表或 mp4 则原样；子流不可达时回退 master，不误伤。
        网络异常/非 200 时重试一次，再失败才回退。"""
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
                return url  # 已是媒体播放列表，直接含分片
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        self.log("  master 解析子流 %s" % sub[:120])
                        return sub
                    self.log("  子流重试后失败: %s" % sub_err)
                    break
        except Exception as e:
            self.log("  子流解析回退: %s" % e)
        return url

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # 传入本身已是裸直链，直接放行（master 则解析到子流）
        if _RE_STREAM.search(play_page):
            final = self._resolve_sub_stream(play_page, header)
            res = {"parse": 0, "playUrl": "", "url": final, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        stream = ""
        if "/play/" in play_page:
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

        if stream:
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链 parse=0 %s" % stream[:140])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        self.log("  => 嗅探兜底 parse=1 %s" % play_page[:120])
        return res

    # ---------------- 其他契约方法 ----------------
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

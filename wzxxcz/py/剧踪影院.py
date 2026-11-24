# coding=utf-8
"""
剧踪影院 juzong01.me | TVBox Python 爬虫（豆花 dhvideo 契约）
站点结构（线上快照实证，MacCMS stui 移动模板）:
  - 首页:   /
  - 主分类: /vodtype/<tid>/            （第 1 页）
            /vodtype/<tid>-<page>/     （分页）
  - 筛选:   /vodshow/<12 段空槽>/
            段0=子类型 tid（未选则主 tid）/ 段1=地区 / 段2=排序 /
            段8=页码 / 段11=年份，空段占位
  - 详情:   /voddetail/<id>/
  - 播放:   /vodplay/<vid>-<sid>-<nid>/
  - 搜索:   /vodsearch/-------------/?wd=<关键词>&page=<页码>（实证段0 关键词路由冷会话返回空壳）

  - 卡片: a.stui-vodlist__thumb[href=/voddetail/<id>/][title][data-original]，
          span.pic-text=备注；h4.title a 兜底片名；p.text=主演（副标题）
  - 详情: h1.title 片名；img.lazyload[data-original|src] 海报（排除 /statics/icon/ 占位）；
          p.data 内 类型：a / 地区：文本 / 年份：文本；主演/导演 a 列表；更新：时间；
          简介 span.detail-content（完整折叠全文）> span.detail-sketch（摘要兜底）> meta description 兜底
  - 线路: div.stui-pannel → h3.title 线路名（剥 img 标签）→ ul.stui-content__playlist
          li a[href=/vodplay/..][集名]；无 vodplay 选集的推荐/排行块跳过；顺序=站点 DOM 序，
          集名保留站点原文（第01集/第1集/数字 混用不统一）
  - 播放: player_data JSON（花括号配平），encrypt=0/空 取 url，转义斜杠还原；
          master 多码率取首条子 m3u8（urljoin）；未命中兜底 parse:1 交客户端嗅探

站点防护（实证）:
  - 首页下发会话 Cookie server_session_<hex>，后续分类/详情/播放复用同一 Session；
    未带会话访问分类页返回 403 + 120 字节 JS 自跳壳（window.location.href），重新落会话重放。
  - 主备域名: 主 https://juzong01.me；别名 https://www.juzong01.me；
    备用 https://juzong02.me（5 秒倒计时跳转页，非独立镜像）。当前域不可达/返回跳转壳时自动轮换。
"""
import re
import sys
import json
import time
import socket
import urllib.parse

sys.path.append('..')

# ---- 强制 IPv4：禁用 IPv6（云端出口 IPv6 不稳）----
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            if r[0] == socket.AF_INET]


socket.getaddrinfo = _ipv4_getaddrinfo

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
                print("[juzong]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站专属配置 =====================
# 主备域名（顺序即轮换顺序）
HOSTS = [
    "https://juzong01.me",
    "https://www.juzong01.me",
    "https://juzong02.me",
]
HOST = HOSTS[0]
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

# 子类型：tid -> [(tid, 名称)]，URL 段0 用子 tid（站点导航实证）
_SUBTYPE = {
    "1": [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
          ("10", "恐怖片"), ("11", "剧情片"), ("12", "战争片"), ("22", "犯罪片"),
          ("23", "动画片")],
    "2": [("13", "国产剧"), ("14", "港台剧"), ("15", "日韩剧"), ("16", "欧美剧"),
          ("20", "海外剧")],
    "3": [],
    "4": [],
}

# 地区：tid -> 名称列表（URL 段1，站点原文）
_AREA = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
          "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["大陆", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
    "3": ["大陆", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
}

# 年份（URL 段11，站点实证 1998~2026）
_YEARS = [str(y) for y in range(2026, 1997, -1)]

# 排序（URL 段2）
_SORTS = [("最新更新", "time"), ("最近热播", "hits")]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    dims = []
    if _SUBTYPE.get(tid):
        dims.append({"key": "subtype", "name": "按类型",
                     "value": [{"n": "全部", "v": ""}] +
                              [{"n": n, "v": v} for v, n in _SUBTYPE[tid]]})
    dims.append({"key": "area", "name": "按地区", "value": _opts(_AREA[tid])})
    dims.append({"key": "year", "name": "按年份", "value": _opts(_YEARS)})
    dims.append({"key": "sort", "name": "排序",
                 "value": [{"n": n, "v": v} for n, v in _SORTS]})
    FILTERS[tid] = dims

# ===================== 正则 =====================
# 卡片
_RE_ANCHOR = re.compile(r'<a\b[^>]*stui-vodlist__thumb[^>]*>', re.I)
_RE_CARD_HREF = re.compile(r'/voddetail/(\d+)/', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_ORIG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
_RE_PICTEXT = re.compile(r'<span class="pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_H4 = re.compile(r'<h4 class="title[^"]*">[\s\S]*?<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_TEXT = re.compile(r'<p class="text[^"]*">([\s\S]*?)</p>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(
    r'<img[^>]*class="lazyload"[^>]*?(?:data-original|src)="([^"]*)"', re.I)
_RE_TYPE = re.compile(r'类型：</span>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_AREA = re.compile(r'地区：</span>\s*([^<]*)', re.I)
_RE_YEAR = re.compile(r'年份：</span>\s*([^<]*)', re.I)
_RE_ACTOR_BLOCK = re.compile(r'主演：</span>([\s\S]*?)</p>', re.I)
_RE_DIR_BLOCK = re.compile(r'导演：</span>([\s\S]*?)</p>', re.I)
_RE_UPDATE = re.compile(r'更新：</span>\s*([^<]*)', re.I)
_RE_INTRO_SKETCH = re.compile(r'<span class="detail-sketch">([\s\S]*?)</span>', re.I)
_RE_INTRO_FULL = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 线路 / 选集
_PANNEL_SPLIT = '<div class="stui-pannel stui-pannel-bg clearfix">'
_RE_PANEL_HEAD = re.compile(r'<h3 class="title">([\s\S]*?)</h3>', re.I)
_RE_EP = re.compile(r'<a[^>]*href="(/vodplay/[^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放直链
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)
# 可直放媒体后缀（m3u8/mp4）；其余为网页外链（爱优腾/B站/芒果等），交客户端二次解析
_RE_DIRECT = re.compile(r'\.(?:m3u8|mp4)(?:\b|[?#])', re.I)

# 占位封面（站点图标）
_PLACEHOLDER_PIC = "/statics/icon/"


class Spider(Spider):

    def getName(self):
        return "剧踪影院"

    # ---------------- 基础 ----------------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.hosts = list(HOSTS)
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self._host_idx = 0
        for i, h in enumerate(self.hosts):
            if h.rstrip("/") == self.site_url:
                self._host_idx = i
                break

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
        self._session = None
        self._warmed = False
        self._play_cache = {}

    def log(self, *a, **kw):
        try:
            print("[juzong]", *a)
        except Exception:
            pass

    # ---------------- 会话 / 主备轮换 ----------------
    def _session_get(self):
        if self._session is None:
            try:
                import requests as _rq
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            except Exception as e:
                self.log("自建 Session 失败:", e)
                self._session = None
        return self._session

    def _is_shell(self, text, status=200):
        if not text or len(text) < 200:
            return True
        if status and int(status) in (403, 502, 503, 500):
            return True
        # targetUrl 是跳转倒计时壳专用变量（备用域名 5 秒跳主站），不受长度限制。
        if "targetUrl" in text:
            return True
        # 跳转壳极短（120 字节自跳 script）；长页面内出现 window.location.href
        # 多为正常 JS 变量（如 vod_url=window.location.href），不误伤。
        if len(text) < 500 and ("window.location.href" in text or "正在跳转" in text):
            return True
        return False

    def _switch_host(self):
        """轮换到下一个主备域名，重置会话与预热标记。"""
        for _ in range(len(self.hosts) - 1):
            self._host_idx = (self._host_idx + 1) % len(self.hosts)
            cand = self.hosts[self._host_idx].rstrip("/")
            if cand != self.site_url:
                self.site_url = cand
                self.headers["Referer"] = self.site_url + "/"
                self._session = None
                self._warmed = False
                self.log("轮换域名 ->", self.site_url)
                return True
        return False

    def _warm_up(self):
        """先访问首页下发会话 Cookie，后续复用同一 Session。"""
        if self._warmed:
            return
        try:
            self._http_get(self.site_url + "/", timeout=(10, 20))
            self._warmed = True
        except Exception as e:
            self.log("预热失败:", e)

    def _http_get(self, url, headers=None, timeout=15):
        """自建 Session 优先；遇壳/403 重落会话重放一次；异常回退基类 fetch。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._session_get()
        rsp = None
        try:
            if sess is not None:
                rsp = sess.get(url, headers=h, timeout=timeout)
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("GET 异常:", url, repr(e)[:120])
            rsp = None

        text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200) if rsp is not None else 0

        if self._is_shell(text, status):
            # 重新落会话后重放一次
            self._session = None
            sess2 = self._session_get()
            try:
                if sess2 is not None:
                    sess2.get(self.site_url + "/", headers=h, timeout=(10, 20))
                    rsp = sess2.get(url, headers=h, timeout=timeout)
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else ""
                status = getattr(rsp, "status_code", 200)
            except Exception as e:
                self.log("重放异常:", repr(e)[:120])
                text, status = "", 0

        return rsp

    def _fetch(self, url, timeout=15, headers=None, tries=3):
        last = ""
        for i in range(tries):
            try:
                rsp = self._http_get(url, headers=headers, timeout=timeout)
                text = rsp.text if rsp is not None and hasattr(rsp, "text") else (
                    rsp.content.decode("utf-8", "ignore")
                    if rsp is not None and hasattr(rsp, "content") else "")
                status = getattr(rsp, "status_code", 200) if rsp is not None else 0
                if not self._is_shell(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, repr(e)[:120])
                last = ""
            if i < tries - 1:
                time.sleep(1.2 * (i + 1))
        # 多次遇壳：尝试轮换主备域名再取一次
        if self._switch_host():
            new_url = self._rebase_url(url, self.site_url)
            try:
                rsp = self._http_get(new_url, headers=headers, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else ""
                if not self._is_shell(text, getattr(rsp, "status_code", 200)):
                    return text
            except Exception as e:
                self.log("轮换后重试失败:", repr(e)[:120])
        return ""

    # ---------------- 工具 ----------------
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

    def _rebase_url(self, url, base):
        """轮换域名后，把本站 URL 的根域替换为新 base；外部直链原样保留。"""
        if not url:
            return url
        for h in self.hosts:
            if url.startswith(h):
                return base + url[len(h):]
        if url.startswith("http"):
            return url
        return base + (url if url.startswith("/") else "/" + url)

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

    # ---------------- 卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        anchors = list(_RE_ANCHOR.finditer(html))
        for i, mt in enumerate(anchors):
            tag = mt.group(0)
            mh = _RE_CARD_HREF.search(tag)
            if not mh:
                continue
            href = "/voddetail/%s/" % mh.group(1)
            if href in seen:
                continue
            seen.add(href)

            seg = html[mt.start():mt.start() + 400]
            end = anchors[i + 1].start() if i + 1 < len(anchors) else len(html)
            seg_full = html[mt.start():end]

            # 片名：title 属性优先，h4 a 兜底
            mt2 = _RE_TITLE.search(tag)
            title = self._clean(mt2.group(1)) if mt2 else ""
            if not title:
                mh4 = _RE_H4.search(seg_full)
                if mh4:
                    title = self._clean(mh4.group(1))
            if not title:
                continue

            # 封面：data-original 兜底 src，排除站点占位图标
            mo = _RE_ORIG.search(seg)
            pic = mo.group(1) if mo else ""
            if not pic:
                ms = _RE_SRC.search(tag)
                pic = ms.group(1) if ms else ""
            pic = pic.replace("&quot;", "").strip()
            if _PLACEHOLDER_PIC in pic:
                pic = ""
            pic = self._fix_url(pic)
            if not pic:
                pic = self.default_pic

            # 备注（更新至xx期 / HD / 上映日期）
            mr = _RE_PICTEXT.search(seg)
            remarks = self._clean(mr.group(1)) if mr else ""

            # 副标题：主演文本（兼容纯文本行与带“主演：”span 前缀两种形态）
            subtitle = ""
            msb = _RE_TEXT.search(seg_full)
            if msb:
                subtitle = re.sub(r"^主演[：:]\s*", "", self._clean(msb.group(1)))

            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })
        return videos

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def _page_count(self, html):
        """num(x/y) 解析总页数；兜底分页块内尾页链接最大页码；无分页块返回 1。
        只在 stui-page 分页块内取数，避免误抓块外详情 id / 年份。"""
        if not html:
            return 1
        block = re.search(r'<ul class="stui-page[\s\S]*?</ul>', html)
        if not block:
            return 1
        scope = block.group(0)
        m = re.search(r'(\d+)\s*/\s*(\d+)', scope)
        if m:
            return max(1, int(m.group(2)))
        pages = [int(x) for x in re.findall(r'-(\d+)/?', scope)]
        return max(1, max(pages)) if pages else 1

    def _filter_url(self, tid, extend, page=1):
        """构造筛选 URL：12 段空槽。
        段0=子类型 tid（未选则主 tid），段1=地区，段2=排序，段8=页码，段11=年份。"""
        parts = [""] * 12
        parts[0] = str(extend.get("subtype") or tid)
        if extend.get("area"):
            parts[1] = extend["area"]
        if extend.get("sort"):
            parts[2] = extend["sort"]
        parts[8] = str(page)
        if extend.get("year"):
            parts[11] = str(extend["year"])
        return self.site_url + "/vodshow/" + "-".join(parts) + "/"

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
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

        if extend:
            url = self._filter_url(tid, extend, page)
        elif page == 1:
            url = self.site_url + "/vodtype/%s/" % tid
        else:
            url = self.site_url + "/vodtype/%s-%d/" % (tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key or "").strip())
        # 实证：关键词搜索走 wd 参数（段0 关键词路由冷会话返回空壳），分页带 page
        url = self.site_url + "/vodsearch/-------------/?wd=%s&page=%d" % (kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _actors(self, html, block_re):
        m = block_re.search(html)
        if not m:
            return ""
        names = [self._clean(a) for a in _RE_A.findall(m.group(1))]
        names = [x for x in names if x]
        return ", ".join(names)

    def _parse_lines(self, html):
        """按 stui-pannel 分组，返回 [(线路名, [(集名, href), ...])]，保 DOM 序。
        无 vodplay 选集的推荐/排行块自然不落盘。"""
        panels = html.split(_PANNEL_SPLIT)[1:]
        play_from, play_url = [], []
        for panel in panels:
            mh = _RE_PANEL_HEAD.search(panel)
            if not mh:
                # 无线路标题的头部快捷播放块，跳过
                continue
            line_name = self._clean(mh.group(1))
            eps = []
            seen = set()
            for ma in _RE_EP.finditer(panel):
                href, ep_name = ma.group(1), self._clean(ma.group(2))
                if href in seen:
                    continue
                seen.add(href)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            if not line_name:
                line_name = "线路%d" % (len(play_from) + 1)
            # 重名线路去重编号
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))
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
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("-")[0].split("_")[0])
        name = name or vod_id

        # 海报（排除站点占位图标）
        pic = self.default_pic
        mp = _RE_POSTER.search(html)
        if mp and _PLACEHOLDER_PIC not in mp.group(1):
            pic = self._fix_url(mp.group(1))

        # 简介：完整折叠全文 detail-content 优先 → detail-sketch 摘要兜底 → meta description 再兜底
        content = ""
        mc = _RE_INTRO_FULL.search(html)
        if mc:
            content = self._clean(mc.group(1))
        if not content:
            ms = _RE_INTRO_SKETCH.search(html)
            if ms:
                content = self._clean(ms.group(1))
        if not content:
            md = _RE_META_DESC.search(html)
            if md:
                content = self._clean(md.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        actor = self._actors(html, _RE_ACTOR_BLOCK)
        director = self._actors(html, _RE_DIR_BLOCK)
        classify = self._clean(_RE_TYPE.search(html).group(1)) if _RE_TYPE.search(html) else ""
        area = self._clean(_RE_AREA.search(html).group(1)) if _RE_AREA.search(html) else ""
        year = self._clean(_RE_YEAR.search(html).group(1)) if _RE_YEAR.search(html) else ""
        update = self._clean(_RE_UPDATE.search(html).group(1)) if _RE_UPDATE.search(html) else ""

        # 线路 / 选集
        play_from, play_url = self._parse_lines(html)
        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        remarks = update or ("%d条线路" % len(play_from))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks,
            "vod_area": area,
            "vod_year": year,
            "vod_lang": "",
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
        html = self._fetch(play_page)
        stream = self._extract_stream(html)

        if stream and _RE_DIRECT.search(stream.lower()):
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # http 网页外链（爱优腾/B站/芒果等）交客户端平台二次解析；
        # 其余为站点加密标识（juzongX- token，浏览器侧第三方嗅探，服务端不可还原），
        # 回退本站播放页交客户端嗅探，不把裸 token 落地。
        target = stream if stream.startswith("http") else play_page
        res = {"parse": 1, "playUrl": "", "url": target, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    def _player_json(self, html):
        """player_data JSON 括号深度配对精确截取（正确处理嵌套对象/转义）。"""
        i = html.find("player_data")
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
                if str(aa.get("encrypt", "0")) in ("0", "") and aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mu:
                    return mu.group(1).replace("\\/", "/")
        m = _RE_STREAM.search(html)
        return m.group(0).replace("\\/", "/") if m else ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率→第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
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
                return url
            text = rm.text if hasattr(rm, "text") else ""
            if "#EXT-X-STREAM-INF" not in text:
                return url
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        return sub
                    break
        except Exception as e:
            self.log("子流解析回退:", e)
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
            rsp = self.fetch(url, headers={"User-Agent": UA, "Referer": self.site_url + "/"})
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

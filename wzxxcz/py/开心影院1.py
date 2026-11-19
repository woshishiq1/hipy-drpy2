# coding=utf-8
"""
开心影院 www.assydjc.com | TVBox Python 爬虫
站点结构（服务端渲染 HTML，MacCMS stui 模板）:
  - 首页:   /
  - 分类:   /assydls/<tid>.html
            /assydls/<tid>-<page>.html          （分页）
  - 筛选:   /assydso/<12段空槽>.html
            （段0=子类型 tid，段1=地区，段3=剧情，段8=页码，段11=年份）
  - 详情:   /assydxq/<id>.html
  - 搜索:   /assydsc/-------------.html?wd=<关键词>
  - 播放:   /assydbf/<vid>-<line>-<ep>.html
      · 线路: li.js-playfrom-tab[data-target="#playfrom_N"] > a，文本即线路名，
              顺序即站点按钮顺序（不按 line 编号重排）
      · 选集: div#playfrom_N > ul.stui-content__playlist > li > a[href]，锚文本即集名
  - 详情字段:
      · 片名 h1.title；海报 img.lazyload[data-original]
      · 主演/导演: p.data 内对应行的 a 文本列表
      · 类型/地区/年份: 同行 span 标签后纯文本
      · 简介: span.detail-content 优先，span.detail-sketch 兜底，meta description 再兜底

站点防护（实证）:
  首页下发会话 Cookie server_session_<hex>，后续详情/播放必须复用同一 Session，
  否则返回 envoy 503 upstream connection timeout；边缘节点间歇抖动，_fetch 内置重试。
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
                print("[assydjc]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.assydjc.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

# ===== 各分类独立筛选（逐分类取自站点快照，顺序对齐页面；折叠可筛选项一并保留）=====
# 按类型：子分类 tid（URL 段0 用子 tid）；key=subtype
_SUBTYPE = {
    "1": [("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
          ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("纪录片", "13"),
          ("悬疑片", "14"), ("犯罪片", "15"), ("动画片", "16")],
    "2": [("国产剧", "17"), ("港台剧", "18"), ("日韩剧", "20"), ("欧美剧", "21"),
          ("海外剧", "22")],
    "3": [("大陆综艺", "23"), ("港台综艺", "24"), ("日韩综艺", "25"), ("欧美综艺", "26")],
    "4": [("国产动漫", "27"), ("日韩动漫", "28"), ("欧美动漫", "29"), ("其他动漫", "30")],
    "5": [],
}

# 按剧情：类型文本（URL 段3）；key=class
_DRAMA = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪", "动画",
          "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春", "文艺", "微电影",
          "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情",
          "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺", "生活",
          "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作", "机战",
          "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智", "励志", "其他"],
    "5": ["女频恋爱", "反转爽", "脑洞悬疑", "年代穿越", "古装仙侠", "现代都市"],
}

# 按地区：地区文本（URL 段1）；key=area
_AREA = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国", "泰国",
          "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
    "5": ["大陆"],
}

# 按年份（URL 段11）；key=year
_YEAR = {
    "1": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
          "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    "2": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
          "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008", "2006",
          "2005", "2004"],
    "3": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
          "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008", "2007",
          "2006", "2005", "2004"],
    "4": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
          "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008", "2007",
          "2006", "2005", "2004"],
    "5": ["2026", "2025", "2024", "2023", "2022"],
}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    dims = []
    if _SUBTYPE.get(tid):
        dims.append({"key": "subtype", "name": "按类型",
                     "value": [{"n": "全部", "v": ""}] +
                              [{"n": n, "v": v} for n, v in _SUBTYPE[tid]]})
    dims.append({"key": "class", "name": "按剧情", "value": _opts(_DRAMA[tid])})
    dims.append({"key": "area", "name": "按地区", "value": _opts(_AREA[tid])})
    dims.append({"key": "year", "name": "按年份", "value": _opts(_YEAR[tid])})
    FILTERS[tid] = dims

# ===================== 正则 =====================
_RE_ANCHOR = re.compile(r'<a\b[^>]*stui-vodlist__thumb[^>]*>', re.I)
_RE_HREF = re.compile(r'href="(/assydxq/\d+\.html)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_BG = re.compile(r'(?:background-image|background)\s*:\s*url\(([^)]+)\)', re.I)
_RE_ORIG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_PICTEXT = re.compile(r'<span class="pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_SUB = re.compile(r'<p class="text[^"]*text-muted[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_SUB2 = re.compile(r'<p>\s*<span class="text-muted">[^<]*</span>([\s\S]*?)</p>', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(r'<img[^>]*class="lazyload"[^>]*data-original="([^"]*)"', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_INTRO_FULL = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_SKETCH = re.compile(r'<span class="detail-sketch">([\s\S]*?)</span>', re.I)

_RE_TAB = re.compile(
    r'<li[^>]*data-target="#(playfrom_\d+)"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_PANE = re.compile(
    r'<div[^>]*id="(playfrom_\d+)"[\s\S]*?(?=<div[^>]*id="playfrom_|$)', re.I)
_RE_EP = re.compile(
    r'<a[^>]*href="(/assydbf/\d+-\d+-\d+\.html)"[^>]*>([\s\S]*?)</a>', re.I)

_RE_NOW = re.compile(r'var\s+now\s*=\s*"([^"]*)"', re.I)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)


class Spider(Spider):

    def getName(self):
        return "开心影院"

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
        self._warmed = False

    # ---------------- 基础工具 ----------------
    def _warm_up(self):
        """先访问首页下发会话 Cookie，后续详情/播放复用同一 Session。"""
        if self._warmed:
            return
        self._fetch(self.site_url + "/", tries=6)
        self._warmed = True

    def _is_upstream_error(self, text):
        if not text:
            return True
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason"))

    def _fetch(self, url, timeout=15, headers=None, tries=3):
        last = ""
        for i in range(tries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self.fetch(url, headers=h, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else (
                    rsp.content.decode("utf-8", "ignore") if hasattr(rsp, "content") else "")
                if not self._is_upstream_error(text):
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
            mh = _RE_HREF.search(tag)
            mt2 = _RE_TITLE.search(tag)
            if not mh or not mt2:
                continue
            href, title = mh.group(1), self._clean(mt2.group(1))
            if href in seen:
                continue
            seen.add(href)
            seg = html[mt.start():mt.start() + 400]
            mo = _RE_ORIG.search(seg)
            if mo:
                pic = mo.group(1)
            else:
                mb = _RE_BG.search(seg)
                pic = mb.group(1) if mb else ""
            pic = pic.replace("&quot;", "").strip()
            pic = self._fix_url(pic)
            if not pic:
                pic = self.default_pic
            mr = _RE_PICTEXT.search(seg)
            remarks = self._clean(mr.group(1)) if mr else ""
            end = anchors[i + 1].start() if i + 1 < len(anchors) else len(html)
            ms = _RE_SUB.search(html[mt.start():end])
            subtitle = self._clean(ms.group(1)) if ms else ""
            if not subtitle:
                ms2 = _RE_SUB2.search(html[mt.start():end])
                subtitle = self._clean(ms2.group(1)) if ms2 else ""
            if not title:
                continue
            videos.append({
                "vod_id": href, "vod_name": title[:100], "vod_pic": pic,
                "vod_remarks": remarks, "vod_subtitle": subtitle,
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
        """从分页块 num(x/y) 解析总页数；兜底尾页链接最大页码；无分页块返回 1。"""
        if not html:
            return 1
        block = re.search(r'<ul class="stui-page[\s\S]*?</ul>', html)
        if not block:
            return 1
        scope = block.group(0)
        m = re.search(r'(\d+)\s*/\s*(\d+)', scope)
        if m:
            return max(1, int(m.group(2)))
        pages = [int(x) for x in re.findall(r'-(\d+)\.html', scope)]
        return max(1, max(pages)) if pages else 1

    def _filter_url(self, tid, extend, page=1):
        """构造筛选 URL：12 段空槽。
        段0=子类型 tid（未选则原 tid），段1=地区，段3=剧情，段8=页码，段11=年份。"""
        parts = [""] * 12
        parts[0] = str(extend.get("subtype") or tid)
        if extend.get("area"):
            parts[1] = extend["area"]
        if extend.get("class"):
            parts[3] = extend["class"]
        parts[8] = str(page)
        if extend.get("year"):
            parts[11] = str(extend["year"])
        return self.site_url + "/assydso/" + "-".join(parts) + ".html"

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
        else:
            url = self.site_url + "/assydls/%s-%d.html" % (tid, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key or "").strip())
        url = self.site_url + "/assydsc/-------------.html?wd=%s&page=%d" % (kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _line_names(self, html):
        """返回 [(pane_id, 线路名)]，顺序即站点 tab 顺序。"""
        return [(m.group(1), self._clean(m.group(2)))
                for m in _RE_TAB.finditer(html)]

    def _ep_groups(self, html):
        """返回 {pane_id: [(集名, href), ...]}，集名/链接原样保留站点顺序。"""
        groups = {}
        for mb in _RE_PANE.finditer(html):
            pid, box = mb.group(1), mb.group(0)
            eps = []
            seen = set()
            for ma in _RE_EP.finditer(box):
                href, ep_name = ma.group(1), self._clean(ma.group(2))
                if href in seen:
                    continue
                seen.add(href)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            groups[pid] = eps
        return groups

    def _meta_text(self, html, label):
        """标签后到下一个 span 前的纯文本（类型/地区/年份同行）。"""
        m = re.search(
            r'<span class="text-muted[^"]*">' + label + r'：</span>\s*([^<]*)', html, re.I)
        return self._clean(m.group(1)) if m else ""

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
        pic = self.default_pic
        mp = _RE_POSTER.search(html)
        if mp:
            pic = self._fix_url(mp.group(1))

        # 简介：完整折叠优先，摘要兜底，meta 再兜底
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

        # 主演 / 导演 / 类型 / 地区 / 年份
        actor = self._actors(html, "主演")
        director = self._actors(html, "导演")
        classify = self._meta_text(html, "类型")
        area = self._meta_text(html, "地区")
        year = self._meta_text(html, "年份")

        # ===== 线路与选集 =====
        tabs = self._line_names(html)
        groups = self._ep_groups(html)
        tab_map = dict(tabs)
        order = [pid for pid, _ in tabs]
        for pid in groups:
            if pid not in order:
                order.append(pid)

        play_from, play_url = [], []
        for pid in order:
            eps = groups.get(pid)
            if not eps:
                continue
            line_name = tab_map.get(pid) or ("线路%s" % pid)
            lines = ["%s$%s" % (n, h) for n, h in eps]
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join(lines))

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
            "vod_remarks": "%d条线路" % len(play_from),
            "vod_area": area,
            "vod_year": year,
            "vod_lang": "",
            "vod_classify": classify,
            "type_name": classify,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _actors(self, html, label):
        m = re.search(
            r'<span class="text-muted">' + label + r'：</span>([\s\S]*?)</p>', html, re.I)
        if not m:
            return ""
        names = [self._clean(a) for a in re.findall(r'<a[^>]*>([\s\S]*?)</a>', m.group(1))]
        names = [x for x in names if x]
        return ", ".join(names)

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

        if stream:
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_stream(self, html):
        if not html:
            return ""
        # 1) MacCMS player_aaaa JSON（括号配对精确截取）
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw)
                if aa.get("url"):
                    return aa["url"]
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mu:
                    return mu.group(1)
        # 2) var now
        m = _RE_NOW.search(html)
        if m:
            return m.group(1).replace("\\/", "/")
        # 3) 裸 m3u8/mp4
        m = _RE_STREAM.search(html)
        return m.group(0) if m else ""

    @staticmethod
    def _player_json(html):
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

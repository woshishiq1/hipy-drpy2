# coding=utf-8
"""
晴天影视 www.gsjsylgs.com | TVBox Python 爬虫 (豆花 dhvideo 契约)
站点结构（MacCMS ewave 模板）:
  - 首页:   /
  - 主分类: /xphjTV7/<tid>.html；子类型同前缀 <subtid>.html
  - 组合筛选/列表: /qSoQnXw/<slug>.html（slug 12 段，段0=tid 段1=地区 段2=排序
            段3=类型 段4=语言 段8=页码 段11=年份，空段占位）
  - 详情:   /FLxxbdA/<vid>.html
  - 播放:   /C7r9s9w/<vid>-<flag>-<ep>.html
  - 搜索:   /index.php/vod/search.html?wd=<关键词>&page=<pg>
  - 卡片:   li.pic > a[href*=FLxxbdA][title]，封面 data-original(绝对CDN)，
            备注 p.item-status，副标题 p.item-blurb
  - 详情:   .info h3 a 片名；.pic img 封面；分类/地区/年份/导演/主演/状态 标签后 <a>；
            简介 .more-box p.pt-10
  - 线路:   .playlist-tab li.ewave-tab[data-target="#ewave-playlist-<n>"]，
            线路名=li 文本，顺序=DOM 顺序；选集 #ewave-playlist-<n> li a
  - 播放直链: 播放页播放器 iframe / player_aaaa / 裸 m3u8·mp4 多层提取，
            未命中兜底 parse:1 交客户端嗅探
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
                print("[gsjsylgs]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.gsjsylgs.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
# 主分类
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "44", "type_name": "短剧"},
]

# 子类型：tid -> 名称（站点导航实证）
_SUBTYPE = {
    "1": [("27", "动作片"), ("6", "爱情片"), ("7", "科幻片"), ("8", "恐怖片"),
          ("9", "战争片"), ("10", "喜剧片"), ("11", "纪录片"), ("12", "剧情片"),
          ("38", "悬疑片"), ("39", "犯罪片"), ("40", "奇幻片"), ("41", "动画片"),
          ("42", "原创电影")],
    "2": [("28", "泰国剧"), ("45", "日本剧"), ("13", "大陆剧"), ("14", "港台剧"),
          ("15", "欧美剧"), ("16", "韩国剧"), ("43", "海外剧")],
    "3": [("34", "内地综艺"), ("35", "港台综艺"), ("36", "日韩综艺"), ("37", "欧美综艺")],
    "4": [("29", "国产动漫"), ("30", "日韩动漫"), ("31", "欧美动漫")],
    "44": [("58", "脑洞短剧"), ("46", "爱情短剧"), ("47", "逆袭短剧"),
           ("51", "都市短剧"), ("59", "穿越短剧"), ("60", "古装短剧")],
}

# 题材（剧情，slug 段3）：按主类取站点该频道库内实际标签（均为页面实证）
_TYPES = {
    # 电影：list_movie.html 快照实证 28 个
    "1": ["剧情", "喜剧", "爱情", "动作", "惊悚", "犯罪", "恐怖", "悬疑", "奇幻",
          "冒险", "科幻", "战争", "家庭", "历史", "古装", "传记", "音乐", "武侠",
          "运动", "短片", "歌舞", "儿童", "动画", "西部", "灾难", "青春", "戏曲",
          "文艺"],
    # 电视剧：泰国剧列表页实证 10 个
    "2": ["古装", "战争", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情", "历史",
          "网剧"],
    # 综艺：内地综艺列表页实证 13 个
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺",
          "生活", "游戏互动", "财经", "求职"],
    # 动漫：动漫主类列表页实证 16 个（末位站点原文为“其他”）
    "4": ["科幻", "热血", "推理", "搞笑", "冒险", "校园", "动作", "机战", "运动",
          "战争", "少年", "少女", "亲子", "益智", "励志", "其他"],
    # 短剧：短剧主类列表页实证 12 个
    "44": ["爱情", "动作", "喜剧", "战争", "科幻", "剧情", "武侠", "冒险", "枪战",
           "恐怖", "微电影", "其它"],
}
# 语言（slug 段4）：按主类实证
_LANGS = {
    "1": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    "2": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "3": ["国语", "英语", "韩语", "日语", "其它"],
    "4": ["国语", "英语", "日语", "其它"],
    "44": ["国语"],
}
# 年份区间（起, 止，含端点），按主类实证
_YEAR_RANGE = {"1": (2026, 2000), "2": (2026, 2004), "3": (2026, 2004),
                "4": (2026, 2004), "44": (2026, 2023)}
# 兜底集（五频道均已实证，此表仅作缺失 tid 的安全回退）
_DEFAULT_TYPES = ["剧情", "喜剧", "爱情", "动作", "犯罪", "战争", "家庭", "古装",
                  "奇幻", "悬疑", "科幻", "网剧"]
_DEFAULT_LANGS = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]
_DEFAULT_YEAR = (2026, 2009)

_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_SORTS = [("最近更新", "time"), ("最多播放", "hits"), ("最好评", "score")]

# slug 12 段：段0=tid/子类型tid 段2=排序 段3=题材 段4=语言 段5=字母 段8=页码 段11=年份
# 段1=地区（站点源码注释隐藏，不下发该维度）
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    types = _TYPES.get(tid, _DEFAULT_TYPES)
    langs = _LANGS.get(tid, _DEFAULT_LANGS)
    y0, y1 = _YEAR_RANGE.get(tid, _DEFAULT_YEAR)
    years = [str(y) for y in range(y0, y1 - 1, -1)]
    dims = []
    subs = _SUBTYPE.get(tid, [])
    if subs:
        dims.append({
            "key": "subtype", "name": "分类",
            "value": [{"n": "全部", "v": ""}] +
                     [{"n": n, "v": v} for v, n in subs],
        })
    dims += [
        {"key": "type", "name": "剧情",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in types]},
        {"key": "lang", "name": "语言",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in langs]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in years]},
        {"key": "letter", "name": "字母",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _LETTERS]},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]
    FILTERS[tid] = dims

# ===================== 正则 =====================
# 卡片 li 块
_RE_LI = re.compile(r'<li[^>]*class="[^"]*col-xs-4[\s\S]*?</li>', re.I)
_RE_CARD_HREF = re.compile(r'href="(/FLxxbdA/\d+\.html)"', re.I)
_RE_CARD_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_CARD_PIC = re.compile(r'data-original="([^"]+)"', re.I)
_RE_CARD_BG = re.compile(r'data-background="([^"]+)"', re.I)
_RE_STATUS = re.compile(r'<p class="item-status[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_BLURB = re.compile(r'<p class="item-blurb[^"]*"[^>]*>([\s\S]*?)</p>', re.I)

# 详情
_RE_TITLE = re.compile(r'<h3><a[^>]*>([\s\S]*?)</a></h3>', re.I)
_RE_POSTER = re.compile(
    r'<div class="pic[^"]*"[^>]*><img[^>]*?(?:data-original|src)="([^"]+)"', re.I)
_RE_FIELD = re.compile(
    r'(分类|地区|年份|导演|主演|状态)：([\s\S]*?)</span>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_INTRO = re.compile(r'<p class="pt-10 pb-10"[\s\S]*?</p>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路 tab / 选集
_RE_TAB = re.compile(
    r'<li[^>]*class="[^"]*ewave-tab[^"]*"[^>]*data-target="#ewave-playlist-(\d+)"[\s\S]*?</li>',
    re.I)
_RE_TAB_NAME = re.compile(r'>([\s\S]*?)<em>', re.I)
_RE_EP = re.compile(
    r'<li[^>]*class="[^"]*ewave-playlist-item[^"]*"[^>]*>\s*'
    r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放直链
_RE_AA_JSON = re.compile(r'aa\s*:\s*JSON\.parse\(\'([\s\S]*?)\'\)', re.S)
_RE_IFRAME = re.compile(r'<iframe[^>]*src="([^"]+)"', re.I)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)


class Spider(Spider):

    def getName(self):
        return "晴天影视"

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
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=15, headers=None, retries=3):
        last = ""
        for attempt in range(retries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self.fetch(url, headers=h, timeout=timeout)
                if hasattr(rsp, "text"):
                    last = rsp.text or ""
                elif hasattr(rsp, "content"):
                    last = rsp.content.decode("utf-8", "ignore")
                else:
                    last = str(rsp)
                if last and "upstream connect error" not in last:
                    return last
            except Exception as e:
                self.log("fetch FAIL", url, e)
            if attempt < retries - 1:
                time.sleep(0.6 * (attempt + 1))
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
        s = re.sub(r"\{self:[^}]*\}", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_LI.finditer(html):
            block = m.group(0)
            mh = _RE_CARD_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            seen.add(href)

            mt = _RE_CARD_TITLE.search(block)
            name = self._clean(mt.group(1)) if mt else ""
            mp = _RE_CARD_PIC.search(block)
            if not mp:
                mp = _RE_CARD_BG.search(block)
            pic = self._fix_url(mp.group(1)) if mp else self.default_pic

            mr = _RE_STATUS.search(block)
            remarks = self._clean(mr.group(1)) if mr else ""
            mb = _RE_BLURB.search(block)
            subtitle = self._clean(mb.group(1)) if mb else ""

            if not name:
                name = href.split("/")[-1].split(".")[0]
            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = re.search(r'<ul[^>]*class="[^"]*ewave-page[^"]*"[\s\S]*?</ul>', html)
        block = m.group(0) if m else html
        # 优先取 “当前页/总页” 文本，如 <span class="num">1/2303</span>
        total = re.search(r'(\d+)\s*/\s*(\d+)', block)
        if total:
            try:
                return int(total.group(2))
            except Exception:
                pass
        # 兜底：分页 slug 段 8 为页码（段 0 是 tid，不能取）
        pages = []
        for lk in re.findall(r'/qSoQnXw/([^"\s]+)\.html', block):
            seg = lk.split("-")
            if len(seg) > 8 and seg[8].isdigit():
                pages.append(int(seg[8]))
        if pages:
            return max(pages)
        return 9999

    # ---------------- 筛选 URL ----------------
    # slug 12 段：0=tid/子类型 2=排序 3=题材 4=语言 5=字母 8=页码 11=年份
    def _filter_slug(self, tid, subtype="", type_="", lang="", letter="",
                     year="", sort="", page=1):
        seg = [""] * 12
        seg[0] = str(subtype or tid)
        seg[2] = sort
        seg[3] = type_
        seg[4] = lang
        seg[5] = letter
        seg[8] = str(page) if page and page > 1 else ""
        seg[11] = year
        return "/qSoQnXw/" + "-".join(seg) + ".html"

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

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

        subtype = extend.get("subtype", "")
        type_ = extend.get("type", "")
        lang = extend.get("lang", "")
        letter = extend.get("letter", "")
        year = extend.get("year", "")
        sort = extend.get("sort", "")

        has_filter = any([subtype, type_, lang, letter, year, sort])
        if not has_filter:
            # 主类导航路由；翻页对齐站点分页按钮，走 slug 段 8 页码
            url = self.site_url + ("/xphjTV7/%s.html" % tid)
            if page > 1:
                url = self.site_url + self._filter_slug(tid, page=page)
        else:
            url = self.site_url + self._filter_slug(
                tid, subtype=subtype, type_=type_, lang=lang, letter=letter,
                year=year, sort=sort, page=page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        url = "%s/index.php/vod/search.html?wd=%s&page=%d" % (
            self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _field_map(self, html):
        fields = {}
        for m in _RE_FIELD.finditer(html):
            label, block = m.group(1), m.group(2)
            texts = [self._clean(a) for a in
                     _RE_A_TEXT.findall(block)]
            texts = [t for t in texts if t]
            if texts:
                fields[label] = ", ".join(texts)
            else:
                fields[label] = self._clean(block)
        return fields

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
        mh = _RE_TITLE.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("-")[0].split("详细介绍")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        mp = _RE_POSTER.search(html)
        if mp:
            pic = self._fix_url(mp.group(1)) or self.default_pic

        # 简介
        content = ""
        mi = _RE_INTRO.search(html)
        if mi:
            content = self._clean(mi.group(0))
        if not content:
            md = _RE_META_DESC.search(html)
            if md:
                content = self._clean(md.group(1))
        content = re.sub(r"^(剧情简介|简介)[：:]\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        f = self._field_map(html)
        classify = f.get("分类", "")
        area = f.get("地区", "")
        year_raw = f.get("年份", "")
        my = re.search(r"(\d{4})", year_raw)
        year = my.group(1) if my else ""
        director = f.get("导演", "")
        actor = f.get("主演", "")
        status = f.get("状态", "")

        # ===== 线路与选集 =====
        play_from, play_url = [], []
        tabs = []
        for mt in _RE_TAB.finditer(html):
            pid = mt.group(1)
            mn = _RE_TAB_NAME.search(mt.group(0))
            line_name = self._clean(mn.group(1)) if mn else ("线路%s" % pid)
            tabs.append((pid, line_name))

        # 选集容器按 id 索引：按容器起点切片到下一个容器
        playlists = {}
        starts = [(m.group(1), m.start()) for m in
                  re.finditer(r'id="ewave-playlist-(\d+)"', html)]
        for idx, (pid, st) in enumerate(starts):
            en = starts[idx + 1][1] if idx + 1 < len(starts) else len(html)
            block = html[st:en]
            eps = []
            seen_ep = set()
            for ma in _RE_EP.finditer(block):
                ep_href, ep_name = ma.group(1), self._clean(ma.group(2))
                if ep_href in seen_ep:
                    continue
                seen_ep.add(ep_href)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, ep_href))
            if eps:
                playlists[pid] = eps

        for pid, line_name in tabs:
            eps = playlists.get(pid)
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

        remarks = status or ("%d条线路" % len(play_from))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks,
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
            stream = self._fix_url(stream)
            stream = self._resolve_master(stream)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % stream[:160])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    # 花括号配平提取 JS 内联 JSON 对象（避开嵌套对象被非贪婪正则截断）
    def _extract_json_obj(self, text, var):
        if not text:
            return ""
        i = text.find(var)
        if i < 0:
            return ""
        i = text.find("{", i)
        if i < 0:
            return ""
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return text[i:j + 1]
        return ""

    # master 多码率列表 -> 首条子流绝对地址；非 master / 失败原样返回
    def _resolve_master(self, url):
        if not url or not url.lower().split("?")[0].endswith(".m3u8"):
            return url
        try:
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"},
                             timeout=15)
            body = rsp.text if hasattr(rsp, "text") else \
                rsp.content.decode("utf-8", "ignore")
            if "#EXT-X-STREAM-INF" in body:
                lines = [l.strip() for l in body.splitlines()
                         if l.strip() and not l.strip().startswith("#")]
                if lines:
                    sub = urllib.parse.urljoin(url, lines[0])
                    self.log("  master -> 子流: %s" % sub[:120])
                    return sub
        except Exception as e:
            self.log("  master 解析失败，回退 master: %s" % e)
        return url

    def _extract_stream(self, html):
        if not html:
            return ""
        # 1) player_aaaa JSON（花括号配平，兼容嵌套 vod_data）
        m = self._extract_json_obj(html, "player_aaaa")
        if m:
            try:
                aa = json.loads(m)
                if aa.get("url"):
                    return aa["url"]
            except Exception:
                pass
        # 2) aa:JSON.parse('...')
        m = _RE_AA_JSON.search(html)
        if m:
            raw = (m.group(1).replace("\\/", "/")
                   .replace("\\u0026", "&").replace("\\\\u0026", "&"))
            try:
                aa = json.loads(raw)
                if aa.get("url"):
                    return aa["url"]
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    return m2.group(1)
        # 3) iframe src
        m = _RE_IFRAME.search(html)
        if m:
            return m.group(1)
        # 4) 裸 m3u8 / mp4
        m = _RE_STREAM.search(html)
        return m.group(0) if m else ""

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
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"})
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

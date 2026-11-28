# coding=utf-8
"""
视界影视 deermk.com | TVBox Python 爬虫 
站点形态: mxprocms / mx001 主题, HTML 直出, 无 PoW / 验证码盾, 列表/详情/播放免登录。

分类(对齐站点顶部导航原序, 共四类; 热榜为排行页, 不入点播分类墙):
  9qz02v 剧集 / p28dqr 电影 / 624xq8 动漫 / d23vw1 综艺。

路由(连字符槽位):
  首页     /
  分类推荐 /cp/<tid>.html            (单屏混排, 弱网兜底单页)
  库页     /ku/<tid>-<area>-<sort>-<type>------<page>---<year>.html
           12 段: seg0 tid / seg1 地区 / seg2 排序 / seg3 类型 /
                   seg8 页码 / seg11 年份 (seg4-7, seg9-10 空)
  搜索     /search/----<kw>----<page>--.html
           13 段: seg5 关键词 / seg10 页码 (query 参数 ?wd= 返空, 必须走 path 段)
  详情     /dt/<slug>.html
  播放     /play/<slug>-<sid>-<nid>.html

筛选 extend key: class(类型 seg3, 仅电影/剧集) / area(地区 seg1) /
  year(年份 seg11) / sort(排序 seg2: time 更新时间 / time_add 添加时间 / score 评分排序)。
  类型/地区逐分类静态表(站点库页面板实证, 见 _FILTER_TABLE)。

卡片:
  海报墙(首页/库页) <a class="module-poster-item module-item" href="/dt/.." title="片名">
    note=.module-item-note 备注, img[data-original] 封面, 片名 title 兜底 .module-poster-item-title。
  搜索页 <div class="module-card-item module-item">, 内 a.module-card-item-poster[href],
    片名 .module-card-item-title>a>strong, 第二 .module-info-item-content 主演→副标题。

详情: h1 片名(兜底 title); 封面 data-original 兜底 og:image;
  tag 链: 第1个分类名(忽略) / 第2个年份 / 第3个地区 a / 第4个类型 a 链;
  info-item: span.module-info-item-title 标签 ↔ div.module-info-item-content 值
    (导演/主演/编剧/上映/片长/更新/备注), a 文本逗号 join;
    备注(HD/正片/第N集完结)优先入 vod_remarks, 缺省兜底片长(集数状态/时长);
    编剧/更新时间 TVBox 无独立键, 并入 vod_subtitle; 上映日期不重复入字段;
  简介 .module-info-introduction-content p 全文 → meta description 两层兜底;
  前缀固定注入, 空简介只回前缀; 本站无评分 / 无语言 / 无又名副标题。

线路: tab .module-tab-item[data-dropdown-value] 名顺序 ↔ .module-list panel DOM 顺序一一配对;
  盒内 button.module-play-list-link onclick=/play/.., span 选集名;
  选集按末段 /<slug>-<sid>-<nid>.html nid 数值正序去重(站点 DOM 已正序, 脚本仍重排保险)。

播放链:
  1) 播放页内嵌 player_aaaa = {encrypt, from, url, url_next, sid, nid, ...}
  2) encrypt=0 且 url 为 http 直链 → parse:0, master m3u8 解析首条子流
  3) 提取不到 / 加密 → parse:1 交壳子嗅探播放页
  直链 header 只带 UA(实测 CDN 无需 Referer, 带不带均 200)。

分页: 站点为滑动窗口(前端分母写死 50, 深页零交集, 无 total 接口), 满页 48 判下一页,
  total 按满页估值; 深页空即返空列表, 不回退推荐页。

脚本文件名: spider_deermk.py (交付 api 链接须含 .py 后缀, 满足壳子 isPy 判定)。
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
                print("[deermk]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://deermk.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/img/load.min.jpg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航原序） =====================
CLASSES = [
    {"type_id": "9qz02v", "type_name": "剧集"},
    {"type_id": "p28dqr",  "type_name": "电影"},
    {"type_id": "624xq8", "type_name": "动漫"},
    {"type_id": "d23vw1", "type_name": "综艺"},
]

# 排序（seg2; 站点面板: 更新时间 / 添加时间 / 评分排序）
_SORTS = [
    {"n": "更新时间", "v": "time"},
    {"n": "添加时间", "v": "time_add"},
    {"n": "评分排序", "v": "score"},
]

# 年份（站点库页列示 2026 → 2012）
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2011, -1)]

# 逐分类筛选面板（站点库页实测; 列表项 v=n=面板名, 顺序与站点一致; "全部"由 _opts 补）
_FILTER_TABLE = {
    "p28dqr": {
        "class": ["喜剧", "动作", "恐怖", "犯罪", "悬疑", "冒险", "科幻", "奇幻",
                  "武侠", "西部", "传记", "剧情", "爱情", "战争"],
        "area": ["大陆", "美国", "英国", "韩国", "日本", "法国", "香港", "台湾",
                 "泰国", "印度", "加拿大", "新加坡", "菲律宾", "其它"],
    },
    "9qz02v": {
        "class": ["古装", "犯罪", "冒险", "悬疑", "爱情", "喜剧", "战争", "武侠",
                  "科幻", "奇幻", "历史"],
        "area": ["大陆", "美国", "英国", "日本", "韩国", "泰国", "香港", "台湾",
                 "法国", "印度", "其它"],
    },
    "624xq8": {
        "class": [],
        "area": ["大陆", "日本", "美国", "台湾", "香港"],
    },
    "d23vw1": {
        "class": [],
        "area": ["大陆", "台湾", "香港", "韩国", "美国", "日本"],
    },
}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    tab = _FILTER_TABLE.get(tid, {})
    groups = []
    # 站点面板行序: 类型(仅电影/剧集) → 地区 → 年份 → 排序
    if tab.get("class"):
        groups.append({"key": "class", "name": "类型", "value": _opts(tab["class"])})
    groups += [
        {"key": "area", "name": "地区", "value": _opts(tab.get("area", []))},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]
    FILTERS[tid] = groups

_PAGE_LIMIT = 48

# ===================== 正则 =====================
# 海报墙卡片块: <a attrs href="/dt/.." class="module-poster-item module-item"> body </a>
_RE_POSTER = re.compile(
    r'<a([^>]*href="(/dt/[^"]+\.html)"[^>]*class="[^"]*module-poster-item[^"]*"[^>]*)>'
    r'([\s\S]*?)</a>', re.I)
# 搜索卡片起点(下一同类起点为块边界)
_RE_CARD_START = re.compile(r'<div class="module-card-item module-item">')
_RE_DT_HREF = re.compile(r'href="(/dt/[^"]+\.html)"', re.I)
_RE_ATTR_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_IMG_PIC = re.compile(r'<img[^>]*?(?:data-original|data-src)="([^"]*)"', re.I)
_RE_POSTER_TITLE = re.compile(
    r'<div class="module-poster-item-title">([^<]*)</div>', re.I)
_RE_CARD_TITLE = re.compile(
    r'<div class="module-card-item-title">[\s\S]*?<a[^>]*>\s*<strong>([^<]*)</strong>', re.I)
_RE_CARD_NOTE = re.compile(
    r'<div class="module-item-note">([^<]*)</div>', re.I)
_RE_CARD_INFO = re.compile(
    r'<div class="module-info-item-content">([\s\S]*?)</div>', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)', re.I)

# 详情 tag 链: 第1个分类名 / 第2个年份 / 第3个地区 a / 第4个类型 a 链
_RE_TAG_LINKS = re.compile(
    r'<div class="module-info-tag">([\s\S]*?)</div>\s*<div class="module-mobile-play">', re.I)
_RE_TAG_LINK = re.compile(r'<div class="module-info-tag-link">([\s\S]*?)</div>', re.I)
_RE_TAG_A = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)

# 详情元信息: span 标签 ↔ div 内容 配对
_RE_INFO_ITEM = re.compile(
    r'<div class="module-info-item">\s*'
    r'<span class="module-info-item-title">([^<]+)</span>\s*'
    r'<div class="module-info-item-content">([\s\S]*?)</div>', re.I)

# 简介容器
_RE_INTRO = re.compile(
    r'<div class="module-info-introduction-content">([\s\S]*?)</div>', re.I)

# 线路 tab 名(顺序) 与 panel 块(DOM 顺序)
_RE_TAB_ITEM = re.compile(
    r'<div class="module-tab-item tab-item"[^>]*data-dropdown-value="([^"]+)"', re.I)
_RE_PANEL = re.compile(
    r'<div class="module-list[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-list'
    r'|<div class="module"><div class="module-heading"><h2 class="module-title">相关推荐)', re.I)
_RE_EPISODE = re.compile(
    r'location\.replace\(\'([^\']+)\'[\s\S]*?<span>([^<]*)</span>', re.I)
_RE_EP_NO = re.compile(r'/([^/]+)-(\d+)-(\d+)\.html')

# 播放页 player_aaaa 起点（JSON 嵌套 vod_data, 需大括号配平, 非贪婪会截断内层 }）
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{)', re.I)


class Spider(Spider):

    def getName(self):
        return "视界影视"

    # ---------------- 工具 ----------------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
        except Exception:
            pass

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

    # ---------------- 卡片提取 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 1) 海报墙卡片(首页 / 库页)
        for attrs, href, body in _RE_POSTER.findall(html):
            if href in seen:
                continue
            seen.add(href)
            title = ""
            mt = _RE_POSTER_TITLE.search(body)
            if mt:
                title = self._clean(mt.group(1))
            if not title:
                ma = _RE_ATTR_TITLE.search(attrs)
                if ma:
                    title = self._clean(ma.group(1))
            mp = _RE_IMG_PIC.search(body)
            pic = mp.group(1) if mp else ""
            mn = _RE_CARD_NOTE.search(body)
            note = self._clean(mn.group(1)) if mn else ""
            videos.append({
                "vod_id": href,
                "vod_name": title[:100] or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": note,
                "vod_subtitle": "",
            })

        # 2) 搜索卡片(起点 split 切块, 规避嵌套 div 提前闭合)
        if not videos:
            blocks = _RE_CARD_START.split(html)[1:]
            for blk in blocks:
                mh = _RE_DT_HREF.search(blk)
                if not mh:
                    continue
                href = mh.group(1)
                if href in seen:
                    continue
                seen.add(href)
                mt = _RE_CARD_TITLE.search(blk)
                title = self._clean(mt.group(1)) if mt else ""
                mp = _RE_IMG_PIC.search(blk)
                pic = mp.group(1) if mp else ""
                mn = _RE_CARD_NOTE.search(blk)
                note = self._clean(mn.group(1)) if mn else ""
                infos = _RE_CARD_INFO.findall(blk)
                # 第一行 年份/地区/类型, 第二行 主演 → 副标题
                actor = self._clean(infos[1]) if len(infos) > 1 else ""
                videos.append({
                    "vod_id": href,
                    "vod_name": title[:100] or href,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": note,
                    "vod_subtitle": actor[:200],
                })

        # 3) 兜底: 详情链接 + 块内封面/标题分离匹配
        if not videos:
            hrefs = _RE_DT_HREF.findall(html)
            imgs = _RE_IMG_PIC.findall(html)
            for i, href in enumerate(hrefs):
                if href in seen:
                    continue
                seen.add(href)
                pic = imgs[i] if i < len(imgs) else ""
                videos.append({
                    "vod_id": href,
                    "vod_name": href,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                    "vod_subtitle": "",
                })
        return videos

    # ---------------- 路由构造 ----------------
    def _build_ku(self, tid, extend, page):
        area = urllib.parse.quote(extend.get("area") or "", safe="")
        sort = extend.get("sort") or ""
        cls = urllib.parse.quote(extend.get("class") or "", safe="")
        year = extend.get("year") or ""
        # 12 段: seg0 tid / seg1 area / seg2 sort / seg3 class /
        #        seg8 page / seg11 year
        segs = [tid, area, sort, cls, "", "", "", "", str(page), "", "", year]
        return self.site_url + "/ku/" + "-".join(segs) + ".html"

    def _build_search(self, keyword, page):
        kw = urllib.parse.quote(str(keyword or "").strip(), safe="")
        # 13 段: seg5 关键词 / seg10 页码
        segs = ["", "", "", "", "", kw, "", "", "", "", str(page), "", "", ""]
        return self.site_url + "/search/" + "-".join(segs) + ".html"

    def homeContent(self, filter=False):
        return {"class": list(CLASSES), "filters": dict(FILTERS)}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        url = self._build_ku(tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  HTML 长度: %d, 卡片: %d" % (len(html), len(videos)))

        pagecount = 1 if not videos else (page if len(videos) < _PAGE_LIMIT else page + 1)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": _PAGE_LIMIT, "total": pagecount * _PAGE_LIMIT,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        url = self._build_search(key, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": 1 if not videos else (page if len(videos) < _PAGE_LIMIT else page + 1),
            "limit": _PAGE_LIMIT, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
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
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*[（(]\d{4}[)）]\s*$", "", name).strip() or vod_id

        # 封面: 详情 data-original 兜底 og:image
        pic = self.default_pic
        mi = re.search(r'data-original="([^"]*)"', html)
        if mi:
            pic = self._fix_url(mi.group(1))
        else:
            mi = _RE_OG_IMG.search(html)
            if mi:
                pic = self._fix_url(mi.group(1))

        # tag 链: 分类名 / 年份 / 地区 / 类型
        year, area, vclass = "", "", ""
        mt = _RE_TAG_LINKS.search(html)
        if mt:
            tags = _RE_TAG_LINK.findall(mt.group(1))
            texts = [self._clean(t) for t in tags]
            # texts[0] 分类名(忽略); texts[1] 年份; texts[2] 地区; texts[3] 类型链
            if len(texts) > 1:
                year = texts[1]
            if len(texts) > 2:
                area = self._clean(texts[2].rstrip("/"))
            if len(texts) > 3:
                vclass = ", ".join(
                    self._clean(a) for a in _RE_TAG_A.findall(tags[3]) if self._clean(a))
                if not vclass:
                    vclass = self._clean(texts[3].rstrip("/"))

        # 元信息配对
        meta = {}
        for lab, val in _RE_INFO_ITEM.findall(html):
            lab = self._clean(lab).rstrip("：:")
            vals = [self._clean(a) for a in _RE_TAG_A.findall(val)]
            vals = [v for v in vals if v]
            if not vals:
                vals = [self._clean(val)]
            meta[lab] = ", ".join(v for v in vals if v)
        director = meta.get("导演", "")
        actor = meta.get("主演", "")
        writer = meta.get("编剧", "")
        update_at = meta.get("更新", "")
        duration = meta.get("片长", "")
        remarks_note = meta.get("备注", "")

        # 备注角标: 站点「备注」(HD/正片/第N集完结) 优先, 缺省兜底「片长」(集数状态/时长)
        remarks = remarks_note or duration

        # 副标题: TVBox 无独立编剧/更新时间键, 挂 vod_subtitle 保留, 不污染导演/主演
        sub_parts = []
        if writer:
            sub_parts.append("编剧：" + writer[:200])
        if update_at:
            sub_parts.append("更新：" + update_at)
        subtitle = " · ".join(sub_parts)

        # 简介: intro 全文 → meta description; 前缀强制注入
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = re.sub(r"^\s*" + re.escape(name) + r"\s*", "", content).strip()
            content = re.sub(r"^剧情\s*[:：]\s*", "", content).strip()
            content = re.sub(r"^[，,、：:；;\s]+", "", content).strip()
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # ===== 线路与选集(tab 名顺序 ↔ panel DOM 顺序配对) =====
        line_names = _RE_TAB_ITEM.findall(html)
        panels = _RE_PANEL.findall(html)
        play_from, play_url = [], []
        for i, panel in enumerate(panels):
            eps = _RE_EPISODE.findall(panel)
            if not eps:
                continue

            def _ep_no(ep):
                em = _RE_EP_NO.search(ep[0])
                return int(em.group(3)) if em else 0

            eps = sorted(eps, key=_ep_no)
            seen_ep, uniq = set(), []
            for h, n in eps:
                if h in seen_ep:
                    continue
                seen_ep.add(h)
                uniq.append((h, n))

            line_name = ""
            if i < len(line_names):
                line_name = self._clean(line_names[i])
            line_name = line_name or ("线路%d" % (len(play_from) + 1))
            play_from.append(line_name)
            play_url.append("#".join(
                "%s$%s" % (self._clean(n) or ("第%d集" % (k + 1)), self._fix_url(h))
                for k, (h, n) in enumerate(uniq)))

        if not play_from:
            return {"list": []}

        remarks = remarks or ("%d条线路" % len(play_from))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_class": vclass,
            "vod_lang": "",
            "vod_score": "",
            "vod_subtitle": subtitle,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _extract_player(self, html):
        """大括号配平提取 player_aaaa JSON（字符串内括号不计深度）。"""
        m = _RE_PLAYER.search(html)
        if not m:
            return {}
        i = m.start(1)
        depth, in_str, esc = 0, False, False
        for j in range(i, len(html)):
            c = html[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = html[i:j + 1]
                    try:
                        return json.loads(raw)
                    except Exception as e:
                        self.log("  player JSON 解析失败: %s" % e)
                        return {}
        return {}

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
        real = ""
        encrypt = 0

        conf = self._extract_player(html)
        if conf:
            encrypt = int(conf.get("encrypt", 0) or 0)
            real = str(conf.get("url") or "")

        if real and real.startswith("http") and encrypt == 0:
            real = self._resolve_master(real)
            res = {
                "parse": 0, "playUrl": "", "url": real,
                "header": {"User-Agent": UA},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % real[:120])
            return res

        # 兜底: 交壳子嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _resolve_master(self, url):
        """master m3u8 取首条子流; 裸子流相对 master 拼接; 非 master 原样返回。"""
        if not url or ".m3u8" not in url.lower():
            return url
        try:
            rsp = self.fetch(url, headers={"User-Agent": UA}, timeout=15)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            if "#EXT-X-STREAM-INF" not in text:
                return url
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            for i, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                    sub = lines[i + 1].strip()
                    if sub.startswith("http"):
                        return sub
                    return urllib.parse.urljoin(url, sub)
        except Exception as e:
            self.log("  master 解析失败: %s" % e)
        return url

    # ---------------- 壳子兼容方法 ----------------
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
            rsp = self.fetch(url, headers={"User-Agent": UA}, timeout=15)
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

# coding=utf-8
"""
Gimy 劇迷 gimytv.biz | TVBox Python 爬虫 
站点形态: MacCMS v10 / gimy 主题, HTML 直出, 无 PoW / 验证码盾, 列表/详情/播放免登录。繁体站。

分类(对齐站点顶部导航原序):
  2 電視劇 / 4 動漫 / 3 綜藝 / 1 電影。
子类(独立 vodtype tid, 选中即换 vodtype/<子tid>.html):
  電影 1: 6 動作片 7 喜劇片 8 愛情片 9 科幻片 10 恐怖片 11 劇情片 12 戰爭片 24 動畫電影
  劇集 2: 13 陸劇 15 韓劇 16 美劇 20 日劇 14 台劇 21 海外劇 22 港劇 23 紀錄片 54 短劇
  動漫 4 / 綜藝 3 無子類型組。

路由:
  首页       /
  主类库页   /vodtype/<tid>-<page>.html       (電影/劇集单页全量; 綜藝/動漫分页)
  子类库页   /vodtype/<子tid>-<page>.html     (全部子类分页)
  筛选库页   /vodshow/<12 槽>/sid/1.html
             12 段: seg0 tid / seg1 地区(别名逗号串) / seg8 页码 / seg11 年份; 无排序/类型段
  详情       /voddetail/<vid>.html
  播放       /video/<vid>-<nid>.html#sid=<sid>
  搜索       /vodsearch/<13 槽>.html
             13 段: seg5 关键词; ?wd= query 兜底

筛选 extend key: class(子类 tid) / area(地区别名串) / year(年份)。
地区选项 v=站点别名逗号串(如 中國大陸,大陸,內地), n=展示名; 年份 2026→2016; 站点无排序组。

卡片:
  库页/首页 <li class="col-md-2 ..."> > <a class="video-pic[ loading]" href="/voddetail/.." title>
    封面 data-original 兜底 img src; span.note 备注; 标题锚 title 兜底 h5>a; .subtitle 主演→副标题。
  搜索页 <div class="details-info-min ..."> 块: 左 a.video-pic, 右 ul.info
    li>a[title] 片名; 狀態 li→备注; 主演 li→副标题。

详情: h1 片名(兜底 title, 剥「線上看 | 站名」后缀); 封面 data-original 兜底 og:image;
  meta li: span.gimy-detail-meta-label 标签 ↔ span/strong/a.gimy-detail-meta-value 值
    (狀態→remarks / 類別→class / 主演→actor / 導演→director / 國家地區→area /
     語言字幕→lang / 年代→year / 更新時間→subtitle / 人氣忽略);
  简介 .details-content-all 全文 → meta description 兜底; 剥「片名線上看:類型,」前缀;
  前缀强制注入, 空简介只回前缀。

线路: 宽松提取所有 <a href="#con_playlist_<sid>"> 文本(含「更多」下拉层), 文本即线路名,
  配对 <ul id="con_playlist_<sid>">; 盒内 a.episode-card-link href=/video/<vid>-<nid>.html,
  集名 episode-title / title 属性; 按末段 nid 数值正序去重; tab DOM 顺序即站点线路顺序, 不重排不删线。

播放链:
  1) 播放页内嵌 player_aaaa={flag,encrypt,from,url,url_next,sid,nid,vod_data...}
  2) encrypt=0 且 url 为 http 直链 → parse:0, master m3u8 解析首条子流
  3) 提取不到 / 加密 → parse:1 交壳子嗅探
  直链 header 只带 UA(实测 CDN v.fengbao14.com 无需 Referer)。

分页: vodtype(主类/子类) 与 vodshow(筛选) 统一按页头总页号 N/M 逐页聚合, 按 vid 去重;
      電影/劇集无分页锚点视为 1 页; 每页大小浮动, 不靠"不足一页"判末页。

脚本文件名: spider_gimytv.py (交付 api 链接须含 .py 后缀, 满足壳子 isPy 判定)。
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
                print("[gimytv]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://gimytv.biz"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/upload/site/20261001-1/default.jpg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类(对齐站点导航原序) =====================
CLASSES = [
    {"type_id": "2",  "type_name": "電視劇"},
    {"type_id": "4",  "type_name": "動漫"},
    {"type_id": "3",  "type_name": "綜藝"},
    {"type_id": "1",  "type_name": "電影"},
]

# 子类(独立 vodtype tid; 電影/劇集有, 動漫/綜藝無)
_SUBCLASS = {
    "1": [
        {"n": "動作片", "v": "6"}, {"n": "喜劇片", "v": "7"},
        {"n": "愛情片", "v": "8"}, {"n": "科幻片", "v": "9"},
        {"n": "恐怖片", "v": "10"}, {"n": "劇情片", "v": "11"},
        {"n": "戰爭片", "v": "12"}, {"n": "動畫電影", "v": "24"},
    ],
    "2": [
        {"n": "陸劇", "v": "13"}, {"n": "韓劇", "v": "15"},
        {"n": "美劇", "v": "16"}, {"n": "日劇", "v": "20"},
        {"n": "台劇", "v": "14"}, {"n": "海外劇", "v": "21"},
        {"n": "港劇", "v": "22"}, {"n": "紀錄片", "v": "23"},
        {"n": "短劇", "v": "54"},
    ],
    "4": [],
    "3": [],
}

# 地区(n=展示名, v=站点别名逗号串; 逐分类实测库页面板)
_AREA = {
    "1": [
        {"n": "中國大陸", "v": "中國大陸,大陸,內地"}, {"n": "韓國", "v": "韓國"},
        {"n": "日本", "v": "日本"}, {"n": "台灣", "v": "台灣,中國台灣"},
        {"n": "香港", "v": "香港"}, {"n": "美國", "v": "美國"},
        {"n": "歐美", "v": "歐美"}, {"n": "泰國", "v": "泰國"},
        {"n": "英國", "v": "英國"}, {"n": "新加坡", "v": "新加坡"},
        {"n": "其他", "v": "其他"},
    ],
    "2": [
        {"n": "中國大陸", "v": "中國大陸,大陸"}, {"n": "韓國", "v": "韓國,韩国"},
        {"n": "日本", "v": "日本"}, {"n": "台灣", "v": "台灣,中國台灣"},
        {"n": "香港", "v": "香港"}, {"n": "美國", "v": "美國,美国"},
        {"n": "歐美", "v": "歐美"}, {"n": "泰國", "v": "泰國"},
        {"n": "英國", "v": "英國"}, {"n": "法國", "v": "法國"},
        {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"},
        {"n": "土耳其", "v": "土耳其"}, {"n": "西班牙", "v": "西班牙"},
    ],
    "4": [
        {"n": "中國大陸", "v": "中國大陸,中國,大陸,內地"}, {"n": "韓國", "v": "韓國"},
        {"n": "日本", "v": "日本"}, {"n": "台灣", "v": "台灣,臺灣,中國台灣"},
        {"n": "香港", "v": "香港"}, {"n": "美國", "v": "美國"},
        {"n": "歐美", "v": "歐美"},
    ],
    "3": [
        {"n": "中國大陸", "v": "中國大陸,中國,大陸,中国大陆,內地"}, {"n": "韓國", "v": "韓國,韩国"},
        {"n": "日本", "v": "日本"}, {"n": "台灣", "v": "台灣,臺灣,中国台湾,台湾,中國台灣"},
        {"n": "香港", "v": "香港"}, {"n": "美國", "v": "美國"},
        {"n": "歐美", "v": "歐美"},
    ],
}

# 年份(站点库页列示 2026 → 2016)
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2015, -1)]


def _all_area(opts):
    return [{"n": "全部", "v": ""}] + opts


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    groups = []
    if _SUBCLASS.get(tid):
        groups.append({"key": "class", "name": "類型",
                       "value": [{"n": "全部", "v": ""}] + _SUBCLASS[tid]})
    groups += [
        {"key": "area", "name": "地區", "value": _all_area(_AREA.get(tid, []))},
        {"key": "year", "name": "年份", "value": _YEARS},
    ]
    FILTERS[tid] = groups

_PAGE_LIMIT = 60
_PAGE_SIZE = 36   # 站点单页参考卡片数(实际每页大小浮动, 末页/总页号以页头 N/M 为准)
_MAX_PAGE = 300  # 预留安全阀(当前 categoryContent 按 pg 单页返回, 不做站内聚合)

# ===================== 正则 =====================
# 库页/首页卡片: <a ...class="video-pic[ loading]"...> 锚点(属性顺序两种, 分项 search)
_RE_PIC_BLOCK = re.compile(r'<a\b([^>]*)>([\s\S]*?)</a>', re.I)
_RE_HREF = re.compile(r'href="(/voddetail/\d+\.html)"', re.I)
_RE_ATTR_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_ATTR_PIC = re.compile(r'(?:data-original|data-src)="([^"]*)"', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]*)"', re.I)
_RE_NOTE = re.compile(r'<span class="note[^"]*">([^<]*)</span>', re.I)
_RE_H5_TITLE = re.compile(
    r'<h5[^>]*>\s*<a[^>]*>([^<]*)</a>', re.I)
_RE_SUBTITLE = re.compile(
    r'<div class="subtitle[^"]*">([\s\S]*?)</div>', re.I)

# 搜索卡片起点
_RE_SEARCH_START = re.compile(r'<div class="details-info-min[^"]*"')
_RE_SEARCH_TITLE = re.compile(
    r'<li[^>]*>\s*<a[^>]*title="([^"]*)"', re.I)
_RE_SEARCH_LI = re.compile(r'<li[^>]*>([\s\S]*?)</li>', re.I)
_RE_LI_LABEL = re.compile(r'<span[^>]*>([^：:]+)[：:]</span>')

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)', re.I)

# 详情 meta li: label ↔ value(span/strong/a.gimy-detail-meta-value)
_RE_META_LI = re.compile(
    r'<li[^>]*gimy-detail-meta-item[^>]*>\s*'
    r'<span class="gimy-detail-meta-label">([^<]+)</span>\s*'
    r'(?:<(span|strong|a)[^>]*gimy-detail-meta-value[^>]*>)([\s\S]*?)</(?:span|strong|a)>',
    re.I)

# 简介正文
_RE_INTRO = re.compile(
    r'<span class="details-content-all">([\s\S]*?)</span>', re.I)

# 线路 tab: <a href="#con_playlist_<sid>" ...>线路名</a> (含下拉层)
_RE_TAB = re.compile(
    r'<a[^>]*href="#con_playlist_(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PLAYLIST = re.compile(
    r'<ul[^>]*id="con_playlist_(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EPISODE = re.compile(
    r'<a[^>]*href="(/video/[^"]+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_EP_NAME = re.compile(r'episode-title[^>]*>([^<]*)', re.I)
_RE_EP_NO = re.compile(r'/video/\d+-(\d+)\.html')

# 播放页 player_aaaa 起点(JSON 嵌套 vod_data, 须大括号配平)
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{)', re.I)


class Spider(Spider):

    def getName(self):
        return "Gimy 劇迷"

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
    def _extract_videos(self, html, search=False):
        videos = []
        seen = set()
        if not html:
            return videos

        # 1) 库页/首页: video-pic 锚点(属性顺序两种, 分项 search)
        #    搜索页包裹为 details-info-min, 走第 2) 段; 搜索 path 段未命中时站点会
        #    渲染「影片排行榜」同构锚点, 必须排除, 故 search=True 时不跑第一段。
        if not search:
            for m in _RE_PIC_BLOCK.finditer(html):
                attrs, body = m.group(1), m.group(2)
                if "video-pic" not in attrs:
                    continue
                mh = _RE_HREF.search(attrs)
                if not mh:
                    continue
                href = mh.group(1)
                if href in seen:
                    continue
                seen.add(href)
                mt = _RE_ATTR_TITLE.search(attrs)
                name = self._clean(mt.group(1)) if mt else ""
                mp = _RE_ATTR_PIC.search(attrs) or _RE_IMG.search(body)
                pic = mp.group(1) if mp else ""
                mn = _RE_NOTE.search(body)
                note = self._clean(mn.group(1)) if mn else ""
                if not name:
                    mh5 = _RE_H5_TITLE.search(body)
                    if mh5:
                        name = self._clean(mh5.group(1))
                tail = html[m.end():m.end() + 400]
                ms = _RE_SUBTITLE.search(tail)
                subtitle = self._clean(ms.group(1)) if ms else ""
                videos.append({
                    "vod_id": href,
                    "vod_name": name[:100] or href,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": note,
                    "vod_subtitle": subtitle[:200],
                })

        # 2) 搜索页: details-info-min 块切块
        if not videos:
            blocks = _RE_SEARCH_START.split(html)[1:]
            for blk in blocks:
                mh = _RE_HREF.search(blk)
                if not mh:
                    continue
                href = mh.group(1)
                if href in seen:
                    continue
                seen.add(href)
                mt = _RE_SEARCH_TITLE.search(blk)
                name = self._clean(mt.group(1)) if mt else ""
                mp = _RE_ATTR_PIC.search(blk) or _RE_IMG.search(blk)
                pic = mp.group(1) if mp else ""
                note, actor = "", ""
                for li in _RE_SEARCH_LI.findall(blk):
                    lab = _RE_LI_LABEL.search(li)
                    lab = self._clean(lab.group(1)) if lab else ""
                    val = self._clean(re.sub(r"<[^>]+>", " ", li))
                    val = re.sub(r"^[^：:]*[：:]\s*", "", val).strip()
                    if lab in ("狀態", "状态"):
                        note = val
                    elif lab == "主演":
                        actor = ", ".join(
                            x.strip() for x in re.split(r"[、,]", val) if x.strip())
                videos.append({
                    "vod_id": href,
                    "vod_name": name[:100] or href,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": note,
                    "vod_subtitle": actor[:200],
                })

        # 3) 兜底: 详情链接 + 块内封面分离匹配(仅库页/首页; 搜索未命中返空走 query 兜底)
        if not videos and not search:
            hrefs = _RE_HREF.findall(html)
            imgs = _RE_IMG.findall(html)
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
    def _build_ku(self, tid, extend, page=1):
        cls = (extend.get("class") or "").strip()
        area = urllib.parse.quote(extend.get("area") or "", safe="")
        year = extend.get("year") or ""
        # 子类: 独立 vodtype/<子tid>-<page>.html
        if cls:
            return self.site_url + "/vodtype/" + cls + "-" + str(page) + ".html"
        # 无任何筛选条件: 主类库页 vodtype/<tid>-<page>.html
        # (電影/劇集站点忽略页码返同页; 綜藝/動漫/子类按页头总页号翻页)
        if not area and not year:
            return self.site_url + "/vodtype/" + tid + "-" + str(page) + ".html"
        # 带地区/年份筛选: 12 段 vodshow/<tid>-<area>-------<page>---<year>/sid/1.html
        # seg0 tid / seg1 地区别名 / seg8 页码 / seg11 年份, 其余空段占位
        segs = [tid, area, "", "", "", "", "", "",
                str(page), "", "", year]
        return self.site_url + "/vodshow/" + "-".join(segs) + "/sid/1.html"

    def _read_page_count(self, html, route, idv):
        """读页头总页号 M: 优先 class=num 的 N/M, 兜底分页锚最大页号; 取不到返 1。"""
        if not html:
            return 1
        m = re.search(r'class="num">\s*\d+\s*/\s*(\d+)', html)
        if m and int(m.group(1)) >= 1:
            return int(m.group(1))
        if route == "vodtype":
            pg = [int(n) for n in re.findall(r'/vodtype/%s-(\d+)\.html' % idv, html)]
        else:
            pg = [int(n) for n in re.findall(r'/vodshow/[^"\']*?-(\d+)-[^"\']*?/sid/1\.html', html)]
        return max(pg) if pg else 1

    def _build_search(self, keyword, page):
        kw = urllib.parse.quote(str(keyword or "").strip(), safe="")
        # 13 段: seg5 关键词
        segs = ["", "", "", "", "", kw, "", "", "", "", "", "", ""]
        return self.site_url + "/vodsearch/" + "-".join(segs) + ".html"

    def homeContent(self, filter=False):
        return {"class": list(CLASSES), "filters": dict(FILTERS)}

    def homeVideoContent(self):
        try:
            self._warm_up()
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            return {"list": self._extract_videos(html)}
        except Exception as e:
            self.log("homeVideoContent FAIL: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            self._warm_up()
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if not isinstance(extend, dict):
                extend = {}
            extend = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

            cls = (extend.get("class") or "").strip()
            area = extend.get("area") or ""
            year = extend.get("year") or ""
            # 通道: 子类/主类 → vodtype; 带地区/年份筛选 → vodshow
            route = "vodshow" if (not cls and (area or year)) else "vodtype"
            idv = cls or tid
            page = int(pg) if str(pg or "1").isdigit() else 1
            page = page if page >= 1 else 1

            url = self._build_ku(tid, extend, page)
            self.log("category p%d: %s" % (page, url))
            html = self._fetch(url)
            videos = self._extract_videos(html)
            pagecount = self._read_page_count(html, route, idv)
            total = len(videos) if videos else pagecount * _PAGE_SIZE
            self.log("  卡片: %d, 页数: %d" % (len(videos), pagecount))

            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": _PAGE_LIMIT, "total": total,
            }
        except Exception as e:
            self.log("categoryContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": _PAGE_LIMIT, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            if not str(key or "").strip():
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": _PAGE_LIMIT, "total": 0}
            self._warm_up()
            url = self._build_search(key, pg)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html, search=True)
            # path 段返空(未命中渲染排行榜)时, 兜底 query 参数通道
            if not videos:
                q = urllib.parse.quote(str(key or "").strip(), safe="")
                alt = self.site_url + "/vodsearch/-------------.html?wd=" + q
                self.log("search 兜底 query: %s" % alt)
                html = self._fetch(alt)
                videos = self._extract_videos(html, search=True)
            return {
                "list": videos, "page": int(pg) if pg else 1,
                "pagecount": 1, "limit": _PAGE_LIMIT, "total": len(videos),
            }
        except Exception as e:
            self.log("searchContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": _PAGE_LIMIT, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        try:
            return self._detail(ids)
        except Exception as e:
            self.log("detailContent FAIL: %s" % e)
            return {"list": []}

    def _detail(self, ids):
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
                t = self._clean(m.group(1))
                t = re.split(r"線上看|线上看|\|", t)[0].strip()
                name = t
        name = re.sub(r"\s*[（(]\d{4}[)）]\s*$", "", name).strip() or vod_id

        # 封面: data-original 兜底 og:image
        pic = self.default_pic
        mi = re.search(r'data-original="([^"]*)"', html)
        if mi:
            pic = self._fix_url(mi.group(1))
        else:
            mi = _RE_OG_IMG.search(html)
            if mi:
                pic = self._fix_url(mi.group(1))

        # 元信息配对
        meta = {}
        for lab, _tag, val in _RE_META_LI.findall(html):
            lab = self._clean(lab).rstrip("：:")
            vals = [self._clean(a) for a in re.findall(r'<a[^>]*>([^<]*)</a>', val)]
            vals = [v for v in vals if v]
            if not vals:
                vals = [self._clean(val)]
            meta[lab] = ", ".join(v for v in vals if v)

        director = meta.get("導演", "") or meta.get("导演", "")
        actor = meta.get("主演", "")
        area = meta.get("國家/地區", "") or meta.get("国家/地区", "")
        lang = meta.get("語言/字幕", "") or meta.get("语言/字幕", "")
        vclass = meta.get("類別", "") or meta.get("类别", "")
        year = meta.get("年代", "") or meta.get("年份", "")
        remarks_note = meta.get("狀態", "") or meta.get("状态", "")
        update_at = meta.get("更新時間", "") or meta.get("更新时间", "")

        # 简介: details-content-all 全文 → meta description; 前缀强制注入
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            # 剥「片名線上看:類型,」前导前缀
            content = re.sub(r"^.*?線上看\s*[:：]\s*[^,，]*,?\s*", "", content).strip()
            content = re.sub(r"^.*?线上看\s*[:：]\s*[^,，]*,?\s*", "", content).strip()
            content = re.sub(r"^剧情\s*[:：]\s*", "", content).strip()
            content = re.sub(r"^[，,、：:；;\s]+", "", content).strip()
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # 副标题: 更新时间(TVBox 无独立键, 挂 subtitle)
        subtitle = ""
        if update_at:
            subtitle = "更新：" + update_at

        # ===== 线路与选集(tab DOM 顺序 ↔ ul#con_playlist_<sid>; dropdown 重复 ul 不覆盖) =====
        tabs = _RE_TAB.findall(html)
        panels = {}
        for sid, body in _RE_PLAYLIST.findall(html):
            panels.setdefault(sid, body)
        play_from, play_url = [], []

        def _ep_name(body):
            m = _RE_EP_NAME.search(body)
            if m:
                name = self._clean(m.group(1))
            else:
                m = _RE_EP_TITLE.search(body)
                name = self._clean(m.group(1)) if m else self._clean(body)
            return re.split(r"[·•]", name)[0].strip()

        for sid, tab_name in tabs:
            body = panels.get(sid, "")
            if not body:
                continue
            eps = _RE_EPISODE.findall(body)
            if not eps:
                continue

            def _ep_no(ep):
                em = _RE_EP_NO.search(ep[0])
                return int(em.group(1)) if em else 0

            eps = sorted(eps, key=_ep_no)
            seen_ep, uniq = set(), []
            for h, nb in eps:
                h = h.split("#")[0]
                if h in seen_ep:
                    continue
                seen_ep.add(h)
                uniq.append((h, nb))

            line_name = self._clean(tab_name) or ("线路%d" % (len(play_from) + 1))
            play_from.append(line_name)
            play_url.append("#".join(
                "%s$%s" % (_ep_name(nb) or ("第%d集" % (k + 1)), self._fix_url(h))
                for k, (h, nb) in enumerate(uniq)))

        if not play_from:
            return {"list": []}

        remarks = remarks_note or ("%d条线路" % len(play_from))

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
            "vod_lang": lang,
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
        try:
            return self._play(flag, id, vipFlags)
        except Exception as e:
            self.log("playerContent FAIL: %s" % e)
            return {"parse": 1, "playUrl": "", "url": id,
                    "header": {"User-Agent": UA}}

    def _play(self, flag, id, vipFlags):
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
            self.log("master 解析失败: %s" % e)
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

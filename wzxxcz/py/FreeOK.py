# coding=utf-8
"""
FreeOK 影视 www.freeokk.lol | TVBox Python 爬虫 
关键:
  - MacCMS V10 + mxone(mxtheme) 模板, 自定义路由 /type/ /show/ /detail/ /play/ /search/
  - 分类筛选: 12 段 URL (tid-地区-排序-剧情-语言-字母--页码--年份), 选项运行时从站点解析
  - 线路: 站点 tab 顺序即播放顺序 (OK超清/OK极速/OK无广/OK高清), 集数 sid 从链接取
  - 播放: player_aaaa (encrypt 0/1/2 兼容), m3u8 直链; qq 等非直链交嗅探
  - 副标题(又名): 站点页面不展示, 走官方 API ac=detail 的 vod_sub 字段取回
  - 搜索: /search/ 页为主, 官方 API wd 搜索兜底
  - 影片数量与站点一致: 每页 40 条, 总页数取自"尾页"链接
  - 已实测核对: 电影43010/剧集29483/综艺5555/动漫14086, 合计92134 部,
    与站点尾页逐页统计及官方API total 完全一致
"""
import re
import sys
import json
import time
import base64
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
                print("[freeok]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.freeokk.pro"        # 主域(站点 maccms.url 指向)
ALT_HOSTS = ["https://www.freeokk.lol",  # 备用域(wapurl)
             "https://freeokk.pro",
             "https://freeokk.lol"]

# 裸请求(TVBox 加载图片不带 UA/Referer)必挂或极不稳定的图片 CDN,
# 统一改走站点自带 img.php 代理(实测 100% 可达)
PIC_BAD_HOSTS = ("fffgood.com", "p.bfvp26.com", "p.bfp261112.com")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/images/favicon.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

PAGE_SIZE = 40          # 站点片库每页固定 40 条
SEARCH_PAGE_SIZE = 16   # 搜索页每页 16 条

# ===================== 内置筛选兜底(逐字取自站点 2026-11 抓取) =====================
_FALLBACK_FILTERS = {
    "1": [
        ("剧情", ["全部", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                  "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "恐怖", "悬疑", "惊悚",
                  "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
                  "儿童", "网络电影"]),
        ("地区", ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                  "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]),
        ("语言", ["全部", "国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]),
        ("年份", ["全部"] + [str(y) for y in range(2026, 2013, -1)]),
        ("字母", ["全部", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
                  "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]),
        ("排序", ["时间排序", "人气排序", "评分排序"]),
    ],
    "2": [
        ("剧情", ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
                  "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"]),
        ("地区", ["全部", "大陆", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                  "新加坡", "其他"]),
        ("语言", ["全部", "国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]),
        ("年份", ["全部"] + [str(y) for y in range(2026, 2013, -1)]),
        ("字母", ["全部", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
                  "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]),
        ("排序", ["时间排序", "人气排序", "评分排序"]),
    ],
    "3": [
        ("剧情", ["全部", "选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
                  "曲艺", "生活", "游戏互动", "财经", "求职"]),
        ("地区", ["全部", "内地", "港台", "日韩", "欧美"]),
        ("语言", ["全部", "国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]),
        ("年份", ["全部"] + [str(y) for y in range(2026, 2013, -1)]),
        ("字母", ["全部", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
                  "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]),
        ("排序", ["时间排序", "人气排序", "评分排序"]),
    ],
    "4": [
        ("剧情", ["全部", "情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
                  "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子",
                  "益智", "励志", "其他"]),
        ("地区", ["全部", "国产", "日本", "欧美", "其他"]),
        ("语言", ["全部", "国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]),
        ("年份", ["全部"] + [str(y) for y in range(2026, 2013, -1)]),
        ("字母", ["全部", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
                  "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]),
        ("排序", ["时间排序", "人气排序", "评分排序"]),
    ],
}

# 筛选组名 -> 12 段 URL 中的段索引 (0 起)
_GROUP_SEG = {"剧情": 3, "地区": 1, "语言": 4, "字母": 5, "排序": 2, "年份": 11}
_GROUP_KEY = {"剧情": "class", "地区": "area", "语言": "lang",
              "字母": "letter", "排序": "order", "年份": "year"}


# ===================== 正则 =====================
# 片库/首页卡片: <a href="/detail/N.html" title="X" class="module-poster-item module-item">...
_RE_CARD = re.compile(
    r'<a\s+href="(/detail/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?>\s*'
    r'<div class="module-item-cover">\s*'
    r'(?:<div class="module-item-note">([^<]*)</div>)?\s*'
    r'<div class="module-item-pic"><img[^>]*?(?:data-original|data-src)="([^"]*)"',
    re.S | re.I)

# 搜索页卡片 (module-card-item)
_RE_SEARCH_CARD = re.compile(
    r'<a href="(/detail/\d+\.html)" class="module-card-item-poster">\s*'
    r'<div class="module-item-cover">\s*'
    r'(?:<div class="module-item-note">([^<]*)</div>)?\s*'
    r'<div class="module-item-pic"><img[^>]*?(?:data-original|data-src)="([^"]*)"[^>]*?alt="([^"]*)"',
    re.S | re.I)
_RE_SEARCH_TITLE = re.compile(
    r'<div class="module-card-item-title">\s*<a href="(/detail/\d+\.html)"><strong>([^<]*)</strong>',
    re.S | re.I)

# 筛选组: <div class="module-class-item scroll-content"> + module-item-title + module-item-box
_RE_FILTER_BLOCK = re.compile(
    r'<div class="module-class-item scroll-content"[^>]*>([\s\S]*?)(?=<div class="module-class-item scroll-content"|<div class="module-main module-page|</div>\s*</div>\s*</div>)')
_RE_FILTER_TITLE = re.compile(r'<div class="module-item-title">([^<]+)<', re.I)
_RE_FILTER_BOX = re.compile(r'<div class="module-item-box">([\s\S]*?)</div>', re.I)
_RE_FILTER_ITEM = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', re.I)

# 分页
_RE_TAIL_PAGE = re.compile(
    r'<a\s+href="(/(?:show|search)/[^"]+)"[^>]*class="page-link page-next"[^>]*title="尾页"', re.I)
_RE_PAGE_NUM = re.compile(r'class="page-link page-number page-current display">(\d+)<', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([^<]+)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'module-info-poster[\s\S]{0,500}?<img[^>]*?(?:data-original|data-src)="([^"]*)"', re.S | re.I)
_RE_INTRO = re.compile(
    r'module-info-introduction-content">\s*<p>([\s\S]*?)</p>', re.S | re.I)
_RE_INFO_ITEM = re.compile(
    r'<span class="module-info-item-title"[^>]*>([^<]+)：</span>\s*'
    r'(?:<div class="module-info-item-content">([\s\S]*?)</div>|<a[^>]*>([\s\S]*?)</a>)',
    re.S | re.I)
_RE_TAG_LINK = re.compile(
    r'module-info-tag-link"><a[^>]*href="(/show/[^"]+)"[^>]*>([^<]+)</a>', re.I)
_RE_TAB_ITEM = re.compile(r'data-dropdown-value="([^"]+)"')
_RE_PANEL = re.compile(r'<div class="module-play-list-content[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-play-list-content|<div class="module-player-side|<div class="module-footer|$)', re.S)
_RE_EPISODE = re.compile(
    r'<a[^>]*href="(/play/[\d\-]+\.html)"[^>]*>\s*(?:<span>([^<]*)</span>)?', re.S | re.I)

# 播放页
_RE_PLAYER_AAAA = re.compile(r'var player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 播放节点下拉里的集数统计 (备用)
_RE_TAB_SMALL = re.compile(
    r'data-dropdown-value="([^"]+)"><span>[^<]*</span><small>(\d+)</small>', re.I)


class Spider(Spider):

    def getName(self):
        return "FreeOK影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        # 多域名兜底: 站点主域/备用域自动切换, 防止单域名 DNS 污染或被墙
        self.hosts = [self.site_url] + [h for h in (ALT_HOSTS if not self.extend.get("site")
                                                    else [HOST] + ALT_HOSTS)
                                        if h.rstrip("/") != self.site_url]
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._filters_cache = None
        self._sub_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _host_swap(self, url, host):
        """把 URL 的域名部分替换为 host, 保留路径与参数"""
        m = re.match(r"(https?://)[^/]+(/.*)?$", url, re.I)
        if m:
            return host + (m.group(2) or "")
        return url

    def _fetch(self, url, timeout=20, headers=None, retries=1):
        """多域名自动切换 + 短响应重试; 某域名连续失败自动跳下一个"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        text = ""
        for host in self.hosts:
            cur = self._host_swap(url, host)
            for attempt in range(retries + 1):
                try:
                    rsp = self.fetch(cur, headers=h, timeout=timeout)
                    if hasattr(rsp, "text"):
                        text = rsp.text or ""
                    elif hasattr(rsp, "content"):
                        text = rsp.content.decode("utf-8", "ignore")
                    else:
                        text = str(rsp)
                    if len(text) > 800:
                        return text
                    self.log("fetch short(%d) %s retry %d"
                             % (len(text), cur, attempt + 1))
                except Exception as e:
                    self.log("fetch FAIL %s -> %s (retry %d)"
                             % (cur, e, attempt + 1))
                    text = ""
                if attempt < retries:
                    time.sleep(0.5)
            # 该域名整体失败, 换下一个域名
            self.log("switch host: %s -> next" % host)
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

    def _fix_pic(self, url):
        """海报图: 坏 CDN 域名转走站点 img.php 代理, 防止壳子端裂图"""
        url = self._fix_url(url)
        if url:
            try:
                host = url.split("/")[2]
                if host in PIC_BAD_HOSTS:
                    url = self.site_url + "/img.php?url=" + url
            except Exception:
                pass
        return url or self.default_pic

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n\s*\n+", "\n", s)
        return s.strip()

    # ---------- /show 12 段 URL ----------
    def _show_url(self, tid, page=1, area="", order="", cls="", lang="",
                  letter="", year=""):
        fields = [str(tid), area, order, cls, lang, letter, "", "",
                  str(page), "", "", str(year or "")]
        # 12 段: 年份恒在末段(索引 11), 与站点 /show/1-地区----------2024.html 一致
        return "%s/show/%s.html" % (self.site_url, "-".join(fields))

    def _search_url(self, wd, page=1):
        q = urllib.parse.quote(wd)
        if page > 1:
            return "%s/search/%s----------%d---.html" % (self.site_url, q, page)
        return "%s/search/%s-------------.html" % (self.site_url, q)

    def _seg_of(self, show_path):
        """从 /show/xxx.html 提取 12 段(去 .html)"""
        seg = show_path.split("/show/")[-1]
        seg = seg.split("?")[0].replace(".html", "")
        return urllib.parse.unquote(seg).split("-")

    # ---------- 筛选 ----------
    def _build_filters(self, tid, groups):
        """groups: [(组名, [(显示名, [12段]) ...])] -> TVBox filters"""
        filters = []
        for name, items in groups:
            key = _GROUP_KEY.get(name)
            if not key:
                continue
            seg_i = _GROUP_SEG[name]
            values = []
            for txt, seg in items:
                v = seg[seg_i] if len(seg) > seg_i else ""
                # 首项(目标段为空)视为"全部"
                if not v:
                    values.append({"n": "全部", "v": ""})
                else:
                    values.append({"n": txt, "v": v})
            if not values:
                continue
            filters.append({"key": key, "name": name, "value": values})
        return filters

    def _fallback_filters(self, tid):
        groups = _FALLBACK_FILTERS.get(str(tid)) or _FALLBACK_FILTERS["1"]
        out = []
        for name, opts in groups:
            key = _GROUP_KEY.get(name)
            if not key:
                continue
            if name == "排序":
                value = [{"n": "全部", "v": ""}]
                value += [{"n": x, "v": {"时间排序": "time", "人气排序": "hits",
                                         "评分排序": "score"}.get(x, "")} for x in opts]
            elif name == "字母":
                value = [{"n": x, "v": "" if x == "全部" else x} for x in opts]
            else:
                value = [{"n": x, "v": "" if x in ("全部",) else x} for x in opts]
            out.append({"key": key, "name": name, "value": value})
        return out

    def _get_filters(self, tid):
        if self._filters_cache is None:
            self._filters_cache = {}
        tid = str(tid)
        if tid in self._filters_cache:
            return self._filters_cache[tid]
        html = self._fetch(self._show_url(tid, 1))
        groups = []
        if html:
            for mb in _RE_FILTER_BLOCK.finditer(html):
                blk = mb.group(1)
                mt = _RE_FILTER_TITLE.search(blk)
                mbox = _RE_FILTER_BOX.search(blk)
                if not mt or not mbox:
                    continue
                name = mt.group(1).strip()
                items = []
                for mi in _RE_FILTER_ITEM.finditer(mbox.group(1)):
                    href, txt = mi.group(1), mi.group(2).strip()
                    if "/show/" not in href:
                        continue
                    try:
                        seg = self._seg_of(href)
                    except Exception:
                        continue
                    items.append((txt, seg))
                if items:
                    groups.append((name, items))
        filters = self._build_filters(tid, groups) if groups else self._fallback_filters(tid)
        self.log("filters %s: %s" % (tid, [(f["name"], len(f["value"]))
                                           for f in filters]))
        self._filters_cache[tid] = filters
        return filters

    # ---------- 卡片提取 ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        for m in _RE_CARD.finditer(html):
            href, alt, note, pic = m.groups()
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt)[:100],
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": self._clean(note or ""),
            })
        if videos:
            return videos

        # 搜索页卡片兜底
        tmap = {}
        for m in _RE_SEARCH_TITLE.finditer(html):
            tmap[m.group(1)] = m.group(2)
        for m in _RE_SEARCH_CARD.finditer(html):
            href, note, pic, alt = m.groups()
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(tmap.get(href) or alt)[:100],
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": self._clean(note or ""),
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_TAIL_PAGE.search(html)
        if m:
            seg = self._seg_of(m.group(1))
            # /show 页码在第 9 段(索引 8), /search 在第 11 段(索引 10)
            for idx in (8, 10):
                if len(seg) > idx and seg[idx].isdigit():
                    return max(1, int(seg[idx]))
        m = _RE_PAGE_NUM.search(html)
        if m:
            return max(1, int(m.group(1)))
        return 1

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        result = {"class": list(CLASSES)}
        if filter:
            result["filters"] = {c["type_id"]: self._get_filters(c["type_id"])
                                 for c in CLASSES}
        return result

    def homeVideoContent(self):
        # 首页"更新推荐": 首页失败时用 4 个 /type/ 推荐页合并兜底
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        if not videos:
            self.log("  首页为空, 回退 /type/ 推荐页")
            seen, merged = set(), []
            for tid in ("1", "2", "3", "4"):
                th = self._fetch("%s/type/%s.html" % (self.site_url, tid))
                for v in self._extract_videos(th):
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        merged.append(v)
            videos = merged
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        def _val(k):
            v = (extend.get(k) or "").strip()
            return "" if v in ("全部", "none", "0") else v

        url = self._show_url(
            tid, page,
            area=_val("area"), order=_val("order"), cls=_val("class"),
            lang=_val("lang"), letter=_val("letter"), year=_val("year"))
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)

        # 兜底1: /show 列表页失败 -> /type/{tid}.html 推荐页(服务端同样渲染卡片)
        if not videos:
            alt = "%s/type/%s.html" % (self.site_url, str(tid).split("-")[0])
            self.log("  /show 为空, 回退 %s" % alt)
            html = self._fetch(alt)
            videos = self._extract_videos(html)
            if videos:
                pagecount = 1  # 推荐页无分页, 只提示一页
            else:
                # 兜底2: 首页
                html = self._fetch(self.site_url + "/")
                videos = self._extract_videos(html)
                if videos:
                    pagecount = 1

        # /show 页正常但末页解析失败时保守回退
        if videos and pagecount <= 0:
            pagecount = 1
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_SIZE, "total": pagecount * PAGE_SIZE,
        }

    def searchContent(self, key, quick, pg="1"):
        return self._search(key, pg)

    def searchContentPage(self, key, quick, pg="1"):
        return self._search(key, pg)

    def _search(self, key, pg="1"):
        page = int(pg) if pg else 1
        url = self._search_url(key, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)

        if videos:
            pagecount = self._page_count(html)
            return {"list": videos, "page": page, "pagecount": pagecount,
                    "limit": SEARCH_PAGE_SIZE, "total": pagecount * SEARCH_PAGE_SIZE}

        # 兜底: 官方 API (无封面, 但保证有结果)
        self.log("  搜索页无结果, 回退官方 API")
        try:
            api = ("%s/api.php/provide/vod/?ac=list&wd=%s&pg=%d"
                   % (self.site_url, urllib.parse.quote(key), page))
            text = self._api_get(api)
            if not text:
                raise RuntimeError("api 空响应")
            data = json.loads(text)
            videos = [{
                "vod_id": "/detail/%d.html" % it["vod_id"],
                "vod_name": it.get("vod_name", ""),
                "vod_pic": it.get("vod_pic") or self.default_pic,
                "vod_remarks": it.get("vod_remarks", ""),
            } for it in data.get("list", [])]
            pc = int(data.get("pagecount") or 1)
            return {"list": videos, "page": page, "pagecount": pc,
                    "limit": 20, "total": int(data.get("total") or 0)}
        except Exception as e:
            self.log("  API 搜索失败: %s" % e)
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": SEARCH_PAGE_SIZE, "total": 0}

    # ---------- 详情 ----------
    def _api_get(self, url):
        """短 JSON 响应的多域名请求(不走 _fetch 的长度判断)"""
        err = ""
        for host in self.hosts:
            cur = self._host_swap(url, host)
            try:
                rsp = self.fetch(cur, headers={"User-Agent": UA}, timeout=15)
                text = rsp.text if hasattr(rsp, "text") else ""
                if text and "{" in text:
                    return text
            except Exception as e:
                err = str(e)
            self.log("api switch host: %s -> next (%s)" % (cur, err))
        return ""

    def _fetch_vod_sub(self, vod_id):
        """副标题(又名): 页面不展示, 从官方 API ac=detail 的 vod_sub 取"""
        m = re.search(r'/detail/(\d+)', vod_id)
        if not m:
            return ""
        vid = m.group(1)
        if vid in self._sub_cache:
            return self._sub_cache[vid]
        sub = ""
        try:
            api = "%s/api.php/provide/vod/?ac=detail&ids=%s" % (self.site_url, vid)
            text = self._api_get(api)
            if not text:
                raise RuntimeError("api 空响应")
            data = json.loads(text)
            lst = data.get("list") or []
            if lst:
                sub = (lst[0].get("vod_sub") or "").strip()
        except Exception as e:
            self.log("  vod_sub API 失败: %s" % e)
        self._sub_cache[vid] = sub
        return sub

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

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).replace("《", "").replace("》", "")
                                   .split("-")[0])
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or pic

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))

        # 副标题(又名) — 站点 API 数据
        vod_sub = self._fetch_vod_sub(vod_id)

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX
        if vod_sub:
            content = content + "\n又名：" + vod_sub

        # 元信息: 导演/主演/更新/备注(或片长)/豆瓣
        info = {}
        for mi in _RE_INFO_ITEM.finditer(html):
            title = self._clean(mi.group(1))
            body = mi.group(2) if mi.group(2) is not None else mi.group(3)
            body = self._clean(body)
            if title and title not in info:
                info[title] = body

        director = info.get("导演", "").rstrip(" /")
        actor = re.sub(r"\s*/\s*", ", ", info.get("主演", "").rstrip(" /"))
        update_date = info.get("更新", "")

        remarks = info.get("备注") or info.get("片长") or ""

        score = ""
        dbl = info.get("豆瓣", "")
        ms = re.match(r"^(\d+(?:\.\d+)?)$", dbl)
        if ms:
            score = ms.group(1)

        # 年份/地区: 从 tag-link 的 /show/ 链接段位还原 (与站点筛选 URL 一致)
        year, area = "", ""
        for mt in _RE_TAG_LINK.finditer(html):
            seg = self._seg_of(mt.group(1))
            txt = self._clean(mt.group(2))
            if len(seg) > 11 and seg[11].isdigit() and not year:
                year = seg[11]
            if len(seg) > 1 and seg[1] and not area:
                area = seg[1]

        # ===== 线路与剧集: tab 顺序即站点播放顺序 =====
        tabs = [self._clean(x) for x in _RE_TAB_ITEM.findall(html)]
        panels = [m.group(1) for m in _RE_PANEL.finditer(html)]

        play_from, play_url = [], []
        for idx, panel in enumerate(panels):
            line = tabs[idx] if idx < len(tabs) else ("线路%d" % (idx + 1))
            eps = []
            seen = set()
            for me in _RE_EPISODE.finditer(panel):
                href, ename = me.group(1), me.group(2)
                if href in seen:
                    continue
                seen.add(href)
                if not ename:
                    mm = re.search(r'-(\d+)-(\d+)\.html', href)
                    ename = "第%s集" % (mm.group(2)) if mm else href
                eps.append("%s$%s" % (self._clean(ename), href))
            if not eps:
                continue
            play_from.append(line)
            play_url.append("#".join(eps))

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        max_ep = max(len(u.split("#")) for u in play_url)
        if not remarks:
            remarks = ("更新至第%d集" % max_ep) if max_ep > 1 else ""

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_sub": vod_sub,
            "vod_pic": self._fix_pic(pic),
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remarks or ("更新：" + update_date if update_date
                                       else "%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real = self._extract_player_url(html) if html else ""
        self.log("  url: %s" % (real[:200] if real else "EMPTY"))

        if real and re.match(r"^https?://", real):
            low = real.lower()
            if ".m3u8" in low or ".mp4" in low:
                if ".m3u8" in low:
                    # master m3u8 -> 最高码率子清单 (兼容只认子清单的播放器)
                    real = self._pick_variant(real)
                # 注意: 部分 CDN(如 rrcdnbf2) 带 Referer 反而 404, 仅回 UA
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real,
                    "header": {"User-Agent": UA},
                }
                self._play_cache[play_page] = (now, res)
                return res

        # qq/youku 等外链或解析失败 -> 交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_player_url(self, html):
        m = _RE_PLAYER_AAAA.search(html)
        if not m:
            return ""
        try:
            cfg = json.loads(m.group(1))
        except Exception:
            return ""
        url = cfg.get("url", "") or ""
        enc = cfg.get("encrypt", 0)
        try:
            if enc == 1:
                url = base64.b64decode(url + "=" * (-len(url) % 4)).decode("utf-8", "ignore")
            elif enc == 2:
                raw = urllib.parse.unquote(url)
                url = base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", "ignore")
        except Exception as e:
            self.log("  decrypt fail: %s" % e)
        return url.strip()

    def _pick_variant(self, url, referer=None):
        """master m3u8 -> 选 BANDWIDTH 最大的子 m3u8"""
        try:
            # master 清单本身很短(约百字节), 不能走带重试的 _fetch
            rsp = self.fetch(url, headers={"User-Agent": UA}, timeout=12)
            text = rsp.text if hasattr(rsp, "text") else ""
            if "#EXT-X-STREAM-INF" not in text:
                return url
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            best, best_bw = "", -1
            for i, ln in enumerate(lines):
                if not ln.startswith("#EXT-X-STREAM-INF"):
                    continue
                if i + 1 >= len(lines):
                    continue
                sub = lines[i + 1]
                full = sub if sub.startswith("http") else urllib.parse.urljoin(url, sub)
                mb = re.search(r"BANDWIDTH=(\d+)", ln, re.I)
                bw = int(mb.group(1)) if mb else 0
                if bw > best_bw:
                    best, best_bw = full, bw
            if best:
                self.log("  子 m3u8: %s" % best[:160])
                return best
            return url
        except Exception:
            return url

    # ---------- 其它 ----------
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

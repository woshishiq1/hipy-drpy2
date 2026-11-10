# coding=utf-8
"""
爱剧网 www.zachiska.com | TVBox Python 爬虫 
关键:
  - 模板 ewave (/template/laoniu_jo3/)，后端 MacCMS
  - 分类只保留站方导航的 6 个顶级: 电视剧/电影/动漫/AI漫剧/短剧/综艺
  - 筛选五行与站方 /vs/{tid}.html 筛选面板完全一致:
    按分类(子分类，选中后切换子 tid) / 按剧情 / 按地区 / 按年份 / 按排序
    注: 站方「按排序」三个链接 href 相同（排序未接线），与站点行为保持一致
  - homeVideoContent/homeContent 返回扁平 vod 列表（TVBox 标准格式，
    分组 {name, videos} 格式会导致首页「更新推荐」海报不显示）
  - 详情简介取站方原文（顶部简介段落 → 底部剧情简介 → meta description 多层兜底），
    类型/更新时间等字段全量保留
  - 结构: 首页分区 → /vs/{tid}/{class}/{area}/{lang}/{year}/{order}/{page}.html
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
                print("[aiju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zachiska.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/laoniu_jo3/static/img/1.svg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_SIZE = 24      # 分类/筛选页每页 24 条
SEARCH_SIZE = 10    # 搜索页每页 10 条
CACHE_TTL = 180     # 页面缓存秒数
FILTER_TTL = 1800   # 兼容保留：筛选已静态化

# 分类：与站方顶部导航完全一致，只要这 6 个
CLASSES = [
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "5",  "type_name": "动漫"},
    {"type_id": "59", "type_name": "AI漫剧"},
    {"type_id": "29", "type_name": "短剧"},
    {"type_id": "37", "type_name": "综艺"},
]

# 按分类（站方 channel-slide 子分类，选中后切换到子分类 tid）
_CHANNEL_MAP = {
    "2":  [("国产剧", "30"), ("韩剧", "15"), ("美剧", "14"), ("港剧", "13"),
           ("日剧", "16"), ("台剧", "27"), ("泰剧", "28")],
    "1":  [("动作片", "6"), ("爱情片", "7"), ("动画片", "58"), ("科幻片", "8"),
           ("恐怖片", "9"), ("喜剧片", "11"), ("剧情片", "12"), ("纪实片", "24")],
    "5":  [("国产动漫", "17"), ("日本动漫", "47"), ("欧美动漫", "49"),
           ("香港动漫", "18"), ("韩国动漫", "48"), ("台湾动漫", "46")],
    "29": [("都市短剧", "55")],
    "37": [("大陆综艺", "38"), ("欧美综艺", "43"), ("香港综艺", "39"),
           ("日本综艺", "41")],
    # AI漫剧(59) 站方无子分类，不提供「按分类」行
}

# 筛选静态表：与站方 /vs/{tid}.html 各筛选块逐项一致（已去重）
_FILTERS_MAP = {
    "2": {
        "class": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
                  "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "area":  ["大陆", "韩国", "香港", "台湾", "日本", "美国", "泰国",
                  "英国", "新加坡", "其他"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                  "2012", "2011", "2010", "2009", "2008", "2006", "2005", "2004"],
    },
    "1": {
        "class": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                  "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
                  "经典", "青春", "文艺", "微电影", "古装", "历史", "运动",
                  "农村", "儿童", "网络电影"],
        "area":  ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                  "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                  "2012", "2011", "2010"],
    },
    "5": {
        "class": ["冒险", "热血", "科幻", "玄幻", "逆袭", "修仙", "爽文", "恋爱", "治愈"],
        "area":  ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国",
                  "英国", "新加坡", "其他"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                  "2012", "2011", "2010"],
    },
    "59": {
        "class": ["剧情", "奇幻", "古装", "动作", "逆袭", "穿越", "爱情", "喜剧",
                  "犯罪", "惊悚"],
        "area":  ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                  "德国", "泰国", "印度", "俄罗斯", "西班牙", "加拿大", "新加坡"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017"],
    },
    "29": {
        "class": ["古装", "现代", "科幻", "悬疑", "爱情"],
        "area":  ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国",
                  "英国", "新加坡", "其他"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                  "2012", "2011", "2010"],
    },
    "37": {
        "class": ["真人秀", "脱口秀", "音综", "文化益智"],
        "area":  ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国",
                  "英国", "新加坡", "其他"],
        "year":  ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                  "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                  "2012", "2011", "2010"],
    },
}

_FILTER_NAMES = {"class": "剧情", "area": "地区", "year": "年份"}

FILTERS = {}
for _tid, _m in _FILTERS_MAP.items():
    _fs = []
    if _tid in _CHANNEL_MAP:
        _fs.append({
            "key": "channel",
            "name": "分类",
            "value": [{"n": "全部", "v": ""}] +
                     [{"n": n, "v": v} for n, v in _CHANNEL_MAP[_tid]],
        })
    for _k in ("class", "area", "year"):
        _fs.append({
            "key": _k,
            "name": _FILTER_NAMES[_k],
            "value": [{"n": "全部", "v": ""}] +
                     [{"n": x, "v": x} for x in _m[_k]],
        })
    # 站方「按排序」最新/最热/评分 三个链接 href 相同（未接线），
    # 这里与站点保持一致：可选中，但结果同「全部」
    _fs.append({
        "key": "order",
        "name": "排序",
        "value": [{"n": "最新", "v": ""}, {"n": "最热", "v": ""},
                  {"n": "评分", "v": ""}],
    })
    FILTERS[_tid] = _fs


# ===================== 正则 =====================
_RE_INFO = re.compile(r'href="(/info/(\d+)\.html)"')
_RE_THUMB_TAG = re.compile(
    r'<(?:a|div)[^>]*class="[^"]*ewave-vodlist__thumb[^"]*"[^>]*>', re.I)
_RE_HREF = re.compile(r'href="([^"]+)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC = re.compile(r'data-original="([^"]*)"', re.I)
_RE_PIC_TEXT = re.compile(r'class="pic-text[^"]*"[^>]*>\s*([^<]*?)\s*<', re.I)
_RE_H4_A = re.compile(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h4>', re.I)
_RE_H3_A = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_LI = re.compile(r'<li(?:\s[^>]*)?>([\s\S]*?)</li>')

# 分页：尾页（分类 /category/{tid}-{n}.html 或 搜索 /search/page/{n}/wd/{kw}.html）
_RE_TAIL_CAT = re.compile(
    r'<a[^>]*href="[^"]*/category/\d+-(\d+)\.html"[^>]*>\s*尾页\s*</a>')
_RE_TAIL_SEARCH = re.compile(
    r'<a[^>]*href="[^"]*/search/page/(\d+)/wd/[^"]*"[^>]*>\s*尾页\s*</a>')
_RE_TAIL_ANY = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>\s*尾页\s*</a>')

# 详情
_RE_DATA_UL = re.compile(r'<ul class="data[^"]*">([\s\S]*?)</ul>', re.I)
_RE_DATA_LI = re.compile(
    r'<li(?:\s[^>]*)?>\s*<span class="text-muted">\s*([^<]+?)\s*</span>'
    r'([\s\S]*?)</li>', re.I)
_RE_PLAYLIST_POS = re.compile(r'<div id="playlist(\d+)"')
_RE_TAB_NAME = re.compile(r'href="#playlist(\d+)"[^>]*>\s*([^<]*?)\s*</a>')
_RE_LIVE = re.compile(r'href="(/live/[^"]+)"[^>]*>\s*([^<]*?)\s*</a>')
_RE_SCORE = re.compile(r'<span class="score">\s*([\d.]+)\s*</span>')
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_THUMB_DIV = re.compile(r'<div class="ewave-content__thumb">([\s\S]*?)</div>')
_RE_OG_TITLE = re.compile(r'<meta property="og:title" content="([^"]+)"')
_RE_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_RE_TITLE_TAG = re.compile(r'<title>([^<]+)</title>')
_RE_YEAR_FALLBACK = re.compile(
    r'<span class="text-muted">\s*年份：\s*</span>\s*(\d{4})')

# 简介（多层兜底：顶部 desc 段落 → 底部剧情简介区块 → meta description）
_RE_DESC = re.compile(r'<p class="desc[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_DESC_BLOCK = re.compile(
    r'id="desc"[\s\S]*?<p class="col-pd">([\s\S]*?)</p>', re.I)
_RE_META_DESC = re.compile(
    r'<meta\s+name="description"\s+content="([^"]+)"', re.I)

# 播放
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>')
_RE_PLAYER2 = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;')


class Spider(Spider):

    def getName(self):
        return "爱剧网"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._cache = {}
        self._last_req = 0.0
        self._last_search = 0.0
        self.log("init: site=%s" % HOST)

    # -------- 基础请求 --------
    def _fetch(self, url, retry=1):
        try:
            now = time.time()
            hit = self._cache.get(url)
            if hit and now - hit[0] < CACHE_TTL:
                return hit[1]

            # 控制请求节奏，避免触发站点限流
            gap = now - self._last_req
            if gap < 0.2:
                time.sleep(0.2 - gap)
            self._last_req = time.time()

            text = ""
            for i in range(retry + 1):
                try:
                    r = self._sess.get(url, headers=self.headers,
                                       timeout=20, verify=False)
                    if r.status_code == 200 and r.text and len(r.text) > 500:
                        text = r.text
                        break
                except Exception as e:
                    self.log("fetch err %s -> %s" % (url, e))
                if i < retry:
                    time.sleep(0.8)

            if text:
                self._cache[url] = (time.time(), text)
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    @property
    def _sess(self):
        s = getattr(self, "_session", None)
        if s is None:
            import requests
            s = requests.Session()
            s.verify = False
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
            self._session = s
        return s

    def _search_fetch(self, url):
        """搜索专用：站点对同会话连续搜索会返回 500，故每次新建会话并限速"""
        try:
            now = time.time()
            hit = self._cache.get(url)
            if hit and now - hit[0] < CACHE_TTL:
                return hit[1]

            gap = now - self._last_search
            if gap < 1.2:
                time.sleep(1.2 - gap)

            text = ""
            for i in range(3):
                s = None
                try:
                    import requests
                    s = requests.Session()
                    s.verify = False
                    r = s.get(url, headers=self.headers, timeout=20)
                    self._last_search = time.time()
                    if (r.status_code == 200 and r.text
                            and len(r.text) > 5000
                            and "System Error" not in r.text):
                        text = r.text
                        break
                except Exception as e:
                    self.log("search err %s -> %s" % (url, e))
                    self._last_search = time.time()
                finally:
                    try:
                        if s is not None:
                            s.close()
                    except Exception:
                        pass
                time.sleep(1.5 * (i + 1))

            if text:
                self._cache[url] = (time.time(), text)
            return text
        except Exception as e:
            self.log("search FAIL %s -> %s" % (url, e))
            return ""

    # -------- 工具 --------
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return HOST + url
        return HOST + "/" + url

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r'<[^>]+>', '', s)
        s = (s.replace('&nbsp;', ' ').replace('&amp;', '&')
              .replace('&quot;', '"').replace('&#39;', "'")
              .replace('&lt;', '<').replace('&gt;', '>'))
        return re.sub(r'\s+', ' ', s).strip()

    def _q(self, s):
        return urllib.parse.quote(str(s or '').strip())

    def _split3(self, s):
        """取前 n 个逗号分隔项，用于主演/导演精简"""
        if not s:
            return []
        return [x.strip() for x in re.split(r'[,，/、]', s) if x.strip()]

    # -------- 列表解析 --------
    def _card_from_block(self, block):
        try:
            tag_m = _RE_THUMB_TAG.search(block)
            info_m = _RE_INFO.search(block)
            if not tag_m or not info_m:
                return None
            tag = tag_m.group(0)
            vid = info_m.group(2)

            # 标题：thumb 的 title → h4/h3 title 的 a → img alt
            name = ""
            t = _RE_TITLE.search(tag)
            if t:
                name = self._clean(t.group(1))
            if not name:
                for reg in (_RE_H4_A, _RE_H3_A):
                    m = reg.search(block)
                    if m:
                        name = self._clean(m.group(1))
                        if name:
                            break
            if not name:
                m = re.search(r'alt="([^"]+)"', tag)
                if m:
                    name = self._clean(m.group(1))
            if not name:
                return None

            # 封面
            pic = ""
            p = _RE_PIC.search(tag)
            if p:
                pic = self._fix_url(p.group(1))
            if not pic:
                m = re.search(r'(?:data-src|src)="([^"]+)"', tag)
                if m:
                    pic = self._fix_url(m.group(1))
            pic = pic or self.default_pic

            # 副标题（更新状态）
            remark = ""
            m = _RE_PIC_TEXT.search(block)
            if m:
                remark = self._clean(m.group(1))

            return {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            }
        except Exception as e:
            self.log("card parse err: %s" % e)
            return None

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos
        try:
            for m in _RE_LI.finditer(html):
                b = m.group(1)
                if "ewave-vodlist__thumb" not in b:
                    continue
                card = self._card_from_block(b)
                if not card or card["vod_id"] in seen:
                    continue
                seen.add(card["vod_id"])
                videos.append(card)
        except Exception as e:
            self.log("list parse err: %s" % e)
        self.log("  解析出 %d 条" % len(videos))
        return videos

    def _page_count(self, html, kind="cat"):
        try:
            if not html:
                return 1
            reg = _RE_TAIL_SEARCH if kind == "search" else _RE_TAIL_CAT
            m = reg.search(html)
            if m:
                return max(int(m.group(1)), 1)
            m = _RE_TAIL_ANY.search(html)
            if m:
                nums = re.findall(r'(\d+)', m.group(1))
                if nums:
                    return max(int(nums[-1]), 1)
        except Exception:
            pass
        return 1

    # -------- 首页 --------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        """首页推荐：返回扁平 vod 列表（TVBox 标准格式，海报才能正常显示）"""
        html = self._fetch(HOST + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = []
        seen = set()
        try:
            parts = html.split(
                '<div class="ewave-pannel ewave-pannel-bg clearfix">')
            for p in parts[1:]:
                for card in self._extract_videos(p):
                    if card["vod_id"] in seen:
                        continue
                    seen.add(card["vod_id"])
                    videos.append(card)
        except Exception as e:
            self.log("home parse err: %s" % e)
        self.log("  首页推荐共 %d 条" % len(videos))
        return {"list": videos}

    # -------- 分类 --------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid or "2")
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

        # 「按分类」选中子分类时切换到子 tid（如 国产剧 → /vs/30）
        tid = str(extend.get("channel") or tid or "2")

        cls = self._q(extend.get("class") or "all")
        area = self._q(extend.get("area") or "all")
        lang = self._q(extend.get("lang") or "all")
        year = self._q(extend.get("year") or "all")
        order = self._q(extend.get("order") or "all")

        url = "%s/vs/%s/%s/%s/%s/%s/%s/%s.html" % (
            HOST, tid, cls, area, lang, year, order, page)
        self.log("category: %s" % url)
        html = self._fetch(url)

        if not html:
            # 兜底：普通分类分页
            url2 = "%s/category/%s%s.html" % (
                HOST, tid, "" if page == 1 else "-%d" % page)
            self.log("  兜底: %s" % url2)
            html = self._fetch(url2)

        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_SIZE, "total": pagecount * PAGE_SIZE,
        }

    # -------- 搜索 --------
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search.html?wd=%s&page=%d" % (HOST, self._q(key), page)
        self.log("search: %s" % url)
        html = self._search_fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        pagecount = self._page_count(html, "search")
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": SEARCH_SIZE, "total": pagecount * SEARCH_SIZE,
        }

    # -------- 详情 --------
    def _detail_data(self, html):
        data = {}
        try:
            m = _RE_DATA_UL.search(html)
            if not m:
                return data
            for li in _RE_DATA_LI.findall(m.group(1)):
                k = self._clean(li[0]).rstrip("：:").strip()
                v = self._clean(li[1])
                if k and k not in data:
                    data[k] = v
        except Exception as e:
            self.log("detail data err: %s" % e)
        return data

    def _build_intro(self, name, year, area, kind, director, actor, remarks):
        kind = self._clean(kind).split()[0] if self._clean(kind) else ""
        area_s = "、".join(self._split3(area)[:3])
        dir_s = "、".join(self._split3(director)[:2])
        act_s = "、".join(self._split3(actor)[:3])

        if year and area_s:
            seg = "《%s》是%s年%s出品的%s" % (name, year, area_s, kind or "影视作品")
        elif year:
            seg = "《%s》是%s年的%s" % (name, year, kind or "影视作品")
        elif kind:
            seg = "《%s》是一部%s" % (name, kind)
        else:
            seg = "《%s》是一部影视作品" % name

        if dir_s:
            seg += "，由%s执导" % dir_s
        if act_s:
            seg += "，%s等主演" % act_s
        if remarks:
            seg += "，目前%s" % self._clean(remarks)
        seg += "。"
        return INTRO_PREFIX + seg

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]).split("$$$")[0].strip()
        vid = re.sub(r'[^\d]', '', vid) or vid
        url = "%s/info/%s.html" % (HOST, vid)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题（多层兜底）
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(
                    re.sub(r'<span class="score">[\s\S]*?</span>', '', m.group(1)))
        except Exception:
            pass
        if not name:
            try:
                m = _RE_OG_TITLE.search(html)
                if m:
                    name = self._clean(m.group(1))
            except Exception:
                pass
        if not name:
            try:
                m = _RE_TITLE_TAG.search(html)
                if m:
                    name = self._clean(m.group(1)).split("-")[0].split("_")[0].strip()
            except Exception:
                pass
        name = name or vid

        # 封面（多层兜底）
        pic = ""
        try:
            m = _RE_THUMB_DIV.search(html)
            if m:
                p = (_RE_PIC.search(m.group(1))
                     or re.search(r'(?:data-src|src)="([^"]+)"', m.group(1)))
                if p:
                    pic = self._fix_url(p.group(1))
        except Exception:
            pass
        if not pic:
            try:
                m = _RE_OG_IMAGE.search(html)
                if m:
                    pic = self._fix_url(m.group(1))
            except Exception:
                pass
        pic = pic or self.default_pic

        # 元信息
        data = self._detail_data(html)
        remarks = data.get("状态") or data.get("备注") or ""
        year = data.get("年份") or ""
        area = data.get("地区") or ""
        type_ = data.get("类型") or ""
        actor = data.get("主演") or ""
        director = data.get("导演") or ""
        if not year:
            try:
                m = _RE_YEAR_FALLBACK.search(html)
                if m:
                    year = m.group(1)
            except Exception:
                pass

        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        # ===== 简介：优先站方原文（顶部简介段落 → 底部剧情简介 → meta description） =====
        content = ""
        try:
            m = _RE_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if content:
            content = re.sub(r'^(简介|剧情简介)[:：]\s*', '', content)
        if not content:
            try:
                m = _RE_DESC_BLOCK.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass
        if not content:
            # 兜底：站方无简介时按元信息拼接
            content = self._build_intro(
                name, year, area, type_, director, actor, remarks)
        content = INTRO_PREFIX + "\n" + content

        # 更新时间：放到详情页备注栏（标题下方），不混入简介
        update_time = data.get("更新时间") or ""
        if update_time:
            remarks = ("%s（更新：%s）" % (remarks, update_time)) if remarks \
                else ("更新：" + update_time)

        # 类型：站方形如 "国产剧 重大革命历史剧,历史,战争,剧情,国产剧,..."，
        # 全量保留并去重（vod_class 为逗号分隔标签，type_name 为原始串）
        type_name = ""
        vod_class = ""
        try:
            t = self._clean(type_)
            if t:
                type_name = t
                segs = re.split(r'[\s,，、]+', t)
                seen_t = set()
                tags = []
                for s in segs:
                    if s and s not in seen_t:
                        seen_t.add(s)
                        tags.append(s)
                vod_class = ",".join(tags)
        except Exception:
            pass

        # ===== 线路：playlist{N} 与 /live/{id}-{N}-{ep}.html 一一对应 =====
        groups = {}
        tab_names = {}
        try:
            mt = re.search(r'<div class="playlist-slide">([\s\S]*?)</div>', html)
            if mt:
                for n, t in _RE_TAB_NAME.findall(mt.group(1)):
                    tab_names[int(n)] = self._clean(t)

            pos = [(int(m.group(1)), m.start()) for m in _RE_PLAYLIST_POS.finditer(html)]
            pos.sort(key=lambda x: x[1])
            for i, (n, st) in enumerate(pos):
                end = pos[i + 1][1] if i + 1 < len(pos) else len(html)
                eps = []
                seen = set()
                for href, epname in _RE_LIVE.findall(html[st:end]):
                    if href in seen:
                        continue
                    seen.add(href)
                    epname = self._clean(epname) or ("第%02d集" % (len(eps) + 1))
                    eps.append("%s$%s%s" % (epname, HOST, href))
                if eps:
                    groups[n] = eps
        except Exception as e:
            self.log("  线路解析失败: %s" % e)

        self.log("  线路: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            # 兜底：全页 /live/ 链接单线路
            try:
                eps = []
                for href, epname in _RE_LIVE.findall(html):
                    eps.append("%s$%s%s" % (
                        self._clean(epname) or "正片", HOST, href))
                if eps:
                    groups[1] = eps
                    tab_names.setdefault(1, "线路一")
            except Exception:
                pass

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        for n in sorted(groups.keys()):
            play_from.append(tab_names.get(n) or ("线路%d" % n))
            play_url.append("#".join(groups[n]))

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        if score:
            vod["vod_score"] = score
        if vod_class:
            vod["vod_class"] = vod_class
        return {"list": [vod]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        try:
            url = id if str(id).startswith("http") else HOST + str(id)
            header = {"User-Agent": UA, "Referer": HOST + "/"}

            self.log("player: %s" % url)
            html = self._fetch(url, retry=1)
            d = None
            if html:
                m = _RE_PLAYER.search(html) or _RE_PLAYER2.search(html)
                if m:
                    try:
                        d = json.loads(m.group(1))
                    except Exception:
                        try:
                            d = json.loads(m.group(1).replace("\\/", "/"))
                        except Exception:
                            d = None

            if not d:
                self.log("  未取到 player_aaaa, 交嗅探")
                return {"parse": 1, "playUrl": "", "url": url, "header": header}

            play = (d.get("url") or "").strip()
            try:
                enc = int(d.get("encrypt", 0))
            except Exception:
                enc = 0

            if play and enc == 0:
                if play.startswith("//"):
                    play = "https:" + play
                elif play.startswith("/"):
                    play = HOST + play
                self.log("  => 直链: %s" % play[:160])
                return {"parse": 0, "playUrl": "", "url": play, "header": header}

            # 站方加密线路：交给嗅探器解析播放页
            self.log("  加密线路(enc=%s), 交嗅探" % enc)
            return {"parse": 1, "playUrl": "", "url": url, "header": header}
        except Exception as e:
            self.log("player FAIL: %s" % e)
            return {"parse": 1, "playUrl": "", "url": str(id), "header": {}}

    # -------- 其它 --------
    def isVideoFormat(self, url):
        u = (url or "").lower()
        for x in (".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi", ".m4a", ".mp3"):
            if x in u:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        try:
            if getattr(self, "_session", None) is not None:
                self._session.close()
        except Exception:
            pass
        self._session = None
        self._cache = {}

    def close(self):
        self.destroy()

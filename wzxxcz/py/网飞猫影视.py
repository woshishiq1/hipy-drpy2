# coding=utf-8
"""
网飞猫影视 allurespabeauty.com | TVBox Python 爬虫
基于实测 页面源码逆向：
  - 分类/筛选：/all/{tid}.html 与 /search.php?searchtype=5&tid=...&page=N
  - 详情：/uty/{id}.html，剧集在两个 ul.stui-content__playlist，线路名在前置 <li>
  - 播放：/play/{id}-{line}-{ep}.html，m3u8 明文藏在 mip-iframe 的 url= 参数
  - 搜索限流 10 秒一次，命中提示页返回空列表
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
                print("[wangfeimao]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.allurespabeauty.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/pic/nopic.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类 =====================
CLASSES = [
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

_SUB_CLASS = {
    "2": [("13", "国产剧"), ("14", "香港剧"), ("15", "台湾剧"), ("16", "欧美剧"),
          ("25", "韩国剧"), ("26", "日本剧"), ("27", "泰国剧"), ("28", "海外剧"),
          ("29", "短剧")],
    "1": [("5", "动作片"), ("6", "喜剧片"), ("7", "爱情片"), ("8", "科幻片"),
          ("9", "恐怖片"), ("10", "剧情片"), ("11", "战争片"), ("12", "纪录片")],
    "3": [("30", "大陆综艺"), ("31", "港台综艺"), ("32", "日韩综艺"), ("33", "欧美综艺")],
    "4": [("34", "大陆动漫"), ("35", "日本动漫"), ("36", "欧美动漫"), ("37", "海外动漫"),
          ("38", "动画片")],
}

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "欧美", "v": "欧美"},
    {"n": "泰国", "v": "泰国"}, {"n": "其他", "v": "其他"},
]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
_SORTS = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hit"}, {"n": "推荐", "v": "commend"}]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = [{"n": "全部", "v": ""}] + [{"n": n, "v": t} for t, n in _SUB_CLASS.get(tid, [])]
    FILTERS[tid] = [
        {"key": "tid", "name": "分类", "value": subs},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "order", "name": "排序", "value": _SORTS},
    ]

# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a[^>]*class="stui-vodlist__thumb[^"]*"[^>]*href="(/uty/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
    r'[\s\S]{0,400}?<mip-img[^>]*?src="([^"]*)"'
    r'[\s\S]{0,200}?<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>',
    re.S | re.I)

_RE_CARD_ULT = re.compile(
    r'href="(/uty/\d+\.html)"[^>]*title="([^"]*)"[\s\S]{0,500}?<mip-img[^>]*?src="([^"]*)"',
    re.S | re.I)

_RE_CARD_MIN = re.compile(
    r'<a[^>]*class="stui-vodlist__thumb[^"]*"[^>]*href="(/uty/\d+\.html)"[^>]*title="([^"]*)"',
    re.I)

_RE_PAGE_TAIL = re.compile(r'尾页[^>]*href="[^"]*?page=(\d+)', re.I)
_RE_PAGE_NUMS = re.compile(r'page=(\d+)', re.I)

_RE_OG = re.compile(r'<meta\s+property="og:([^"]+)"\s+content="([^"]*)"', re.I)
_RE_TITLE_H1 = re.compile(r'<h3[^>]*class="title"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_DESC_DIV = re.compile(r'<div[^>]*class="stui-content__desc"[^>]*>([\s\S]*?)</div>', re.I)
_RE_PIC = re.compile(r'<mip-img[^>]*?src="([^"]+)"', re.I)

# 提取年份、地区、类型信息
_RE_YEAR = re.compile(r'年份：</span>\s*(\d+)', re.I)
_RE_AREA = re.compile(r'地区：</span>([^<]+)', re.I)
_RE_TYPE = re.compile(r'类型：</span>([^<]+)', re.I)

_RE_TABS_BLOCK = re.compile(r'<mip-vd-tabs[\s\S]*?</mip-vd-tabs>', re.I)
_RE_TAB_NAME = re.compile(r'<li>([^<]+)</li>', re.I)
_RE_PLAYLIST_UL = re.compile(r'<ul[^>]*class="stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*title="([^"]*)"[^>]*href="(/play/[^"]+\.html)"', re.I)

_RE_IFRAME_URL = re.compile(r'<mip-iframe[^>]*?src="([^"]+)"', re.I)
_RE_URL_PARAM = re.compile(r'[?&]url=([^&"\']+)', re.I)

_RE_LIMIT = re.compile(r'搜索限制为\s*\d+\s*秒一次', re.I)


class Spider(Spider):

    def getName(self):
        return "网飞猫影视"

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
        self._last_search = 0.0
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=20, headers=None, allow_redirects=True):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout,
                             allow_redirects=allow_redirects)
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
        s = re.sub(r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", s)
        s = re.sub(r"@[^@\s]{0,30}@", "", s)
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        s = re.sub(r'\.\.$', '', s.strip()) # 去掉结尾的多余小点
        return s.strip()

    # ---------- 列表解析 ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href, title, pic, remark = m.group(1), m.group(2), m.group(3), m.group(4)
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })

        if videos:
            return videos

        for m in _RE_CARD_ULT.finditer(html):
            href, title, pic = m.group(1), m.group(2), m.group(3)
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })

        if videos:
            return videos

        for m in _RE_CARD_MIN.finditer(html):
            href, title = m.group(1), m.group(2)
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_TAIL.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        nums = [int(x) for x in _RE_PAGE_NUMS.findall(html) if x.isdigit()]
        return max(nums) if nums else 1

    # ---------- 首页 / 分类 / 搜索 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML len=%d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        static_url = "%s/all/%s.html" % (self.site_url, tid)
        if page > 1:
            static_url = "%s/all/%s-%d.html" % (self.site_url, tid, page)
            
        self.log("category (static): %s" % static_url)
        html = self._fetch(static_url)
        videos = self._extract_videos(html)
        
        if not videos:
            self.log("  static empty, trying search.php fallback...")
            real_tid = extend.get("tid") or tid
            if real_tid == "2": real_tid = "13"
            elif real_tid == "1": real_tid = "5"
            elif real_tid == "3": real_tid = "30"
            elif real_tid == "4": real_tid = "34"

            params = {
                "searchtype": "5",
                "tid": real_tid,
                "page": page,
                "year": extend.get("year") or "2026"
            }
            if extend.get("area"): params["area"] = extend["area"]
            if extend.get("order"): params["order"] = extend["order"]
            
            search_url = "%s/search.php?%s" % (self.site_url, urllib.parse.urlencode(params))
            self.log("category (search): %s" % search_url)
            html2 = self._fetch(search_url)
            
            if _RE_LIMIT.search(html2):
                self.log("  命中限流提示页")
                return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
                
            videos = self._extract_videos(html2)
            if videos:
                html = html2

        pagecount = self._page_count(html)
        self.log("  videos=%d pagecount=%d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        now = time.time()
        wait = 10 - (now - self._last_search)
        if wait > 0: time.sleep(wait)
        self._last_search = time.time()

        keyword = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)

        if _RE_LIMIT.search(html):
            self.log("  命中限流提示页，返回空")
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html: return {"list": []}

        # 1. 优先用 OG 标签
        og = {}
        for m in _RE_OG.finditer(html):
            og[m.group(1).lower()] = self._clean(m.group(2))

        name = og.get("title") or ""
        if not name:
            m = _RE_TITLE_H1.search(html)
            if m: name = self._clean(m.group(1))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        pic = og.get("image") or ""
        if not pic:
            m = _RE_PIC.search(html)
            if m: pic = m.group(1)
        pic = self._fix_url(pic) or self.default_pic

        # 2. 导演/演员/分类/地区 直接从 og 拿
        director = og.get("video:director", "")
        actor = og.get("video:actor", "")
        
        # 3. 年份、类型、地区：用正则强抓（优先正则，兜底 OG）
        vclass = ""
        m_type = _RE_TYPE.search(html)
        if m_type: vclass = m_type.group(1)
        else: vclass = og.get("video:class", "")

        varea = ""
        m_area = _RE_AREA.search(html)
        if m_area: varea = m_area.group(1)
        else: varea = og.get("video:area", "")

        vyear = ""
        m_year = _RE_YEAR.search(html)
        if m_year: vyear = m_year.group(1)

        # 4. 简介
        content = ""
        m = _RE_DESC_DIV.search(html)
        if m: content = self._clean(m.group(1))
        if not content: content = og.get("description", "")
        if not content:
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if m: content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 5. 剧集与线路
        play_from, play_url = self._parse_playlists(html)
        remarks = "%d条线路" % len(play_from) if play_from else ""

        # 组装并塞入年份、地区、类型
        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": varea,
            "vod_year": vyear,
            "vod_type": vclass,  # <--- 类型完美补全
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _parse_playlists(self, html):
        play_from, play_url = [], []
        if not html: return play_from, play_url

        block_m = _RE_TABS_BLOCK.search(html)
        block = block_m.group(0) if block_m else html

        names = [self._clean(x) for x in _RE_TAB_NAME.findall(block)]
        names = [n for n in names if n]
        seen_n = set()
        names = [n for n in names if not (n in seen_n or seen_n.add(n))]

        uls = _RE_PLAYLIST_UL.findall(block)
        for idx, ul_html in enumerate(uls):
            eps = []
            for m in _RE_EP_A.finditer(ul_html):
                ep_name = self._clean(m.group(1))
                href = m.group(2).replace("&amp;", "&")
                if href.startswith("/"): href = self.site_url + href
                if not ep_name: ep_name = "第%02d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps: continue
            line_name = names[idx] if idx < len(names) else ("线路%d" % (idx + 1))
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))
        return play_from, play_url

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600: return res

        html = self._fetch(play_page, headers={"Referer": self.site_url + "/"})
        m3u8 = self._extract_m3u8(html)

        if m3u8:
            res = {"parse": 0, "playUrl": "", "url": m3u8, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        else:
            res = {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        self._play_cache[play_page] = (now, res)
        return res

    def _extract_m3u8(self, html):
        if not html: return ""
        m = _RE_IFRAME_URL.search(html)
        if not m: return ""
        iframe_src = m.group(1).replace("&amp;", "&")
        mu = _RE_URL_PARAM.search(iframe_src)
        if not mu: return ""
        real = urllib.parse.unquote(mu.group(1))
        if real.startswith("//"): real = "https:" + real
        return real if ".m3u8" in real.lower() or real.startswith("http") else ""

    # ---------- 杂项 ----------
    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict): url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url": url = v
            if not url: return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={"User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            return [200, rsp.headers.get("Content-Type", "image/jpeg"), rsp.content, ""]
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

# coding=utf-8
"""
小蜜蜂影院 www.xmfyy.com | TVBox Python 爬虫
站点结构（线上实证）:
  - 频道筛选列表: /filter?channel=<1..5>&type=<id>&area=<中文>&year=<2026..2018|-1>&sort=<hot|time|score>&page=<n>
  - 搜索:         /search?keyword=<词>&field=<all|name|actor>&page=<n>
  - 详情:         /detail/<id>.html
  - 播放页:       /vodplay/<id>-<线路slug>-<集号>.html
  - 播放解析API:  /api/play-url?vodId=<id>&playFrom=<slug>&index=<集号>
                  返回 {"code":200,"url":"...","mode":"native|iframe","headers":{...}}
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
                print("[xmfyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.xmfyy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 频道（type_id 即 channel 编号）=====================
CHANNELS = [
    {"type_id": "1", "type_name": "电视剧"},
    {"type_id": "2", "type_name": "电影"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
    {"type_id": "5", "type_name": "短剧"},
]

# 各频道类型 id 映射（与站点 /filter 页标签一一对应）
TYPE_MAP = {
    "1": [("剧情", "7"), ("古装", "9"), ("战争", "10"), ("谍战", "11"), ("爱情", "12"),
          ("罪案", "13"), ("悬疑", "14"), ("家庭", "15"), ("军旅", "16"), ("喜剧", "17"),
          ("都市", "18"), ("武侠", "19"), ("言情", "20"), ("偶像", "21"), ("青春", "22"),
          ("农村", "23"), ("穿越", "24"), ("奇幻", "25"), ("历史", "26"), ("年代", "27"),
          ("科幻", "28"), ("生活", "29"), ("剧情", "30"), ("励志", "31"), ("婚姻", "32"),
          ("警匪", "33"), ("犯罪", "34"), ("推理", "35"), ("商战", "36"), ("宫廷", "37"),
          ("仙侠", "38"), ("神话", "39"), ("动作", "40"), ("复仇", "41"), ("惊悚", "42")],
    "2": [("动作", "43"), ("喜剧", "44"), ("爱情", "45"), ("科幻", "46"), ("恐怖", "47"),
          ("剧情", "48"), ("战争", "49"), ("犯罪", "50"), ("惊悚", "51"), ("冒险", "52"),
          ("悬疑", "53"), ("动画", "54"), ("武侠", "55"), ("古装", "56"), ("历史", "57"),
          ("传记", "58"), ("纪录片", "59")],
    "3": [("热血", "60"), ("恋爱", "61"), ("校园", "62"), ("搞笑", "63"), ("机甲", "64"),
          ("神魔", "65"), ("竞技", "66"), ("冒险", "67"), ("治愈", "68"), ("百合", "69"),
          ("萝莉", "70"), ("后宫", "71"), ("励志", "72"), ("泡面番", "73"), ("国产动漫", "74"),
          ("日本动漫", "75"), ("欧美动漫", "76")],
    "4": [("选秀", "77"), ("情感", "78"), ("访谈", "79"), ("播报", "80"), ("旅游", "81"),
          ("音乐", "82"), ("美食", "83"), ("纪实", "84"), ("曲艺", "85"), ("游戏", "86"),
          ("亲子", "87"), ("职场", "88"), ("脱口秀", "89"), ("真人秀", "90"), ("晚会", "91")],
    "5": [],
}

AREAS = [("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"), ("韩国", "韩国"),
         ("日本", "日本"), ("美国", "美国"), ("泰国", "泰国"), ("法国", "法国"), ("英国", "英国"),
         ("德国", "德国"), ("印度", "印度"), ("其他", "其他")]

YEARS = [("全部", ""), ("2026", "2026"), ("2025", "2025"), ("2024", "2024"), ("2023", "2023"),
         ("2022", "2022"), ("2021", "2021"), ("2020", "2020"), ("2019", "2019"), ("2018", "2018"),
         ("其他", "-1")]

SORTS = [("热度排序", "hot"), ("上映时间", "time"), ("评分排序", "score")]

FILTERS = {}
for c in CHANNELS:
    tid = c["type_id"]
    flt = []
    if TYPE_MAP.get(tid):
        flt.append({"key": "type", "name": "类型",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": n, "v": v} for n, v in TYPE_MAP[tid]]})
    flt.append({"key": "area", "name": "地区",
                "value": [{"n": n, "v": v} for n, v in AREAS]})
    flt.append({"key": "year", "name": "年份",
                "value": [{"n": n, "v": v} for n, v in YEARS]})
    flt.append({"key": "sort", "name": "排序",
                "value": [{"n": n, "v": v} for n, v in SORTS]})
    FILTERS[tid] = flt


# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a\s+href="(/detail/[^"]+?\.html)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:data-src|src)="([^"]*)"[^>]*?(?:alt="([^"]*)")?', re.S | re.I)
_RE_IMG_ALT_FIRST = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"', re.S | re.I)
_RE_TITLE = re.compile(r'vod-title[^>]*>([^<]*)<', re.I)
_RE_SUB = re.compile(r'vod-subtitle[^>]*>([^<]*)<', re.I)
_RE_BADGE = re.compile(r'vod-badge[^>]*>([^<]*)<', re.I)

_RE_H1 = re.compile(r'<h1[^>]*class="detail-title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S | re.I)
_RE_COVER = re.compile(
    r'<img[^>]*src="([^"]+)"[^>]*alt="[^"]*海报[^"]*"', re.S | re.I)
_RE_TAGS = re.compile(r'tag-pill">([^<]+)<', re.I)
_RE_META = re.compile(
    r'<span\s+class="meta-label">([^：<]+)：</span>\s*'
    r'<span\s+class="meta-value">([\s\S]*?)</span>', re.I)
_RE_INTRO = re.compile(
    r'<div[^>]*class="synopsis-content"[^>]*>([\s\S]*?)</div>', re.I)
_RE_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_RATING = re.compile(r'"ratingValue"\s*:\s*"([\d.]+)"', re.I)
_RE_TAB = re.compile(
    r'data-target="(source-\d+)"[^>]*>([^<]+)<', re.I)
_RE_PANEL = re.compile(
    r'<div\s+class="source-panel"[^>]*id="(source-\d+)"([\s\S]*?)(?=<div\s+class="source-panel"|<h2\s+class="vod-section-title"|$)',
    re.I)
_RE_EP = re.compile(
    r'<a\s+href="(/vodplay/[^"]+?\.html)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PLAY_HREF = re.compile(
    r'/vodplay/(\d+)-([A-Za-z0-9]+)-(\d+)\.html', re.I)

_RE_PAGE = re.compile(r'data-page="(\d+)"')

# 搜索结果专用布局 .search-item
_RE_S_ITEM = re.compile(r'<div\s+class="search-item">', re.I)
_RE_S_HREF = re.compile(r'(/detail/\d+\.html)')
_RE_S_IMG = re.compile(r'<img[^>]*?(?:src|data-src)="([^"]*)"[^>]*?(?:alt="([^"]*)")?', re.S | re.I)
_RE_S_IMG_ALT = re.compile(r'<img[^>]*?alt="([^"]*)"[^>]*?(?:src|data-src)="([^"]*)"', re.S | re.I)
_RE_S_TITLE = re.compile(r'search-item-title[^>]*>([^<]*)<', re.I)
_RE_S_TYPE = re.compile(r'search-item-type">([^<]*)<', re.I)
_RE_S_META = re.compile(
    r'search-meta-label">([^<：]+)：</span>\s*'
    r'<span\s+class="search-meta-value">([\s\S]*?)</span>', re.I)


class Spider(Spider):

    def getName(self):
        return "小蜜蜂影院"

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
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
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

    def _clean_alt(self, alt):
        alt = self._clean(alt)
        alt = re.sub(r"(封面图片|海报图片|海报|封面)$", "", alt).strip()
        return alt

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif"):
            if bad in low:
                return True
        return False

    # ---------------- 卡片提取 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href = m.group(1).replace("&amp;", "&")
            block = m.group(2)
            if href in seen:
                continue

            # 封面 / alt
            pic, alt = "", ""
            mi = _RE_IMG_ALT_FIRST.search(block)
            if mi:
                alt, pic = mi.group(1), mi.group(2)
            else:
                mi = _RE_IMG.search(block)
                if mi:
                    pic, alt = mi.group(1), (mi.group(2) or "")

            title = self._clean(_RE_TITLE.search(block).group(1)) if _RE_TITLE.search(block) else ""
            subtitle = self._clean(_RE_SUB.search(block).group(1)) if _RE_SUB.search(block) else ""
            badge = self._clean(_RE_BADGE.search(block).group(1)) if _RE_BADGE.search(block) else ""

            if not title:
                title = self._clean_alt(alt)
            if self._is_placeholder_pic(pic):
                pic = self.default_pic
            else:
                pic = self._fix_url(pic)

            remarks = badge
            if subtitle and subtitle != badge:
                remarks = (badge + " " + subtitle).strip() if badge else subtitle

            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": title[:100] or href,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })

        # 兜底：ld+json 结构化数据里的 名称/链接 成对补齐
        if not videos:
            pairs = re.findall(
                r'"name"\s*:\s*"([^"]+)"[^}]*?"url"\s*:\s*"(https?://[^"]*?/detail/\d+\.html)"',
                html)
            for name, url in pairs:
                href = urllib.parse.urlparse(url).path
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": self._clean(name)[:100],
                    "vod_pic": self.default_pic,
                    "vod_remarks": "",
                    "vod_subtitle": "",
                })
        return videos

    def _extract_search_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        blocks = _RE_S_ITEM.split(html)[1:]
        for blk in blocks:
            hm = _RE_S_HREF.search(blk)
            if not hm:
                continue
            href = hm.group(1)
            if href in seen:
                continue
            seen.add(href)

            title = ""
            mt = _RE_S_TITLE.search(blk)
            if mt:
                title = self._clean(mt.group(1))

            pic, alt = "", ""
            mi = _RE_S_IMG_ALT.search(blk)
            if mi:
                alt, pic = mi.group(1), mi.group(2)
            else:
                mi = _RE_S_IMG.search(blk)
                if mi:
                    pic, alt = mi.group(1), (mi.group(2) or "")
            if not title:
                title = self._clean_alt(alt)
            if self._is_placeholder_pic(pic):
                pic = self.default_pic
            else:
                pic = self._fix_url(pic)

            meta = {}
            for mm in _RE_S_META.finditer(blk):
                meta[self._clean(mm.group(1))] = self._clean(mm.group(2))
            subtitle = meta.get("主演", "")
            type_tag = self._clean(_RE_S_TYPE.search(blk).group(1)) if _RE_S_TYPE.search(blk) else ""
            genre = meta.get("类型", "")
            remarks = " ".join(x for x in (type_tag, genre) if x)

            videos.append({
                "vod_id": href,
                "vod_name": title[:100] or href,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })
        # 兜底：无 .search-item 结构时走通用卡片解析
        if not videos:
            videos = self._extract_videos(html)
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = _RE_PAGE.findall(html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CHANNELS, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        params = {"channel": str(tid), "page": page}
        for k in ("type", "area", "year", "sort"):
            v = extend.get(k)
            if v in ("", None, "全部"):
                continue
            params[k] = v
        if not extend.get("sort"):
            params["sort"] = "hot"

        url = self.site_url + "/filter?" + urllib.parse.urlencode(params)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 12, "total": pagecount * 12,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        params = {"keyword": key, "field": "all", "page": page}
        url = self.site_url + "/search?" + urllib.parse.urlencode(params)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_search_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 12, "total": 999,
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
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_COVER.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if self._is_placeholder_pic(pic):
            mi = _RE_IMG.search(html)
            if mi and not self._is_placeholder_pic(mi.group(1)):
                pic = self._fix_url(mi.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        meta = {}
        for mm in _RE_META.finditer(html):
            label = self._clean(mm.group(1))
            val = self._clean(mm.group(2))
            meta[label] = val

        director = meta.get("导演", "")
        actor = re.sub(r"\s*,\s*", ", ", meta.get("主演", ""))
        area = meta.get("地区", "")
        lang = meta.get("语言", "")
        year = meta.get("年份", "")
        alias = meta.get("别名", "")
        update = meta.get("更新", "")
        remarks = meta.get("备注", "")

        tags = [self._clean(t) for t in _RE_TAGS.findall(html)]
        classify = ",".join([t for t in tags if t])

        # 评分（仅豆瓣评分，0.0 视为无评分占位；不取播放热度/总集数）
        score = ""
        m = _RE_RATING.search(html)
        if m:
            score = m.group(1)
        if not score:
            m = re.search(
                r'stat-number">\s*<span>([\d.]+)</span>\s*</div>\s*'
                r'<span class="stat-text">豆瓣评分', html)
            if m and float(m.group(1)) > 0:
                score = m.group(1)

        # ===== 线路 / 选集 =====
        tab_map = {tid: self._clean(lab) for tid, lab in _RE_TAB.findall(html)}

        groups = []  # [(line_label, [(ep_name, play_href), ...])]
        for pm in _RE_PANEL.finditer(html):
            panel_id, block = pm.group(1), pm.group(2)
            eps = []
            seen_ep = set()
            for em in _RE_EP.finditer(block):
                href = em.group(1).replace("&amp;", "&")
                if href in seen_ep:
                    continue
                seen_ep.add(href)
                ep_name = self._clean(em.group(2))
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if eps:
                label = tab_map.get(panel_id, panel_id)
                groups.append((label, eps))

        self.log("  线路: %s" % {k: len(v) for k, v in groups})

        if not groups:
            return {"list": []}

        play_from, play_url = [], []
        for label, eps in groups:
            play_from.append(label)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(groups)),
            "vod_area": area,
            "vod_year": year,
            "vod_lang": lang,
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": alias,
            "vod_update": update,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        hm = _RE_PLAY_HREF.search(play_page)
        if hm:
            vod_id, slug, index = hm.group(1), hm.group(2), hm.group(3)
            api = ("%s/api/play-url?vodId=%s&playFrom=%s&index=%s"
                   % (self.site_url, vod_id, slug, index))
            self.log("  api: %s" % api)
            text = self._fetch(api, headers={"Referer": play_page,
                                              "Accept": "application/json,*/*"})
            if text:
                try:
                    data = json.loads(text)
                except Exception:
                    data = {}
                if data and data.get("code") == 200 and data.get("url"):
                    play_url = data["url"]
                    mode = data.get("mode") or "native"
                    api_headers = data.get("headers") or {}
                    header = {"User-Agent": UA, "Referer": self.site_url + "/"}
                    if isinstance(api_headers, dict):
                        for hk in ("Referer", "User-Agent", "Origin"):
                            if api_headers.get(hk):
                                header[hk] = api_headers[hk]
                    if mode == "iframe":
                        res = {"parse": 1, "playUrl": "", "url": play_url,
                               "header": header}
                    else:
                        res = {"parse": 0, "playUrl": "", "url": play_url,
                               "header": header}
                    self.log("  => mode=%s url=%s" % (mode, play_url[:160]))
                else:
                    self.log("  API 未返回有效地址, 兜底播放页")
            else:
                self.log("  API 无响应, 兜底播放页")
        else:
            self.log("  无法解析播放链接, 兜底播放页")

        self._play_cache[play_page] = (now, res)
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

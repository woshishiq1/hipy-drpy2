# coding=utf-8
"""
极速追剧 jisuzhuiju.com | TVBox Python 爬虫
覆盖：首页、分类、筛选（类型/地区/年份/排序）、详情、多线路选集、播放解析、搜索、副标题。
播放地址由站点接口 /api/play-url 异步解析，返回直链 m3u8/mp4 或 iframe 线路。
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
                print("[jisuzhuiju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://jisuzhuiju.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 频道：1 电视剧 2 电影 3 动漫 4 综艺 5 短剧（与站点 /filter?channel= 一致）
CLASSES = [
    {"type_id": "1", "type_name": "电视剧"},
    {"type_id": "2", "type_name": "电影"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
    {"type_id": "5", "type_name": "短剧"},
]

# 各频道类型（站点 /filter 页 type=id 与中文标签一一对应）
_GENRES = {
    "1": [("7", "剧情"), ("9", "古装"), ("10", "战争"), ("11", "谍战"), ("12", "爱情"),
          ("13", "罪案"), ("14", "悬疑"), ("15", "家庭"), ("16", "军旅"), ("17", "喜剧"),
          ("18", "都市"), ("19", "武侠"), ("20", "言情"), ("21", "偶像"), ("22", "青春"),
          ("23", "农村"), ("24", "穿越"), ("25", "奇幻"), ("26", "历史"), ("27", "年代"),
          ("28", "科幻"), ("29", "生活"), ("30", "剧情"), ("31", "励志"), ("32", "婚姻"),
          ("33", "警匪"), ("34", "犯罪"), ("35", "推理"), ("36", "商战"), ("37", "宫廷"),
          ("38", "仙侠"), ("39", "神话"), ("40", "动作"), ("41", "复仇"), ("42", "惊悚")],
    "2": [("43", "动作"), ("44", "喜剧"), ("45", "爱情"), ("46", "科幻"), ("47", "恐怖"),
          ("48", "剧情"), ("49", "战争"), ("50", "犯罪"), ("51", "惊悚"), ("52", "冒险"),
          ("53", "悬疑"), ("54", "动画"), ("55", "武侠"), ("56", "古装"), ("57", "历史"),
          ("58", "传记"), ("59", "纪录片")],
    "3": [("60", "热血"), ("61", "恋爱"), ("62", "校园"), ("63", "搞笑"), ("64", "机甲"),
          ("65", "神魔"), ("66", "竞技"), ("67", "冒险"), ("68", "治愈"), ("69", "百合"),
          ("70", "萝莉"), ("71", "后宫"), ("72", "励志"), ("73", "泡面番"), ("74", "国产动漫"),
          ("75", "日本动漫"), ("76", "欧美动漫")],
    "4": [("77", "选秀"), ("78", "情感"), ("79", "访谈"), ("80", "播报"), ("81", "旅游"),
          ("82", "音乐"), ("83", "美食"), ("84", "纪实"), ("85", "曲艺"), ("86", "游戏"),
          ("87", "亲子"), ("88", "职场"), ("89", "脱口秀"), ("90", "真人秀"), ("91", "晚会")],
    "5": [],
}

_AREAS = ["大陆", "香港", "台湾", "韩国", "日本", "美国", "泰国", "法国",
          "英国", "德国", "印度", "其他"]
_YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]
_SORTS = [("hot", "热度排序"), ("time", "上映时间"), ("score", "评分排序")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    fl = []
    if _GENRES.get(tid):
        fl.append({"key": "type", "name": "分类",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": n, "v": v} for v, n in _GENRES[tid]]})
    fl.append({"key": "area", "name": "地区",
               "value": [{"n": "全部", "v": ""}] +
                        [{"n": a, "v": a} for a in _AREAS]})
    fl.append({"key": "year", "name": "年份",
               "value": [{"n": "全部", "v": ""}] +
                        [{"n": y, "v": y} for y in _YEARS] +
                        [{"n": "其他", "v": "-1"}]})
    fl.append({"key": "sort", "name": "排序",
               "value": [{"n": n, "v": v} for v, n in _SORTS]})
    FILTERS[tid] = fl


# ===================== 正则 =====================
# 通用锚点（兼容相对路径 / 绝对地址 / 首尾空格）
_RE_ANCHOR = re.compile(
    r'<a\s+href="([^"]*)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_TITLE = re.compile(r'class="vod-title[^>]*>([\s\S]*?)</p>', re.I)
_RE_SUB = re.compile(r'class="vod-subtitle[^>]*>([\s\S]*?)</p>', re.I)
_RE_BADGE = re.compile(
    r'class="vod-badge vod-badge-episodes"[^>]*>([\s\S]*?)</span>', re.I)

# 搜索卡片
_RE_SEARCH_SPLIT = re.compile(r'<div class="search-item">', re.I)
_RE_SEARCH_POSTER = re.compile(
    r'<a\s+href="([^"]*)"[^>]*>\s*<img[^>]*?(?:data-src|src)="([^"]*)"[^>]*?(?:alt="([^"]*)")?',
    re.S | re.I)
_RE_SEARCH_TITLE = re.compile(
    r'class="search-item-title[^>]*>([\s\S]*?)</a>', re.I)
_RE_SEARCH_TYPE = re.compile(
    r'class="search-item-type">([\s\S]*?)</span>', re.I)
_RE_SEARCH_META = re.compile(
    r'search-meta-label">([^<]*)</span>\s*<span class="search-meta-value">([\s\S]*?)</span>', re.I)

# 详情线路
_RE_TAB = re.compile(
    r'<button[^>]*source-tab[^>]*data-target="([^"]+)"[^>]*>([\s\S]*?)</button>', re.I)
_RE_PANEL = re.compile(
    r'<div[^>]*source-panel[^>]*id="([^"]+)"[^>]*>([\s\S]*?)(?=<div[^>]*source-panel|$)', re.I)
_RE_EP_A = re.compile(
    r'<a\s+href="([^"]*)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PLAY_HREF = re.compile(
    r'^/vodplay/(\d+)-(.+)-(\d+)\.html$', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([\s\S]*?)</title>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_META_ROW = re.compile(
    r'class="meta-label"[^>]*>([\s\S]*?)</span>\s*<[^>]*class="meta-value"[^>]*>([\s\S]*?)</span>', re.I)
_RE_POSTER_IMG = re.compile(
    r'<div class="detail-poster-wrapper">\s*<img[^>]*?(?:data-src|src)="([^"]*)"', re.S | re.I)
_RE_SYNOPSIS = re.compile(
    r'<div[^>]*class="synopsis-content"[^>]*>([\s\S]*?)</div>', re.I)
_RE_TAG_PILL = re.compile(r'<span class="tag-pill"[^>]*>([\s\S]*?)</span>', re.I)


class Spider(Spider):

    def getName(self):
        return "极速追剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础工具 ----------
    def _fetch(self, url, timeout=20, headers=None):
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

    def _norm_detail(self, raw):
        if not raw:
            return ""
        u = raw.strip().replace("&amp;", "&")
        m = re.search(r'/detail/(\d+)\.html', u)
        return "/detail/%s.html" % m.group(1) if m else ""

    def _norm_play(self, raw):
        if not raw:
            return ""
        u = raw.strip().replace("&amp;", "&")
        m = re.search(r'/vodplay/(\d+)-(.+)-(\d+)\.html', u)
        return "/vodplay/%s-%s-%s.html" % m.groups() if m else ""

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

    # ---------- 卡片解析 ----------
    def _parse_list_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_ANCHOR.finditer(html):
            href = self._norm_detail(m.group(1))
            inner = m.group(2)
            if not href or href in seen:
                continue
            img = ""
            alt = ""
            mi = re.search(r'<img[^>]*?(?:data-src|src)="([^"]*)"', inner, re.I)
            if mi:
                img = mi.group(1)
            ma = re.search(r'<img[^>]*?alt="([^"]*)"', inner, re.I)
            if ma:
                alt = ma.group(1)
            mt = _RE_TITLE.search(inner)
            title = self._clean(mt.group(1)) if mt else ""
            ms = _RE_SUB.search(inner)
            sub = self._clean(ms.group(1)) if ms else ""
            mb = _RE_BADGE.search(inner)
            badge = self._clean(mb.group(1)) if mb else ""
            if not title:
                title = alt.replace("封面图片", "").strip()
            if not title:
                continue
            seen.add(href)
            remarks = " ｜ ".join([x for x in (badge, sub) if x])
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": self._fix_url(img) or self.default_pic,
                "vod_remarks": remarks,
            })

        # 兜底：锚点与图片分开配对
        if not videos:
            hrefs = [self._norm_detail(h) for h in re.findall(r'href="([^"]*)"', html)]
            hrefs = [h for h in hrefs if h]
            imgs = re.findall(r'<img[^>]*?(?:data-src|src)="([^"]*)"', html)
            alts = re.findall(r'<img[^>]*?alt="([^"]*)"', html)
            for i, href in enumerate(hrefs):
                if href in seen:
                    continue
                seen.add(href)
                img = imgs[i] if i < len(imgs) else ""
                alt = alts[i] if i < len(alts) else ""
                videos.append({
                    "vod_id": href,
                    "vod_name": self._clean(alt).replace("封面图片", "").strip() or href,
                    "vod_pic": self._fix_url(img) or self.default_pic,
                    "vod_remarks": "",
                })
        return videos

    def _parse_search_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        parts = _RE_SEARCH_SPLIT.split(html)
        for block in parts[1:]:
            mp = _RE_SEARCH_POSTER.search(block)
            if not mp:
                continue
            href = self._norm_detail(mp.group(1))
            if not href or href in seen:
                continue
            img = mp.group(2)
            alt = mp.group(3) or ""
            mt = _RE_SEARCH_TITLE.search(block)
            title = self._clean(mt.group(1)) if mt else alt.replace("封面图片", "").strip()
            if not title:
                continue
            mtype = _RE_SEARCH_TYPE.search(block)
            remarks = self._clean(mtype.group(1)) if mtype else ""
            metas = {}
            for ml, mv in _RE_SEARCH_META.findall(block):
                metas[self._clean(ml).rstrip("：:")] = self._clean(mv)
            if not remarks and metas.get("类型"):
                remarks = metas["类型"]
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": self._fix_url(img) or self.default_pic,
                "vod_remarks": remarks,
            })
        # 兜底：与列表相同的卡片结构
        if not videos:
            videos = self._parse_list_cards(html)
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'data-page="(\d+)"', html)
        if not pages:
            pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ---------- 首页 / 分类 / 搜索 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_list_cards(html)}

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

        params = {
            "channel": tid,
            "type": extend.get("type", ""),
            "area": extend.get("area", ""),
            "year": extend.get("year", ""),
            "sort": extend.get("sort") or "hot",
            "page": page,
        }
        url = "%s/filter?%s" % (self.site_url, urllib.parse.urlencode(params))
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._parse_list_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 12, "total": pagecount * 12,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        params = {"keyword": key, "field": "all", "sort": "hits"}
        if page > 1:
            params["page"] = page
        url = "%s/search?%s" % (self.site_url, urllib.parse.urlencode(params))
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._parse_search_cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) if videos else 1,
            "limit": 20, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def _load_jsonld(self, html):
        m = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>', html)
        if not m:
            return {}
        try:
            data = json.loads(m.group(1))
        except Exception:
            return {}
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else []
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") in ("TVSeries", "Movie", "VideoObject", "TVEpisode"):
                return node
        return nodes[0] if nodes and isinstance(nodes[0], dict) else {}

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

        ld = self._load_jsonld(html)

        # 标题
        name = self._clean(ld.get("name", ""))
        if not name:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = ld.get("image", "") or ld.get("thumbnailUrl", "") or ""
        if isinstance(pic, list):
            pic = pic[0] if pic else ""
        if not pic:
            mp = _RE_POSTER_IMG.search(html)
            if mp:
                pic = mp.group(1)
        pic = self._fix_url(pic) or self.default_pic

        # 简介（优先页面完整简介容器，再 JSON-LD / meta description 兜底）
        content = ""
        ms = _RE_SYNOPSIS.search(html)
        if ms:
            content = self._clean(ms.group(1))
        if not content:
            content = self._clean(ld.get("description", ""))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息行
        meta = {}
        for ml, mv in _RE_META_ROW.findall(html):
            meta[self._clean(ml).rstrip("：:")] = self._clean(mv)

        actor = ld.get("actor", "") or meta.get("主演", "")
        if isinstance(actor, list):
            actor = ",".join(str(x) for x in actor)
        actor = re.sub(r"\s*,\s*", ", ", self._clean(str(actor)))

        director = ld.get("director", "") or meta.get("导演", "")
        if isinstance(director, list):
            director = ",".join(str(x) for x in director)
        director = self._clean(str(director))

        score = ""
        rating = ld.get("aggregateRating", {})
        if isinstance(rating, dict) and rating.get("ratingValue"):
            score = str(rating["ratingValue"])

        # 地区 / 年份 / 语言 / 别名 / 更新 / 类型标签（与站点详情元信息一致）
        area = meta.get("地区", "")
        year = meta.get("年份", "")
        lang = meta.get("语言", "")
        alias = meta.get("别名", "")
        update_time = meta.get("更新", "")
        genre = self._clean(str(ld.get("genre", "") or ""))
        if not genre:
            pills = [self._clean(p) for p in _RE_TAG_PILL.findall(html)]
            genre = ",".join([p for p in pills if p])

        remarks = meta.get("备注", "") or update_time

        # ===== 线路 / 选集 =====
        tab_labels = dict(_RE_TAB.findall(html))
        groups = {}
        order = []
        for pid, block in _RE_PANEL.findall(html):
            label = self._clean(tab_labels.get(pid, "")) or pid
            eps = []
            for em in _RE_EP_A.finditer(block):
                href = self._norm_play(em.group(1))
                if not href:
                    continue
                ep_name = self._clean(em.group(2))
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if eps:
                groups[label] = eps
                order.append(label)

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        play_from, play_url = [], []
        for label in order:
            eps = groups[label]
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
            "vod_classify": genre,
            "type_name": genre,
            "vod_alias": alias,
            "vod_update": update_time,
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

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        # 解析 /vodplay/{vodId}-{playFrom}-{index}.html（兼容绝对地址 / 首尾空格）
        rel = self._norm_play(id) or urllib.parse.urlparse(play_page).path
        m = _RE_PLAY_HREF.match(rel)
        if m:
            vod_id, play_from, index = m.group(1), m.group(2), m.group(3)
            params = {"vodId": vod_id, "playFrom": play_from, "index": index}
            api = self.site_url + "/api/play-url?" + urllib.parse.urlencode(params)
            self.log("  api: %s" % api)
            body = self._fetch(api, headers={"Referer": play_page, "Accept": "application/json,*/*"})
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            if data and str(data.get("code")) == "200" and data.get("url"):
                real_url = self._fix_url(str(data["url"]))
                mode = str(data.get("mode") or "native")
                headers = dict(data.get("headers") or {})
                headers.setdefault("User-Agent", UA)
                headers.setdefault("Referer", self.site_url + "/")
                if mode == "iframe":
                    # iframe 线路交由播放器内嵌打开
                    res = {"parse": 1, "playUrl": "", "url": real_url, "header": headers}
                else:
                    res = {"parse": 0, "playUrl": "", "url": real_url, "header": headers}
                self.log("  => mode=%s url=%s" % (mode, real_url[:160]))
            else:
                self.log("  接口未返回地址: %s" % str(body)[:120])

        self._play_cache[play_page] = (now, res)
        return res

    # ---------- 其它契约方法 ----------
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

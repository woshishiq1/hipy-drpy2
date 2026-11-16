# coding=utf-8
# OK看剧网 www.okkanju.com | TVBox Python 爬虫 
# 站点: https://www.okkanju.com/  (SSR 页面 + 第三方解析 iframe)
# 覆盖: 分类 / 地区·年份·状态·排序筛选 / 列表翻页 / 搜索 / 详情 / 多线路顺序 / 播放解析 / 副标题

import re
import json
import urllib.parse

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
                print("[okkanju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.okkanju.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 露骨/伦理类标题过滤 (与站点“伦理片”频道不上榜保持一致)
_ADULT_RE = re.compile(r"操逼|性爱|色情|淫荡|H\s*版|癖好|AV片|成人影片|Cosplay|cosplay")

# 频道: slug -> 名称 (伦理片频道按要求不上榜)
CHANNELS = [
    {"type_id": "movie",        "type_name": "电影"},
    {"type_id": "tv",           "type_name": "电视剧"},
    {"type_id": "variety",      "type_name": "综艺"},
    {"type_id": "anime",        "type_name": "动漫"},
    {"type_id": "short-drama",  "type_name": "短剧"},
]

_AREAS = ["大陆", "美国", "日本", "韩国", "欧美", "泰国", "英国", "香港", "台湾", "其他"]
_YEARS = ["2030", "2028", "2027", "2026", "2025", "2024", "2023", "2022"]
_STATUS = [("更新中", "updating"), ("已完结", "completed"), ("已收录", "available")]
_SORTS = [("热度", "popular"), ("评分", "rating")]


def _filter_rows():
    rows = [
        {"key": "area", "name": "地区",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _AREAS]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _YEARS]},
        {"key": "status", "name": "状态",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": v} for n, v in _STATUS]},
        {"key": "sort", "name": "排序",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": v} for n, v in _SORTS]},
    ]
    return rows


FILTERS = {c["type_id"]: _filter_rows() for c in CHANNELS}

# ===================== 正则 =====================

_RE_CARD = re.compile(
    r'<a[^>]+href="(/detail/video-(\d+))"[^>]*>([\s\S]*?)</a>', re.I)
_RE_ARIA = re.compile(r'aria-label="查看《([^》]*)》详情"', re.I)
_RE_ALT = re.compile(r'alt="《([^》]*)》海报"', re.I)
_RE_PIC = re.compile(r'data-lazy-src="([^"]+)"', re.I)
_RE_PIC_FALLBACK = re.compile(r'<noscript><img[^>]*src="([^"]+)"', re.I)
_RE_STATUS = re.compile(r'<span class="(?:home-card-)?status">([^<]*)</span>', re.I)
_RE_SCORE = re.compile(r'<span class="(?:home-card-)?score">([^<]*)</span>', re.I)
_RE_PAGE = re.compile(r'/channel/[a-z-]+\?[^"\']*?page=(\d+)')
_RE_PAGE_SEARCH = re.compile(r'/search\?[^"\']*page=(\d+)')

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_EYEBROW = re.compile(r'class="eyebrow">([^<]*)<', re.I)
_RE_OGIMG = re.compile(r'og:image"[^>]*content="([^"]+)"', re.I)
_RE_SCORE_BIG = re.compile(r'class="detail-score"><strong>([^<]*)<', re.I)
_RE_FACT = re.compile(r'<dt>([^<]+)</dt>\s*<dd>([^<]*)</dd>', re.I)
_RE_STORY = re.compile(r'id="story-copy">([\s\S]*?)</p>', re.I)
_RE_SUBTITLE = re.compile(r'class="detail-subtitle">([^<]*)<', re.I)
_RE_SOURCE_BTN = re.compile(
    r'<button[^>]*data-detail-source="[^"]*"[^>]*>[\s\S]*?</button>', re.I)
_RE_SRC_NAME = re.compile(r'data-source-name="([^"]*)"', re.I)
_RE_SRC_EPS = re.compile(r'data-source-episodes="([^"]*)"', re.I)
_RE_PLAYER_URL = re.compile(r'data-player-url="([^"]*)"', re.I)
_RE_PLAYER_DATA = re.compile(r'id="player-data"[^>]*>([\s\S]*?)</script>', re.I)
_RE_DIRECT_MEDIA = re.compile(
    r'https?://[^"\'\s\\]+\.(?:m3u8|mp4|flv)[^"\'\s\\]*', re.I)


class Spider(Spider):

    def __init__(self, *args, **kwargs):
        self.extend = {}
        self.site_url = HOST
        self._session = None
        self.init(kwargs.get("extend", ""))

    def getName(self):
        return "OK看剧网"

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

    # ---------- 工具 ----------

    def _fetch(self, url, timeout=15, referer=None):
        try:
            import urllib.request as _u
            headers = dict(self.headers)
            if referer:
                headers["Referer"] = referer
            req = _u.Request(url, headers=headers)
            with _u.urlopen(req, timeout=timeout) as rsp:
                return rsp.read().decode("utf-8", "ignore")
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&#43;", "+"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

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

    def _parse_cards(self, html):
        videos, seen = [], set()
        for m in _RE_CARD.finditer(html):
            href, vid, block = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            name = ""
            ma = _RE_ARIA.search(block)
            if ma:
                name = ma.group(1)
            if not name:
                ma = _RE_ALT.search(block)
                if ma:
                    name = ma.group(1)
            if not name:
                continue
            if _ADULT_RE.search(name):
                continue
            mp = _RE_PIC.search(block)
            if not mp:
                mp = _RE_PIC_FALLBACK.search(block)
            pic = self._fix_url(mp.group(1)) if mp else ""
            mr = _RE_STATUS.search(block)
            remarks = self._clean(mr.group(1)) if mr else ""
            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": self._clean(name)[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    # ---------- 分类 / 首页 ----------

    def homeContent(self, filter=False):
        return {"class": CHANNELS, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_cards(html)}

    # ---------- 列表 ----------

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend else {}
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        ext = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        qs = [("page", page)]
        if ext.get("area"):
            qs.append(("area", ext["area"]))
        if ext.get("year"):
            qs.append(("year", ext["year"]))
        if ext.get("status"):
            qs.append(("status", ext["status"]))
        if ext.get("sort"):
            qs.append(("sort", ext["sort"]))

        url = "%s/channel/%s?%s" % (
            self.site_url, tid, urllib.parse.urlencode(qs))
        html = self._fetch(url)
        videos = self._parse_cards(html)

        pages = [int(x) for x in _RE_PAGE.findall(html)]
        pagecount = max(pages) if pages else page
        if pagecount < page:
            pagecount = page

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    # ---------- 搜索 ----------

    def _search_url(self, key, page):
        q = urllib.parse.quote(key)
        return "%s/search?q=%s&page=%d" % (self.site_url, q, page)

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            page = int(pg) if pg else 1
        except (ValueError, TypeError):
            page = 1
        html = self._fetch(self._search_url(key, page))
        videos = self._parse_cards(html)
        pages = [int(x) for x in _RE_PAGE_SEARCH.findall(html)]
        pagecount = max(pages) if pages else page
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    # ---------- 详情 ----------

    def _detail_id(self, ids):
        raw = str(ids[0]) if ids else ""
        m = re.search(r"video-(\d+)", raw)
        return m.group(1) if m else raw

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = self._detail_id(ids)
        html = self._fetch("%s/detail/video-%s" % (self.site_url, vid))
        if not html:
            return {"list": []}

        name = ""
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            name = vid
        if _ADULT_RE.search(name):
            return {"list": []}

        eyebrow = ""
        me = _RE_EYEBROW.search(html)
        if me:
            eyebrow = self._clean(me.group(1))
        classify = ""
        remarks = ""
        if eyebrow and "·" in eyebrow:
            classify, remarks = [x.strip() for x in eyebrow.split("·", 1)]
        elif eyebrow:
            remarks = eyebrow

        mp = _RE_OGIMG.search(html)
        pic = self._fix_url(mp.group(1)) if mp else ""

        facts = dict(_RE_FACT.findall(html))
        year = facts.get("年份", "")
        area = facts.get("地区", "")
        language = facts.get("语言", "")

        director, actor = "", ""
        for m in re.finditer(r"<dt>([^<]+)</dt>\s*<dd>([\s\S]*?)</dd>", html, re.I):
            label, dd = self._clean(m.group(1)), m.group(2)
            texts = [self._clean(a) for a in re.findall(r"<a[^>]*>([\s\S]*?)</a>", dd, re.I)]
            texts = [t for t in texts if t]
            if label == "导演":
                director = ", ".join(texts)
            elif label == "主演":
                actor = ", ".join(texts)

        score = ""
        ms = _RE_SCORE_BIG.search(html)
        if ms:
            score = self._clean(ms.group(1))

        subtitle = ""
        msb = _RE_SUBTITLE.search(html)
        if msb:
            subtitle = self._clean(msb.group(1))

        content = ""
        mc = _RE_STORY.search(html)
        if mc:
            content = self._clean(mc.group(1))
        body = "\n".join(x for x in (subtitle, content) if x)
        content = INTRO_PREFIX + ("\n" + body if body else "")

        # 线路与选集 (线路顺序即 button 出现顺序, 1 基)
        from_names, from_urllists = [], []
        seen = {}
        source_pos = 0
        for btn in _RE_SOURCE_BTN.finditer(html):
            block = btn.group(0)
            mn = _RE_SRC_NAME.search(block)
            meps = _RE_SRC_EPS.search(block)
            if not mn or not meps:
                continue
            source_pos += 1
            src_name = self._clean(mn.group(1)) or "线路"
            try:
                import html as _html
                episodes = json.loads(_html.unescape(meps.group(1)))
            except Exception:
                episodes = []
            if not episodes:
                continue
            if src_name in seen:
                seen[src_name] += 1
                src_name = src_name + str(seen[src_name])
            else:
                seen[src_name] = 1

            segs = []
            for idx, ep in enumerate(episodes, 1):
                ep_name = self._clean(ep.get("t") or "") or ("第%d集" % idx)
                ep_name = ep_name.replace("$", "_").replace("#", "_")
                watch = ep.get("u") or ""
                segs.append("%s$%d:%s" % (ep_name, source_pos, watch))
            from_names.append(src_name)
            from_urllists.append("#".join(segs))

        if not from_urllists:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks,
            "vod_content": content,
            "vod_year": year,
            "vod_area": area,
            "vod_classify": classify,
            "vod_lang": language,
            "vod_score": score,
            "vod_play_from": "$$$".join(from_names),
            "vod_play_url": "$$$".join(from_urllists),
        }]}

    # ---------- 播放 ----------

    @staticmethod
    def _mime_for(vtype, url):
        vtype = (vtype or "").lower()
        url = (url or "").lower()
        if vtype == "mp4" or ".mp4" in url:
            return "video/mp4"
        if vtype == "flv" or ".flv" in url:
            return "video/x-flv"
        # 默认按 HLS 处理 (m3u8 / 无后缀的 m3u8 直链)
        return "application/vnd.apple.mpegurl"

    def _resolve_parser(self, parser_url):
        """解析第三方解析器页面, 提取内嵌直链; 返回 (直链, 类型), 取不到 ("", "")。"""
        if not parser_url or not parser_url.startswith("http"):
            return "", ""
        page = self._fetch(parser_url, referer=self.site_url + "/")
        if not page:
            return "", ""
        md = _RE_PLAYER_DATA.search(page)
        if md:
            try:
                import html as _html
                data = json.loads(_html.unescape(md.group(1)))
                if isinstance(data, dict) and data.get("url"):
                    return data["url"].strip(), (data.get("type") or "")
            except Exception:
                pass
        mm = _RE_DIRECT_MEDIA.search(page)
        if mm:
            return mm.group(0).replace("&amp;", "&"), ""
        return "", ""

    def playerContent(self, flag, id, vipFlags=""):
        # id 形态: "{sourceIndex}:{watchPath}"
        source_idx, watch_path = "1", ""
        if ":" in str(id):
            source_idx, watch_path = str(id).split(":", 1)
        else:
            watch_path = str(id)
        if not source_idx:
            source_idx = "1"

        watch_url = self._fix_url(watch_path)
        if "source=" not in watch_url:
            sep = "&" if "?" in watch_url else "?"
            watch_url = "%s%ssource=%s" % (watch_url, sep, source_idx)

        html = self._fetch(watch_url)
        mu = _RE_PLAYER_URL.search(html)
        parser_url = ""
        if mu:
            import html as _html
            parser_url = urllib.parse.unquote(_html.unescape(mu.group(1)))

        if parser_url:
            direct, vtype = self._resolve_parser(parser_url)
            if direct:
                return {"parse": 0, "playUrl": "", "url": direct,
                        "format": self._mime_for(vtype, direct),
                        "header": {"User-Agent": UA, "Referer": parser_url}}
            # 解析器页面无内嵌直链 (如 m3u8 类解析器需浏览器环境), 交播放器打开 iframe 嗅探
            return {"parse": 1, "playUrl": "", "url": parser_url,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        # 兜底: 交播放器打开播放页自行嗅探
        return {"parse": 1, "playUrl": "", "url": watch_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    # ---------- 其他契约 ----------

    def localProxy(self, param):
        try:
            import urllib.request as _u
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
            req = _u.Request(self._fix_url(url), headers=self.headers)
            with _u.urlopen(req, timeout=15) as rsp:
                content = rsp.read()
                ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

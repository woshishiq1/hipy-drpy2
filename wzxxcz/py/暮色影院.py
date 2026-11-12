# coding=utf-8
"""
暮色影院 msyy.tv | TVBox Python 爬虫 (V1.0)
站点：MacCMS V10 + ds3 主题

关键点（全部经真实抓包验证）：
  1. 列表/筛选不在 HTML 里，由 /index.php/api/vod 动态返回；
     该接口为 POST，必须带签名：key = md5("DS" + time + "DCC147D11943AF75")
  2. 参数与网页完全一致：type / class / area / year / lang / version / state / letter / by / page
     （分类=子频道 type_id，类型=class，地区=area，年份=year，语言=lang，排序=by: time|hits|score）
  3. 详情页 HTML 提供：标题、备注、导演、演员、评分、年份/地区/类型、简介、
     线路名+顺序（.anthology-tab）、剧集名+顺序（.anthology-list-play）
  4. 播放页 /play/{vid}/{sid}/{nid}.html 内含 var player_aaaa={...}，encrypt=0 时 url 即真实 m3u8
  5. 官方 JSON 接口 /api.php/provide/vod/ 用作副标题(vod_sub)+直链 m3u8 的来源与全链路兜底
  6. 简介统一加上 INTRO_PREFIX 前缀
"""
import re
import sys
import json
import time
import hashlib
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
            if getattr(self, "_session", None) is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 20)
            method = kw.pop('method', 'get')
            data = kw.pop('data', None)
            if method.lower() == 'post':
                r = self._sess.post(url, data=data, headers=headers,
                                    timeout=timeout, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[msyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.msyy.tv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/upload/site/20250804-1/c03011f61dce868d6d17ae1d017e8fab.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 列表接口签名密钥（抓包取自站点 /static/ds3/js/ecscript.js 的 Md5('DS'+time+密钥)）
API_SECRET = "DCC147D11943AF75"

# ===================== 分类（与站点顶部导航顺序一致） =====================
CLASSES = [
    {"type_id": "63",  "type_name": "电影"},
    {"type_id": "64",  "type_name": "电视剧"},
    {"type_id": "66",  "type_name": "综艺"},
    {"type_id": "65",  "type_name": "动漫"},
    {"type_id": "67",  "type_name": "短剧"},
    {"type_id": "68",  "type_name": "纪录片"},
    {"type_id": "127", "type_name": "体育赛事"},
]

# 子分类（点“分类”即切换到对应 type_id，和站点行为一致）
_SUB = {
    "63": [("剧情片", "70"), ("动作片", "71"), ("喜剧片", "73"), ("科幻片", "81"),
           ("恐怖片", "75"), ("惊悚片", "77"), ("爱情片", "79"),
           ("动画电影", "83"), ("战争片", "94")],
    "64": [("国产剧", "84"), ("港剧", "85"), ("韩剧", "86"), ("日剧", "87"),
           ("泰剧", "88"), ("台剧", "89"), ("欧美剧", "90"), ("其他剧", "92")],
    "65": [("欧美动漫", "117"), ("日韩动漫", "118"), ("国产动漫", "120"),
           ("其他动漫", "123")],
    "66": [("大陆综艺", "97"), ("港台综艺", "98"), ("日韩综艺", "100"),
           ("欧美综艺", "102")],
    "67": [("重生民国", "110"), ("穿越现代", "105"), ("反转爽剧", "106"),
           ("言情总裁", "107"), ("现代都市", "108"), ("古装仙侠", "109"),
           ("悬疑烧脑", "111")],
    "127": [("篮球", "128"), ("足球", "129"), ("网球", "130"), ("斯诺克", "131")],
}

# 类型（class）
_TYPES = ["动作", "奇幻", "古装", "历史", "喜剧", "科幻", "恐怖", "悬疑",
          "犯罪", "爱情", "都市", "剧情", "战争"]

# 地区（area）
_AREAS = ["中国大陆", "中国香港", "中国台湾", "美国", "英国", "法国",
          "意大利", "德国", "日本", "韩国", "泰国"]

# 语言（lang）
_LANGS = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]

# 年份（year）
_YEARS = [str(y) for y in range(2026, 2004, -1)]

# 排序（by）
_SORTS = [("最新", "time"), ("最热", "hits"), ("评分", "score")]


def _opt(pairs):
    return [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in pairs]


_FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    flt = []
    if _SUB.get(tid):
        flt.append({"key": "sub", "name": "分类", "value": _opt(_SUB[tid])})
    if tid in ("64", "65"):
        flt.append({"key": "class", "name": "类型",
                    "value": _opt([(x, x) for x in _TYPES])})
    if tid in ("63", "68"):
        flt.append({"key": "area", "name": "地区",
                    "value": _opt([(x, x) for x in _AREAS])})
    if tid == "68":
        flt.append({"key": "lang", "name": "语言",
                    "value": _opt([(x, x) for x in _LANGS])})
    if tid in ("63", "64", "65", "66"):
        flt.append({"key": "year", "name": "年份",
                    "value": _opt([(x, x) for x in _YEARS])})
    flt.append({"key": "by", "name": "排序",
                "value": [{"n": n, "v": v} for n, v in _SORTS]})
    _FILTERS[tid] = flt

FILTERS = _FILTERS


# ===================== 正则 =====================
# 列表卡片（首页 / 分类页 HTML 通用）
_RE_CARD = re.compile(
    r'<div class="public-list-box[^"]*">\s*'
    r'<div class="public-list-div[^"]*">\s*'
    r'<a[^>]*href="(/vod/(\d+)\.html)"[^>]*?(?:title="([^"]*)")?[^>]*>'
    r'([\s\S]*?)</a>'
    r'([\s\S]*?)</div>\s*</div>', re.S | re.I)
_RE_PRB = re.compile(r'<span class="public-list-prb[^"]*">([^<]*)</span>', re.I)
_PIC_ATTRS = ("data-src", "data-original", "data-echo", "src")


def _pick_pic(body):
    """卡片里 src 常是 base64 占位图，真实地址在 data-src"""
    for attr in _PIC_ATTRS:
        for mt in re.finditer(attr + r'="([^"]+)"', body, re.I):
            u = mt.group(1).strip()
            if u and not u.startswith("data:"):
                return u
    return ""
_RE_SUB_TITLE = re.compile(
    r'<div class="public-list-subtitle[^"]*">([\s\S]*?)</div>', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="slide-info-title">([\s\S]*?)</h1>', re.I)
_RE_REMARKS = re.compile(r'备注\s*[:：]\s*</strong>([\s\S]*?)</div>', re.I)
_RE_DIRECTOR = re.compile(r'导演\s*[:：]\s*</strong>([\s\S]*?)</div>', re.I)
_RE_ACTOR = re.compile(r'演员\s*[:：]\s*</strong>([\s\S]*?)</div>', re.I)
_RE_SCORE = re.compile(r'<div class="fraction">\s*([\d.]+)\s*</div>', re.I)
_RE_SCORE_NUM = re.compile(r'(\d+)\s*次评分', re.I)
_RE_META_ITEM = re.compile(
    r'<span class="slide-info-remarks">([\s\S]*?)</span>', re.I)
_RE_INTRO = re.compile(r'<div id="height_limit"[^>]*>([\s\S]*?)</div>', re.I)
_RE_OG_DESC = re.compile(
    r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', re.I)
_RE_PIC = re.compile(
    r'<div class="detail-pic">[\s\S]*?(?:data-src|src)="([^"]+)"', re.I)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', re.I)

# 线路 tab / 剧集列表
_RE_TAB_BOX = re.compile(
    r'<div class="anthology-tab[^"]*">([\s\S]*?)</div>\s*<div class="anthology-list',
    re.I)
_RE_TAB = re.compile(r'<a class="swiper-slide"[^>]*>([\s\S]*?)</a>', re.I)
_RE_BADGE = re.compile(r'<span class="badge">[\s\S]*?</span>', re.I)
_RE_EP_UL = re.compile(
    r'<ul class="anthology-list-play[^"]*">([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页
_RE_PLAYER = re.compile(r'var player_aaaa=(\{[\s\S]*?\})\s*</script>', re.I)

# 线路代码 -> 中文名（HTML 无线路名时兜底）
_FROM_ALIAS = {
    "rym3u8": "如意M3U8", "bfzym3u8": "暴风资源", "lzm3u8": "量子M3U8",
    "wjm3u8": "无尽M3U8", "ffm3u8": "非凡M3U8", "kym3u8": "快云M3U8",
    "tkm3u8": "天空M3U8", "sdm3u8": "闪电M3U8", "hhm3u8": "豪华M3U8",
    "dbm3u8": "豆瓣M3U8", "modum3u8": "魔都M3U8", "jsm3u8": "极速M3U8",
}


class Spider(Spider):

    def getName(self):
        return "暮色影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.secret = self.extend.get("secret") or API_SECRET
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.ajax_headers = dict(self.headers)
        self.ajax_headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.site_url,
        })
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._detail_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ------------------------------------------------------------------ 基础
    def _sign(self):
        ts = int(time.time())
        key = hashlib.md5(("DS" + str(ts) + self.secret).encode()).hexdigest()
        return ts, key

    def _post(self, url, data, headers=None, timeout=25):
        h = dict(self.ajax_headers)
        if headers:
            h.update(headers)

        # 1) 优先 requests（TVBox python 内核自带），保证是真正的 POST
        try:
            import requests
            r = requests.post(url, data=data, headers=h, timeout=timeout,
                              verify=False)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception as e:
            self.log("requests.post 不可用: %s" % e)

        # 2) 退化为内核 fetch
        try:
            rsp = self.fetch(url, headers=h, timeout=timeout,
                             method="post", data=data)
            return self._text(rsp)
        except Exception as e:
            self.log("POST FAIL %s -> %s" % (url, e))
            return ""

    def _get(self, url, headers=None, timeout=25):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            return self._text(rsp)
        except Exception as e:
            self.log("GET FAIL %s -> %s" % (url, e))
            return ""

    def _text(self, rsp):
        if rsp is None:
            return ""
        if hasattr(rsp, "text"):
            return rsp.text or ""
        if hasattr(rsp, "content"):
            try:
                return rsp.content.decode("utf-8", "ignore")
            except Exception:
                return ""
        return str(rsp)

    def _json(self, text):
        if not text:
            return {}
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return {}

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return self.site_url + "/" + url

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

    # -------------------------------------------------------- 列表（ajax 签名接口）
    def _api_list(self, tid, page, extend=None):
        """POST /index.php/api/vod —— 与站点 JS 完全一致的列表接口"""
        extend = extend or {}
        data = {
            "type": str(tid),
            "class": extend.get("class") or "",
            "area": extend.get("area") or "",
            "year": extend.get("year") or "",
            "lang": extend.get("lang") or "",
            "version": extend.get("version") or "",
            "state": extend.get("state") or "",
            "letter": extend.get("letter") or "",
            "by": extend.get("by") or "time",
            "page": str(page),
        }
        ts, key = self._sign()
        data["time"] = str(ts)
        data["key"] = key
        url = self.site_url + "/index.php/api/vod"
        for attempt in (1, 2):
            txt = self._post(url, data, headers={
                "Referer": "%s/vodshow/id/%s.html" % (self.site_url, tid)})
            js = self._json(txt)
            if js and js.get("code") == 1:
                return js
            self.log("api_list 失败(%d): %s" % (attempt, txt[:120]))
            if attempt == 1:
                time.sleep(1)
                ts, key = self._sign()
                data["time"] = str(ts)
                data["key"] = key
        return None

    def _api_list_fallback(self, tid, page):
        """兜底：/index.php/ajax/data（不支持筛选，仅按频道分页）"""
        url = ("%s/index.php/ajax/data?mid=1&tid=%s&page=%d&limit=20"
               % (self.site_url, tid, page))
        js = self._json(self._get(url, headers={"Referer": self.site_url + "/"}))
        if js and js.get("list"):
            return js
        return None

    def _videos_from_api(self, js):
        out = []
        for it in (js.get("list") or []):
            vid = it.get("vod_id")
            if vid in (None, ""):
                continue
            pic = it.get("vod_pic") or it.get("vod_pic_thumb") or ""
            sub = self._clean(it.get("vod_sub") or "")
            out.append({
                "vod_id": str(vid),
                "vod_name": self._clean(it.get("vod_name") or ""),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(it.get("vod_remarks") or "") or sub,
            })
        return out

    # -------------------------------------------------------- HTML 卡片解析
    def _videos_from_html(self, html, limit=0):
        out, seen = [], set()
        if not html:
            return out
        for m in _RE_CARD.finditer(html):
            href, vid, title = m.group(1), m.group(2), m.group(3)
            body, tail = m.group(4), m.group(5)
            if vid in seen:
                continue
            seen.add(vid)
            pic = _pick_pic(body)
            name = self._clean(title or "")
            if not name:
                alt = re.search(r'alt="([^"]*)"', body)
                name = self._clean(alt.group(1)) if alt else ""
                name = re.sub(r"封面图$", "", name).strip()
            if not name:
                m2 = re.search(r'<a[^>]*class="time-title[^"]*"[^>]*>([\s\S]*?)</a>',
                               tail)
                name = self._clean(m2.group(1)) if m2 else vid
            prb = _RE_PRB.search(body) or _RE_PRB.search(tail)
            sub = _RE_SUB_TITLE.search(tail)
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(prb.group(1)) if prb else "",
                "_sub": self._clean(sub.group(1)) if sub else "",
            })
            if limit and len(out) >= limit:
                break
        return out

    # -------------------------------------------------------- 首页
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._get(self.site_url + "/")
        self.log("home HTML: %d" % len(html))
        videos = self._videos_from_html(html, limit=60)
        if not videos:
            js = self._api_list("63", 1)
            if js:
                videos = self._videos_from_api(js)
        for v in videos:
            v.pop("_sub", None)
        return {"list": videos}

    # -------------------------------------------------------- 分类 + 筛选
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = dict(extend or {})
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        # “分类”= 切换子频道（站点点击分类即跳转到子频道页面）
        real_tid = str(extend.pop("sub", "") or tid)
        if not str(real_tid).isdigit():
            real_tid = str(tid)

        js = self._api_list(real_tid, page, extend)
        pagecount = 1
        if js:
            videos = self._videos_from_api(js)
            try:
                pagecount = int(js.get("pagecount") or 1)
            except Exception:
                pagecount = 1
            total = js.get("total") or pagecount * 40
        else:
            js2 = self._api_list_fallback(real_tid, page)
            videos = self._videos_from_api(js2) if js2 else []
            try:
                pagecount = int((js2 or {}).get("pagecount") or 1)
            except Exception:
                pagecount = 1
            total = pagecount * 20
            # 年份筛选兜底：官方 JSON 接口
            if extend.get("year") and not videos:
                js3 = self._json(self._get(
                    "%s/api.php/provide/vod/?ac=list&t=%s&year=%s&pg=%d"
                    % (self.site_url, real_tid, extend["year"], page)))
                if js3:
                    videos = self._videos_from_api(js3)
                    pagecount = int(js3.get("pagecount") or 1)
                    total = js3.get("total") or 0

        self.log("category tid=%s page=%d -> %d 条 / %d 页"
                 % (real_tid, page, len(videos), pagecount))
        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": 40, "total": total}

    # -------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        word = urllib.parse.quote(key)
        url = ("%s/api.php/provide/vod/?ac=videolist&wd=%s&pg=%d"
               % (self.site_url, word, page))
        js = self._json(self._get(url))
        videos = self._videos_from_api(js) if js else []
        if not videos:
            js = self._json(self._get(
                "%s/api.php/provide/vod/?ac=list&wd=%s&pg=%d"
                % (self.site_url, word, page)))
            videos = self._videos_from_api(js) if js else []
        pagecount = int((js or {}).get("pagecount") or 1)
        self.log("search %s -> %d 条" % (key, len(videos)))
        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": 40, "total": (js or {}).get("total") or 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # -------------------------------------------------------- 详情
    def _api_detail(self, vid):
        if vid in self._detail_cache:
            return self._detail_cache[vid]
        js = self._json(self._get(
            "%s/api.php/provide/vod/?ac=detail&ids=%s" % (self.site_url, vid)))
        one = {}
        for it in (js.get("list") or []):
            if str(it.get("vod_id")) == str(vid):
                one = it
                break
        if one:
            self._detail_cache[vid] = one
        return one

    def _parse_detail_html(self, html):
        d = {}
        m = _RE_H1.search(html)
        d["name"] = self._clean(m.group(1)) if m else ""

        m = _RE_REMARKS.search(html)
        d["remarks"] = self._clean(m.group(1)) if m else ""

        def _names(p):
            m = p.search(html)
            if not m:
                return ""
            block = m.group(1)
            links = [self._clean(x) for x in
                     re.findall(r'<a[^>]*>([\s\S]*?)</a>', block)]
            links = [x for x in links if x]
            return ", ".join(links) if links else self._clean(block)

        d["director"] = _names(_RE_DIRECTOR)
        d["actor"] = _names(_RE_ACTOR)

        m = _RE_SCORE.search(html)
        d["score"] = m.group(1) if m else ""
        m = _RE_SCORE_NUM.search(html)
        d["score_num"] = m.group(1) if m else ""

        metas = [self._clean(x) for x in _RE_META_ITEM.findall(html)]
        metas = [x for x in metas if x]
        d["year"] = metas[0] if len(metas) > 0 else ""
        d["area"] = metas[1] if len(metas) > 1 else ""
        d["class"] = " ".join(metas[2:]) if len(metas) > 2 else ""

        m = _RE_INTRO.search(html)
        d["intro"] = self._clean(m.group(1)) if m else ""
        if not d["intro"]:
            m = _RE_OG_DESC.search(html)
            d["intro"] = self._clean(m.group(1)) if m else ""

        m = _RE_PIC.search(html)
        pic_url = _pick_pic(m.group(0)) if m else ""
        if not pic_url:
            m2 = _RE_OG_IMG.search(html)
            pic_url = m2.group(1) if m2 else ""
        d["pic"] = self._fix_url(pic_url)

        # 线路名（顺序即站点展示顺序）
        tabs = []
        m = _RE_TAB_BOX.search(html)
        if m:
            for x in _RE_TAB.findall(m.group(1)):
                x = _RE_BADGE.sub("", x)
                x = self._clean(x)
                if x:
                    tabs.append(x)
        d["tabs"] = tabs

        # 每条线路的剧集（顺序即站点展示顺序）
        # 按 .anthology-list-box 的位置逐块取，空线路也占位，保证与线路 tab 一一对应
        groups = []
        chunks = html.split('<div class="anthology-list-box')
        if len(chunks) > 1:
            for chunk in chunks[1:]:
                m = re.search(r'<ul class="anthology-list-play[^"]*">([\s\S]*?)</ul>',
                              chunk, re.I)
                eps = []
                if m:
                    for href, nm in _RE_EP_A.findall(m.group(1)):
                        href = href.replace("&amp;", "&")
                        if "/play/" not in href:
                            continue
                        eps.append((self._clean(nm), self._fix_url(href)))
                groups.append(eps)
        else:
            for ul in _RE_EP_UL.findall(html):
                eps = []
                for href, nm in _RE_EP_A.findall(ul):
                    href = href.replace("&amp;", "&")
                    if "/play/" not in href:
                        continue
                    eps.append((self._clean(nm), self._fix_url(href)))
                groups.append(eps)
        d["groups"] = groups
        return d

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = str(ids[0])
        vid = re.search(r"/vod/(\d+)\.html", raw)
        vid = vid.group(1) if vid else re.sub(r"\D", "", raw)
        if not vid:
            return {"list": []}

        url = "%s/vod/%s.html" % (self.site_url, vid)
        html = self._get(url, headers={"Referer": self.site_url + "/"})
        self.log("detail %s HTML=%d" % (vid, len(html)))
        if not html:
            return {"list": []}

        d = self._parse_detail_html(html)
        api = self._api_detail(vid)

        # 名称 / 封面
        name = d["name"] or self._clean((api or {}).get("vod_name") or "") or vid
        pic = d["pic"] or self._fix_url((api or {}).get("vod_pic") or "") \
            or self.default_pic

        # 副标题（站点卡片上的副标题，取自同库 JSON 接口）
        sub = self._clean((api or {}).get("vod_sub") or "")

        # 简介 = 指定前缀 + 副标题 + 正文
        body = d["intro"] or self._clean((api or {}).get("vod_content") or "")
        body = re.sub(r"<[^>]+>", "", body)
        parts = [INTRO_PREFIX]
        if sub:
            parts.append("又名：%s" % sub)
        if body:
            parts.append(body)
        content = "\n".join(parts)

        remarks = d["remarks"] or self._clean((api or {}).get("vod_remarks") or "")
        if not remarks:
            remarks = sub or ("%d条线路" % len(d["groups"]))

        actor = d["actor"] or self._clean((api or {}).get("vod_actor") or "")
        director = d["director"] or self._clean((api or {}).get("vod_director") or "")

        # ---------------- 线路 & 剧集 ----------------
        # API 侧：线路（按站点顺序）+ 直链 m3u8
        api_from = []
        api_urls = []
        if api:
            api_from = [x for x in (api.get("vod_play_from") or "").split("$$$") if x]
            api_urls = [x for x in (api.get("vod_play_url") or "").split("$$$") if x]

        def _split_eps(s):
            out = []
            for seg in (s or "").split("#"):
                if not seg:
                    continue
                if "$" in seg:
                    n, u = seg.split("$", 1)
                else:
                    n, u = "正片", seg
                out.append((n.strip(), u.strip()))
            return out

        play_from, play_url = [], []
        groups = d["groups"]
        tabs = d["tabs"]
        used_names = set()

        for i, eps in enumerate(groups):
            if not eps:
                continue
            # 线路名：优先站点 tab 名，其次接口代码转中文
            fname = tabs[i] if i < len(tabs) else ""
            if not fname:
                code = api_from[i] if i < len(api_from) else ""
                fname = _FROM_ALIAS.get(code, code) or ("线路%d" % (i + 1))
            fname = "%s" % fname
            # 同名线路会导致 TVBox 合并 tab，补序号区分
            if fname in used_names:
                fname = "%s%d" % (fname, i + 1)
            used_names.add(fname)

            # 剧集直链：接口线路与站点线路条数一致时取 m3u8 直链（同顺序）
            use_api = False
            api_eps = _split_eps(api_urls[i]) if i < len(api_urls) else []
            if api_eps and len(api_eps) == len(eps):
                use_api = True

            items = []
            for j, (nm, link) in enumerate(eps):
                if use_api:
                    u = api_eps[j][1]
                    if u and u.startswith("http"):
                        items.append("%s$%s" % (nm or api_eps[j][0], u))
                        continue
                items.append("%s$%s" % (nm or ("第%d集" % (j + 1)), link))
            play_from.append(fname)
            play_url.append("#".join(items))

        if not play_from:
            # 详情页无剧集时退回接口数据
            for i, code in enumerate(api_from):
                eps = _split_eps(api_urls[i]) if i < len(api_urls) else []
                if not eps:
                    continue
                play_from.append(_FROM_ALIAS.get(code, code) or ("线路%d" % (i + 1)))
                play_url.append("#".join("%s$%s" % (n, u) for n, u in eps))

        if not play_from:
            return {"list": []}

        self.log("  lines=%s eps=%s" % (play_from, [len(x.split('#')) for x in play_url]))

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": d["score"] or str((api or {}).get("vod_score") or ""),
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        if d["year"]:
            vod["vod_year"] = d["year"]
        if d["area"]:
            vod["vod_area"] = d["area"]
        if d["class"]:
            vod["vod_class"] = d["class"]
        return {"list": [vod]}

    # -------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        pid = (id or "").strip()
        now = int(time.time())
        if pid in self._play_cache:
            ts, res = self._play_cache[pid]
            if now - ts < 600:
                return res

        # 已是直链
        if pid.startswith("http") and (".m3u8" in pid.lower() or ".mp4" in pid.lower()):
            return {"parse": 0, "playUrl": "", "url": pid,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        play_page = pid if pid.startswith("http") else self._fix_url(pid)
        self.log("player: %s" % play_page)

        url = ""
        encrypt = 0
        frm = ""
        if play_page:
            html = self._get(play_page, headers={"Referer": self.site_url + "/"})
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    p = json.loads(m.group(1))
                    url = (p.get("url") or "").strip()
                    frm = p.get("from") or ""
                    try:
                        encrypt = int(p.get("encrypt") or 0)
                    except Exception:
                        encrypt = 0
                except Exception as e:
                    self.log("player_aaaa 解析失败: %s" % e)

        if url and encrypt == 0 and url.startswith("http"):
            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {"User-Agent": UA,
                           "Referer": self.site_url + "/",
                           "Origin": self.site_url},
            }
            self._play_cache[pid] = (now, res)
            self.log("  => %s [%s]" % (url[:140], frm))
            return res

        # 兜底：交给 TVBox 嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[pid] = (now, res)
        self.log("  => 交解析: %s" % play_page)
        return res

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

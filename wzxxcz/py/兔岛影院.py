# coding=utf-8
"""
兔岛影院 ct0592.com | TVBox Python 爬虫 
关键:
  - MacCMS10 模板(free 资源站)，路径 ct0list / ct0vod / ct0player
  - 桌面 UA 会被 WAF 直接掐断(TCP 空响应)，必须使用移动端 UA
  - 播放页 inline script 里 var now="xxx.m3u8" 即真实地址，直链播放
  - 详情页多线路（秒播/量子/U酷/索尼），按线路分组，集数正序
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
                print("[tudao]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.ct0592.com"

# 站点 WAF：桌面 UA 一律空响应，只能走移动端 UA
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
      "Mobile/15E148 Safari/604.1")
MOBILE_UA = UA

DEFAULT_PIC = HOST + "/templets/ct0592/images/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
    {"type_id": "yugao",     "type_name": "预告"},
]

# 分类名 -> 站点 tid (站点 /ct0list/N.html 的真实 ID)
_TID_MAP = {
    "dianying":  1,
    "dianshiju": 2,
    "zongyi":    3,
    "dongman":   4,
    "duanju":    30,
    "yugao":     55,
}

# 子分类（站点「按分类」筛选，直接跳转 /ct0list/N.html）
_SUB_CLASS = {
    "dianying": [("动作片", 5), ("爱情片", 6), ("科幻片", 7), ("恐怖片", 8),
                 ("战争片", 9), ("喜剧片", 10), ("纪录片", 11), ("剧情片", 12),
                 ("悬疑片", 28), ("犯罪片", 29)],
    "dianshiju": [("国产剧", 13), ("港剧", 14), ("欧美剧", 15), ("韩剧", 16),
                  ("台湾剧", 32), ("日本剧", 33), ("海外剧", 34), ("泰剧", 42),
                  ("亚洲剧", 60)],
    "zongyi": [("国产综艺", 45), ("日韩综艺", 46), ("港台综艺", 47),
               ("欧美综艺", 48)],
    "dongman": [("国产动漫", 49), ("日韩动漫", 50), ("欧美动漫", 51),
                ("动漫电影", 52), ("港台动漫", 53), ("海外动漫", 54),
                ("有声动漫", 61)],
    "duanju": [("女频恋爱", 62), ("反转爽剧", 63), ("脑洞悬疑", 64),
               ("年代穿越", 65), ("古装仙侠", 66), ("现代都市", 67),
               ("爽文短剧", 69)],
    "yugao": [],
}

# 地区 / 年份：站点实际取值（search.php?searchtype=5&area=/year=）
_AREAS = [
    ("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
    ("日本", "日本"), ("韩国", "韩国"), ("欧美", "欧美"), ("泰国", "泰国"),
    ("其他", "其他"),
]

_YEARS = ([{"n": "全部", "v": ""}] +
          [{"n": str(y), "v": str(y)} for y in range(2026, 2012, -1)])

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = _SUB_CLASS.get(tid, [])
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": str(i)} for n, i in subs]},
        {"key": "area", "name": "地区",
         "value": [{"n": n, "v": v} for n, v in _AREAS]},
        {"key": "year", "name": "年份", "value": _YEARS},
    ]


# ===================== 正则 =====================
# 列表卡片：/ct0vod/123.html + title + data-original + 备注
_RE_CARD = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*'
    r'href="(/ct0vod/\d+\.html)"[^>]*'
    r'title="([^"]*)"[^>]*'
    r'data-original="([^"]*)"[^>]*>'
    r'([\s\S]{0,400}?)</a>',
    re.S | re.I)

_RE_CLASS_TAG = re.compile(
    r'<span class="pic-tag[^"]*">\s*([\d.]+)\s*分\s*</span>', re.I)
_RE_PIC_TEXT = re.compile(
    r'<span class="pic-text[^"]*">\s*([^<]*?)\s*</span>', re.I)

# 兜底：只有 href + title 的卡片
_RE_CARD_LOOSE = re.compile(
    r'href="(/ct0vod/\d+\.html)"[^>]*title="([^"]*)"', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)
_RE_SCORE = re.compile(r'<span class="score[^"]*">\s*([\d.]+)\s*</span>', re.I)
_RE_PIC = re.compile(
    r'class="[^"]*stui-content__thumb[^"]*"[\s\S]{0,600}?'
    r'data-original="([^"]+)"', re.I)
_RE_PIC_ANY = re.compile(
    r'data-original="(https?://[^"]+)"', re.I)
# 占位图（懒加载 gif），不能当封面
_RE_PLACEHOLDER = re.compile(r'/img/load\.gif|/img/lazy|blank\.gif', re.I)

# 简介：detail-content（完整）优先，其次 detail-sketch（截断）
_RE_DESC_FULL = re.compile(
    r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_DESC_SHORT = re.compile(
    r'<span class="detail-sketch"[^>]*>([\s\S]*?)</span>', re.I)

# 元信息：类型 / 地区 / 年份 / 主演 / 导演 / 更新
_RE_TYPE = re.compile(
    r'<span class="text-muted">类型：</span>\s*<a[^>]*>([^<]*)</a>', re.I)
_RE_AREA = re.compile(
    r'<span class="text-muted[^"]*">地区：</span>\s*<a[^>]*>([^<]*)</a>', re.I)
_RE_YEAR = re.compile(
    r'<span class="text-muted[^"]*">年份：</span>\s*<a[^>]*>([^<]*)</a>', re.I)
_RE_ACTOR = re.compile(
    r'<span class="text-muted">主演：</span>([\s\S]*?)</p>', re.I)
_RE_DIRECTOR = re.compile(
    r'<span class="text-muted">导演：</span>([\s\S]*?)</p>', re.I)
_RE_UPDATED = re.compile(
    r'<span class="text-muted">更新：</span>\s*([\d\-: ]+)', re.I)
_RE_REMARK = re.compile(
    r'<span class="pic-text[^"]*">\s*([^<]*?)\s*</span>', re.I)

# 线路面板：<h3 class="title">线路名</h3> ... <ul class="stui-content__playlist">
_RE_PANEL = re.compile(
    r'<div class="stui-pannel stui-pannel-bg clearfix">'
    r'([\s\S]*?)</div>\s*</div>\s*</div>', re.S)

_RE_PANEL_TITLE = re.compile(r'<h3 class="title">\s*([^<]*?)\s*</h3>', re.I)
_RE_PLAYLIST = re.compile(
    r'<ul class="([^"]*stui-content__playlist[^"]*)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP = re.compile(
    r'<a[^>]*title="([^"]*)"[^>]*href="(/ct0player/[^"]+)"', re.I)

# 播放页
_RE_PLAYER_VAR = re.compile(
    r'<script>\s*var\s+vid=.*?</script>', re.S)
_RE_NOW = re.compile(r'var\s+now\s*=\s*"([^"]*)"')
_RE_PN = re.compile(r'var\s+pn\s*=\s*"([^"]*)"')
_RE_VFROM = re.compile(r'var\s+vfrom\s*=\s*"([^"]*)"')

# 分页
_RE_NUM = re.compile(r'class="num">\s*(\d+)\s*/\s*(\d+)\s*<')
_RE_TAIL = re.compile(r'/ct0list/\d+-(\d+)\.html')
_RE_TOTAL = re.compile(r'共有“?(\d+)”?部影片')

# iframe 播放器（兜底嗅探用）
_RE_IFRAME = re.compile(r'<iframe[^>]*src="([^"]+)"', re.I)

_LINE_PRIORITY = ["秒播", "极速", "量子", "U酷", "索尼", "优酷", "魔都", "茅台"]


class Spider(Spider):

    def getName(self):
        return "兔岛影院"

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
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础 ----------------
    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text or ""
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

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        # 只取主列表区，避开侧栏排行榜的重复卡片
        start = 0
        m = re.search(r'<ul class="[^"]*stui-vodlist(?:__media)?[^"]*"', html)
        if m:
            start = m.start()
        body = html[start:]

        # 卡片：<a class="stui-vodlist__thumb" href title data-original>…</a>
        for m in re.finditer(
                r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>',
                body, re.I):
            tag = m.group(0)
            href_m = re.search(r'href="(/ct0vod/\d+\.html)"', tag)
            if not href_m:
                continue
            href = href_m.group(1)
            if href in seen:
                continue
            seen.add(href)

            alt_m = re.search(r'title="([^"]*)"', tag)
            alt = self._clean(alt_m.group(1)) if alt_m else ""

            pic_m = re.search(r'data-original="([^"]*)"', tag)
            if not pic_m:
                pic_m = re.search(r'src="([^"]*)"', tag)
            pic = self._fix_url(pic_m.group(1)) if pic_m else ""

            # 卡片内的备注 / 评分
            seg = body[m.end():m.end() + 500]
            rm = _RE_PIC_TEXT.search(seg)
            remarks = self._clean(rm.group(1)) if rm else ""
            if not remarks:
                sm = _RE_CLASS_TAG.search(seg)
                if sm:
                    remarks = sm.group(1) + "分"

            videos.append({
                "vod_id":      href,
                "vod_name":    alt or href,
                "vod_pic":     pic or self.default_pic,
                "vod_remarks": remarks,
            })

        self.log("  卡片: %d 条" % len(videos))

        if videos:
            return videos

        # 兜底：href + title
        for href, alt in _RE_CARD_LOOSE.findall(body):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt) or href,
                "vod_pic":     self.default_pic,
                "vod_remarks": "",
            })
        self.log("  兜底: %d 条" % len(videos))
        return videos

    def _page_count(self, html, per_page=30):
        if not html:
            return 1
        m = _RE_NUM.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        tails = _RE_TAIL.findall(html)
        if tails:
            try:
                return max(int(t) for t in tails)
            except Exception:
                pass
        m = _RE_TOTAL.search(html)
        if m:
            try:
                return (int(m.group(1)) + per_page - 1) // per_page
            except Exception:
                pass
        return 1

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    # ---------------- 分类 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
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

        # extend["class"] 是站点子分类 tid，命中后直接走 /ct0list/N.html
        real_tid = _TID_MAP.get(str(tid), 1)
        sub = str(extend.get("class") or "").strip()
        if sub.isdigit():
            real_tid = int(sub)

        area = (extend.get("area") or "").strip()
        year = (extend.get("year") or "").strip()

        if area or year:
            # 高级搜索：?page=N（1 基）
            params = [("searchtype", "5"), ("tid", str(real_tid))]
            if area:
                params.append(("area", area))
            if year:
                params.append(("year", year))
            params.append(("page", str(page)))
            url = "%s/search.php?%s" % (self.site_url,
                                        urllib.parse.urlencode(params))
        else:
            # 普通分类：/ct0list/N.html 或 /ct0list/N-2.html
            if page <= 1:
                url = "%s/ct0list/%d.html" % (self.site_url, real_tid)
            else:
                url = "%s/ct0list/%d-%d.html" % (self.site_url, real_tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        url = "%s/search.php?%s" % (
            self.site_url,
            urllib.parse.urlencode({"searchword": key, "page": page}))
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 30, "total": 999,
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
            name = self._clean(re.sub(r'<span[^>]*>[\s\S]*?</span>', "",
                                      m.group(1)))
        if not name:
            m = _RE_H1_ANY.search(html)
            if m:
                name = self._clean(re.sub(r'<span[^>]*>[\s\S]*?</span>', "",
                                          m.group(1)))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("-")[0]
                                    .split("_")[0].replace("《", "")
                                    .replace("》", ""))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 封面（站点是 lazyload，src 是占位 gif，真图在 data-original）
        pic = ""
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic or _RE_PLACEHOLDER.search(pic):
            for cand in _RE_PIC_ANY.findall(html):
                cand = self._fix_url(cand)
                if cand and not _RE_PLACEHOLDER.search(cand) \
                        and "templets/" not in cand:
                    pic = cand
                    break
        if _RE_PLACEHOLDER.search(pic or "") or "templets/" in (pic or ""):
            pic = ""
        pic = pic or self.default_pic

        # 简介（优先完整版 detail-content）
        content = ""
        m = _RE_DESC_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC_SHORT.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                          html, re.I)
            if m:
                content = self._clean(m.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 元信息
        def _one(rx, src=html):
            mm = rx.search(src)
            return self._clean(mm.group(1)) if mm else ""

        vod_type = _one(_RE_TYPE)
        area = _one(_RE_AREA)
        year = _one(_RE_YEAR)
        updated = _one(_RE_UPDATED)

        # 演员/导演：站点用 <a> 逐个包，拆成逗号分隔文本
        def _people(rx):
            mm = rx.search(html)
            if not mm:
                return ""
            raw = mm.group(1)
            names = [self._clean(x) for x in
                     re.findall(r'<a[^>]*>([\s\S]*?)</a>', raw)]
            names = [x for x in names if x and x not in ("内详", "更多")]
            if not names:
                txt = self._clean(re.sub(r"<[^>]+>", ",", raw))
                names = [x.strip() for x in re.split(r"[,，、/]", txt)
                         if x.strip() and x.strip() not in ("内详", "更多")]
            return ", ".join(names)

        actor = _people(_RE_ACTOR)
        director = _people(_RE_DIRECTOR)

        # 无效 / 已下架页面（站点返回统一「提示信息」页）
        if not vod_type or name in ("提示信息", "404", "页面不存在"):
            self.log("  无效详情页，跳过: %s" % name)
            return {"list": []}

        remark = _one(_RE_REMARK)

        # ---------------- 线路与剧集 ----------------
        groups = self._parse_playlists(html)
        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": [{
                "vod_id": vod_id, "vod_name": name, "vod_pic": pic,
                "vod_content": content, "vod_actor": actor or "内详",
                "vod_director": director or "内详", "vod_score": score,
                "vod_remarks": remark,
                "vod_play_from": "", "vod_play_url": "",
                "vod_year": year, "vod_area": area, "vod_type": vod_type,
            }]}

        names = list(groups.keys())
        names.sort(key=lambda x: (_LINE_PRIORITY.index(x)
                                  if x in _LINE_PRIORITY else 99))

        play_from = []
        play_url = []
        for line in names:
            eps = groups[line]
            ep_str = "#".join("%s$%s" % (n, h) for n, h in eps)
            play_from.append(line)
            play_url.append(ep_str)

        parts = [p for p in (year, area) if p]
        remark = remark or " · ".join(parts)
        if updated:
            remark = ("%s | 更新%s" % (remark, updated[:10])).strip(" |")

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor or "内详",
            "vod_director": director or "内详",
            "vod_score": score,
            "vod_remarks": remark,
            "vod_year": year,
            "vod_area": area,
            "vod_type": vod_type,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _parse_playlists(self, html):
        """解析详情页所有线路：{线路名: [(集名, 播放页URL), ...]}，集数正序

        站点每个线路是一个 stui-pannel 块：<h3 class="title">线路名</h3> …
        <ul class="stui-content__playlist">。用位置就近配对，避免块间越界。
        """
        groups = {}

        titles = [(m.start(), self._clean(m.group(1)))
                  for m in re.finditer(r'<h3 class="title">\s*([^<]*?)\s*</h3>',
                                       html)]
        uls = [(m.start(), m.group(1))
               for m in re.finditer(
                   r'<ul class="[^"]*stui-content__playlist[^"]*"[^>]*>'
                   r'([\s\S]*?)</ul>', html)]

        skip_words = ("剧情", "简介", "相关", "推荐", "评论", "猜你喜欢")

        for upos, ubody in uls:
            # 取该列表之前最近的线路标题
            line = ""
            for tpos, tname in titles:
                if tpos < upos:
                    line = tname
                else:
                    break
            if not line or line in skip_words:
                line = "线路%d" % (len(groups) + 1)

            lis = re.findall(r'<li[^>]*>([\s\S]*?)</li>', ubody)
            eps = []
            for li in lis:
                m = _RE_EP.search(li)
                if not m:
                    continue
                ep_name = self._clean(m.group(1))
                href = self._fix_url(m.group(2).replace("&amp;", "&"))
                if not ep_name:
                    ep_name = "正片"
                eps.append((ep_name, href))
            if not eps:
                continue

            # 站点默认倒序（最新在前），统一改为正序
            eps = self._sort_eps(eps)

            key = line
            n = 2
            while key in groups:
                key = "%s%d" % (line, n)
                n += 1
            groups[key] = eps

        return groups

    @staticmethod
    def _sort_eps(eps):
        def key(item):
            name = item[0]
            m = re.search(r"第\s*(\d+)\s*[集话期]", name)
            if m:
                return (0, int(m.group(1)), name)
            m = re.search(r"(\d+)", name)
            if m:
                return (0, int(m.group(1)), name)
            if "正片" in name or "HD" in name.upper():
                return (1, 0, name)
            return (2, 0, name)

        try:
            out = sorted(eps, key=key)
        except Exception:
            return eps

        # 若原本就是正序，sorted 结果一致；否则说明是倒序，取反后仍为正序
        if [x[0] for x in out] == [x[0] for x in eps]:
            return out
        if list(reversed([x[0] for x in eps])) == [x[0] for x in out]:
            return out
        return out

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
        real, pn = self._extract_now(html)
        self.log("  now: %s | pn: %s" % (real[:160] if real else "EMPTY", pn))

        if real and real.startswith("http"):
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：把播放页交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA,
                          "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_now(self, html):
        """播放页 inline script: var now="https://.../index.m3u8"; var pn="jsm3u8" """
        if not html:
            return "", ""
        now_url = ""
        pn = ""
        seg = ""
        m = _RE_PLAYER_VAR.search(html)
        if m:
            seg = m.group(0)
        else:
            i = html.find("var now=")
            if i >= 0:
                seg = html[i:i + 1200]

        if seg:
            m = _RE_NOW.search(seg)
            if m:
                now_url = m.group(1).strip()
            m = _RE_PN.search(seg)
            if m:
                pn = m.group(1).strip()

        now_url = now_url.replace("\\/", "/").replace("&amp;", "&")
        if now_url.startswith("//"):
            now_url = "https:" + now_url
        if now_url and not now_url.startswith("http"):
            now_url = ""
        return now_url, pn

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

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

    def destroy(self):
        pass

    def close(self):
        self.destroy()

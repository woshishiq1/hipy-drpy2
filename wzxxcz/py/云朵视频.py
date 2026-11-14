# coding=utf-8
"""
云朵视频 egradiomarketing.com | TVBox Python 爬虫
关键:
  - 站点前置 easy_slider 滑块盾，移动端 UA 直接放行，无需破验证
  - 分类 /egrafbtype/{tid}.html，筛选 /egrafbshow/{12槽位}.html，翻页 ?page=N
  - 筛选只有三行：分类(子类 id)/首字母/年份，槽位: tid----年份-首字母------
  - 详情 /egrafb/{id}.html，线路为 name17「线路N」+ 其下 list-number1 选集
  - 播放 /egrafbplay/{vod}-{sid}-{nid}.html，player_aaaa encrypt=0 明文 m3u8
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
                print("[yunduo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://egradiomarketing.com"
# 站点带滑块盾，PC UA 会被拦，移动端 UA 直接放行
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
      "Mobile/15E148 Safari/604.1")
DEFAULT_PIC = HOST + "/style/26/static/images/load5.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "9",  "type_name": "短视频"},
    {"type_id": "51", "type_name": "即将上映"},
]

_YEARS = [str(y) for y in range(2026, 2015, -1)]
_LETTERS = [chr(c) for c in range(65, 91)]

# 站点“分类”行的子类 id（严格取站点面板原值）
_FILTERS_MAP = {
    "1":  [("喜剧片", "35"), ("动作片", "36"), ("爱情片", "37"), ("科幻片", "38"),
           ("恐怖片", "39"), ("剧情片", "40"), ("战争片", "41")],
    "2":  [("国产剧", "42"), ("港台剧", "43"), ("日韩剧", "44"), ("欧美剧", "45")],
    "3":  [("国内综艺", "46"), ("海外综艺", "47")],
    "4":  [("国内动漫", "48"), ("海外动漫", "49")],
    "9":  [("动画短片", "57"), ("短剧", "58")],
    "51": [],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = _FILTERS_MAP.get(tid, [])
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": v} for n, v in subs]},
        {"key": "letter", "name": "首字母",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _LETTERS]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": y, "v": y} for y in _YEARS]},
    ]


# ===================== 正则 =====================
# 卡片：列表页 ys-name6 / 首页 filmName，统一从 a+img 取（名称用 alt 全名）
_RE_CARD = re.compile(r'<a href="/egrafb/(\d+)\.html"[^>]*>[\s\S]{0,80}?<img([^>]*)>', re.S | re.I)
_RE_CARD_NAME = re.compile(r'<div class="(?:ys-name6|filmName)">([\s\S]*?)</div>')
_RE_ATTR = re.compile(r'\b(href|src|data-src|alt)="([^"]*)"', re.I)

_RE_PAGECOUNT = re.compile(r'<span class="total">(\d+)</span>')
_RE_H1 = re.compile(r'<div class="ys-name18">([\s\S]*?)</div>')
_RE_DETAIL_PIC = re.compile(r'class="poster5"><img[\s\S]{0,80}?data-src="([^"]+)"')
_RE_YEAR1 = re.compile(r'<div class="year1">([\s\S]*?)</div>')
_RE_DIRECTOR = re.compile(r'导演：([\s\S]*?)</div>')
_RE_ACTOR = re.compile(r'主演：([\s\S]*?)</div>')
_RE_AREA = re.compile(r'地区：<span>([\s\S]*?)</span>')
_RE_INTRO = re.compile(r'<div class="Synopsis-word"[^>]*>([\s\S]*?)</div>')
_RE_INTRO_P = re.compile(r'<div class="Synopsis-word"[^>]*>[\s\S]*?<p>([\s\S]*?)</p>')

_RE_PLAYER_AA = re.compile(r"player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>")
# 线路块：name17「线路N」+ 紧随其后的 list-number1 选集
_RE_LINE_HEAD = re.compile(r'<div class="name17">(线路\d+)</div>')
_RE_LINE_A = re.compile(r'href="(/egrafbplay/[^"]+)"[^>]*>[\s\S]{0,40}?<div[^>]*>([^<]*)</div>')


class Spider(Spider):

    def getName(self):
        return "云朵视频"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
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
        url = url.strip().replace("&amp;", "&")
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&hellip;", "…"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip(" \n,，")

    # ---------- 列表 ----------
    def _build_show_url(self, tid, page, ext):
        # 槽位: 分类-空-空-空-年份-首字母-空-空-空-空-空-空
        seg = [str(tid), "", "", "",
               ext.get("year") or "",
               ext.get("letter") or "",
               "", "", "", "", "", ""]
        url = "%s/egrafbshow/%s.html" % (self.site_url, "-".join(seg))
        if page > 1:
            url += "?page=%d" % page
        return url

    def _page_count(self, html):
        m = _RE_PAGECOUNT.search(html or "")
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return 1
        return 0

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos
        for m in _RE_CARD.finditer(html):
            vid, attrs = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            a = {k.lower(): v for k, v in _RE_ATTR.findall(attrs)}
            pic = a.get("data-src") or a.get("src") or ""
            name = self._clean(a.get("alt"))
            if not name:
                nm = _RE_CARD_NAME.search(html, m.end(), m.end() + 400)
                name = self._clean(nm.group(1)) if nm else ""
            videos.append({
                "vod_id": "/egrafb/%s.html" % vid,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

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

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        # 站点“分类”行是子类 id，直接顶替 slot1
        sub = extend.get("class") or ""
        if sub:
            tid = sub

        url = self._build_show_url(tid, page, extend)
        self.log("category: " + url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html) or 1
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search/%s-------------.html" % (
            self.site_url, urllib.parse.quote(key))
        if page > 1:
            url += "?page=%d" % page
        self.log("search: " + url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        pagecount = self._page_count(html) or (page + 1 if len(videos) >= 36 else page)
        return {
            "list": videos, "page": page,
            "pagecount": pagecount, "limit": 36, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: " + url)

        html = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("完整版")[0].strip("《》"))
        name = name or vod_id

        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic

        # 站点详情页名称下面那行就是“2026-11-12 18:31:58”，
        # 站点没有单独“年份”字段，年份取这行前 4 位，整行原样作副标题
        year = remarks = ""
        m = _RE_YEAR1.search(html)
        if m:
            remarks = self._clean(m.group(1))
            ym = re.search(r"(\d{4})", remarks)
            if ym:
                year = ym.group(1)

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()
            actor = re.sub(r"\s*更多\s*(...|\.\.\.)?\s*$", "", actor).strip()

        area = ""
        m = _RE_AREA.search(html)
        if m:
            area = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()

        content = ""
        m = _RE_INTRO_P.search(html) or _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 线路 + 选集：严格按站点「线路N」出现顺序
        play_from = []
        play_url = []
        marks = [mm for mm in _RE_LINE_HEAD.finditer(html)]
        for idx, mm in enumerate(marks):
            head = mm.group(1)
            start = mm.end()
            end = marks[idx + 1].start() if idx + 1 < len(marks) else len(html)
            block = html[start:end]
            # 该线路块到《…》演员表为止，避免把后面的推荐卡混进来
            cut = block.find('<div class="name17">《')
            if cut > 0:
                block = block[:cut]
            eps = []
            for a in _RE_LINE_A.finditer(block):
                href = self._fix_url(a.group(1))
                ep = self._clean(a.group(2)) or str(len(eps) + 1)
                eps.append("%s$%s" % (ep, href))
            if not eps:
                continue
            play_from.append(head)
            play_url.append("#".join(eps))

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: " + play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        data = self._player_data(html)
        url = self._direct_url(data)
        if url:
            res = {
                "parse": 0, "playUrl": "", "url": url,
                "header": {"User-Agent": UA, "Referer": play_page},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % url[:160])
            return res

        # 非明文（encrypt=3 等）就交给 App 嗅探站点自己的播放页
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        self.log("  => 兜底嗅探: %s" % play_page)
        return res

    def _player_data(self, html):
        if not html:
            return {}
        m = _RE_PLAYER_AA.search(html)
        if not m:
            return {}
        try:
            return json.loads(m.group(1).replace("\\/", "/"))
        except Exception:
            return {}

    def _direct_url(self, data):
        if not data:
            return ""
        raw = data.get("url") or ""
        enc = str(data.get("encrypt") or "0")
        if not raw:
            return ""
        try:
            if enc == "1":
                raw = urllib.parse.unquote(raw)
            elif enc == "2":
                raw = urllib.parse.unquote(base64.b64decode(
                    raw + "=" * ((4 - len(raw) % 4) % 4)).decode("utf-8", "ignore"))
            elif enc != "0":
                return ""
        except Exception:
            return ""
        if raw.startswith("http") and (".m3u8" in raw or ".mp4" in raw):
            return raw
        return ""

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

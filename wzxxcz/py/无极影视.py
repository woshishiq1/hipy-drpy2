# coding=utf-8
"""
无极影视 www.yyywlfwzx.com | TVBox Python 爬虫
关键:
  - 苹果CMS10 + stui 模板，页面中文全部是 HTML 实体，取回后先 unescape 再解析
  - 分类 /vodtype/{tid}.html，翻页 &page=N，总页数在 <span class="num">1/N</span>
  - 筛选 /vodtype/{tid}.html?area=..&year=..（站点路由真实支持，页面无筛选按钮）
  - 分类页每页 30 条，右侧「本周热门」侧栏要去掉，否则会混进列表
  - 详情 /vod/{id}.html，副标题在 pic-text，线路为《名》线路一…+ 各自选集
  - 播放 /vodplay/{vod}_{sid}_{nid}.html，player_aaaa encrypt=0 明文 m3u8
"""
import re
import sys
import json
import time
import base64
import html
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
                print("[wuji]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.yyywlfwzx.com"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
      "Mobile/15E148 Safari/604.1")
DEFAULT_PIC = HOST + "/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 站点导航顺序，去掉伦理片(20)
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
    {"type_id": "5", "type_name": "短剧"},
]

_YEARS = [str(y) for y in range(2026, 2015, -1)]

# 站点「类型」一栏跳转的各子类 tid（严格照站点导航）
_FILTERS_MAP = {
    "1": [("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
          ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("Netflix电影", "17")],
    "2": [("国产剧", "13"), ("港台剧", "14"), ("日韩剧", "15"),
          ("欧美剧", "16"), ("Netflix电视剧", "18")],
    "3": [],
    "4": [],
    "5": [],
}

# 站点路由实测有数据的地区
_AREAS = ["大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "印度",
          "英国", "法国", "德国", "意大利", "西班牙", "加拿大",
          "澳大利亚", "俄罗斯", "新加坡", "马来西亚", "其他"]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    rows = []
    subs = _FILTERS_MAP.get(tid, [])
    if subs:
        rows.append({"key": "class", "name": "类型",
                     "value": [{"n": "全部", "v": ""}] +
                              [{"n": n, "v": v} for n, v in subs]})
    rows.append({"key": "area", "name": "地区",
                 "value": [{"n": "全部", "v": ""}] +
                          [{"n": a, "v": a} for a in _AREAS]})
    rows.append({"key": "year", "name": "年份",
                 "value": [{"n": "全部", "v": ""}] +
                          [{"n": y, "v": y} for y in _YEARS]})
    FILTERS[tid] = rows


# ===================== 正则 =====================
_RE_CARD_A = re.compile(r'<a[^>]*href="/vod/(\d+)\.html"[^>]*>', re.S)
_RE_TITLE = re.compile(r'title="([^"]*)"')
_RE_PIC = re.compile(r'(?:data-original|data-src|src)="([^"]*)"')
_RE_REMARKS = re.compile(r'<span class="pic-text text-right">([^<]*)</span>')
_RE_PAGENUM = re.compile(r'<span class="num">\d+/(\d+)</span>')
# 站点主列表容器：分类页 stui-vodlist clearfix，搜索页 stui-vodlist__media col-pd
_RE_UL_CAT = re.compile(r'<ul class="stui-vodlist clearfix">[\s\S]*?</ul>')
_RE_UL_SEARCH = re.compile(r'<ul class="stui-vodlist__media col-pd clearfix">[\s\S]*?</ul>')

_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>')
_RE_D_PIC = re.compile(r'<div class="stui-content__thumb">[\s\S]{0,200}?data-original="([^"]+)"')
_RE_TYPE = re.compile(r'类型：</span>([\s\S]*?)<span class="split-line">')
_RE_DIRECTOR = re.compile(r'导演：</span>([\s\S]*?)</p>')
_RE_ACTOR = re.compile(r'主演：</span>([\s\S]*?)</p>')
_RE_AREA = re.compile(r'地区：</span>([\s\S]*?)<span class="split-line">')
_RE_YEAR = re.compile(r'年份：</span>([\s\S]*?)</p>')
_RE_SKETCH = re.compile(r'detail-sketch">([\s\S]*?)</span>')
_RE_CONTENT = re.compile(r'detail-content"[^>]*>([\s\S]*?)</span>')

_RE_H3 = re.compile(r'<h3 class="title">([^<]*)</h3>')
_RE_LINE_NAME = re.compile(r'(线路[一二三四五六七八九十百\d]+)')
_RE_PLAY_A = re.compile(r'href="/vodplay/(\d+)_(\d+)_(\d+)\.html">([^<]*)</a>')
_RE_PLAYER_AA = re.compile(r"player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>")


class Spider(Spider):

    def getName(self):
        return "无极影视"

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
    def _fetch(self, url, timeout=20, retry=4):
        """站点源站偶发 503(upstream ...)，取不到就重试；取回后统一 unescape。"""
        for i in range(retry):
            try:
                rsp = self.fetch(url, headers=self.headers, timeout=timeout)
                code = getattr(rsp, "status_code", 200)
                text = getattr(rsp, "text", "") or ""
                if code == 200 and len(text) > 2000:
                    return html.unescape(text)
                self.log("  retry %d/%d code=%s len=%d %s"
                         % (i + 1, retry, code, len(text), url))
            except Exception as e:
                self.log("  retry %d/%d err=%s" % (i + 1, retry, e))
            time.sleep(1 + i)
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
        s = (s.replace("\xa0", " ").replace("&nbsp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&hellip;", "…"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip(" \n,，")

    def _drop_seo(self, text):
        """站点简介里夹了自家的『完整版免费在线观看地址 / 分享给小伙伴』推广句，去掉。"""
        if not text:
            return ""
        keep = []
        for line in text.split("\n"):
            t = line.strip()
            if not t:
                continue
            if ("完整版免费在线观看地址" in t
                    or "分享给你的小伙伴" in t
                    or self.site_url in t):
                continue
            keep.append(t)
        return "\n".join(keep).strip()

    # ---------- 列表 ----------
    def _list_url(self, tid, page, ext):
        q = []
        if ext.get("area"):
            q.append("area=" + urllib.parse.quote(ext["area"]))
        if ext.get("year"):
            q.append("year=" + urllib.parse.quote(ext["year"]))
        if page > 1:
            q.append("page=%d" % page)
        url = "%s/vodtype/%s.html" % (self.site_url, tid)
        if q:
            url += "?" + "&".join(q)
        return url

    def _extract_videos(self, html_text):
        videos = []
        seen = set()
        if not html_text:
            self.log("  HTML 为空")
            return videos
        body = html_text
        for m in _RE_CARD_A.finditer(body):
            vid = m.group(1)
            if vid in seen:
                continue
            tag = m.group(0)
            tm = _RE_TITLE.search(tag)
            if not tm:
                continue
            pm = _RE_PIC.search(tag)
            rm = _RE_REMARKS.search(body[m.end():m.end() + 300])
            seen.add(vid)
            videos.append({
                "vod_id": "/vod/%s.html" % vid,
                "vod_name": self._clean(tm.group(1)),
                "vod_pic": self._fix_url(pm.group(1)) if pm else self.default_pic,
                "vod_remarks": self._clean(rm.group(1)) if rm else "",
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html_text = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html_text))
        # 首页只取 7 个主列表块，右侧「本周热门xx」侧栏不进首页列表
        blocks = _RE_UL_CAT.findall(html_text)
        return {"list": self._extract_videos("".join(blocks) or html_text)}

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

        # 站点「类型」一行是跳子类 tid，直接顶替
        sub = extend.get("class") or ""
        if sub:
            tid = sub

        url = self._list_url(tid, page, extend)
        self.log("category: " + url)
        html_text = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html_text))

        # 分类页主列表就是那一个 stui-vodlist clearfix 块，侧栏「本周热门」不算
        m = _RE_UL_CAT.search(html_text)
        videos = self._extract_videos(m.group(0) if m else html_text)
        pagecount = 1
        m = _RE_PAGENUM.search(html_text)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = 1
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/vodsearch/_____________.html?wd=%s" % (
            self.site_url, urllib.parse.quote(key))
        if page > 1:
            url += "&page=%d" % page
        self.log("search: " + url)
        html_text = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html_text))

        # 搜索结果只在 stui-vodlist__media 这一个块里，后面的「本周热门/排行」不算结果
        m = _RE_UL_SEARCH.search(html_text)
        videos = self._extract_videos(m.group(0) if m else html_text)
        pagecount = 1
        m = _RE_PAGENUM.search(html_text)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = 1
        self.log("  结果: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 10, "total": pagecount * 10,
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

        html_text = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html_text))
        if not html_text:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html_text)
        if m:
            name = self._clean(m.group(1))
        name = name or vod_id

        pic = self.default_pic
        m = _RE_D_PIC.search(html_text)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic
        else:
            m = _RE_PIC.search(html_text)
            if m:
                pic = self._fix_url(m.group(1)) or self.default_pic

        # 副标题：站点详情页封面上的「更新第24集 / 更新HD / 全集」
        remarks = ""
        m = _RE_REMARKS.search(html_text)
        if m:
            remarks = self._clean(m.group(1))

        type_name = ""
        m = _RE_TYPE.search(html_text)
        if m:
            type_name = self._clean(m.group(1))

        area = ""
        m = _RE_AREA.search(html_text)
        if m:
            area = self._clean(m.group(1))

        year = ""
        m = _RE_YEAR.search(html_text)
        if m:
            year = self._clean(m.group(1))

        director = ""
        m = _RE_DIRECTOR.search(html_text)
        if m:
            director = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()

        actor = ""
        m = _RE_ACTOR.search(html_text)
        if m:
            actor = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()

        # 简介：站点有 detail-sketch(截断) 与 detail-content(完整)，取完整版
        content = ""
        m = _RE_CONTENT.search(html_text) or _RE_SKETCH.search(html_text)
        if m:
            content = self._clean(m.group(1))
        content = self._drop_seo(content)
        if not content:
            m = _RE_SKETCH.search(html_text)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 线路 + 选集：按站点「线路一/二/三…」出现顺序
        play_from = []
        play_url = []
        heads = [h for h in _RE_H3.finditer(html_text)]
        for i, h in enumerate(heads):
            head = self._clean(h.group(1))
            if "线路" not in head:
                continue
            start = h.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(html_text)
            block = html_text[start:end]
            lm = _RE_LINE_NAME.search(head)
            line_name = lm.group(1) if lm else head
            eps = []
            for a in _RE_PLAY_A.finditer(block):
                ep = self._clean(a.group(4)) or str(len(eps) + 1)
                eps.append("%s$%s" % (ep, self._fix_url(
                    "/vodplay/%s_%s_%s.html" % (a.group(1), a.group(2), a.group(3)))))
            if not eps:
                continue
            play_from.append(line_name)
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
            "vod_type": type_name,
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

        html_text = self._fetch(play_page)
        data = self._player_data(html_text)
        url = self._direct_url(data)
        if url:
            res = {
                "parse": 0, "playUrl": "", "url": url,
                "header": {"User-Agent": UA, "Referer": play_page},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % url[:160])
            return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        self.log("  => 兜底嗅探: %s" % play_page)
        return res

    def _player_data(self, html_text):
        if not html_text:
            return {}
        m = _RE_PLAYER_AA.search(html_text)
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

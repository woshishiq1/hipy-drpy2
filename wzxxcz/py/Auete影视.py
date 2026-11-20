# coding=utf-8
"""
Auete 影视网 www.aeete.com | TVBox Python 爬虫
站点结构（MacCMS stui/bootstrap 模板）:
  - 首页:   /
  - 分类:   /<Cat>/index.html；类型子页 /<Cat>/<sub>/index.html
            分页: 第1页 index.html，第 N 页 index<N>.html
  - 详情:   /<Cat>/<sub>/<slug>/
  - 播放:   /<Cat>/<sub>/<slug>/play-<line>-<ep>.html
  - 搜索:   /auete4so.php?searchword=<关键词>（图形验证码墙，命中返回空列表）
  - 线路:   div.play-card，card-header > b 线路名（『片名』前缀需剥离），
            ul.episode-list > li > a[title][href]，顺序即站点 DOM 顺序
  - 播放直链: var now=base64decode("...")，解码即 m3u8；非 master，无 Referer 防盗链
  - 详情字段:
      · 片名 h1（去《》）/ og:title；海报 img.img-fluid.lazy / og:image
      · 导演/主演/分类/地区/年份/语言: detail-label 后 <b> 文本，og:video:* 兜底
      · 简介: og:description 优先，name=description 兜底
      · 状态: 状态 <b>（至8集/共40集）
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
                print("[aeete]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.aeete.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "Movie", "type_name": "电影"},
    {"type_id": "Tv",    "type_name": "电视剧"},
    {"type_id": "Zy",    "type_name": "综艺"},
    {"type_id": "Dm",    "type_name": "动漫"},
    {"type_id": "qita",  "type_name": "其他"},
]

# 按类型（子分类 slug，URL 子路径）；key=subtype
_SUBTYPE = {
    "Movie": [("xjp", "喜剧片"), ("dzp", "动作片"), ("aqp", "爱情片"),
              ("khp", "科幻片"), ("kbp", "恐怖片"), ("jsp", "惊悚片"),
              ("zzp", "战争片"), ("jqp", "剧情片")],
    "Tv": [("oumei", "美剧"), ("hanju", "韩剧"), ("riju", "日剧"),
           ("yataiju", "泰剧"), ("wangju", "网剧"), ("taiju", "台剧"),
           ("neidi", "国产"), ("tvbgj", "港剧"), ("yingju", "英剧"),
           ("waiju", "外剧"), ("weiduanju", "微短剧")],
    "Zy": [("guozong", "国综"), ("hanzong", "韩综"), ("meizong", "美综")],
    "Dm": [("donghua", "动画"), ("riman", "日漫"), ("guoman", "国漫"),
           ("meiman", "美漫")],
    "qita": [("Jlp", "记录片"), ("Jdp", "经典片"), ("Jdj", "经典剧"),
             ("wlp", "网大电影"), ("laodianying", "国产老电影")],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [{
        "key": "subtype", "name": "类型",
        "value": [{"n": "全部", "v": ""}] +
                 [{"n": n, "v": v} for v, n in _SUBTYPE.get(tid, [])],
    }]

# ===================== 正则 =====================
# 卡片：li[data-href] 整块
_RE_LI = re.compile(
    r'<li[^>]*data-href="([^"]+)"[^>]*>([\s\S]*?)</li>', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:src|data-src)="([^"]*)"[^>]*?(?:alt|title)="([^"]*)"', re.S | re.I)
_RE_IMG_ALT = re.compile(r'<img[^>]*alt="([^"]*)"', re.I)
_RE_HDTAG = re.compile(r'<span class="hdtag">([^<]*)</span>', re.I)
_RE_H2 = re.compile(r'<h2>\s*<a[^>]*title="([^"]*)"', re.I)
_RE_H2_TEXT = re.compile(r'<h2>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_TIME = re.compile(r'class="update-time"[^>]*>([\s\S]*?)</span>', re.I)
_RE_RATING = re.compile(r'<span class="rating">([\s\S]*?)</span>', re.I)

_RE_OG = re.compile(r'<meta\s+property="og:([^"]+)"\s+content="([^"]*)"', re.I)
_RE_TITLE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(
    r'<img[^>]*class="[^"]*img-fluid[^"]*lazy[^"]*"[^>]*src="([^"]*)"', re.I)
_RE_DES = re.compile(r'<p class="detail-des">([\s\S]*?)</p>', re.I)

_RE_LABEL = re.compile(
    r'◎[^：:]*?(导演|主演|分类|地区|上映年份|语言)[：:]</span>\s*<b>([\s\S]*?)</b>', re.I)
_RE_STATUS = re.compile(r'状态：</span><b[^>]*>([\s\S]*?)</b>', re.I)

_RE_PLAY_CARD = re.compile(
    r'<div class="card mb-3 play-card"[\s\S]*?(?=<div class="card mb-3 play-card"|$)', re.I)
_RE_TAB_NAME = re.compile(r'<b>([\s\S]*?)</b>', re.I)
_RE_EP = re.compile(
    r'<a[^>]*title="([^"]*)"[^>]*href="([^"]*play-[^"]*)"', re.I)

_RE_NOW_B64 = re.compile(r'var\s+now\s*=\s*base64decode\("([^"]+)"\)', re.I)
_RE_NOW = re.compile(r'var\s+now\s*=\s*"([^"]*)"', re.I)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)

_RE_LIMIT = re.compile(r'系统安全验证|vdimgck|name="validate"', re.I)


class Spider(Spider):

    def getName(self):
        return "Auete影视"

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
            self.log("fetch FAIL", url, e)
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
        # 模板占位残留，如 {self:share}
        s = re.sub(r"\{self:[^}]*\}", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&emsp14;", " ").replace("&#12288;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_LI.finditer(html):
            href, block = m.group(1), m.group(2)
            if href in seen:
                continue
            seen.add(href)

            pic, name = "", ""
            mi = _RE_IMG.search(block)
            if mi:
                pic, name = mi.group(1), self._clean(mi.group(2))
            else:
                ma = _RE_IMG_ALT.search(block)
                if ma:
                    name = self._clean(ma.group(1))

            mh = _RE_H2.search(block)
            if mh:
                name = self._clean(mh.group(1))
            elif not name:
                mt = _RE_H2_TEXT.search(block)
                if mt:
                    name = self._clean(mt.group(1))

            mr = _RE_HDTAG.search(block)
            remarks = self._clean(mr.group(1)) if mr else ""
            mrating = _RE_RATING.search(block)
            if mrating and not remarks:
                remarks = self._clean(mrating.group(1))

            mt = _RE_TIME.search(block)
            subtitle = self._clean(mt.group(1)) if mt else ""

            pic = self._fix_url(pic) or self.default_pic
            if not name:
                continue
            videos.append({
                "vod_id": href, "vod_name": name[:100], "vod_pic": pic,
                "vod_remarks": remarks, "vod_subtitle": subtitle,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        block = re.search(r'<ul class="[^"]*page[^"]*"[\s\S]*?</ul>', html)
        scope = block.group(0) if block else html
        nums = [int(x) for x in re.findall(r'index(\d+)\.html', scope)]
        return max(1, max(nums)) if nums else 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def _category_url(self, tid, subtype, page):
        sub = subtype or ""
        if page <= 1:
            path = "/%s/%s/index.html" % (tid, sub) if sub else "/%s/index.html" % tid
        else:
            path = "/%s/%s/index%d.html" % (tid, sub, page) if sub \
                else "/%s/index%d.html" % (tid, page)
        return self.site_url + path

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        subtype = extend.get("subtype") or ""
        url = self._category_url(tid, subtype, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 20, "total": pagecount * 20,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        url = "%s/auete4so.php?searchword=%s&page=%d" % (
            self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)

        # 图形验证码墙：识别验证页返回空，不崩
        if _RE_LIMIT.search(html):
            self.log("  命中搜索安全验证（图形验证码），返回空")
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 20, "total": 0}

        videos = self._parse_cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 20, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _og_map(self, html):
        og = {}
        for m in _RE_OG.finditer(html):
            og[m.group(1).lower()] = self._clean(m.group(2))
        return og

    def _label_field(self, html, label):
        m = re.search(
            r'◎[^：:]*?' + label + r'[：:]</span>\s*<b>([\s\S]*?)</b>', html, re.I)
        return self._clean(m.group(1)) if m else ""

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        og = self._og_map(html)

        # 片名（h1 内 <small class="detail-subtitle"> 为别名，需剥离）
        name = ""
        mh = _RE_TITLE_H1.search(html)
        if mh:
            raw = re.sub(r"<small[\s\S]*?</small>", "", mh.group(1), flags=re.I)
            name = self._clean(raw)
        name = re.sub(r"[《》]", "", name).strip()
        if not name:
            name = og.get("title", "")
        name = name or vod_id

        # 海报
        pic = ""
        mp = _RE_POSTER.search(html)
        if mp:
            pic = mp.group(1)
        pic = self._fix_url(pic) or self._fix_url(og.get("image", "")) or self.default_pic

        # 简介：详情正文 p.detail-des 完整版优先，og:description /
        # name=description（被站点截断）兜底
        content = ""
        md = _RE_DES.search(html)
        if md:
            content = self._clean(md.group(1))
        if not content:
            content = og.get("description", "")
        if not content:
            md = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if md:
                content = self._clean(md.group(1))
        content = re.sub(r'\{self:[^}]*\}', "", content)
        content = re.sub(r'^(剧情简介|简介)[：:]\s*', "", content)
        content = re.sub(r'。?高清全集免费在线观看.*$', "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        director = self._label_field(html, "导演") or og.get("video:director", "")
        actor = self._label_field(html, "主演") or og.get("video:actor", "")
        classify = self._label_field(html, "分类") or og.get("video:class", "")
        area = self._label_field(html, "地区") or og.get("video:area", "")
        year_raw = self._label_field(html, "上映年份")
        my = re.search(r"(\d{4})", year_raw)
        year = my.group(1) if my else ""
        lang = self._label_field(html, "语言")

        # ===== 线路与选集 =====
        play_from, play_url = [], []
        for block in _RE_PLAY_CARD.findall(html):
            mn = _RE_TAB_NAME.search(block)
            line_name = self._clean(mn.group(1)) if mn else ""
            line_name = re.sub(r"^『[^』]*』", "", line_name).strip()
            eps = []
            seen_ep = set()
            for ma in _RE_EP.finditer(block):
                ep_name, href = self._clean(ma.group(1)), ma.group(2)
                if href in seen_ep:
                    continue
                seen_ep.add(href)
                if not ep_name:
                    ep_name = "第%02d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        status = ""
        ms = _RE_STATUS.search(html)
        if ms:
            status = self._clean(ms.group(1))
        remarks = status or ("%d条线路" % len(play_from))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": og.get("video:score", ""),
            "vod_remarks": remarks,
            "vod_area": area,
            "vod_year": year,
            "vod_lang": lang,
            "vod_classify": classify,
            "type_name": classify,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        html = self._fetch(play_page, headers=header)
        stream = self._extract_stream(html)

        if stream:
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_stream(self, html):
        if not html:
            return ""
        m = _RE_NOW_B64.search(html)
        if m:
            try:
                return base64.b64decode(m.group(1)).decode("utf-8", "ignore")
            except Exception:
                pass
        m = _RE_NOW.search(html)
        if m:
            return m.group(1).replace("\\/", "/")
        m = _RE_STREAM.search(html)
        return m.group(0) if m else ""

    def _resolve_sub_stream(self, url, header):
        """多码率 master 列表：解析首条子 m3u8 并 urljoin 成绝对地址；
        已是媒体播放列表/mp4 原样返回；子流不可达回退 master，不误伤。"""
        if not url or ".mp4" in url.lower():
            return url

        def _get(target):
            last = None
            for _ in range(2):
                try:
                    rs = self.fetch(target, headers=header, timeout=10)
                    if getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?"))
                except Exception as e:
                    last = e
            return None, last

        try:
            rm, err = _get(url)
            if err is not None:
                self.log("  master 拉取重试后失败: %s" % err)
                return url
            text = rm.text if hasattr(rm, "text") else (
                rm.content.decode("utf-8", "ignore") if hasattr(rm, "content") else "")
            if "#EXT-X-STREAM-INF" not in text:
                return url  # 已是含分片的媒体播放列表
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        self.log("  master 解析子流 %s" % sub[:120])
                        return sub
                    self.log("  子流重试后失败: %s" % sub_err)
                    break
        except Exception as e:
            self.log("  子流解析回退: %s" % e)
        return url

    # ---------------- 其余契约 ----------------
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
            rsp = self.fetch(url, headers={"User-Agent": UA, "Referer": self.site_url + "/"})
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, rsp.content, ""]
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

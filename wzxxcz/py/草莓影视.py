# coding=utf-8
"""
草莓影视 artcoast.cc | TVBox Python 爬虫 
关键:
  - 首页/分类 /cid/{id}.html 与筛选页 /vodshow/{cid}-{...}.html (?page=N 分页)
  - 详情 /vid/{id}.html, 播放页 /pid/{vid}-{sid}-{nid}.html
  - 解析 player_aaaa JSON 取直链 m3u8
  - 搜索 /search/{关键词}.html, 分页 /search/{关键词}/page/{n}.html
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
                print("[caomei]", *a, **kw)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://artcoast.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/quartz/asset/img/placeholder.svg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 一级分类(与站内导航一致) + 二级子类
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺剧场"},
    {"type_id": "4",  "type_name": "动漫大全"},
]

# 一级分类下的子类(站内 nav-sub)
_SUBS = {
    "1": [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
          ("10", "恐怖片"), ("11", "剧情片"), ("12", "战争片")],
    "2": [("13", "国产剧"), ("14", "港台剧"), ("15", "日韩剧"), ("16", "欧美剧")],
    "3": [("20", "国产"), ("21", "日韩"), ("22", "欧美"), ("23", "港台"),
          ("24", "海外")],
    "4": [("17", "国产动漫"), ("18", "日韩动漫"), ("19", "欧美动漫")],
}

# 类型筛选(站内 filter-row 类型)
_GENRES = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
          "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
          "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["都市", "古装", "言情", "武侠", "军事", "喜剧", "家庭", "悬疑", "科幻",
          "历史", "战争", "犯罪", "奇幻", "剧情", "年代", "谍战"],
    "3": ["真人秀", "脱口秀", "音乐", "益智", "文化", "美食", "情感", "访谈",
          "游戏", "旅游", "生活", "选秀", "晚会"],
    "4": ["冒险", "热血", "搞笑", "恋爱", "机战", "运动", "日常", "治愈",
          "悬疑", "奇幻", "科幻", "恋爱", "校园"],
}

_SORTS = [{"n": "更新", "v": "time"},
          {"n": "热度", "v": "hits"},
          {"n": "评分", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "sub", "name": "子类",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": v} for v, n in _SUBS.get(tid, [])]},
        {"key": "class", "name": "类型",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _GENRES.get(tid, [])]},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 影片卡片: 逐个 <article class="quartz-card"> 块解析
_RE_ARTICLE = re.compile(r'<article class="quartz-card[^"]*">([\s\S]*?)</article>')
_RE_COVER_HREF = re.compile(r'<a class="quartz-cover" href="(/vid/\d+\.html)"(?:[^>]*title="([^"]*)")?', re.I)
_RE_PIC_ATTR = re.compile(r'data-src="([^"]*)"')
_RE_PIC_ATTR2 = re.compile(r'<img[^>]*?src="([^"]*)"', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"')
_RE_DURATION = re.compile(r'<span class="duration">([^<]*)</span>')
_RE_SCORE_TAG = re.compile(r'<span class="score-tag">([^<]*)</span>')

# 简化兜底: href + img
_RE_HREF = re.compile(r'href="(/vid/\d+\.html)"', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"', re.S | re.I)

# 详情页
_RE_DETAIL_BLOCK = re.compile(
    r'<div class="detail-copy">([\s\S]*?)</div>\s*</div>\s*</div>', re.S)
_RE_H1 = re.compile(r'<h1>([^<]*)</h1>')
_RE_PIC = re.compile(
    r'<a class="detail-poster-wrap"[^>]*>[\s\S]{0,200}?<img[^>]*src="([^"]*)"', re.I)
_RE_DESC = re.compile(r'<p class="description">([\s\S]*?)</p>')
_RE_META = re.compile(r'<p class="detail-meta">([\s\S]*?)</p>')
_RE_SCORE = re.compile(r'<b>([\d.]+)</b>\s*分')
_RE_ALIAS = re.compile(r'<p class="quartz-desc">([\s\S]*?)</p>')

# 导演/主演: 每个名字是独立 <span>, 必须抓整段 p 再拆
_RE_CAST_P = re.compile(r'<p class="cast[^"]*">([\s\S]*?)</p>')
_RE_CAST_SPAN = re.compile(r'<span>([^<]*)</span>')
_RE_CAST_TAG = re.compile(r'<span>(导演|主演)[：:]\s*</span>')

# 播放目录: <div class="play-source"><h3>播放线路 1</h3><div class="episode-list"><a href="/pid/87095-1-1.html">HD中字</a>...</div>
_RE_SOURCE = re.compile(
    r'<div class="play-source"><h3>([^<]*)</h3><div class="episode-list">([\s\S]*?)</div></div>')
_RE_EP_A = re.compile(r'<a href="(/pid/[^"]+\.html)"[^>]*>([^<]*)</a>')

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 分页
_RE_PAGE_NUM = re.compile(r'/cid/\d+-(\d+)\.html')
_RE_SEARCH_PAGE = re.compile(r'/page/(\d+)\.html')


# 线路别名
_LINE_ALIAS = {
    "1080zyk": "1080资源", "bfzym3u8": "暴风资源", "wjm3u8": "无限资源",
    "lzm3u8": "量子资源", "ffm3u8": "非凡资源", "dyttm3u8": "电影天堂",
    "jsm3u8": "极速资源", "modum3u8": "魔都资源", "dbm3u8": "豆瓣资源",
    "wolong": "卧龙资源", "ikm3u8": "爱坤资源", "vip": "VIP线路",
    "kkm3u8": "快看资源", "tpm3u8": "淘片资源", "ssm3u8": "闪速资源",
}


class Spider(Spider):

    def getName(self):
        return "草莓影视"

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
        self._line_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=30, headers=None):
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
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        """从列表页 HTML 提取影片卡片"""
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        articles = _RE_ARTICLE.findall(html)
        for block in articles:
            m = _RE_COVER_HREF.search(block)
            if not m:
                continue
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)

            title = m.group(2) or ""
            if not title:
                ma = _RE_ALT.search(block)
                title = ma.group(1) if ma else ""

            # 优先 data-src(懒加载真实图), 否则 src
            mp = _RE_PIC_ATTR.search(block) or _RE_PIC_ATTR2.search(block)
            pic = mp.group(1) if mp else ""
            if "placeholder" in pic:
                pic = ""

            remarks = ""
            md = _RE_DURATION.search(block)
            if md:
                remarks = self._clean(md.group(1))
            if not remarks:
                ms = _RE_SCORE_TAG.search(block)
                if ms:
                    remarks = "评分%s" % ms.group(1)

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks[:40],
            })
        if videos:
            self.log("  完整卡片: %d 条" % len(videos))
            return videos

        # 兜底: href 与 img 分开配对
        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  兜底: href=%d img=%d" % (len(hrefs), len(imgs)))
        for i, href in enumerate(hrefs):
            if href in seen:
                continue
            seen.add(href)
            alt, pic = "", ""
            if i < len(imgs):
                alt, pic = imgs[i]
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        nums = _RE_PAGE_NUM.findall(html)
        if nums:
            try:
                return max(int(n) for n in nums)
            except Exception:
                pass
        nums = _RE_SEARCH_PAGE.findall(html)
        if nums:
            try:
                return max(int(n) for n in nums)
            except Exception:
                pass
        return 1

    # ================= TVBox 接口 =================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

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

        sub = extend.get("sub") or ""
        cls = extend.get("class") or ""
        year = extend.get("year") or ""
        sort = extend.get("sort_field") or ""

        if sub and not (cls or year or sort):
            # 纯子类直达 /cid/{sub}-{page}.html (分页为 1 起)
            url = "%s/cid/%s-%d.html" % (self.site_url, sub, page)
        else:
            # /vodshow/{tid}-{f2}-{sort}-{class}-{f5..f11}-{year}.html
            parts = [tid, "", sort, cls, "", "", "", "", "", "", "", year]
            url = "%s/vodshow/%s.html?page=%d" % (
                self.site_url, "-".join(parts), page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = max(1, self._page_count(html))
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 48, "total": pagecount * 48,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page <= 1:
            url = "%s/search/%s.html" % (self.site_url, kw)
        else:
            url = "%s/search/%s/page/%d.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": max(1, self._page_count(html)),
            "limit": 48, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

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
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic

        # 元信息(评分/年份/地区/类型)
        # 形如: <span><b>1.0</b> 分</span><span>2026</span><span>大陆</span><span>爱情,古装,剧情,国产</span>
        score, vyear, area, vclass = "", "", "", ""
        m = _RE_META.search(html)
        if m:
            meta_html = m.group(1)
            ms = _RE_SCORE.search(meta_html)
            if ms:
                score = ms.group(1)
            # 拆所有 span, 去掉内层标签; 用"年份"定位, 彻底避免评分位错位
            spans = []
            for raw in re.findall(r"<span>([\s\S]*?)</span>", meta_html):
                t = self._clean(raw)
                if t:
                    spans.append(t)

            idx = -1
            for i, t in enumerate(spans):
                if re.match(r"^(19|20)\d{2}$", t):
                    idx = i
                    break
            if idx >= 0:
                vyear = spans[idx]
                if idx + 1 < len(spans):
                    area = spans[idx + 1]
                if idx + 2 < len(spans):
                    vclass = spans[idx + 2]
            else:
                # 无年份(极少数未标注): 剔除评分位后按顺序补
                rest = [x for x in spans if not x.endswith("分")]
                if len(rest) >= 3:
                    area, vclass = rest[1], rest[2]
                elif len(rest) == 2:
                    area = rest[1]

        # 简介
        content = ""
        m = _RE_DESC.search(html)
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

        # 导演/主演: 逐个 <p class="cast"> 块, 拆出所有 <span> 名字
        # 形如: <p class="cast cast-links"><span>主演：</span><span>谭松韵</span> <span>刘学义</span> ...
        director = ""
        actor = ""
        for cm in _RE_CAST_P.finditer(html):
            block = cm.group(1)
            if "导演" in block[:60]:
                tag = "director"
            elif "主演" in block[:60]:
                tag = "actor"
            else:
                tag = "actor" if director else "director"

            names = []
            for span_txt in _RE_CAST_SPAN.findall(block):
                t = self._clean(span_txt)
                if not t:
                    continue
                # 跳过标签本身 "导演：" / "主演：" / "导演:"
                if re.fullmatch(r"(导演|主演)\s*[：:]?", t):
                    continue
                if t not in names:
                    names.append(t)

            if not names:
                continue
            joined = ", ".join(names)
            if tag == "director" and not director:
                director = joined
            elif tag == "actor" and not actor:
                actor = joined

        # 别名(如 "兰香缘")
        alias_name = ""
        m = _RE_ALIAS.search(html)
        if m:
            alias_name = self._clean(m.group(1))
            if alias_name and alias_name == name:
                alias_name = ""

        # ===== 播放目录(多线路多剧集) =====
        groups = []          # [(line_title, [(ep_name, href), ...])]
        for m in _RE_SOURCE.finditer(html):
            line_title = self._clean(m.group(1)) or "播放线路"
            eps = []
            for href, ep in _RE_EP_A.findall(m.group(2)):
                href = href.replace("&amp;", "&")
                eps.append((self._clean(ep) or "播放", href))
            if eps:
                groups.append((line_title, eps))

        self.log("  线路: %s" % [(t, len(e)) for t, e in groups])
        if not groups:
            return {"list": []}

        # 尝试用播放页 player_aaaa 的 from 字段生成更友好的线路名
        play_from = []
        play_url = []
        for idx, (line_title, eps) in enumerate(groups, 1):
            alias = self._line_alias(eps[0][1], line_title, idx)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        # 备注: 集数/更新状态 + 线路数
        remarks = []
        if groups and len(groups[0][1]) > 1:
            ep_cnt = len(groups[0][1])
            remarks.append("全%d集" % ep_cnt)
        elif groups and groups[0][1]:
            remarks.append(groups[0][1][0][0])
        if score:
            remarks.append("%s分" % score)
        remarks.append("%d条线路" % len(groups))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_sub": alias_name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_class": vclass,
            "vod_area": area,
            "vod_year": vyear,
            "vod_score": score,
            "vod_remarks": " ".join(remarks),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _line_alias(self, first_ep_url, fallback_title, index):
        """访问该线路第一集播放页, 用 player_aaaa.from 生成线路名"""
        if first_ep_url in self._line_cache:
            return self._line_cache[first_ep_url]
        alias = fallback_title
        try:
            html = self._fetch(self._fix_url(first_ep_url), timeout=10)
            m = _RE_PLAYER.search(html)
            if m:
                info = json.loads(m.group(1))
                frm = info.get("from") or ""
                if frm:
                    alias = _LINE_ALIAS.get(frm, frm)
        except Exception:
            pass
        if not alias or alias == fallback_title:
            alias = fallback_title if fallback_title != "播放线路" \
                else "播放线路%d" % index
        self._line_cache[first_ep_url] = alias
        return alias

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        # 简单缓存(10 分钟)
        now = int(time.time())
        cached = self._play_cache.get(play_page)
        if cached and now and now - cached[0] < 600:
            return cached[1]

        res = self._resolve_play(play_page)
        self._play_cache[play_page] = (now, res)
        return res

    def _resolve_play(self, play_page):
        html = self._fetch(play_page)
        if not html:
            return {"parse": 1, "playUrl": "", "url": play_page,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        info = {}
        m = _RE_PLAYER.search(html)
        if m:
            try:
                info = json.loads(m.group(1))
            except Exception:
                try:
                    info = json.loads(m.group(1).replace("\\/", "/"))
                except Exception:
                    info = {}

        raw_url = info.get("url") or ""
        encrypt = int(info.get("encrypt") or 0)
        frm = info.get("from") or ""

        if raw_url and encrypt in (1, 2):
            try:
                raw_url = base64.b64decode(raw_url).decode("utf-8", "ignore")
            except Exception:
                pass

        raw_url = raw_url.replace("\\/", "/").replace("&amp;", "&").strip()
        self.log("  from=%s encrypt=%s url=%s" % (frm, encrypt, raw_url[:150]))

        if raw_url.startswith("http") and (
                ".m3u8" in raw_url.lower() or ".mp4" in raw_url.lower()):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        # 兜底: 交给 TVBox 嗅探
        return {"parse": 1, "playUrl": "", "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

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

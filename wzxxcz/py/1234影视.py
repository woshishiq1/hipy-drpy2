# coding=utf-8
"""
1234影视 m.aotanajeans.com | TVBox Python 爬虫 
关键:
  - 苹果CMS(stui模板) 站点, 与网站完全一致:
    分类: /html/{tid}.html  ->  筛选列表: /htmlshow/{tid}-{area}-空-{class}-{lang}-{letter}-空-空-{page}-空-空-{year}.html
    详情: /vod/{id}.html   播放页: /paly/{id}-{sid}-{nid}.html  搜索: /htmlsearch/-------------.html?wd=xxx
  - 站点有 TLS 指纹检测(裸 requests/curl 会被挂起), 优先用 curl_cffi(chrome120 + HTTP/1.1) 伪装
  - 解析 player_aaaa JSON, 提取直链 m3u8 (encrypt=0 全部直链, parse=0 直接播)
  - 线路播放顺序与网站一致(路线二/路线三/播放四/路线一 按页面顺序)
"""
import re
import sys
import json
import time
import base64
import urllib.parse

sys.path.append('..')

# ---------- HTTP 层: 站点屏蔽非浏览器 TLS 指纹, 优先 curl_cffi ----------
try:
    from curl_cffi import requests as _cf
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

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
                print("[1234ys]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://m.aotanajeans.com"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

# 分类 type_id -> 站点真实栏目 id
_TID_MAP = {
    "dianying":  "1",
    "dianshiju": "2",
    "zongyi":    "3",
    "dongman":   "4",
    "duanju":    "26",
}

# 子分类(站点一级栏目下的二级栏目, 与网站导航完全一致)
_SUBS_DY = [
    {"n": "全部", "v": ""}, {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"},
    {"n": "爱情片", "v": "8"}, {"n": "科幻片", "v": "9"}, {"n": "恐怖片", "v": "10"},
    {"n": "剧情片", "v": "11"}, {"n": "战争片", "v": "12"}, {"n": "纪录片", "v": "24"},
]
_SUBS_TV = [
    {"n": "全部", "v": ""}, {"n": "美剧", "v": "20"}, {"n": "韩剧", "v": "13"},
    {"n": "日剧", "v": "14"}, {"n": "泰剧", "v": "15"}, {"n": "港剧", "v": "16"},
    {"n": "国产剧", "v": "25"},
]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2021, 1999, -1)]
_LETTERS = [{"n": "全部", "v": ""}] + \
           [{"n": c, "v": c} for c in
            list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]]

_CLASS_DY = ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
             "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
             "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
             "儿童", "网络电影"]
_AREA_DY = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
            "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]
_LANG_DY = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]

_CLASS_TV = ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
             "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"]
_AREA_TV = ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国",
            "英国", "新加坡", "其他"]

_CLASS_ZY = ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
             "曲艺", "生活", "游戏互动", "财经", "求职"]
_AREA_ZY = ["内地", "港台", "日韩", "欧美"]

_CLASS_DM = ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
             "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
             "亲子", "益智", "励志", "其他"]
_AREA_DM = ["国产", "日本", "欧美", "其他"]


def _kv(name, values):
    opts = [{"n": "全部", "v": ""}]
    opts += [{"n": str(v), "v": str(v)} for v in values]
    return {"key": name, "name": {"class": "剧情", "area": "地区", "year": "年份",
                                  "lang": "语言", "letter": "字母",
                                  "sub": "分类"}[name],
            "value": opts}


FILTERS = {
    "dianying": [
        {"key": "sub", "name": "分类", "value": _SUBS_DY},
        _kv("class", _CLASS_DY), _kv("area", _AREA_DY),
        _kv("year", [y for y in range(2021, 1999, -1)]),
        _kv("lang", _LANG_DY), _kv("letter", list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]),
    ],
    "dianshiju": [
        {"key": "sub", "name": "分类", "value": _SUBS_TV},
        _kv("class", _CLASS_TV), _kv("area", _AREA_TV),
        _kv("year", [y for y in range(2021, 1999, -1)]),
    ],
    "zongyi": [
        _kv("class", _CLASS_ZY), _kv("area", _AREA_ZY),
        _kv("year", [y for y in range(2021, 1999, -1)]),
    ],
    "dongman": [
        _kv("class", _CLASS_DM), _kv("area", _AREA_DM),
        _kv("year", [y for y in range(2021, 1999, -1)]),
    ],
    "duanju": [
        # 站点短剧页自身不渲染筛选栏, 但 URL 年份槽位可用, 补一个年份过滤
        _kv("year", [y for y in range(2021, 1999, -1)]),
    ],
}


# ===================== 正则 =====================
# 列表卡片: <a class="stui-vodlist__thumb..." href="/vod/x.html" title="名" data-original="图">
_RE_CARD = re.compile(
    r'<a[^>]+href="(/vod/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"[^>]*>([\s\S]{0,300}?)</a>', re.S | re.I)
_RE_PIC_TEXT = re.compile(r'<span class="pic-text[^"]*">([^<]+)</span>', re.I)

# 搜索页媒体卡片
_RE_CARD_MEDIA = re.compile(
    r'<a[^>]+href="(/vod/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"', re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S)
_RE_POSTER = re.compile(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', re.I)
_RE_ACTOR = re.compile(
    r'<span class="text-muted">主演：</span>([\s\S]*?)</p>', re.I)
_RE_DIRECTOR = re.compile(
    r'<span class="text-muted">导演：</span>([\s\S]*?)</p>', re.I)
_RE_SCORE = re.compile(r'class="branch">([\d.]+)<', re.I)
_RE_INTRO_SKETCH = re.compile(
    r'<span class="detail-sketch">([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路面板(与网站显示顺序一致): 标题(路线二/路线三/播放四/路线一) + 剧集列表
_RE_PANEL = re.compile(
    r'<h3 class="title">([^<]+)</h3></div></div>'
    r'<div class="stui-pannel_bd col-pd clearfix">'
    r'<ul class="stui-content__playlist[^"]*">([\s\S]*?)</ul>', re.S | re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', re.I)

# 总页数: <span class="num">1/266</span>
_RE_PAGE_NUM = re.compile(r'<span class="num">\s*\d+/(\d+)\s*</span>', re.I)

# 主网格卡片块(兜底, 只取主列表, 排除侧栏"本周热门/最新更新")
_RE_BOX_LI = re.compile(
    r'<li class="col-md-\d+[^"]*">([\s\S]*?)</li>', re.I)

# 播放页 player_aaaa JSON
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)


class Spider(Spider):

    def getName(self):
        return "1234影视"

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
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self._cf_sess = None
        self.log("init: site=%s curl_cffi=%s" % (self.site_url, _HAS_CF))

    # -------- HTTP --------
    def _cf_get(self, url, headers, timeout):
        """curl_cffi 伪装 chrome120 指纹 + HTTP/1.1 (绕过站点 TLS 检测)"""
        if not _HAS_CF:
            return None
        try:
            if self._cf_sess is None:
                self._cf_sess = _cf.Session(impersonate="chrome120")
            try:
                r = self._cf_sess.get(url, headers=headers,
                                      timeout=timeout, http_version="v1",
                                      verify=False)
            except TypeError:
                r = self._cf_sess.get(url, headers=headers, timeout=timeout)
            return r.text or ""
        except Exception as e:
            self.log("cf get FAIL: %s" % e)
            # 会话可能已损坏, 重建
            try:
                self._cf_sess = _cf.Session(impersonate="chrome120")
            except Exception:
                pass
            return None

    def _fetch(self, url, timeout=15, headers=None, retry=3):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        for i in range(retry):
            # 1) curl_cffi 指纹伪装
            text = self._cf_get(url, h, timeout) or ""
            if text:
                return text
            # 2) 兜底: base.fetch (requests)
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout)
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)
                if text:
                    return text
            except Exception as e:
                self.log("fetch retry%d FAIL %s -> %s" % (i + 1, url, e))
            text = ""
            time.sleep(0.5)
        return text

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

    def _quote(self, s):
        return urllib.parse.quote(str(s), safe="")

    # -------- 列表解析 --------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))
        for href, alt, pic, inner in matches:
            if href in seen:
                continue
            seen.add(href)
            remarks = ""
            mt = _RE_PIC_TEXT.search(inner)
            if mt:
                remarks = self._clean(mt.group(1))
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic),
                "vod_remarks": remarks,
            })
        if videos:
            return videos

        matches = _RE_CARD_MEDIA.findall(html)
        self.log("  媒体卡片: %d 条" % len(matches))
        for href, alt, pic in matches:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic),
                "vod_remarks": "",
            })
        if videos:
            return videos

        # 兜底: 主网格卡片块 (按属性顺序无关解析, 排除侧栏)
        for chunk in _RE_BOX_LI.findall(html):
            href = re.search(r'href="(/vod/\d+\.html)"', chunk)
            if not href or href.group(1) in seen:
                continue
            seen.add(href.group(1))
            alt = re.search(r'title="([^"]*)"', chunk)
            pic = re.search(r'data-original="([^"]*)"', chunk)
            remarks = ""
            mt = _RE_PIC_TEXT.search(chunk)
            if mt:
                remarks = self._clean(mt.group(1))
            videos.append({
                "vod_id":      href.group(1),
                "vod_name":    self._clean(alt.group(1))[:100] if alt else href.group(1),
                "vod_pic":     self._fix_url(pic.group(1)) if pic else "",
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        return 1

    # ===================== TVBox 接口 =====================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def _build_list_url(self, real_tid, extend, page):
        """完全按站点 URL 规则拼筛选链接:
           /htmlshow/{tid}-{area}-空-{class}-{lang}-{letter}-空-空-{page}-空-空-{year}.html"""
        slot = [""] * 12
        slot[0] = str(real_tid)
        slot[1] = self._quote(extend.get("area", "")) if extend.get("area") else ""
        slot[3] = self._quote(extend["class"]) if extend.get("class") else ""
        slot[4] = self._quote(extend["lang"]) if extend.get("lang") else ""
        slot[5] = self._quote(extend["letter"]) if extend.get("letter") else ""
        slot[8] = str(page)
        slot[11] = self._quote(extend["year"]) if extend.get("year") else ""
        return "%s/htmlshow/%s.html" % (self.site_url, "-".join(slot))

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

        # tid / 子分类
        real_tid = _TID_MAP.get(tid, tid)
        if extend.get("sub"):
            real_tid = extend["sub"]

        url = self._build_list_url(real_tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = ("%s/htmlsearch/-------------.html?wd=%s"
               % (self.site_url, self._quote(key)))
        if page > 1:
            url = ("%s/htmlsearch/-%s------------%d.html"
                   % (self.site_url, self._quote(key), page))
        self.log("search: %s" % url)
        html = self._fetch(url, retry=4)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) if videos else 1,
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url, retry=4)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 封面 + 副标题(pic-text)
        pic = ""
        remarks = ""
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        m = _RE_PIC_TEXT.search(html)
        if m:
            remarks = self._clean(m.group(1))

        # 主演 / 导演 (优先取演员链接, 用逗号分隔)
        def _names(seg):
            names = [self._clean(x) for x in re.findall(r'<a[^>]*>([^<]+)</a>', seg)]
            names = [x for x in names if x]
            return ",".join(names) if names else self._clean(seg)

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = _names(m.group(1))
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = _names(m.group(1))

        # 评分
        score = ""
        cut = html.find("stui-content__playlist")
        content_zone = html[:cut] if cut > 0 else html
        m = _RE_SCORE.search(content_zone)
        if m:
            score = m.group(1)

        # 类型/地区/年份/语言/时间 (站点详情页逐项提取)
        def _field(label):
            mm = re.search(
                r'<span class="text-muted[^"]*">%s：</span>\s*([^<]*)' % label, html)
            return self._clean(mm.group(1)) if mm else ""

        v_type = _field("类型")
        v_area = _field("地区")
        v_year = _field("年份")
        v_lang = _field("语言")
        v_time = _field("时间")

        # 简介 (该站模板简介常为空, 多层兜底)
        intro = ""
        m = _RE_INTRO_SKETCH.search(html)
        if m:
            intro = self._clean(m.group(1))
        if not intro:
            m = _RE_META_DESC.search(html)
            if m:
                intro = self._clean(m.group(1))
        # 站点简介为空时 meta 里只剩 "片名:" 这种噪声, 丢弃
        if intro and re.fullmatch(r".{0,40}[:：]", intro):
            intro = ""

        # 简介只放剧情简介本身(类型/地区/年份等走结构化字段, 由详情面板显示)
        content = INTRO_PREFIX
        if intro:
            content += "\n" + intro

        # ===== 线路 + 剧集 (顺序与网站一致) =====
        play_from = []
        play_url = []
        try:
            for pm in _RE_PANEL.finditer(html):
                line_name = self._clean(pm.group(1))
                eps = []
                for em in _RE_EP_A.finditer(pm.group(2)):
                    href = em.group(1).replace("&amp;", "&")
                    ep_name = self._clean(em.group(2))
                    if not href.startswith("/paly/"):
                        continue
                    if not ep_name:
                        ep_name = "第%d集" % (len(eps) + 1)
                    eps.append("%s$%s" % (ep_name, href))
                if eps:
                    play_from.append(line_name or ("线路%d" % (len(play_from) + 1)))
                    play_url.append("#".join(eps))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

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
            "vod_score": score,
            "vod_type": v_type,
            "vod_class": v_type,
            "type_name": v_type,
            "vod_area": v_area,
            "vod_year": v_year,
            "vod_lang": v_lang,
            "vod_remarks": remarks or v_time or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        info = self._parse_player(html) if html else None

        if info:
            real_url = info.get("url", "")
            if real_url.startswith("//"):
                real_url = "https:" + real_url
            if real_url.startswith("http") and \
                    (".m3u8" in real_url.lower() or ".mp4" in real_url.lower()):
                self.log("  => 直链: %s (from=%s)" % (real_url[:120], info.get("from")))
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self.site_url + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

        # 兜底: 交给 TVBox 嗅探
        self.log("  => 未取到直链, 交嗅探")
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _parse_player(self, html):
        m = _RE_PLAYER.search(html)
        if not m:
            return None
        try:
            d = json.loads(m.group(1))
        except Exception:
            return None
        url = d.get("url", "")
        enc = d.get("encrypt", 0)
        try:
            if enc == 1 and url:
                url = base64.b64decode(url).decode("utf-8")
            elif enc == 2 and url:
                url = base64.b64decode(url + "=" * (-len(url) % 4)).decode("utf-8")
        except Exception:
            pass
        d["url"] = url
        return d

    # -------- 图片代理 --------
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
        self._cf_sess = None

    def close(self):
        self.destroy()

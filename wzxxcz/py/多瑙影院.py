# coding=utf-8
"""
多瑙影院 m.wzdiefa.com | TVBox Python 爬虫 
关键:
  - MacCMS(macplus 模板) 站点
  - 筛选: /vodshow/{tid}-{area}-{by}-{class}-----{page}---{year}.html (12段)
  - 线路: 详情页 playTab(gico xxx) + con_playlist_N 剧集列表, 按站点原顺序
  - 播放: /vodplay/{id}-{sid}-{nid}.html -> player_aaaa JSON 直出 m3u8 (parse:0)
  - 副标题/备注: 卡片 pic-text (如 "HD中字" / "更新至第62集")
"""
import re
import sys
import json
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

    class Spider(_BaseSpider):
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[duonao]", *a)
            except Exception:
                pass


HOST = "https://m.wzdiefa.com"
UA = ("Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "20", "type_name": "短剧"},
]

# 排序 by 参数（与站点 "按时间/按人气/按评分" 一致）
_SORTS = [{"n": "最新上线", "v": "time"},
          {"n": "人气最高", "v": "hits"},
          {"n": "评分最高", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 地区值与站点 vodshow 链接完全一致
_AREA_ALL = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "内地", "v": "内地"},
    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "美国", "v": "美国"}, {"n": "英国", "v": "英国"},
    {"n": "泰国", "v": "泰国"}, {"n": "新加坡", "v": "新加坡"},
    {"n": "其他", "v": "其他"},
]
_AREA_MOVIE = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "加拿大", "v": "加拿大"}, {"n": "印度", "v": "印度"},
    {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "泰国", "v": "泰国"},
    {"n": "其他", "v": "其他"},
]

# 分类(class 参数)值, 与站点 "按类型" 筛选一致
_CLASS_MOVIE = ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争",
                "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战",
                "悬疑", "惊悚", "文艺", "古装", "儿童", "经典", "微电影",
                "历史", "农村", "运动", "青春", "网络电影"]
_CLASS_TV = ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
             "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战",
             "网剧", "其他"]
_CLASS_ZY = ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食",
             "纪实", "曲艺", "生活", "游戏互动", "财经", "求职"]
_CLASS_DM = ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉",
             "校园", "动作", "机战", "运动", "战争", "少年", "少女",
             "社会", "原创", "亲子", "益智", "励志", "其他"]

# 电视剧子频道(tid), 与站点 "按分类" 一致
_TV_SUBS = [
    {"n": "全部", "v": ""}, {"n": "国产剧", "v": "13"},
    {"n": "港剧", "v": "14"}, {"n": "台剧", "v": "15"},
    {"n": "日剧", "v": "16"}, {"n": "韩剧", "v": "22"},
    {"n": "泰剧", "v": "23"}, {"n": "美剧", "v": "24"},
    {"n": "海外剧", "v": "25"},
]


def _class_filter(classes):
    return {"key": "class", "name": "分类",
            "value": [{"n": "全部", "v": ""}] +
                     [{"n": x, "v": x} for x in classes]}


FILTERS = {
    "1": [
        _class_filter(_CLASS_MOVIE),
        {"key": "area", "name": "地区", "value": _AREA_MOVIE},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ],
    "2": [
        {"key": "tv_sub", "name": "频道",
         "value": _TV_SUBS},
        _class_filter(_CLASS_TV),
        {"key": "area", "name": "地区", "value": _AREA_ALL},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ],
    "3": [
        _class_filter(_CLASS_ZY),
        {"key": "area", "name": "地区", "value": _AREA_ALL},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ],
    "4": [
        _class_filter(_CLASS_DM),
        {"key": "area", "name": "地区", "value": _AREA_ALL},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ],
    "20": [
        _class_filter(_CLASS_TV),
        {"key": "area", "name": "地区", "value": _AREA_ALL},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ],
}

# 电视剧子频道 tid -> 保留其主分类名（用于展示）
_TV_SUB_NAME = {s["v"]: s["n"] for s in _TV_SUBS if s["v"]}


# ===================== 正则 =====================
# 列表卡片: 缩略图锚点带 title + data-original, 后跟 pic-text 备注
_RE_CARD = re.compile(
    r'<a[^>]*href="(/voddetail/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"[^>]*>[\s\S]{0,600}?'
    r'<span class="pic-text[^"]*">([^<]*)</span>',
    re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="title[^"]*">([^<]+)</h1>', re.I)
_RE_PIC = re.compile(r'data-original="(https?://[^"]+\.(?:jpg|png|webp))"',
                     re.I)
_RE_INTRO = re.compile(r'id="cText"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_M = re.compile(
    r'detail-intro-txt[^"]*">([\s\S]*?)<span class="more">', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)
_RE_META = re.compile(
    r'<span class="text-muted">([^：]+)：</span>([\s\S]*?)</p>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)
_RE_UPDATE = re.compile(r'<span class="pic-text[^"]*">([^<]*)</span>', re.I)
_RE_SCORE = re.compile(r'id="pingfen">([\d.]+)<', re.I)

# 剧集: 线路 tab (gico 源名) + 对应 ul#con_playlist_N
_RE_TAB = re.compile(
    r'<a class="gico ([\w]+)" href="#(con_playlist_\d+)"[^>]*>([^<]+)</a>',
    re.I)
_RE_LIST = re.compile(
    r'<ul[^>]*id="(con_playlist_\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP = re.compile(r'<a href="(/vodplay/[\w\-]+\.html)">([^<]+)</a>', re.I)

# 播放页: player_aaaa JSON
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 分页: "共 N 个影片" / 翻页链接
_RE_TOTAL = re.compile(r'共&nbsp;<span class="text-green">(\d+)</span>')
_RE_PGLINK = re.compile(
    r'<a class="page[^"]*" href="/(?:vodshow|vodsearch)/([^"]+)"'
    r'[^>]*title="([^"]*)"', re.I)


class Spider(Spider):

    def getName(self):
        return "多瑙影院"

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
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, retries=2, headers=None):
        for i in range(retries):
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
                self.log("fetch FAIL(%d) %s -> %s" % (i + 1, url, e))
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
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos
        for href, title, pic, remark in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic),
                "vod_remarks": self._clean(remark),
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def _page_count(self, html, limit=42):
        if not html:
            return 1
        def _page_num(href):
            # vodshow/vodsearch 路径 12 段: 第 9 段(idx 8) 为页码
            segs = (urllib.parse.unquote(href)
                    .replace(".html", "").split("-"))
            if len(segs) > 8 and segs[8].isdigit():
                return int(segs[8])
            digs = [int(x) for x in segs if x.isdigit()]
            return max(digs) if digs else 0

        last = 0
        has_next = False
        for href, title in _RE_PGLINK.findall(html):
            if title == "下一页":
                has_next = True
                last = max(last, _page_num(href))
            else:
                m2 = re.search(r"第(\d+)页", title)
                if m2:
                    last = max(last, int(m2.group(1)))
                elif title == "尾页":
                    last = max(last, _page_num(href))
        if last:
            return last
        if has_next:
            return 9999
        m = _RE_TOTAL.search(html)
        if m:
            try:
                return max(1, (int(m.group(1)) + limit - 1) // limit)
            except Exception:
                pass
        return 9999

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

        # 电视剧子频道 (国产剧/港剧... 独立 tid)
        real_tid = str(extend.get("tv_sub") or tid)

        area = urllib.parse.quote(str(extend.get("area") or ""))
        by = str(extend.get("by") or "")
        cls = urllib.parse.quote(str(extend.get("class") or ""))
        year = str(extend.get("year") or "")

        # /vodshow/{tid}-{area}-{by}-{class}-----{page}---{year}.html
        # 12 段: [tid, area, by, class, '', '', '', '', page, '', '', year]
        segs = [real_tid, area, by, cls, "", "", "", "",
                str(page), "", "", year]
        url = "%s/vodshow/%s.html" % (self.site_url, "-".join(segs))
        self.log("category: %s" % url)
        html = self._fetch(url)

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 40, "total": pagecount * 40,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        # /vodsearch/{kw}----------{page}---.html
        url = "%s/vodsearch/%s----------%d---.html" % (
            self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html, limit=24),
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
        pic = ""
        m = _RE_PIC.search(html)
        if m:
            pic = m.group(1)

        # 备注 (副标题: "HD中字"/"更新至第62集")
        remarks = ""
        m = _RE_UPDATE.search(html)
        if m:
            remarks = self._clean(m.group(1))

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 元信息: 导演/主演/年代/地区/类型
        meta = {}
        for k, v in _RE_META.findall(html):
            k = self._clean(k)
            seg = self._clean(v)
            texts = [self._clean(x) for x in _RE_A_TEXT.findall(v)]
            if texts:
                seg = ", ".join([t for t in texts if t])
            meta[k] = seg.strip(" ,")

        director = meta.get("导演", "")
        actor = re.sub(r"\s*,\s*", ", ", meta.get("主演", ""))
        year = meta.get("年代", "")
        area = meta.get("地区", "")
        vtype = meta.get("类型", "")

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_M.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))

        # 元信息(年代/地区/类型)走 vod_year/vod_area/vod_class 字段,
        # 由 TVBox 详情页头部渲染; 简介只保留前缀 + 剧情正文
        content = INTRO_PREFIX + "\n" + (content or "暂无简介")

        # ===== 剧集提取（按站点 tab 顺序）=====
        tabs = []
        seen_tab = set()
        for src, pid, label in _RE_TAB.findall(html):
            if pid in seen_tab:
                continue
            seen_tab.add(pid)
            tabs.append((src, pid, self._clean(label)))

        lists = {pid: body for pid, body in _RE_LIST.findall(html)}

        play_from = []
        play_url = []
        for src, pid, label in tabs:
            body = lists.get(pid)
            if not body:
                continue
            eps = []
            for href, ep in _RE_EP.findall(body):
                href = href.replace("&amp;", "&")
                if href.startswith("/"):
                    href = self.site_url + href
                eps.append("%s$%s" % (self._clean(ep), href))
            if not eps:
                continue
            play_from.append(label)
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
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_class": vtype,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        # 播放页地址缓存 10 分钟
        import time
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page, headers={
            "Referer": self.site_url + "/"})
        real_url = ""
        if html:
            m = _RE_PLAYER.search(html)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{[^\n]*\})', html)
            if m:
                raw = (m.group(1)
                       .replace("\\/", "/").replace('\\"', '"'))
                try:
                    pj = json.loads(raw)
                    real_url = pj.get("url", "") or ""
                    encrypt = int(pj.get("encrypt", 0) or 0)
                    self.log("  from=%s encrypt=%s url=%s" % (
                        pj.get("from", ""), encrypt, real_url[:160]))
                    # encrypt=1: url 为 encodeURIComponent 后的直链
                    if encrypt == 1 and real_url:
                        real_url = urllib.parse.unquote(real_url)
                except Exception as e:
                    self.log("  player_aaaa 解析失败: %s" % e)
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if m2:
                        real_url = m2.group(1)

        if real_url and (".m3u8" in real_url.lower() or
                         ".mp4" in real_url.lower()):
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
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
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
                "User-Agent": UA, "Referer": self.site_url + "/"},
                timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

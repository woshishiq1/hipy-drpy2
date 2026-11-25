# coding=utf-8
"""
七五网 qwfun.com | TVBox Python 爬虫
站点结构（线上快照实证，MacCMS piankuwap 移动模板）:
  - 首页:   /
  - 主分类: /vt/<tid>.html            （第 1 页）
            /vt/<tid>-<page>.html     （分页）
  - 筛选:   /ms/<12 段空槽>.html
            段0=tid / 段1=地区 / 段2=排序 / 段3=类型 / 段4=语言 /
            段8=页码 / 段11=年代年份，段5~7、9~10 空段占位；中文段 percent-encode
  - 详情:   /mv/<id>.html
  - 播放:   /py/<vid>-<sid>-<nid>.html
  - 搜索:   优先 /ajax/suggest?mid=1&wd=<词>&limit=60 JSON（不过验证码墙，
            不支持 page 翻页、固定前 60 条本地切片）；兜底 /vs/-------------.html
            ?wd=<词>，命中图形验证码判空，不强行破解

  - 卡片(分类/搜索): li > a[href=/mv/<id>.html][title]，
            article img src；span.s1=清晰度(HD)；span.s2=评分；
            h3 b=片名；p=副标题(年份 / 地区 / 类型,…)
  - 卡片(首页): a.pic[href=/mv/..][img] + a.tit[href=/mv/..][片名]（indicator-info 角标）
  - 详情:   h1 片名 + span.year (2026)；.img img 海报；
            简介 p.sqjj_a(完整折叠全文) > p.zkjj_a(摘要) > meta description 兜底；
            导演/主演/地区/类型 标签后 <a> 列表（部分被 HTML 注释包裹，取注释内外可见文本）；
            评分 豆瓣 x.x；状态 HD + 更新时间
  - 线路:   select.py-tabs option 线路名(剥 (n) 计数)，顺序=站点 DOM 序；
            player-all-ul 内 <li style="display:.."> 块与 option 一一对应，
            块内 ul.player li a[href=/py/..][集名]
  - 播放:   player_aaaa JSON（花括号配平），encrypt=0/空 取 url；
            master 多码率取首条子 m3u8（urljoin）；未命中兜底 parse:1 交客户端嗅探

站点防护（实证）:
  - 间歇返回 envoy upstream connect error / connection timeout（91 字节纯文本小页），
    重试即恢复；首页下发会话 Cookie，后续分类/详情/播放复用同一 Session。
  - 主备域名（顺序即轮换顺序，均为同站镜像，2026-11-24 实测）:
      qwfun → qwmkv → qwfilm → qnnull → qwshow → qnhot → qmp4（末位兜底，标注需科学上网）
    qncool / qwmp4 / gmp4 实测 503 未写入；qn63.com 为地址公告页非影视源，未写入。
  - 选集分段: 单条 play_url 超 1900B 切段，子线路名加 (1)(2) 后缀，
    froms/urls 一一对应，防客户端 2048B 截断长剧/短剧选集。
"""
import re
import sys
import json
import time
import socket
import urllib.parse

sys.path.append('..')

# ---- 强制 IPv4：禁用 IPv6（云端出口 IPv6 不稳）----
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            if r[0] == socket.AF_INET]


socket.getaddrinfo = _ipv4_getaddrinfo

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
                print("[qwfun]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站专属配置 =====================
# 主备域名（顺序即轮换顺序，均为同站镜像）
HOSTS = [
    "https://www.qwfun.com",
    "https://www.qwmkv.com",
    "https://www.qwfilm.com",
    "https://www.qnnull.com",
    "https://www.qwshow.com",
    "https://www.qnhot.com",
    "https://www.qmp4.com",  # 标注需科学上网，间歇不通，置末位兜底
]
# 未写入：www.qncool.com / www.qwmp4.com / www.gmp4.com 实测 503；
#         www.qn63.com 为地址公告页，非影视源。
HOST = HOSTS[0]
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "剧集"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "30", "type_name": "短剧"},
]

# 类型（URL 段3，各分类站点库内实际标签，页面实证）
_TYPES = {
    "1": ["剧情", "科幻", "动作", "喜剧", "爱情", "冒险", "儿童", "歌舞", "音乐",
          "奇幻", "动画", "恐怖", "惊悚", "丧尸", "战争", "传记", "纪录", "犯罪",
          "悬疑", "西部", "灾难", "古装", "武侠", "家庭", "短片", "校园", "文艺",
          "运动", "青春", "同性", "励志", "人性", "美食", "女性", "治愈", "历史"],
    "2": ["剧情", "科幻", "动作", "喜剧", "爱情", "冒险", "儿童", "歌舞", "音乐",
          "奇幻", "动画", "恐怖", "惊悚", "丧尸", "战争", "传记", "纪录", "犯罪",
          "悬疑", "西部", "灾难", "古装", "武侠", "家庭", "短片", "校园", "文艺",
          "运动", "青春", "同性", "励志", "人性", "美食", "女性", "治愈", "历史"],
    "3": ["真人秀", "脱口秀", "选秀", "情感", "喜剧", "访谈", "播报", "旅游", "音乐",
          "美食", "纪实", "曲艺", "生活", "游戏", "财经", "求职", "体育", "MV", "纪录"],
    "4": ["剧情", "萌系", "科幻", "日常", "战斗", "战争", "热血", "机战", "游戏",
          "搞笑", "恋爱", "后宫", "百合", "基腐", "冒险", "儿童", "歌舞", "音乐",
          "奇幻", "恐怖", "惊悚", "犯罪", "悬疑", "西部", "灾难", "古装", "武侠",
          "泡面", "校园", "运动", "体育", "青春", "美食", "治愈", "致郁", "励志",
          "历史", "其他"],
    "30": ["短剧", "古装", "复仇", "强者", "悬疑", "甜宠", "神豪", "穿越", "虐恋",
           "逆袭", "重生", "萌宝"],
}

# 地区（URL 段1，站点原文；线上实证：动漫 tid4 站点单独排序，其余四分类同序）
_AREAS_COMMON = ["大陆", "香港", "台湾", "日本", "韩国", "泰国", "美国", "英国", "法国",
                 "德国", "印度", "丹麦", "瑞典", "荷兰", "加拿大", "俄罗斯", "意大利",
                 "比利时", "西班牙", "澳大利亚", "其他"]
_AREAS_ANIME = ["美国", "英国", "法国", "大陆", "日本", "香港", "台湾", "韩国", "泰国",
                "德国", "印度", "丹麦", "瑞典", "荷兰", "加拿大", "俄罗斯", "意大利",
                "比利时", "西班牙", "澳大利亚", "其他"]
_AREAS = {"1": _AREAS_COMMON, "2": _AREAS_COMMON, "3": _AREAS_COMMON,
          "4": _AREAS_ANIME, "30": _AREAS_COMMON}

# 语言（URL 段4，站点原文；线上实证：动漫 tid4 站点单独排序，其余四分类同序）
_LANGS_COMMON = ["国语", "粤语", "英语", "法语", "日语", "韩语", "泰语", "德语", "俄语",
                 "闽南语", "丹麦语", "波兰语", "瑞典语", "印地语", "挪威语", "意大利语",
                 "西班牙语", "无对白", "其他"]
_LANGS_ANIME = ["英语", "法语", "国语", "粤语", "日语", "韩语", "泰语", "德语", "俄语",
                "闽南语", "丹麦语", "波兰语", "瑞典语", "印地语", "挪威语", "意大利语",
                "西班牙语", "无对白", "其他"]
_LANGS = {"1": _LANGS_COMMON, "2": _LANGS_COMMON, "3": _LANGS_COMMON,
          "4": _LANGS_ANIME, "30": _LANGS_COMMON}

# 年代（URL 段11，站点实证 2010~2027）
_YEARS = [str(y) for y in range(2027, 2009, -1)]

# 排序（URL 段2）
_SORTS = [("最新更新", "time"), ("人气最高", "hits"), ("评分最高", "score")]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    # 展示顺序对齐站点展开筛选（dl c1~c4）：类型 → 年代 → 地区 → 语言；排序在筛选区末行
    FILTERS[tid] = [
        {"key": "type", "name": "类型", "value": _opts(_TYPES.get(tid, []))},
        {"key": "year", "name": "年代", "value": _opts(_YEARS)},
        {"key": "area", "name": "地区", "value": _opts(_AREAS.get(tid, _AREAS_COMMON))},
        {"key": "lang", "name": "语言", "value": _opts(_LANGS.get(tid, _LANGS_COMMON))},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]

# ===================== 正则 =====================
# 分类/搜索卡片 li 块
_RE_LI = re.compile(r'<li[^>]*>\s*<a\s+href="(/mv/\d+\.html)"[\s\S]*?</li>', re.I)
_RE_CARD_HREF = re.compile(r'/mv/(\d+)\.html', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_IMG = re.compile(r'<img[^>]*?(?:data-original|src)="([^"]*)"', re.I)
_RE_S1 = re.compile(r'<span class="s1"[^>]*>([\s\S]*?)</span>', re.I)
_RE_S2 = re.compile(r'<span class="s2"[^>]*>([\s\S]*?)</span>', re.I)
_RE_H3B = re.compile(r'<h3[^>]*>\s*<b[^>]*>([\s\S]*?)</b>', re.I)
_RE_P = re.compile(r'<p[^>]*>([\s\S]*?)</p>', re.I)

# 首页卡片：a.pic[href][img] + a.tit[href][片名]
_RE_PIC_A = re.compile(
    r'<a\s+class="pic"[^>]*href="(/mv/\d+\.html)"[^>]*>\s*<img[^>]*?(?:src|data-original)="([^"]*)"',
    re.I)
_RE_TIT_A = re.compile(
    r'<a\s+class="tit"[^>]*href="(/mv/\d+\.html)"[^>]*>([\s\S]*?)</a>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_YEAR_SPAN = re.compile(r'<span class="year"[^>]*>\s*[（(]?(\d{4})[)）]?\s*</span>', re.I)
_RE_POSTER = re.compile(
    r'<div class="img"[^>]*>\s*<a[^>]*>\s*<img[^>]*?(?:src|data-original)="([^"]*)"', re.I)
_RE_INTRO_FULL = re.compile(r'<p class="sqjj_a"[^>]*>([\s\S]*?)</p>', re.I)
_RE_INTRO_SKETCH = re.compile(r'<p class="zkjj_a"[^>]*>([\s\S]*?)</p>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 标签块：导演/主演/地区/类型/状态，到 </p> 结束；标签后 </span> 位置不固定（可选）
_RE_FIELD_BLOCK = {
    "director": re.compile(r'导演：(?:</span>)?([\s\S]*?)</p>', re.I),
    "actor":    re.compile(r'主演：(?:</span>)?([\s\S]*?)</p>', re.I),
    "area":     re.compile(r'地区：(?:</span>)?([\s\S]*?)</p>', re.I),
    "classify": re.compile(r'类型：(?:</span>)?([\s\S]*?)</p>', re.I),
    "status":   re.compile(r'状态：(?:</span>)?([\s\S]*?)</p>', re.I),
}
_RE_SCORE = re.compile(r'豆瓣\s*([0-9]+(?:\.[0-9])?)', re.I)
_RE_SCORE_IMDB = re.compile(r'IMDB\s*([0-9]+(?:\.[0-9])?)', re.I)

# 线路 option / 选集
_RE_OPTION = re.compile(r'<option[^>]*>([^<]*)</option>', re.I)
_RE_LINE_BLOCK = re.compile(
    r'<li style="display:[^"]*">\s*<ul class="player"[^>]*>([\s\S]*?)</ul>\s*</li>', re.I)
_RE_EP = re.compile(r'<a[^>]*href="(/py/[^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放直链
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)
_RE_IFRAME = re.compile(r'<iframe[^>]*src="([^"]+)"', re.I)
_RE_DIRECT = re.compile(r'\.(?:m3u8|mp4)(?:\b|[?#])', re.I)

# 验证码 / 安全验证页（图形人机验证，requests 无法自动过，判空兜底）
_RE_CAPTCHA = re.compile(r'系统安全验证|vdimgck|name="validate"', re.I)

# 上游网关故障纯文本小页
_RE_UPSTREAM = re.compile(
    r'upstream connect error|connection timeout|connection reset|bad gateway|'
    r'service unavailable|reset reason', re.I)


class Spider(Spider):

    def getName(self):
        return "七五网"

    # ---------------- 基础 ----------------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.hosts = list(HOSTS)
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self._host_idx = 0
        for i, h in enumerate(self.hosts):
            if h.rstrip("/") == self.site_url:
                self._host_idx = i
                break

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
        self._session = None
        self._warmed = False
        self._play_cache = {}

    def getDependence(self):
        return []

    def log(self, *a, **kw):
        try:
            print("[qwfun]", *a)
        except Exception:
            pass

    # ---------------- 会话 / 主备轮换 ----------------
    def _session_get(self):
        if self._session is None:
            try:
                import requests as _rq
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            except Exception as e:
                self.log("自建 Session 失败:", e)
                self._session = None
        return self._session

    def _is_bad(self, text, status=200):
        if not text:
            return True
        if status and int(status) in (403, 502, 503, 500, 404):
            return True
        if len(text) < 200 and _RE_UPSTREAM.search(text.lower()):
            return True
        return False

    def _switch_host(self):
        """轮换到下一个主备域名，重置会话与预热标记。"""
        for _ in range(len(self.hosts) - 1):
            self._host_idx = (self._host_idx + 1) % len(self.hosts)
            cand = self.hosts[self._host_idx].rstrip("/")
            if cand != self.site_url:
                self.site_url = cand
                self.headers["Referer"] = self.site_url + "/"
                self._session = None
                self._warmed = False
                self.log("轮换域名 ->", self.site_url)
                return True
        return False

    def _warm_up(self):
        """先访问首页下发会话 Cookie，后续复用同一 Session。"""
        if self._warmed:
            return
        try:
            self._http_get(self.site_url + "/", timeout=(10, 20))
            self._warmed = True
        except Exception as e:
            self.log("预热失败:", e)

    def _http_get(self, url, headers=None, timeout=15):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._session_get()
        rsp = None
        try:
            if sess is not None:
                rsp = sess.get(url, headers=h, timeout=timeout)
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("GET 异常:", url, repr(e)[:120])
            rsp = None

        text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200) if rsp is not None else 0

        if self._is_bad(text, status):
            # 重新落会话后重放一次
            self._session = None
            sess2 = self._session_get()
            try:
                if sess2 is not None:
                    sess2.get(self.site_url + "/", headers=h, timeout=(10, 20))
                    rsp = sess2.get(url, headers=h, timeout=timeout)
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else ""
                status = getattr(rsp, "status_code", 200)
            except Exception as e:
                self.log("重放异常:", repr(e)[:120])
                text, status = "", 0
        return rsp

    def _fetch(self, url, timeout=15, headers=None, tries=3):
        last = ""
        for i in range(tries):
            try:
                rsp = self._http_get(url, headers=headers, timeout=timeout)
                text = rsp.text if rsp is not None and hasattr(rsp, "text") else (
                    rsp.content.decode("utf-8", "ignore")
                    if rsp is not None and hasattr(rsp, "content") else "")
                status = getattr(rsp, "status_code", 200) if rsp is not None else 0
                if not self._is_bad(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, repr(e)[:120])
                last = ""
            if i < tries - 1:
                time.sleep(1.2 * (i + 1))
        # 多次遇障：轮换主备域名再取一次
        if self._switch_host():
            new_url = self._rebase_url(url, self.site_url)
            try:
                rsp = self._http_get(new_url, headers=headers, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else ""
                if not self._is_bad(text, getattr(rsp, "status_code", 200)):
                    return text
            except Exception as e:
                self.log("轮换后重试失败:", repr(e)[:120])
        return ""

    # ---------------- 工具 ----------------
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

    def _rebase_url(self, url, base):
        """轮换域名后，把本站 URL 的根域替换为新 base；外部直链原样保留。"""
        if not url:
            return url
        for h in self.hosts:
            if url.startswith(h):
                return base + url[len(h):]
        if url.startswith("http"):
            return url
        return base + (url if url.startswith("/") else "/" + url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<!--[\s\S]*?-->", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _try_json(self, text):
        """宽松 JSON 解析：先直解，失败再截取首个 {...} 块；非 JSON 返回 None。"""
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", str(text), re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    # ---------------- 卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 1) 分类/搜索：li > a[href=/mv/<id>.html] 块
        for m in _RE_LI.finditer(html):
            block = m.group(0)
            mh = _RE_CARD_HREF.search(block)
            if not mh:
                continue
            href = "/mv/%s.html" % mh.group(1)
            if href in seen:
                continue

            mt = _RE_TITLE.search(block)
            title = self._clean(mt.group(1)) if mt else ""
            if not title:
                mh3 = _RE_H3B.search(block)
                if mh3:
                    title = self._clean(mh3.group(1))
            if not title:
                # 轮播等无 title 块：不占用 seen，留给第二步 pic/tit 兜底配对
                continue
            seen.add(href)

            mp = _RE_IMG.search(block)
            pic = self._fix_url(mp.group(1)) if mp else self.default_pic

            # 备注：清晰度 s1 + 评分 s2
            remarks = ""
            ms1 = _RE_S1.search(block)
            if ms1:
                remarks = self._clean(ms1.group(1))
            ms2 = _RE_S2.search(block)
            if ms2:
                score = self._clean(ms2.group(1))
                if score and score.upper() != "N/A":
                    remarks = (remarks + " " + score).strip()

            # 副标题：p 行（年份 / 地区 / 类型,…）
            subtitle = ""
            mpb = _RE_P.search(block)
            if mpb:
                subtitle = self._clean(mpb.group(1))

            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })

        # 2) 首页兜底：a.pic 出封面，a.tit 出片名，按 href 配对（与第一步 seen 去重）
        pics = {}
        for mp in _RE_PIC_A.finditer(html):
            pics[mp.group(1)] = mp.group(2)
        for mt in _RE_TIT_A.finditer(html):
            href, inner = mt.group(1), mt.group(2)
            if href in seen:
                continue
            title = self._clean(inner)
            title = re.sub(r"^[\d/]+\s*", "", title).strip()
            if not title:
                continue
            seen.add(href)
            pic = self._fix_url(pics.get(href, ""))
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": "",
                "vod_subtitle": "",
            })
        return videos

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            self._warm_up()
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            return {"list": self._parse_cards(html)}
        except Exception as e:
            self.log("homeVideoContent 异常:", e)
            return {"list": []}

    def _pagecount(self, videos, page, limit=36):
        """满页滑动判断（线上实证：站点分页为 5 页滑动窗口，HTML/JS 均不下发真实
        总页数与影片总数，深页持续返满页）。
        - 当前页 0 张：空页，仅 1 页；
        - 0 < 张数 < limit：末页；
        - 张数 >= limit：视为尚有下一页，可继续翻页。
        不再取分页窗口内最大页码（首页窗口只列 1~5，会把翻页截断在第 5 页，
        漏掉第 6 页起的真实新片）。"""
        n = len(videos)
        if n == 0:
            return 1
        if n >= limit:
            return page + 1
        return page

    def _filter_slug(self, tid, extend, page=1):
        """构造筛选 12 段空槽 URL。
        段0=tid / 段1=地区 / 段2=排序 / 段3=类型 / 段4=语言 /
        段8=页码 / 段11=年代年份，段5~7、9~10 空段占位。"""
        seg = [""] * 12
        seg[0] = str(tid)
        if extend.get("area"):
            seg[1] = extend["area"]
        if extend.get("sort"):
            seg[2] = extend["sort"]
        if extend.get("type"):
            seg[3] = extend["type"]
        if extend.get("lang"):
            seg[4] = extend["lang"]
        seg[8] = str(page) if page else ""
        if extend.get("year"):
            seg[11] = str(extend["year"])
        parts = [urllib.parse.quote(x, safe="") for x in seg]
        return "/ms/" + "-".join(parts) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        try:
            self._warm_up()
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

            if extend:
                url = self.site_url + self._filter_slug(tid, extend, page)
            elif page == 1:
                url = self.site_url + "/vt/%s.html" % tid
            else:
                url = self.site_url + "/vt/%s-%d.html" % (tid, page)

            self.log("category: %s" % url)
            html = self._fetch(url)
            self.log("  HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            limit = 36
            pagecount = self._pagecount(videos, page, limit)
            total = 0 if not videos else pagecount * limit
            self.log("  最终: %d 条, 当前页 %d, 估总页 %d" % (len(videos), page, pagecount))

            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": limit, "total": total,
            }
        except Exception as e:
            self.log("categoryContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 36, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            self._warm_up()
            page = int(pg) if pg else 1
            raw_kw = str(key or "").strip()
            if not raw_kw:
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": 36, "total": 0}
            q = urllib.parse.quote(raw_kw)
            videos = []

            # 第一通道：站内 suggest JSON（实测不经过图形验证码墙）；
            # 接口不支持 page 翻页，固定返回前 60 条，本地按 36/页切片。
            api = "%s/ajax/suggest?mid=1&wd=%s&limit=60" % (self.site_url, q)
            self.log("search suggest: %s" % api)
            text = self._fetch(api)
            data = self._try_json(text)
            if isinstance(data, dict):
                for it in (data.get("list") or []):
                    vid = str(it.get("id") or it.get("vod_id") or "").strip()
                    if not vid:
                        continue
                    name = self._clean(it.get("name") or it.get("vod_name") or "")
                    pic = self._fix_url(it.get("pic") or "") or self.default_pic
                    videos.append({
                        "vod_id": "/mv/%s.html" % vid,
                        "vod_name": name[:100],
                        "vod_pic": pic,
                        "vod_remarks": "",
                        "vod_subtitle": "",
                    })

            # 第二通道兜底：HTML 搜索页（命中图形验证码墙则判空，不强行破解）
            if not videos:
                url = "%s/vs/-------------.html?wd=%s&page=%d" % (
                    self.site_url, q, page)
                self.log("search html 兜底: %s" % url)
                html = self._fetch(url)
                if _RE_CAPTCHA.search(html):
                    self.log("  搜索命中安全验证页，返回空")
                    return {"list": [], "page": page, "pagecount": 1,
                            "limit": 36, "total": 0}
                videos = self._parse_cards(html)

            total = len(videos)
            start = (page - 1) * 36
            part = videos[start:start + 36]
            pc = (total + 35) // 36 if total else 1
            return {"list": part, "page": page, "pagecount": pc,
                    "limit": 36, "total": total}
        except Exception as e:
            self.log("searchContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 36, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _field_text(self, plain, key):
        """plain 为已剥 HTML 注释的页面；取标签后 <a> 文本，兜底纯文本。"""
        m = _RE_FIELD_BLOCK[key].search(plain)
        if not m:
            return ""
        block = m.group(1)
        names = [self._clean(a) for a in _RE_A.findall(block)]
        names = [x for x in names if x and x not in ("-->", "<!--")]
        if names:
            return ", ".join(names)
        return self._clean(block)

    def _clean_status(self, text):
        """状态角标：去掉更新日期时间，保留清晰度/集数状态文本。"""
        if not text:
            return ""
        text = re.sub(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?", "", text)
        text = re.sub(r"\s+/\s*", " ", text)
        return self._clean(text)

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vod_id = str(ids[0])
            url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
            self.log("detail: %s" % url)

            html = self._fetch(url)
            if not html:
                return {"list": []}

            # 片名
            name = ""
            mh = _RE_H1.search(html)
            if mh:
                name = self._clean(mh.group(1))
            if not name:
                mt = re.search(r"<title>(.*?)</title>", html, re.S)
                if mt:
                    name = self._clean(mt.group(1).split("-")[0].split("_")[0])
            name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

            # 年份
            year = ""
            my = _RE_YEAR_SPAN.search(html)
            if my:
                year = my.group(1)

            # 海报
            pic = self.default_pic
            mp = _RE_POSTER.search(html)
            if mp:
                pic = self._fix_url(mp.group(1)) or self.default_pic

            # 简介：完整折叠全文 sqjj_a 优先 → 摘要 zkjj_a 兜底 → meta description
            content = ""
            mc = _RE_INTRO_FULL.search(html)
            if mc:
                content = self._clean(mc.group(1))
            if not content:
                ms = _RE_INTRO_SKETCH.search(html)
                if ms:
                    content = self._clean(ms.group(1))
            if not content:
                md = _RE_META_DESC.search(html)
                if md:
                    content = self._clean(md.group(1))
            # 剥展开/收起标记
            content = re.sub(r"\[(?:展开全部|收起部分|收起)\]", "", content).strip()
            content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

            # 先剥 HTML 注释（部分字段链接/整块被注释包裹），字段提取在 plain 上进行
            plain = re.sub(r"<!--[\s\S]*?-->", "", html)

            # 元信息
            director = self._field_text(plain, "director")
            actor = self._field_text(plain, "actor")
            area = self._field_text(plain, "area")
            classify = self._field_text(plain, "classify")
            status = self._clean_status(self._field_text(plain, "status"))

            # 评分：豆瓣优先，IMDB 兜底；N/A / 空值返空
            score = ""
            ms = _RE_SCORE.search(plain)
            if ms:
                score = ms.group(1)
            if not score:
                mi = _RE_SCORE_IMDB.search(plain)
                if mi:
                    score = mi.group(1)

            # ===== 线路与选集 =====
            play_from, play_url = self._parse_lines(html)
            if not play_from:
                self.log("  未解析到选集")
                return {"list": []}

            remarks = status or ("%d条线路" % len(play_from))

            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name[:100],
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_score": score,
                "vod_remarks": remarks,
                "vod_area": area,
                "vod_year": year,
                "vod_lang": "",
                "vod_class": classify,
                "type_name": classify,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]}
        except Exception as e:
            self.log("detailContent 异常:", e)
            return {"list": []}

    def _parse_lines(self, html):
        """select.py-tabs option 顺序 = 站点线路顺序；player-all-ul 内 li 块按
        DOM 序与 option 一一对应。返回 (play_from, play_url)，保序去重。"""
        options = [self._clean(o) for o in _RE_OPTION.findall(html)]
        # 剥线路名后的 (n) 计数，如 西瓜(1) → 西瓜
        line_names = []
        for o in options:
            line_names.append(re.sub(r"\(\d+\)\s*$", "", o).strip() or "线路")

        blocks = _RE_LINE_BLOCK.findall(html)
        play_from, play_url = [], []
        count = min(len(line_names), len(blocks))
        for i in range(count):
            block = blocks[i]
            eps = []
            seen = set()
            for ma in _RE_EP.finditer(block):
                href, ep_name = ma.group(1), self._clean(ma.group(2))
                if href in seen:
                    continue
                seen.add(href)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            line_name = line_names[i]
            # 重名线路去重编号
            base, k = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, k)
                k += 1
            body = "#".join("%s$%s" % (n, h) for n, h in eps)
            # 单条 play_url 超字节上限时切段，子线路名加 (1)(2) 后缀，froms/urls 一一对应
            for sub_label, sub_body in self._seg(line_name, body):
                play_from.append(sub_label)
                play_url.append(sub_body)
        return play_from, play_url

    # 单条 play_url 的 UTF-8 字节上限（客户端单条超 2048B 会截断长剧选集）
    SEG_BYTES = 1900

    def _seg(self, label, body):
        """选集串按字节上限切段；未超限原样返回。返回 [(子线路名, 选集串), ...]。"""
        eps = [x for x in str(body or "").split("#") if x.strip()]
        chunks, cur, size = [], [], 0
        for seg in eps:
            b = len(seg.encode("utf-8")) + 1
            if cur and size + b > self.SEG_BYTES:
                chunks.append(cur)
                cur, size = [], 0
            cur.append(seg)
            size += b
        if cur:
            chunks.append(cur)
        if len(chunks) <= 1:
            return [(label, body)]
        return [("%s(%d)" % (label, i + 1), "#".join(c))
                for i, c in enumerate(chunks)]

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        try:
            play_page = id if str(id).startswith("http") else self._fix_url(id)
            now = int(time.time())
            if play_page in self._play_cache:
                ts, res = self._play_cache[play_page]
                if now - ts < 600:
                    return res

            header = {"User-Agent": UA, "Referer": self.site_url + "/"}
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

            if stream and _RE_DIRECT.search(stream.lower()):
                stream = self._resolve_sub_stream(stream, header)
                res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链: %s" % stream[:160])
                return res

            # 提取不到直链：交客户端嗅探播放页
            target = stream if stream.startswith("http") else play_page
            res = {"parse": 1, "playUrl": "", "url": target, "header": header}
            self._play_cache[play_page] = (now, res)
            return res
        except Exception as e:
            self.log("playerContent 异常:", e)
            header = {"User-Agent": UA, "Referer": self.site_url + "/"}
            return {"parse": 1, "playUrl": "",
                    "url": str(id) if str(id).startswith("http") else self._fix_url(id),
                    "header": header}

    def _player_json(self, html):
        """player_aaaa JSON 括号深度配对精确截取（正确处理嵌套对象/转义）。"""
        i = html.find("player_aaaa")
        if i < 0:
            return ""
        j = html.find("{", i)
        if j < 0:
            return ""
        depth, instr, esc = 0, False, False
        for k in range(j, len(html)):
            c = html[k]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                instr = not instr
                continue
            if instr:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return html[j:k + 1]
        return ""

    def _extract_stream(self, html):
        if not html:
            return ""
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw.replace("\\/", "/"))
                if str(aa.get("encrypt", "0")) in ("0", "") and aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mu:
                    return mu.group(1).replace("\\/", "/")
        mi = _RE_IFRAME.search(html)
        if mi:
            return mi.group(1).replace("&amp;", "&")
        m = _RE_STREAM.search(html)
        return m.group(0).replace("\\/", "/") if m else ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率→第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
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
                return url
            text = rm.text if hasattr(rm, "text") else ""
            if "#EXT-X-STREAM-INF" not in text:
                return url
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        return sub
                    break
        except Exception as e:
            self.log("子流解析回退:", e)
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
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"})
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

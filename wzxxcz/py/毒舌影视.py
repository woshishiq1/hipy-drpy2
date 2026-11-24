# coding=utf-8
"""
m.xnhrsb.com | TVBox Python 爬虫
站点: 毒舌影视（MacCMS stui 模板 dsshiyi，移动端 m 站）
线上实证：首页/电影/电视剧列表/详情(单集合集+多集连续剧)/播放页/搜索结果/筛选区落盘核对。

已实证路由（audit/xnhrsb 样本）:
  - 首页:     /
  - 主分类:   /dsshiyitp/<tid>.html
  - 分页/筛选: /dsshiyisw/<tid>-<area>-<order>-<class>-<lang>-<letter>--<page>--<year>.html
              12 槽位: 0=tid 1=地区 2=排序 3=类型 4=语言 5=字母 8=页码 11=年份
  - 详情:     /dsshiyidt/<id>.html
  - 播放:     /dsshiyipy/<vid>-<sid>-<nid>.html
  - 搜索:     /dsshiyisc/<kw>-------------.html；分页 /dsshiyisc/<kw>----------<page>---.html
  - 注: /index.php/vod/search.html?wd= 在本站回退首页，非搜索结果；关键词搜索走伪静态 /dsshiyisc/

分类导航（线上实证首页菜单，两组）:
  主菜单 navlist: 1 电影 2 电视剧 3 综艺 4 动漫 5 短剧 豆瓣Top250(/label/duoban.html)
  子分类 submenu_mi: 6 动作片 7 喜剧片 8 爱情片 9 科幻片 10 恐怖片 11 剧情片
                     12 战争片 13 纪录片 14 悬疑片 15 犯罪片
  豆瓣Top250 分页: /label/movie/page/<N>.html（第1页 /label/duoban.html）

列表卡片（首页/分类/搜索同构，实证）:
  - li > a[href=/dsshiyidt/<id>.html] > img.thumb.lazy[alt=片名][data-original=封面]
  - div.hdinfo > span.qb = 副标(已完结/更新至N集)；div.rating = 评分
  - h3.dytit > a = 片名兜底；p.inzhuy = 主演行
  - 封面兜底: data-original → data-src(轮播 coveimg) → src；排除 blank.gif/logo/caid 占位

详情字段（实证详情页）:
  - 片名 div.moviedteail_tt > h1
  - 海报: 背景 cover url 优先，兜底 moviedteail 前非占位 img src
  - 元信息 ul.moviedteail_list > li: 类型/地区/年份/又名/导演/编剧/主演/语言/更新
  - 简介 div.yp_context
  - 线路 div.mi_paly_box: 线路名 div.ypxingq_t(去“-在线播放”后缀)；
    选集 div.paly_list_btn > a.play_movie；外链 //app2.* (APP秒播) 排除，仅取 /dsshiyipy/ 本站选集

播放直链: 播放页内联 player_aaaa JSON，括号深度配对截取；encrypt:0 时取 url 直出 m3u8；
          master m3u8 取首条子流拆分兜底，失败回退 parse:1 嗅探。

反爬校验（XCDN Bot detection，实证 2026-11-23）:
  - 边缘节点对可疑请求回 408，body 为 PoW 挑战页（title "Bot detection"，含 /__xcdn/captcha/api/init）。
  - 闭环: GET /__xcdn/captcha/api/init → {challenge, difficulty}；
    枚举 nonce 使 sha256(challenge + nonce) 十六进制前 difficulty 位为 '0'；
    GET /__xcdn/captcha/api/verify，头 X-CDN-VERIFY-NONCE / X-CDN-VERIFY-RESULT；
    verify 200 后服务端 Set-Cookie __xcdn_captcha_verified=<JWT>（次日过期），携带该 Cookie 访问内容页即 200 出片。
  - 同一 session 内 Cookie 跨页复用；失效后再次遇挑战自动重解。
"""
import re
import sys
import json
import time
import socket
import hashlib
import urllib.parse

sys.path.append('..')

# 云端出口 IPv6 不通/国内 IPv6 不稳：强制 IPv4 解析（壳子本地网络正常时不影响）
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        res = _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        v4 = [x for x in res if x[0] == socket.AF_INET]
        return v4 or res
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

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
                print("[xnhrsb]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://m.xnhrsb.com"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航 navlist，线上实证）=====================
# 站点顶部导航仅: 电影/电视剧/综艺/动漫/短剧/豆瓣Top250；第二行标签(动作片…犯罪片)不进一级分类栏
# 豆瓣Top250 为自定义标签页 /label/duoban.html，分页 /label/movie/page/<N>.html
CLASSES = [
    {"type_id": "1",      "type_name": "电影"},
    {"type_id": "2",      "type_name": "电视剧"},
    {"type_id": "3",      "type_name": "综艺"},
    {"type_id": "4",      "type_name": "动漫"},
    {"type_id": "5",      "type_name": "短剧"},
    {"type_id": "duoban", "type_name": "豆瓣Top250"},
]

# ===================== 筛选（线上实证静态下发，各频道选项与站点一致）=====================
_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
            "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0~9"]
_ORDER = [
    {"n": "按时间", "v": "time"},
    {"n": "按人气", "v": "hits"},
    {"n": "按评分", "v": "score"},
]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


def _build(types, areas, langs, years):
    # 维度顺序对齐站点筛选栏：影片类型→年份→地区→语言→字母→排序
    dims = []
    if types:
        dims.append({"key": "class", "name": "影片类型", "value": _opts(types)})
    if years:
        dims.append({"key": "year", "name": "年份", "value": _opts(years)})
    if areas:
        dims.append({"key": "area", "name": "地区", "value": _opts(areas)})
    if langs:
        dims.append({"key": "lang", "name": "语言", "value": _opts(langs)})
    dims.append({"key": "letter", "name": "字母", "value": _opts(_LETTERS)})
    dims.append({"key": "order", "name": "排序", "value": _ORDER})
    return dims


# —— 电影系（电影/动作/喜剧/爱情/科幻/恐怖/剧情/战争/纪录/悬疑/犯罪 共用一套）——
_MOVIE_TYPES = ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
    "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "恐怖", "悬疑", "惊悚", "经典",
    "青春", "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"]
_MOVIE_AREA = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
    "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]
_MOVIE_LANG = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"]
_MOVIE_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
    "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"]

# —— 电视剧 ——
_TV_TYPES = ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
    "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"]
_TV_AREA = ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"]
_TV_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
    "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008",
    "2006", "2005", "2004"]

# —— 综艺 ——
_VAR_TYPES = ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺",
    "生活", "游戏互动", "财经", "求职"]
_VAR_AREA = ["内地", "港台", "日韩", "欧美"]
_VAR_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
    "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008",
    "2007", "2006", "2005", "2004"]

# —— 动漫 ——
_ANI_TYPES = ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
    "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智", "励志", "其他"]
_ANI_AREA = ["国产", "日本", "欧美", "其他"]
_ANI_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
    "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008",
    "2007", "2006", "2005", "2004"]

# —— 短剧 ——
_SH_TYPES = ["短剧"]
_SH_AREA = ["大陆"]
_SH_LANG = ["国语"]
_SH_YEAR = ["2026", "2025", "2024", "2023", "2022"]

_LANG_MAIN = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"]

FILTERS = {}
FILTERS["1"] = _build(_MOVIE_TYPES, _MOVIE_AREA, _MOVIE_LANG, _MOVIE_YEAR)
FILTERS["2"] = _build(_TV_TYPES, _TV_AREA, _LANG_MAIN, _TV_YEAR)
FILTERS["3"] = _build(_VAR_TYPES, _VAR_AREA, _LANG_MAIN, _VAR_YEAR)
FILTERS["4"] = _build(_ANI_TYPES, _ANI_AREA, _LANG_MAIN, _ANI_YEAR)
FILTERS["5"] = _build(_SH_TYPES, _SH_AREA, _SH_LANG, _SH_YEAR)
FILTERS["duoban"] = []

# ===================== 正则 =====================
# 列表卡片（普通 thumb lazy / 轮播 coveimg）
_RE_LI = re.compile(r'<li[^>]*>([\s\S]*?)</li>', re.I)
_RE_HREF = re.compile(r'href="(/dsshiyidt/\d+\.html)"', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*class="[^"]*(?:thumb lazy|coveimg)[^"]*"[^>]*>', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_ORIG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
_RE_DSRC = re.compile(r'data-src="([^"]*)"', re.I)
_RE_QB = re.compile(r'<span[^>]*class="qb"[^>]*>([\s\S]*?)</span>', re.I)
_RE_RATING = re.compile(r'<div[^>]*class="rating"[^>]*>([\s\S]*?)</div>', re.I)
_RE_DYTIT = re.compile(
    r'<h3[^>]*class="dytit"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_INZHU = re.compile(r'<p[^>]*class="inzhuy"[^>]*>([\s\S]*?)</p>', re.I)

# 详情
_RE_H1 = re.compile(
    r'<div[^>]*class="moviedteail_tt"[^>]*>\s*<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_BG_COVER = re.compile(r'background-image:\s*url\(([^)]+)\)', re.I)
_RE_INFO_LI = re.compile(r'<li[^>]*>([\s\S]*?)</li>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SPAN = re.compile(r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO = re.compile(
    r'<div[^>]*class="yp_context"[^>]*>([\s\S]*?)</div>', re.I)
_RE_INTRO_META = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路分组
_RE_BOX = re.compile(
    r'<div[^>]*class="mi_paly_box"[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>', re.I)
_RE_BOX_SIMPLE = re.compile(
    r'<div[^>]*class="mi_paly_box"[^>]*>([\s\S]*?)(?=<div[^>]*class="mi_paly_box"|猜您还喜欢|$)', re.I)
_RE_BOX_TITLE = re.compile(
    r'<div[^>]*class="ypxingq_t[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_EP = re.compile(
    r'<a[^>]*class="play_movie"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 筛选区
_RE_TAX = re.compile(
    r'<div class="beautiful-taxonomy-filters-tax[^"]*"[^>]*>([\s\S]*?)(?=<div class="beautiful-taxonomy-filters-tax|</div>\s*</div>\s*</div>|$)', re.I)
_RE_TAX_LABEL = re.compile(r'<label[^>]*>([^<]*)</label>', re.I)
_RE_TAX_A = re.compile(
    r'<a[^>]*href="(/dsshiyisw/[^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 分页总页
_RE_PAGE_NUM = re.compile(r'<span[^>]*class="num"[^>]*>\s*(\d+)\s*/\s*(\d+)', re.I)


class Spider(Spider):

    def getName(self):
        return "m.xnhrsb.com"

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
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        # XCDN PoW 校验会话：自建 session 保留挑战 Cookie，JWT 字符串双保险写入请求头
        self._cd_session = None
        self._cd_cookie = ""

    # ---------------- 基础工具 ----------------
    @staticmethod
    def _is_placeholder_pic(pic):
        if not pic:
            return True
        low = pic.lower()
        return any(k in low for k in ("blank.gif", "logo.png", "caid.png",
                                      "load.png", "load.gif", "placeholder",
                                      "blank", "default"))

    @staticmethod
    def _is_upstream_error(text, status=200):
        if not text or len(text) < 200:
            return True
        try:
            if status and int(status) != 200:
                return True
        except Exception:
            pass
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "error code", "ray id", "web server is down",
            "sorry, you have been blocked"))

    # ---------------- XCDN PoW 校验 ----------------
    def _cd_session_get(self):
        if self._cd_session is None:
            try:
                import requests as rq
                sess = rq.Session()
                sess.verify = False
                adapter = rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                sess.mount('https://', adapter)
                sess.mount('http://', adapter)
            except Exception:
                sess = None
            self._cd_session = sess
        return self._cd_session

    @staticmethod
    def _is_challenge(text, status):
        if text and ("Bot detection" in text or "/__xcdn/captcha/api/init" in text):
            return True
        try:
            if status and int(status) in (403, 408, 429):
                return True
        except Exception:
            pass
        return False

    def _solve_captcha(self):
        """解 XCDN SHA-256 PoW；成功后把 verified JWT 存入 session 与请求头 Cookie。"""
        try:
            sess = self._cd_session_get()
            h = dict(self.headers)
            init_url = self.site_url + "/__xcdn/captcha/api/init"
            if sess is not None:
                ri = sess.get(init_url, headers=h, timeout=(10, 30))
                settings = ri.json()
            else:
                ri = self.fetch(init_url, headers=h, timeout=(10, 30))
                settings = ri.json()
            challenge = str(settings.get("challenge", ""))
            difficulty = int(settings.get("difficulty", 4))
            if not challenge:
                return False
            target = "0" * difficulty
            nonce = 0
            result = ""
            while nonce < 3_000_000:
                nonce += 1
                result = hashlib.sha256(
                    (challenge + str(nonce)).encode("utf-8")).hexdigest()
                if result[:difficulty] == target:
                    break
            else:
                self.log("PoW 枚举未命中")
                return False
            vh = dict(h)
            vh["X-CDN-VERIFY-NONCE"] = str(nonce)
            vh["X-CDN-VERIFY-RESULT"] = result
            verify_url = self.site_url + "/__xcdn/captcha/api/verify"
            jwt = ""
            if sess is not None:
                rv = sess.get(verify_url, headers=vh, timeout=(10, 30))
                if getattr(rv, "status_code", 200) != 200:
                    self.log("verify 状态", getattr(rv, "status_code", "?"))
                    return False
                jwt = sess.cookies.get("__xcdn_captcha_verified", "")
            else:
                rv = self.fetch(verify_url, headers=vh, timeout=(10, 30))
            if jwt:
                self._cd_cookie = "__xcdn_captcha_verified=" + jwt
                self.headers["Cookie"] = self._cd_cookie
            self.log("PoW 校验通过 nonce=%s" % nonce)
            return True
        except Exception as e:
            self.log("PoW 求解异常", e)
            return False

    def _http_get(self, url, headers=None, timeout=15):
        """本站 GET：优先自建 session（保留校验 Cookie）；遇挑战自动解 PoW 后重放一次。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        if self._cd_cookie:
            h["Cookie"] = self._cd_cookie
        sess = self._cd_session_get()
        if sess is not None:
            rsp = sess.get(url, headers=h, timeout=timeout)
        else:
            rsp = self.fetch(url, headers=h, timeout=timeout)
        text = rsp.text if hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200)
        if self._is_challenge(text, status):
            self.log("遇 XCDN 挑战，解 PoW")
            if self._solve_captcha():
                if self._cd_cookie:
                    h["Cookie"] = self._cd_cookie
                if sess is not None:
                    rsp = sess.get(url, headers=h, timeout=timeout)
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
        return rsp

    def _fetch(self, url, headers=None, tries=3):
        last = ""
        for _ in range(tries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self._http_get(url, headers=h, timeout=(10, 30))
                status = getattr(rsp, "status_code", 200)
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)
                if not self._is_upstream_error(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, e)
                last = ""
            time.sleep(1.2)
        return last

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
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表卡片解析 ----------------
    def _parse_one_card(self, block):
        mh = _RE_HREF.search(block)
        if not mh:
            return None
        href = mh.group(1).replace("&amp;", "&")

        # 片名：img alt 优先，h3.dytit>a 兜底
        name = ""
        mi = _RE_IMG.search(block)
        if mi:
            ma = _RE_ALT.search(mi.group(0))
            if ma:
                name = self._clean(ma.group(1))
        if not name:
            mt = _RE_DYTIT.search(block)
            if mt:
                name = self._clean(mt.group(1))
        if not name:
            return None

        # 封面：data-original → data-src → src，排除占位
        pic = ""
        if mi:
            mo = _RE_ORIG.search(mi.group(0))
            if mo:
                pic = mo.group(1)
            if not pic:
                md = _RE_DSRC.search(mi.group(0))
                if md:
                    pic = md.group(1)
            if not pic:
                ms = _RE_SRC.search(mi.group(0))
                if ms:
                    pic = ms.group(1)
        if self._is_placeholder_pic(pic):
            pic = ""

        mp = _RE_QB.search(block)
        remarks = self._clean(mp.group(1)) if mp else ""

        mr = _RE_RATING.search(block)
        score = self._clean(mr.group(1)) if mr else ""

        return {
            "vod_id": href,
            "vod_name": name[:100],
            "vod_pic": self._fix_url(pic) or self.default_pic,
            "vod_remarks": remarks,
            "vod_score": score,
        }

    def _parse_cards(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for li in _RE_LI.finditer(html):
            block = li.group(1)
            if not _RE_HREF.search(block):
                continue
            card = self._parse_one_card(block)
            if not card:
                continue
            if card["vod_id"] in seen:
                continue
            seen.add(card["vod_id"])
            videos.append(card)
        return videos

    # ---------------- 筛选动态解析 ----------------
    _LABEL_KEY = {
        "影片类型": "class", "类型": "class",
        "地区": "area", "语言": "lang", "字母": "letter",
        "年份": "year", "排序": "order", "时间": "order",
    }

    def _parse_filters(self, html):
        """从分类页 beautiful-taxonomy-filters-tax 动态解析筛选组（与站点逐字一致）。"""
        groups = {}
        for blk in _RE_TAX.finditer(html):
            body = blk.group(1)
            ml = _RE_TAX_LABEL.search(body)
            label = self._clean(ml.group(1)) if ml else ""
            key = self._LABEL_KEY.get(label)
            if not key:
                continue
            items = [{"n": "全部", "v": ""}]
            for href, txt in _RE_TAX_A.findall(body):
                tok = href.split("/dsshiyisw/")[1].replace(".html", "").split("-")
                tok += [""] * (12 - len(tok))
                v = {"area": tok[1], "order": tok[2], "class": tok[3],
                     "lang": tok[4], "letter": tok[5], "year": tok[11]}.get(key, "")
                v = urllib.parse.unquote(v)
                n = self._clean(txt)
                if n and n != "全部":
                    items.append({"n": n, "v": v})
            if len(items) > 1:
                groups[key] = {"key": key, "name": label, "value": items}
        order = ["class", "area", "lang", "year", "letter", "order"]

        # 排序组：独立 view-filter 容器 a.order（按时间/人气/评分）
        vf = re.search(r'<div[^>]*class="view-filter"[^>]*>([\s\S]*?)</div>', html)
        if vf:
            order_items = [{"n": "全部", "v": ""}]
            for m in re.finditer(
                    r'<a([^>]*)>([\s\S]*?)</a>', vf.group(1)):
                attrs, txt = m.group(1), m.group(2)
                href = re.search(r'href="(/dsshiyisw/[^"]+)"', attrs)
                if not href or "order" not in attrs:
                    continue
                tok = href.group(1).split("/dsshiyisw/")[1].replace(".html", "").split("-")
                tok += [""] * (12 - len(tok))
                v = tok[2]
                n = self._clean(txt)
                if n and v:
                    order_items.append({"n": n, "v": v})
            if len(order_items) > 1:
                groups["order"] = {"key": "order", "name": "排序", "value": order_items}

        return [groups[k] for k in order if k in groups]

    def _list_url(self, tid, extend, page=1):
        extend = extend or {}
        def _val(k):
            v = (extend.get(k) or "").strip()
            return "" if v in ("全部", "none") else v
        area = _val("area"); order = _val("order"); cls = _val("class")
        lang = _val("lang"); letter = _val("letter"); year = _val("year")
        page = int(page) if page else 1
        if not any([area, order, cls, lang, letter, year]) and page <= 1:
            return "%s/dsshiyitp/%s.html" % (self.site_url, tid)
        tok = [str(tid), area, order, cls, lang, letter, "", "",
               str(page), "", "", year]
        seg = "-".join(urllib.parse.quote(x) if not x.isascii() else x for x in tok)
        return "%s/dsshiyisw/%s.html" % (self.site_url, seg)

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        # 豆瓣Top250：自定义标签页，独立路由，无筛选组
        if tid == "duoban":
            url = self._duoban_url(page)
            self.log("category(豆瓣): %s" % url)
            html = self._fetch(url)
            self.log("  HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            pagecount = self._page_count(html, page)
            self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": 48, "total": pagecount * 48,
            }

        url = self._list_url(tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._parse_cards(html)
        pagecount = self._page_count(html, page)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 45, "total": pagecount * 45,
        }

    def _duoban_url(self, page=1):
        page = int(page) if page else 1
        if page <= 1:
            return "%s/label/duoban.html" % self.site_url
        return "%s/label/movie/page/%d.html" % (self.site_url, page)

    def _page_count(self, html, page):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return max(1, int(m.group(2)))
            except Exception:
                pass
        # 豆瓣标签页末页 /label/movie/page/<N>.html
        label_pages = [int(x) for x in re.findall(r'/label/movie/page/(\d+)\.html', html)]
        if label_pages:
            return max(label_pages)
        pages = [int(x) for x in re.findall(r'/dsshiyisw/\d+--------(\d+)---', html)]
        return max(pages) if pages else max(1, page)

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page <= 1:
            url = "%s/dsshiyisc/%s-------------.html" % (self.site_url, kw)
        else:
            url = "%s/dsshiyisc/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html, page)
        self.log("  搜索: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 45, "total": pagecount * 45,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _info_field(self, html, label):
        """提取 moviedteail_list 中指定标签后的文本（a 逗号拼接 / span 纯文本）。"""
        for li in _RE_INFO_LI.finditer(html):
            seg = li.group(1)
            if ("%s：" % label) not in seg and ("%s:" % label) not in seg:
                continue
            after = re.split(r'%s[：:]' % re.escape(label), seg, 1)[-1]
            links = [self._clean(a) for a in _RE_A_TEXT.findall(after)]
            links = [x for x in links if x]
            if links:
                return ",".join(links)
            sp = _RE_SPAN.search(after)
            if sp:
                return self._clean(sp.group(1))
            return self._clean(after)
        return ""

    def detailContent(self, ids):
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
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报：背景 cover 优先，兜底 moviedteail 前非占位 img
        pic = ""
        mb = _RE_BG_COVER.search(html)
        if mb:
            pic = mb.group(1)
        if self._is_placeholder_pic(pic):
            pic = ""
        if not pic:
            h1pos = html.find("moviedteail")
            head = html[:h1pos] if h1pos > 0 else html
            for im in re.finditer(r'<img[^>]*src="([^"]*)"', head):
                if not self._is_placeholder_pic(im.group(1)):
                    pic = im.group(1)
                    break
        pic = self._fix_url(pic) or self.default_pic

        # 简介：yp_context 优先，meta description 末层兜底
        content = ""
        mf = _RE_INTRO.search(html)
        if mf:
            content = self._clean(mf.group(1))
        if not content:
            mm = _RE_INTRO_META.search(html)
            if mm:
                content = self._clean(mm.group(1))
        content = re.sub(r"^(影片介绍|简介|剧情简介)\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        actor = self._info_field(html, "主演")
        director = self._info_field(html, "导演")
        classify = self._info_field(html, "类型")
        area = self._info_field(html, "地区")
        year_raw = self._info_field(html, "年份")
        my = re.search(r"(\d{4})", year_raw)
        year = my.group(1) if my else year_raw

        # 副标：仅限主信息区（片名→线路盒之间），避免误取“猜您还喜欢”推荐卡片的 qb。
        # 主区无 qb 时取“更新：日期”，再兜底线路数。
        h1pos = html.find("moviedteail_tt")
        boxpos = html.find("mi_paly_box", h1pos) if h1pos > 0 else -1
        main_seg = html[h1pos:boxpos] if h1pos > 0 and boxpos > h1pos else html
        remarks = ""
        mr = _RE_QB.search(main_seg)
        if mr:
            remarks = self._clean(mr.group(1))
        if not remarks:
            upd = self._info_field(html, "更新")
            if upd:
                remarks = "更新：" + upd

        # ===== 线路与选集：mi_paly_box 分组，保 DOM 顺序 =====
        play_from, play_url = [], []
        for bm in _RE_BOX_SIMPLE.finditer(html):
            block = bm.group(1)
            # 线路名
            line = ""
            mt = _RE_BOX_TITLE.search(block)
            if mt:
                line = self._clean(mt.group(1))
                line = re.sub(r"[-—]\s*(在线播放|在线|播放)\s*$", "", line).strip()
            # 选集
            eps, seen_ep = [], set()
            for em in _RE_EP.finditer(block):
                href, ep_inner = em.group(1), em.group(2)
                href = href.replace("&amp;", "&")
                # 排除外链 APP 秒播，仅取本站 /dsshiyipy/ 选集
                if "/dsshiyipy/" not in href:
                    continue
                if href in seen_ep:
                    continue
                seen_ep.add(href)
                ep_name = self._clean(ep_inner)
                if not ep_name:
                    ep_name = "第%02d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            if not line:
                line = "线路%d" % (len(play_from) + 1)
            base, i = line, 2
            while line in play_from:
                line = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": area,
            "vod_year": year,
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

        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    @staticmethod
    def _player_json(html):
        """括号深度配对精确截取 player_aaaa JSON（正确处理嵌套对象）。"""
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
                if str(aa.get("encrypt", "0")) not in ("0", ""):
                    return ""
                if aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    return m2.group(1).replace("\\/", "/")
        m2 = re.search(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', html, re.I)
        return m2.group(0) if m2 else ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率：取首条子 m3u8 并 urljoin；已是含分片媒体列表/mp4 原样返回。"""
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
                return url
            lines = [ln.strip().replace("\\/", "/") for ln in text.splitlines()]
            for i, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF"):
                    if i + 1 < len(lines):
                        sub = lines[i + 1].strip()
                        if sub and not sub.startswith("#"):
                            sub = urllib.parse.urljoin(url, sub)
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
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"})
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
        self._play_cache = {}

    def close(self):
        self.destroy()

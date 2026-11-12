# coding=utf-8
"""
大白鲨影院 shipin.trjsgc.com | TVBox Python 爬虫
站点: stui 模板 + MacCMS + Cloudflare
关键:
  - 分类 16 个（拼音 slug），筛选走 12 段 /vodshow/ URL（类型-地区-空-剧情-语言-字母-空-空-页码-空-空-年份）
  - 分页必须用 ?page=N（路径式页码会被 Cloudflare 拦），列表 36 条/页
  - 详情 /tr-{slug}.html，播放 /trplay-{slug}-{sid}-{ep}.html
  - 线路顺序按页面 stui-pannel-box b playlist 块顺序（与 sid 大小无关）
  - Cloudflare 挑战页用附加随机 query 绕过
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
                print("[dabaisha]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://shipin.trjsgc.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

DEFAULT_PIC = HOST + "/statics/img/load.gif"

PAGE_SIZE = 36
SEARCH_SIZE = 10

# ------------------------------------------------------------------ 分类
# 站点导航 16 个分类（全部为拼音 slug，详情页即 /tr-{slug}.html）
CLASSES = [
    {"type_id": "dianying",      "type_name": "电影",   "tpl": "MOVIE"},
    {"type_id": "dongzuopian",   "type_name": "动作片", "tpl": "MOVIE"},
    {"type_id": "xijupian",      "type_name": "喜剧片", "tpl": "MOVIE"},
    {"type_id": "aiqingpian",    "type_name": "爱情片", "tpl": "MOVIE"},
    {"type_id": "kehuanpian",    "type_name": "科幻片", "tpl": "MOVIE"},
    {"type_id": "kongbupian",    "type_name": "恐怖片", "tpl": "MOVIE"},
    {"type_id": "juqingpian",    "type_name": "剧情片", "tpl": "MOVIE"},
    {"type_id": "zhanzhengpian", "type_name": "战争片", "tpl": "MOVIE"},
    {"type_id": "lianxuju",      "type_name": "连续剧", "tpl": "TV"},
    {"type_id": "guochanju",     "type_name": "国产剧", "tpl": "TV"},
    {"type_id": "gangtaiju",     "type_name": "港台剧", "tpl": "TV"},
    {"type_id": "rihanju",       "type_name": "日韩剧", "tpl": "TV"},
    {"type_id": "oumeiju",       "type_name": "欧美剧", "tpl": "TV"},
    {"type_id": "zongyi",        "type_name": "综艺",   "tpl": "VARIETY"},
    {"type_id": "dongman",       "type_name": "动漫",   "tpl": "ANIME"},
    {"type_id": "duanju",        "type_name": "短剧",   "tpl": "SHORT"},
]

# 各分类页真实筛选维度（抓自站点 stui-screen__list，按字母顺序去重）
_F_MOVIE = {
    "剧情": "喜剧 爱情 恐怖 动作 科幻 剧情 战争 警匪 犯罪 动画 奇幻 武侠 冒险 枪战 悬疑 惊悚 经典 青春 文艺 微电影 古装 历史 运动 农村 儿童 网络电影",
    "地区": "大陆 香港 台湾 美国 法国 英国 日本 韩国 德国 泰国 印度 意大利 西班牙 加拿大 其他",
    "年份": "2018 2017 2016 2015 2014 2013 2012 2011 2010",
    "语言": "国语 英语 粤语 闽南语 韩语 日语 法语 德语 其它",
    "字母": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
}

_F_TV = {
    "剧情": "古装 战争 青春偶像 喜剧 家庭 犯罪 动作 奇幻 剧情 历史 经典 乡村 情景 商战 网剧 其他",
    "地区": "内地 韩国 香港 台湾 日本 美国 泰国 英国 新加坡 其他",
    "年份": "2018 2017 2016 2015 2014 2013 2012 2011 2010 2009 2008 2006 2005 2004",
    "语言": "国语 英语 粤语 闽南语 韩语 日语 其它",
    "字母": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
}

_F_VARIETY = {
    "剧情": "选秀 情感 访谈 播报 旅游 音乐 美食 纪实 曲艺 生活 游戏互动 财经 求职",
    "地区": "内地 港台 日韩 欧美",
    "年份": "2018 2017 2016 2015 2014 2013 2012 2011 2010 2009 2008 2007 2006 2005 2004",
    "语言": "国语 英语 粤语 闽南语 韩语 日语 其它",
    "字母": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
}

_F_ANIME = {
    "剧情": "情感 科幻 热血 推理 搞笑 冒险 萝莉 校园 动作 机战 运动 战争 少年 少女 社会 原创 亲子 益智 励志 其他",
    "地区": "国产 日本 欧美 其他",
    "年份": "2018 2017 2016 2015 2014 2013 2012 2011 2010 2009 2008 2007 2006 2005 2004",
    "语言": "国语 英语 粤语 闽南语 韩语 日语 其它",
    "字母": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
}

_F_SHORT = {
    "剧情": "喜剧 爱情 恐怖 动作 科幻 剧情 战争 警匪 犯罪",
    "地区": "大陆 香港 台湾 美国 法国 英国 日本 韩国 其他",
    "年份": "2024 2023 2022 2021",
    "语言": "国语 英语 粤语 闽南语 韩语 日语 其它",
    "字母": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
}

_TPL = {
    "MOVIE": _F_MOVIE,
    "TV": _F_TV,
    "VARIETY": _F_VARIETY,
    "ANIME": _F_ANIME,
    "SHORT": _F_SHORT,
}

# 12 段 URL 中各筛选维度所在的位置
# 巧妙地把「排序」塞进第 6 段（原本字母的位置），实现下拉菜单
SEG_IDX = {"剧情": 3, "地区": 1, "年份": 11, "语言": 4, "字母": 5, "排序": 5}

# ------------------------------------------------------------------ 正则
_RE_THUMB_A = re.compile(r'<a\b[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>', re.I)
_RE_PIC_TEXT = re.compile(r'<span class="pic-text[^"]*">([\s\S]*?)</span>', re.I)
_RE_DETAIL_TITLE = re.compile(r'<h[34][^>]*class="[^"]*title[^"]*"[^>]*>[\s\S]{0,120}?<a\b[^>]*>([\s\S]*?)</a>', re.I)
_RE_ACTORS_P = re.compile(r'<p class="text[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_SLUG = re.compile(r'/tr-([A-Za-z0-9_\-]+)\.html', re.I)
_RE_NUM = re.compile(r'<span class="num">\s*(\d+)\s*/\s*(\d+)\s*</span>')
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_SCREEN = re.compile(r'<ul class="stui-screen__list[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_HEAD = re.compile(r'<div class="stui-pannel__head[^"]*"[^>]*>', re.I)
_RE_RANK_LI = re.compile(r'<li class="bottom-line-dot">([\s\S]*?)</li>', re.I)
_RE_EXT = re.compile(r'\.(m3u8|mp4|flv|mkv|ts|avi|mov|rmvb|webm)(\?|#|$)', re.I)

# Cloudflare 挑战页特征
_CF_MARKS = (
    "One moment, please",
    "Just a moment",
    "your request is being verified",
    "webdriverCheck",
    "userAgentCheck",
    "_cf_chl_opt",
)


def _attr(tag, name):
    m = re.search(r'\b' + name + r'\s*=\s*"([^"]*)"', tag, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b" + name + r"\s*=\s*'([^']*)'", tag, re.I)
    return m.group(1).strip() if m else ""


def _html(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&ldquo;", "“").replace("&rdquo;", "”")
          .replace("&hellip;", "…").replace("&mdash;", "—"))
    s = re.sub(r'&[a-zA-Z#0-9]{2,8};', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _pic(u):
    u = (u or "").strip()
    if not u:
        return DEFAULT_PIC
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return HOST + u
    return DEFAULT_PIC


def _seg_body(href):
    """把 /vodshow/xxx.html 拆成 12 段"""
    body = href.split("?")[0].split("#")[0]
    body = body.replace("/vodshow/", "").replace(".html", "")
    return urllib.parse.unquote(body).split("-")


class Spider(Spider):

    # ------------------------------------------------------------ 基础
    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self._session = None
        self.header = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self._last_req = 0.0
        self._fmeta = {}      # tid -> {维度: {值: (段位, 值)}}
        self._fmeta_raw = {}  # tid -> {维度: [值...]} 顺序保留
        self._home_html = ""

    def getName(self):
        return "大白鲨影院"

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        return bool(url and _RE_EXT.search(url))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return

    def close(self):
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass
        self._session = None

    # ------------------------------------------------------------ 网络
    def _is_cf(self, h):
        if not h:
            return True
        if len(h) < 12000:
            for k in _CF_MARKS:
                if k in h:
                    return True
        return "stui" not in h

    def _raw(self, url):
        import requests as _rq
        if self._session is None:
            self._session = _rq.Session()
            self._session.verify = False
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
        gap = time.time() - self._last_req
        if gap < 0.25:
            time.sleep(0.25 - gap)
        self._last_req = time.time()
        try:
            r = self._session.get(url, headers=self.header, timeout=25, verify=False)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text or ""
        except Exception as e:
            self.log("req err %s %s" % (url, e))
        return ""

    def _fetch(self, url):
        """取页面；遇到 Cloudflare 挑战页就附加随机 query 重取（站点对无参路径有缓存拦截）"""
        h = self._raw(url)
        if not self._is_cf(h):
            return h
        for i in range(3):
            sep = "&" if "?" in url else "?"
            probe = "%s%s__r=%d%d" % (url, sep, int(time.time() * 1000) % 99991, i)
            h2 = self._raw(probe)
            if not self._is_cf(h2):
                return h2
            time.sleep(0.5 + i * 0.4)
        return h or ""

    # ------------------------------------------------------------ 卡片解析
    def _cards(self, h):
        if not h:
            return []
        # 详情页的大图块会被误判为列表卡片，先剔除
        h = re.sub(r'<div class="stui-content__thumb">[\s\S]*?</div>', '', h, count=1)
        out = []
        seen = set()
        for m in _RE_THUMB_A.finditer(h):
            tag = m.group(0)
            href = _attr(tag, "href")
            sm = _RE_SLUG.search(href)
            if not sm:
                continue
            slug = sm.group(1)
            if slug in seen:
                continue
            seg = h[m.end(): m.end() + 1400]
            name = _html(_attr(tag, "title"))
            if not name:
                tm = _RE_DETAIL_TITLE.search(seg)
                name = _html(tm.group(1)) if tm else ""
            if not name:
                continue
            seen.add(slug)
            
            # 强行获取真实封面（优先拿 data-original，过滤默认 loading 图）
            pic = _attr(tag, "data-original") or _attr(tag, "data-src") or _attr(tag, "src")
            if not pic or "load.gif" in pic:
                img = re.search(r'<img\b[^>]*>', seg, re.I)
                if img:
                    pic = _attr(img.group(0), "data-original") or _attr(img.group(0), "data-src") or _attr(img.group(0), "src")

            rm = _RE_PIC_TEXT.search(seg)
            remark = _html(rm.group(1)) if rm else ""
            am = _RE_ACTORS_P.search(seg)
            actors = _html(am.group(1)) if am else ""
            out.append({
                "vod_id": slug,
                "vod_name": name,
                "vod_pic": _pic(pic),
                "vod_remarks": remark,
                "vod_actor": actors,
            })
        return out

    def _rank_items(self, seg):
        """首页榜单（stui-vodlist__text 文字列表）"""
        out = []
        seen = set()
        for m in _RE_RANK_LI.finditer(seg):
            blk = m.group(1)
            a = re.search(r'<a\b([^>]*)>([\s\S]*?)</a>', blk, re.I)
            if not a:
                continue
            href = _attr(a.group(1), "href")
            sm = _RE_SLUG.search(href)
            if not sm:
                continue
            slug = sm.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            name = _html(_attr(a.group(1), "title")) or _html(a.group(2))
            if not name:
                continue
            rm = _RE_PIC_TEXT.search(blk)
            if not rm:
                rm = re.search(r'<span class="text-muted[^"]*">([\s\S]*?)</span>', blk)
            out.append({
                "vod_id": slug,
                "vod_name": name,
                "vod_pic": DEFAULT_PIC,
                "vod_remarks": _html(rm.group(1)) if rm else "",
            })
        return out

    def _pagecount(self, h, pg, size):
        m = _RE_NUM.search(h or "")
        if m:
            try:
                return max(1, int(m.group(2)))
            except Exception:
                pass
        return pg

    # ------------------------------------------------------------ 首页
    def homeContent(self, filter):
        result = {}
        classes = self._nav_classes()
        if not classes:
            classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CLASSES]
        result["class"] = classes

        if filter:
            filters = {}
            for c in classes:
                tid = c["type_id"]
                meta = self._fmeta.get(tid)
                if meta is None:
                    h = self._fetch(HOST + "/vodtype/%s.html" % tid)
                    meta, order = self._parse_filters(h, tid)
                    self._fmeta[tid] = meta
                    self._fmeta_raw[tid] = order
                
                fl = []
                if meta:
                    # 动态解析出的真实筛选（已包含排序）
                    for dim in ("排序", "剧情", "地区", "年份", "语言", "字母"):
                        vals_map = meta.get(dim) or {}
                        if not vals_map:
                            continue
                        seq = self._fmeta_raw.get(tid, {}).get(dim) or list(vals_map.keys())
                        vals = [{"n": "全部", "v": ""}]
                        for label in seq:
                            if label and label != "全部":
                                vals.append({"n": label, "v": label})
                        fl.append({"key": dim, "name": dim, "value": vals})
                else:
                    # 抓不到时的硬编码兜底（加入排序）
                    tpl = _TPL.get(next((c2["tpl"] for c2 in CLASSES if c2["type_id"] == tid), "MOVIE"), _F_MOVIE)
                    # 排序兜底
                    fl.append({"key": "排序", "name": "排序", "value": [{"n": "全部", "v": ""}, {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"}]})
                    for dim in ("剧情", "地区", "年份", "语言", "字母"):
                        words = (tpl.get(dim) or "").split()
                        if not words:
                            continue
                        vals = [{"n": "全部", "v": ""}]
                        for w in words:
                            vals.append({"n": w, "v": w})
                        fl.append({"key": dim, "name": dim, "value": vals})
                filters[tid] = fl
            result["filters"] = filters
        return result

    def _nav_classes(self):
        h = self._home_html or self._fetch(HOST + "/")
        if not h:
            return []
        self._home_html = h
        out = []
        seen = set()
        m = re.search(r'<ul class="stui-header__menu[^"]*">([\s\S]*?)</ul>', h, re.I)
        if not m:
            return []
        for href, tx in re.findall(r'<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', m.group(1), re.I):
            hm = re.search(r'/vodtype/([A-Za-z0-9_]+)\.html', href, re.I)
            if not hm:
                continue
            tid = hm.group(1)
            if tid in seen:
                continue
            seen.add(tid)
            nm = _html(tx)
            if nm and nm != "首页":
                out.append({"type_id": tid, "type_name": nm})
        return out

    def homeVideoContent(self):
        h = self._home_html or self._fetch(HOST + "/")
        if h:
            self._home_html = h
        if not h:
            return {"list": []}

        groups = []
        # 按顶层 stui-pannel 块切分
        blocks = re.split(r'<div class="stui-pannel stui-pannel-bg', h)
        for blk in blocks[1:]:
            # 排除底部纯榜单块（没左栏的）
            if 'col-lg-wide-75' not in blk:
                continue

            # 提取当前块的标题（如“最新电影”）
            m = re.search(r'<div class="col-lg-wide-75[^"]*">[\s\S]*?<h3 class="title">[\s\S]*?<a[^>]*>([\s\S]*?)</a>', blk)
            gname = _html(m.group(1)) if m else "最新推荐"

            # 精确提取左侧卡片列表，防止沾染右侧榜单
            lm = re.search(r'<div class="col-lg-wide-75[^"]*">[\s\S]*?<ul class="stui-vodlist clearfix">([\s\S]*?)</ul>', blk)
            if not lm:
                continue
                
            cards = self._cards(lm.group(1))
            if cards:
                groups.append({"vod_name": gname, "vod_id": "", "vod_list": cards})

        return {"list": groups}

    # ------------------------------------------------------------ 筛选
    def _parse_filters(self, h, tid):
        """动态解析分类页筛选块，返回 {维度: {显示名: (段位, 值)}}"""
        meta = {}
        order = {}
        for m in _RE_SCREEN.finditer(h or ""):
            blk = m.group(1)
            nm = re.search(r'<span class="text-muted">([^<]+)</span>', blk)
            if not nm:
                continue
            raw = nm.group(1).strip()
            if raw == "按类型":      # 这是分类导航（换 seg[0]），不是筛选
                continue
            dim = raw.replace("按", "").strip()
            if dim not in SEG_IDX:
                continue
            vals = {}
            seq = []
            for href, tx in re.findall(r'<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', blk, re.I):
                label = _html(tx)
                if not label or "vodshow" not in href:
                    continue
                if label == "全部":
                    continue
                seg = _seg_body(href)
                if len(seg) < 12:
                    continue
                idx = SEG_IDX.get(dim)
                if idx is not None and idx < len(seg) and seg[idx]:
                    vals[label] = (idx, seg[idx])
                    if label not in seq:
                        seq.append(label)
                    continue
                filled = [i for i in range(1, min(len(seg), 12)) if seg[i]]
                if not filled:
                    continue
                last = filled[-1]
                vals[label] = (last, seg[last])
                if label not in seq:
                    seq.append(label)
            if vals:
                meta[dim] = vals
                order[dim] = seq
                
        # 特殊追加：把网页顶部的「排序」栏加进筛选里，强行绑定到第 6 段（索引 5）
        if 'nav nav-head' in (h or ''):
            sort_vals = {"按时间": (5, "time"), "按人气": (5, "hits"), "按评分": (5, "score")}
            meta["排序"] = sort_vals
            order["排序"] = list(sort_vals.keys())
            
        return meta, order

    def _cat_url(self, tid, segs, pg):
        s = [""] * 12
        s[0] = tid
        for i in range(1, 12):
            s[i] = segs[i] if i < len(segs) else ""
        s[8] = ""       # 页码一律走 ?page=N，路径式会被 Cloudflare 拦
        url = HOST + "/vodshow/%s.html" % "-".join(s)
        if pg and int(pg) > 1:
            url += "?page=%d" % int(pg)
        return url

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        ext = dict(extend or {})
        meta = self._fmeta.get(tid)
        if meta is None:
            base = self._fetch(HOST + "/vodtype/%s.html" % tid)
            meta, order = self._parse_filters(base, tid)
            self._fmeta[tid] = meta
            self._fmeta_raw[tid] = order
            if pg == 1 and not ext and base:
                cards = self._cards(base)
                return {
                    "list": cards,
                    "page": 1,
                    "pagecount": self._pagecount(base, 1, PAGE_SIZE),
                    "limit": PAGE_SIZE,
                    "total": len(cards) * self._pagecount(base, 1, PAGE_SIZE),
                }

        segs = [""] * 12
        for k, v in ext.items():
            if not v:
                continue
            if meta and k in meta and v in meta[k]:
                hit = meta[k][v]
                segs[hit[0]] = hit[1]
            else:
                if k in SEG_IDX:
                    segs[SEG_IDX[k]] = v

        h = self._fetch(self._cat_url(tid, segs, pg))
        cards = self._cards(h)
        pc = self._pagecount(h, pg, PAGE_SIZE)
        return {
            "list": cards,
            "page": pg,
            "pagecount": pc,
            "limit": PAGE_SIZE,
            "total": len(cards) * pc if cards else 0,
        }

    # ------------------------------------------------------------ 详情
    def _field(self, h, label):
        # 形式一：<span class="text-muted">总点击量：306</span>
        m = re.search(r'<span class="text-muted[^"]*">\s*' + label + r'\s*[:：]\s*([^<]*)</span>', h)
        if m and m.group(1).strip():
            return _html(m.group(1))
        # 形式二：<span class="text-muted">类型：</span><a>国产</a>
        m = re.search(r'<span class="text-muted[^"]*">\s*' + label + r'\s*[:：]\s*</span>([\s\S]*?)(?=</p>|<span class="text-muted)', h)
        if not m:
            return ""
        seg = m.group(1)
        links = re.findall(r'<a\b[^>]*>([\s\S]*?)</a>', seg, re.I)
        if links:
            vals = [_html(x) for x in links]
            vals = [x for x in vals if x]
            if vals:
                return ",".join(vals)
        return _html(seg)

    def _long_desc(self, h):
        i = h.find('id="desc"')
        if i < 0:
            return ""
        blk = h[i: i + 6000]
        p = re.search(r'<p class="col-pd">([\s\S]*?)</p>', blk, re.I)
        if not p:
            return ""
        txt = _html(p.group(1))
        m = re.search(r'剧情简述\s*[:：]?\s*(.+)$', txt)
        if m and len(m.group(1).strip()) > 8:
            return m.group(1).strip()
        return txt

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = str(vid or "").strip()
        m = _RE_SLUG.search(vid)
        slug = m.group(1) if m else vid.strip("/").replace("tr-", "").replace(".html", "")
        if not slug:
            return {"list": []}

        h = self._fetch(HOST + "/tr-%s.html" % slug)
        if not h:
            return {"list": []}

        # 标题 / 评分
        t = re.search(r'<h1 class="title">([\s\S]*?)</h1>', h, re.I)
        title_raw = t.group(1) if t else ""
        score = ""
        sm = re.search(r'<span class="score[^"]*">([\s\S]*?)</span>', title_raw, re.I)
        if sm:
            score = _html(sm.group(1))
            title_raw = title_raw.replace(sm.group(0), "")
        name = _html(title_raw)
        if not name:
            return {"list": []}

        # 竖图 / 副标题
        pic = ""
        remark = ""
        tm = re.search(r'<div class="stui-content__thumb">([\s\S]*?)</div>', h, re.I)
        if tm:
            thumb = tm.group(1)
            a = re.search(r'<a\b[^>]*>', thumb, re.I)
            if a:
                pic = _attr(a.group(0), "data-original") or _attr(a.group(0), "data-src")
            if not pic:
                im = re.search(r'<img\b[^>]*>', thumb, re.I)
                if im:
                    pic = _attr(im.group(0), "data-original") or _attr(im.group(0), "data-src") or _attr(im.group(0), "src")
            rm = _RE_PIC_TEXT.search(thumb)
            if rm:
                remark = _html(rm.group(1))
        if not pic:
            im = re.search(r'<img\b[^>]*data-original="([^"]+)"', h, re.I)
            if im:
                pic = im.group(1)

        type_name = self._field(h, "类型")
        area = self._field(h, "地区")
        year = self._field(h, "年份")
        lang = self._field(h, "语言")
        actor = self._field(h, "主演")
        director = self._field(h, "导演")
        score_cnt = self._field(h, "网友对评分")

        # 面包屑分类
        cat = ""
        cm = re.search(r'<a href="/vodshow/[^"]*"[^>]*>([^<]{1,12})</a>\s*<i class="icon iconfont icon-more">', h)
        if cm:
            cat = _html(cm.group(1))

        # 短简介
        desc = ""
        dm = re.search(r'<p class="desc[^"]*">([\s\S]*?)</p>', h, re.I)
        if dm:
            seg = re.sub(r'<a href="#desc">[\s\S]*?</a>', '', dm.group(1))
            desc = _html(seg)
            desc = re.sub(r'^简介\s*[:：]\s*', '', desc)
        if len(desc) < 12:
            desc = ""

        long_desc = self._long_desc(h)

        # 简介拼装：短简介优先，缺失则用长简介里的剧情简述
        if desc:
            content = INTRO_PREFIX + "\n" + desc
            if long_desc and desc[:30] not in long_desc:
                content += "\n" + long_desc
        else:
            body = long_desc
            if not body:
                bits = []
                if year and area:
                    bits.append("%s年%s出品的%s" % (year, area, type_name or "影视作品"))
                elif year:
                    bits.append("%s年出品的%s" % (year, type_name or "影视作品"))
                if director:
                    bits.append("由%s执导" % director)
                if actor:
                    bits.append("由%s等主演" % actor)
                if remark:
                    bits.append("当前更新至%s" % remark)
                body = "，".join(bits) if bits else "暂无简介"
            content = INTRO_PREFIX + "\n" + body

        # 线路：按 stui-pannel-box b playlist 块顺序取，块顺序与 sid 无关
        play_from = []
        play_url = []
        pos = [m.start() for m in re.finditer(r'<div class="stui-pannel-box b playlist', h, re.I)]
        for i, p in enumerate(pos):
            e = pos[i + 1] if i + 1 < len(pos) else len(h)
            blk = h[p:e]
            ht = re.search(r'<h3 class="title">([\s\S]*?)</h3>', blk, re.I)
            raw = _html(ht.group(1)) if ht else ""
            flag = re.sub(r'^《[^》]*》', '', raw)
            flag = re.sub(r'免费在线播放线路\s*$', '', flag).strip()
            if not flag:
                flag = "线路%d" % (i + 1)
            um = re.search(r'<ul class="stui-content__playlist[^"]*">([\s\S]*?)</ul>', blk, re.I)
            if not um:
                continue
            eps = []
            for href, tx in re.findall(r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', um.group(1), re.I):
                if "/trplay-" not in href:
                    continue
                nm = _html(tx) or "播放"
                eps.append("%s$%s" % (nm, href))
            if not eps:
                continue
            if flag in play_from:
                flag = "%s%d" % (flag, i + 1)
            play_from.append(flag)
            play_url.append("#".join(eps))

        vod = {
            "vod_id": slug,
            "vod_name": name,
            "vod_pic": _pic(pic),
            "vod_remarks": remark or "正片",
            "type_name": cat or type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score or score_cnt,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }

        return {"list": [vod]}

    # ------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith("http") else HOST + str(id)
        h = self._fetch(url)
        m = _RE_PLAYER.search(h or "")
        if not m:
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": json.dumps({"User-Agent": UA, "Referer": HOST + "/"})}
        try:
            j = json.loads(m.group(1))
        except Exception:
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": json.dumps({"User-Agent": UA, "Referer": HOST + "/"})}

        u = (j.get("url") or "").strip()
        if u.startswith("//"):
            u = "https:" + u
        if not u:
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": json.dumps({"User-Agent": UA, "Referer": HOST + "/"})}
        # hnyun 等源给的是 /play/xxx 无后缀，需补 index.m3u8
        if not _RE_EXT.search(u):
            u = u.rstrip("/") + "/index.m3u8"
        header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Origin": HOST,
        }
        return {"parse": 0, "playUrl": "", "url": u, "header": json.dumps(header)}

    # ------------------------------------------------------------ 搜索
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        kw = urllib.parse.quote(str(key or "").strip())
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1, "limit": SEARCH_SIZE, "total": 0}
        url = HOST + "/vodsearch/%s-------------.html" % kw
        if pg > 1:
            url += "?page=%d" % pg
        h = self._fetch(url)
        cards = self._cards(h)
        pc = self._pagecount(h, pg, SEARCH_SIZE)
        if pc <= pg and len(cards) >= SEARCH_SIZE:
            pc = pg + 1
        return {
            "list": cards,
            "page": pg,
            "pagecount": pc,
            "limit": SEARCH_SIZE,
            "total": len(cards) * pc if cards else 0,
        }

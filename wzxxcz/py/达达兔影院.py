# coding=utf-8
"""
达达兔影院 kshaodj.com | TVBox Python 爬虫
覆盖：首页、分类、筛选（分类片种/类型/地区/年份/排序）、详情、多线路多选集、
      播放解析、搜索、副标题/备注/地区/年份/别名等详情字段。
播放：优先将 player_data.url 混淆串还原为 m3u8/mp4 直链（parse:0）；
      还原失败时回退站点原生 CDN 解码页 p/d.html?p=<from>&u=<url> 内嵌播放（parse:1）。
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
                print("[dadaotu]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://kshaodj.com"
CDN_CACHE = "https://safari11.jinbianpiao.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 频道：与站点 /type/<slug>.html 路由一致
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "lianxuju",  "type_name": "连续剧"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

# 「分类」片种/剧种：值为短链 slug，占短链第 0 槽；空 = 频道本身
_FENLEI = {
    "dianying": [("动作片", "dongzuopian"), ("喜剧片", "xijupian"),
                 ("爱情片", "aiqingpian"), ("科幻片", "kehuanpian"),
                 ("恐怖片", "kongbupian"), ("剧情片", "juqingpian"),
                 ("战争片", "zhanzhengpian"), ("动漫片", "dongmanpian"),
                 ("纪录片", "jilupian")],
    "lianxuju": [("国产剧", "guochanju"), ("欧美剧", "oumeiju"),
                 ("日韩剧", "rihanju"), ("港台剧", "gangtaiju"),
                 ("海外剧", "haiwaiju")],
    "dongman": [("国产动漫", "guochandongman"), ("日韩动漫", "rihandongman"),
                ("欧美动漫", "oumeidongman"), ("港台动漫", "gangtaidongman"),
                ("海外动漫", "haiwaidongman")],
    "zongyi": [("内地综艺", "neidizongyi"), ("港台综艺", "gangtaizongyi"),
               ("日韩综艺", "rihanzongyi"), ("欧美综艺", "oumeizongyi")],
    "duanju": [],
}

# 「类型」：值为中文，占短链第 3 槽
_GENRES = {
    "dianying": ["剧情", "喜剧", "动作", "爱情", "恐怖", "惊悚", "犯罪", "科幻",
                 "悬疑", "冒险", "奇幻", "纪录", "动画", "动漫", "古装", "家庭",
                 "战争", "历史", "武侠", "传记", "运动", "音乐", "歌舞"],
    "lianxuju": ["剧情", "爱情", "喜剧", "犯罪", "悬疑", "恐怖", "科幻", "惊悚",
                 "古装", "动作", "家庭", "奇幻", "历史", "战争", "冒险", "武侠",
                 "传记", "同性", "纪录", "动画"],
    "dongman": ["动画", "剧情", "喜剧", "动作", "奇幻", "冒险", "科幻", "爱情",
                "悬疑", "儿童", "短片", "运动", "惊悚", "武侠", "战争", "家庭",
                "古装", "犯罪", "恐怖", "历史", "音乐"],
    "zongyi": ["真人秀", "脱口秀", "音乐", "盛会", "访谈", "选秀", "美食", "曲艺",
               "搞笑", "生活", "游戏", "歌舞", "情感", "文化", "旅游", "纪实",
               "竞技", "益智", "晚会", "少儿", "其它"],
    "duanju": [],
}

# 「地区」：占短链第 1 槽
_AREAS = {
    "dianying": ["大陆", "香港", "台湾", "泰国", "日本", "印度", "美国", "英国",
                 "法国", "韩国", "德国", "加拿大", "西班牙", "意大利", "澳大利亚",
                 "俄罗斯", "其它"],
    "lianxuju": ["大陆", "香港", "台湾", "日本", "泰国", "韩国", "美国", "英国",
                 "法国", "加拿大", "西班牙", "新加坡", "澳大利亚", "其它"],
    "dongman": ["大陆", "台湾", "日本", "美国", "韩国", "法国", "英国", "加拿大",
                "澳大利亚", "其它"],
    "zongyi": ["大陆", "台湾", "香港", "日本", "韩国", "美国", "英国"],
    "duanju": [],
}

_YEARS_FULL = [str(y) for y in range(2025, 1999, -1)]
_YEARS_DJ = [str(y) for y in range(2025, 2019, -1)]
_YEARS = {"duanju": _YEARS_DJ}

_SORTS = [("按最新", "time"), ("按最热", "hits"), ("按评分", "score")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    fl = []
    if _FENLEI[tid]:
        fl.append({"key": "fenlei", "name": "分类",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": n, "v": v} for n, v in _FENLEI[tid]]})
    if _GENRES[tid]:
        fl.append({"key": "class", "name": "类型",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": x, "v": x} for x in _GENRES[tid]]})
    if _AREAS[tid]:
        fl.append({"key": "area", "name": "地区",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": x, "v": x} for x in _AREAS[tid]]})
    fl.append({"key": "year", "name": "年份",
               "value": [{"n": "全部", "v": ""}] +
                        [{"n": x, "v": x} for x in _YEARS.get(tid, _YEARS_FULL)]})
    fl.append({"key": "sort", "name": "排序",
               "value": [{"n": "默认", "v": ""}] +
                        [{"n": n, "v": v} for n, v in _SORTS]})
    FILTERS[tid] = fl


# ===================== 正则 =====================
_RE_SUBJECT = re.compile(r'/subject/([A-Za-z0-9_-]+)\.html')
_RE_START = re.compile(r'/start/([A-Za-z0-9_-]+)-(\d+)-(\d+)\.html')
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"')
_RE_BG = re.compile(r"background-image:\s*url\(\s*\\?'?([^\s)\"'\\]+)")
_RE_IMG = re.compile(r'<img[^>]*?(?:data-src|src)="([^"]*)"', re.I)
_RE_THUMB = re.compile(r'class="vodlist_thumb[^"]*"[^>]*>', re.I)
_RE_TITLE_P = re.compile(r'class="vodlist_title"[\s\S]*?<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SUB = re.compile(r'class="vodlist_sub"[^>]*>([\s\S]*?)</p>', re.I)
_RE_PICTEXT = re.compile(r'class="pic_text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_VODDATE = re.compile(r'class="voddate[^"]*"[^>]*>([\s\S]*?)</em>', re.I)

_RE_TITLE_TAG = re.compile(r"<title>([\s\S]*?)</title>", re.I)
_RE_HEADING = re.compile(r'<h[1-4][^>]*>([\s\S]*?)</h[1-4]>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_DESC_FULL = re.compile(r'content_desc[^"]*full_text[^>]*>([\s\S]*?)</div>', re.I)
_RE_DESC = re.compile(r'content_desc[^>]*>([\s\S]*?)</div>', re.I)

_RE_DATA_ROW = re.compile(r'<li class="data"[^>]*>([\s\S]*?)</li>', re.I)
_RE_SEARCHKEY = re.compile(
    r'class="searchkey"[^>]*>([\s\S]*?)</a>', re.I)
_RE_DATA_STYLE = re.compile(r'class="data_style"[^>]*>([\s\S]*?)</span>', re.I)
_RE_EM = re.compile(r'<em[^>]*>([\s\S]*?)</em>', re.I)

_RE_TAB_ALT = re.compile(
    r'<a[^>]*alt="([^"]*)"[^>]*>(?:<i[^>]*></i>)?&nbsp;?[\s\S]*?</a>', re.I)
_RE_EP_A = re.compile(r'<a\s+href="(/start/[^"]+)">([\s\S]*?)</a>', re.I)

_RE_PLAYER = re.compile(r'player_data\s*=\s*(\{[\s\S]*?\})</script>', re.I)
_RE_WZ = re.compile(r'var\s+wz\s*=\s*(\{[\s\S]*?\});', re.I)


class Spider(Spider):

    def getName(self):
        return "达达兔影院"

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
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础工具 ----------
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
        # 去除图标字体私有码位实体（如 &#xe631;）与普通数字实体
        s = re.sub(r"&#x[0-9a-fA-F]+;", "", s)
        s = re.sub(r"&#\d+;", "", s)
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _decode_direct(self, s):
        """还原 CDN 混淆直链：去 cache 后缀 -> 标记 yMcA 还原为 a -> Base64 解码。"""
        try:
            if not s:
                return ""
            if s.startswith("http") and (".m3u8" in s or ".mp4" in s):
                return s
            core = re.split(r"[&]cache=", s, 1)[0]
            core = urllib.parse.unquote(core)
            b = core.replace("yMcA", "a")
            b += "=" * (-len(b) % 4)
            txt = base64.b64decode(b, validate=False).decode("utf-8", "ignore").strip()
            if txt.startswith("http") and (".m3u8" in txt or ".mp4" in txt):
                return txt
            return ""
        except Exception:
            return ""

    # ---------- 卡片解析 ----------
    def _cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 按 <li ...>...</li> 分块，兼容 vodlist_item / searchlist_item / balist_item
        blocks = re.split(r'<li\b', html)
        for block in blocks:
            m = _RE_SUBJECT.search(block)
            if not m:
                continue
            # 剔除频道导航(smlist_box/hidden_xs)、纯文字周榜(part_eone)等非海报卡片
            li_cls = re.search(r'<li\s+class="([^"]*)"', block)
            cls_txt = li_cls.group(1) if li_cls else ""
            if ("part_eone" in cls_txt or "smlist_box" in cls_txt
                    or cls_txt.strip() == "hidden_xs"):
                continue
            # 仅保留带封面的海报卡片；剔除标题栏分栏链接等无封面块
            if not (_RE_BG.search(block) or _RE_IMG.search(block)):
                continue
            sid = m.group(1)
            href = "/subject/%s.html" % sid

            # 标题：优先锚点 title 属性，其次 vodlist_title 文本，最后锚点内文本
            title = ""
            ma = re.search(r'<a[^>]*href="/subject/%s\.html"[^>]*>' % sid, block)
            if ma:
                tattr = _RE_TITLE_ATTR.search(ma.group(0))
                if tattr:
                    title = self._clean(tattr.group(1))
            if not title:
                mt = _RE_TITLE_P.search(block)
                if mt:
                    title = self._clean(mt.group(1))
            if not title:
                inner = re.search(r'<a[^>]*href="/subject/%s\.html"[^>]*>([\s\S]*?)</a>' % sid, block)
                if inner:
                    title = self._clean(inner.group(1))
            # 去除标题前的排名序号（1-2 位短数字 + 空格；避免误删年份 4 位数字开头）
            title = re.sub(r"^[1-9]\d{0,1}\s+", "", title)
            if not title:
                continue

            # 封面：背景图优先，其次 img
            pic = ""
            mb = _RE_BG.search(block)
            if mb:
                pic = mb.group(1)
            if not pic:
                mi = _RE_IMG.search(block)
                if mi:
                    pic = mi.group(1)
            pic = self._fix_url(pic) or self.default_pic
            # loading 占位图 / 站点资源图不算真实封面，置空以便后续真实封面覆盖
            if "/asset/img/" in pic or "loading1.gif" in pic:
                pic = self.default_pic

            # 备注/角标：pic_text > voddate > vodlist_sub
            remarks = ""
            mp = _RE_PICTEXT.search(block)
            if mp:
                remarks = self._clean(mp.group(1))
            if not remarks:
                mv = _RE_VODDATE.search(block)
                if mv:
                    remarks = self._clean(mv.group(1))
            if not remarks:
                ms = _RE_SUB.search(block)
                if ms:
                    remarks = self._clean(ms.group(1))

            if sid in seen:
                for v in videos:
                    if v["vod_id"] == href:
                        if (not v["vod_pic"] or v["vod_pic"] == self.default_pic) and pic:
                            v["vod_pic"] = pic
                        if not v["vod_remarks"] and remarks:
                            v["vod_remarks"] = remarks
                        break
                continue

            seen.add(sid)
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    # ---------- 首页 / 分类 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._cards(html)}

    def _show_slug(self, channel, fenlei, area, sort, cls, page, year):
        # 12 字段定宽短链：分类/频道-地区-排序-类型-(空)-分页-(空)-年份
        seg = [""] * 12
        seg[0] = fenlei or channel
        seg[1] = area or ""
        seg[2] = sort or ""
        seg[3] = cls or ""
        seg[8] = str(page) if page else ""
        seg[11] = year or ""
        return "/show/%s.html" % urllib.parse.quote("-".join(seg))

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        ext = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        fenlei = ext.get("fenlei", "")
        area = ext.get("area", "")
        cls = ext.get("class", "")
        year = ext.get("year", "")
        sort = ext.get("sort", "")

        url = self.site_url + self._show_slug(tid, fenlei, area, sort, cls, page, year)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._cards(html)
        pagecount = self._page_count(html, page)
        self.log("  最终: %d 条, 当前页: %d, 总页数: %d" % (len(videos), page, pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def _page_count(self, html, cur=1):
        if not html:
            return cur
        pages = [int(x) for x in re.findall(r'--------(\d+)---', html)]
        if pages:
            return max(cur, max(pages))
        pages = [int(x) for x in re.findall(r'[?&]page=(\d+)', html)]
        if pages:
            return max(cur, max(pages))
        return cur

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key))
        if page > 1:
            path = "/vod/search/wd/%s-%d.html" % (kw, page)
        else:
            path = "/vod/search/wd/%s.html" % kw
        url = self.site_url + path
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html, page) if videos else 1,
            "limit": 20, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def _label_value(self, row, label):
        """取某元信息标签后第一个链接文本。"""
        idx = row.find(label)
        if idx < 0:
            return ""
        tail = row[idx + len(label):]
        m = re.search(r'<a[^>]*>([^<]+)</a>', tail)
        return self._clean(m.group(1)) if m else ""

    def _label_values(self, row, label):
        """取某元信息标签后全部链接文本。"""
        idx = row.find(label)
        if idx < 0:
            return []
        tail = row[idx + len(label):]
        return [self._clean(x) for x in re.findall(r'<a[^>]*>([^<]+)</a>', tail)]

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
        mh = _RE_HEADING.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = _RE_TITLE_TAG.search(html)
            if mt:
                name = self._clean(mt.group(1))
        if name:
            name = name.replace("﹛", "").replace("﹜", "")
            name = re.sub(r"完整版$", "", name).strip()
            name = re.sub(r"_[^_]*影院$", "", name).strip()
        name = name or vod_id

        # 封面：详情大图（content_thumb 内缩略图）优先，再取首张背景图
        pic = self.default_pic
        mc = re.search(r'class="content_thumb[\s\S]*', html)
        if mc:
            mb = _RE_BG.search(mc.group(0))
            if mb:
                pic = mb.group(1)
        if pic == self.default_pic:
            mb = _RE_BG.search(html)
            if mb:
                pic = mb.group(1)
        pic = self._fix_url(pic) or self.default_pic

        # 简介：完整简介容器优先，其次普通简介，再 meta description
        content = ""
        mf = _RE_DESC_FULL.search(html)
        if mf:
            content = self._clean(mf.group(1))
        if not content:
            md = _RE_DESC.search(html)
            if md:
                content = self._clean(md.group(1))
        if not content:
            mmeta = _RE_META_DESC.search(html)
            if mmeta:
                content = self._clean(mmeta.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息行
        year = area = classify = director = actor = remarks = update_time = ""
        rows = _RE_DATA_ROW.findall(html)
        for row in rows:
            if "年份" in row:
                year = self._label_value(row, "年份：")
            if "地区" in row:
                area = self._label_value(row, "地区：")
            if "类型" in row:
                gl = self._label_values(row, "类型：")
                if gl:
                    classify = "/".join(gl)
            if "主演" in row:
                actor = "、".join(self._clean(x) for x in _RE_SEARCHKEY.findall(row))
            if "导演" in row:
                director = "、".join(self._clean(x) for x in _RE_SEARCHKEY.findall(row))
            ms = _RE_DATA_STYLE.search(row)
            if ms:
                remarks = self._clean(ms.group(1))
            me = _RE_EM.search(row)
            if me:
                update_time = self._clean(me.group(1))

        if not remarks:
            remarks = update_time

        # ===== 线路 / 选集 =====
        groups = {}
        order = []

        # 取播放线路区（id=aaa 优先，截止“相关推荐”），排除推荐标签区
        source_block = ""
        ma = re.search(r'<div class="play_source"[^>]*id="aaa"[^>]*>([\s\S]*?)(?=相关推荐|<div class="pannel|$)', html)
        if ma:
            source_block = ma.group(1)
        else:
            msrc = re.search(r'<div class="play_source"[^>]*>([\s\S]*?)(?=相关推荐|$)', html)
            if msrc:
                source_block = msrc.group(1)

        if source_block:
            # 线路标签：#NumTab 内 a[alt]
            tabs = []
            mtab = re.search(r'class="play_source_tab[^>]*id="NumTab"[^>]*>([\s\S]*?)</div>', source_block)
            tab_scope = mtab.group(1) if mtab else source_block
            for alt in re.findall(r'<a[^>]*alt="([^"]*)"', tab_scope):
                alt = self._clean(alt)
                if alt and alt not in ("同类型", "同主演", "同年份"):
                    tabs.append(alt)

            # 选集盒：按 play_list_box 切块，每块仅取其 content_playlist
            chunks = re.split(r'<div class="play_list_box', source_block)
            boxes = []
            for chunk in chunks[1:]:
                mul = re.search(r'<ul class="content_playlist[\s\S]*?</ul>', chunk)
                if mul:
                    boxes.append(mul.group(0))

            for idx, box in enumerate(boxes):
                eps = []
                for em in _RE_EP_A.finditer(box):
                    href = em.group(1).replace("&amp;", "&")
                    ep_name = self._clean(em.group(2)) or "第%d集" % (len(eps) + 1)
                    eps.append((ep_name, href))
                if not eps:
                    continue
                label = tabs[idx] if idx < len(tabs) else ("线路%d" % (idx + 1))
                if label in groups:
                    groups[label].extend(eps)
                else:
                    groups[label] = eps
                    order.append(label)

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        for label in order:
            eps = groups[label]
            play_from.append(label)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks or ("%d条线路" % len(groups)),
            "vod_area": area,
            "vod_year": year,
            "vod_lang": "",
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": "",
            "vod_update": update_time,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        html = self._fetch(play_page)
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    raw = m.group(1).replace("\\/", "/")
                    data = json.loads(raw)
                except Exception as e:
                    self.log("  player_data 解析失败: %s" % e)
                    data = {}
                if data:
                    url_enc = str(data.get("url") or "")
                    encrypt = str(data.get("encrypt") or "0")
                    # 与站点 27pan.js 一致的编码分支
                    if encrypt == "1":
                        url_enc = urllib.parse.unquote(url_enc)
                    elif encrypt == "2":
                        try:
                            url_enc = urllib.parse.unquote(
                                base64.b64decode(url_enc).decode("utf-8", "ignore"))
                        except Exception:
                            pass

                    # CDN 缓存域名：取页面 wz.cache，缺省回退公共 CDN
                    cache = CDN_CACHE
                    mw = _RE_WZ.search(html)
                    if mw:
                        try:
                            wz = json.loads(mw.group(1).replace("\\/", "/"))
                            if wz.get("cache"):
                                cache = wz["cache"]
                        except Exception:
                            pass
                    if not cache.endswith("/"):
                        cache += "/"

                    if url_enc:
                        # 优先还原直链（parse:0）；失败回退站点原生解码页 iframe（parse:1）
                        direct = self._decode_direct(url_enc)
                        if direct:
                            res = {
                                "parse": 0,
                                "playUrl": "",
                                "url": direct,
                                "header": {
                                    "User-Agent": UA,
                                    "Referer": cache,
                                },
                            }
                            self.log("  => direct: %s" % direct[:160])
                        else:
                            from_flag = str(data.get("from") or "")
                            iframe = "%sp/d.html?%s" % (cache, urllib.parse.urlencode(
                                {"p": from_flag, "u": url_enc}))
                            res = {
                                "parse": 1,
                                "playUrl": "",
                                "url": iframe,
                                "header": {
                                    "User-Agent": UA,
                                    "Referer": cache,
                                },
                            }
                            self.log("  => iframe: %s" % iframe[:160])

        self._play_cache[play_page] = (now, res)
        return res

    # ---------- 其它契约方法 ----------
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

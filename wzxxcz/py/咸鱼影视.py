# coding=utf-8
"""
咸鱼影视 www.xianyu8.my | TVBox Python 爬虫
站点: 自研模板（非 MacCMS/stui）+ 图片走 /pic.php 反代 + 播放数据内嵌 const VOD

结构要点（全部对着站点实测）:
  - 分类（站点顶部 chip）: /list/{id}.html
      1 电影片 / 2 连续剧 / 3 综艺片 / 4 动漫片 / 35 电影解说 / 36 体育 / 46 短剧(🎬 短剧剧场) / kids 儿童专区
  - 子分类：是另一个 list id（动作片=6 喜剧片=7 …，国产剧=13 …，大陆综艺=25 …，国产动漫=29 …，足球=37 …）
  - 筛选：/list/{id}-{page}.html?y={年份}&area={地区}（分类页的“分类/年份/地区”三行，无排序行）
  - 分页：/list/{id}-{page}.html；页码与总数取页面“共 X 页 / 共 X 部”
  - 儿童专区：/kids.php?p={page}，卡片是 /play.php?id=xxx&from=kids
  - 详情/播放同一路径：/detail/{id}.html 选集；/detail/{id}-{集}-{线路}.html 播放页
      播放页内嵌 const VOD = {...}，一次拿全: 名称/副标题/年份/地区/语言/分类/导演/主演/评分/简介/全部线路与选集直链
      线路顺序 = VOD.lines 顺序 = play_from_raw，与站点“换线路”列表一致
  - 线路显示名取站点 player.js 的 LINE_META（佛爷/高清/量子…）
  - 搜索：/?wd={关键词}（站点只出 1 页 50 条，无翻页）
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
                print("[xianyu]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.xianyu8.my"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEFAULT_PIC = HOST + "/assets/nopic.svg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ------------------------------------------------------------------ 分类
# 与站点顶部 chip 顺序完全一致（1 电影片 / 2 连续剧 / 3 综艺片 / 4 动漫片 / 35 电影解说 / 36 体育 / 46 短剧剧场 / 儿童专区）
CLASSES = [
    {"type_id": "1",    "type_name": "电影片"},
    {"type_id": "2",    "type_name": "连续剧"},
    {"type_id": "3",    "type_name": "综艺片"},
    {"type_id": "4",    "type_name": "动漫片"},
    {"type_id": "35",   "type_name": "电影解说"},
    {"type_id": "36",   "type_name": "体育"},
    {"type_id": "46",   "type_name": "短剧"},
    {"type_id": "kids", "type_name": "儿童专区"},
]

# 站点“分类”行（子分类 = 另一个 list id），仅这些栏目页有
_SUB = {
    "1":  [("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
           ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("记录片", "20"),
           ("预告片", "45"), ("动画电影", "47")],
    "2":  [("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"), ("欧美剧", "16"),
           ("台湾剧", "21"), ("日本剧", "22"), ("海外剧", "23"), ("泰国剧", "24")],
    "3":  [("大陆综艺", "25"), ("港台综艺", "26"), ("日韩综艺", "27"), ("欧美综艺", "28")],
    "4":  [("国产动漫", "29"), ("日韩动漫", "30"), ("欧美动漫", "31"), ("港台动漫", "32"),
           ("海外动漫", "33")],
    "36": [("足球", "37"), ("篮球", "38"), ("网球", "39"), ("斯诺克", "40")],
}

# 站点“年份”行（各栏目页自己的年份池，顺序照抄站点）
_YEARS = {
    "1":  ["2028", "2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
           "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009"],
    "2":  ["2028", "2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
           "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009"],
    "3":  ["2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
           "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008"],
    "4":  ["2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
           "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008"],
    "35": ["2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
           "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008"],
    "36": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
           "2017", "2016", "2014", "2013", "2012", "2011", "2007", "2003", "2002", "2000", "1996"],
    "46": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
           "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008", "2007"],
}

# 站点“地区”行（各栏目页自己的地区池）
_AREAS = {
    "1":  ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "法国",
           "德国", "俄罗斯", "印度", "泰国", "加拿大", "澳大利亚", "意大利", "西班牙",
           "巴西", "新加坡"],
    "2":  ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "法国",
           "德国", "俄罗斯", "印度", "泰国", "加拿大", "澳大利亚", "意大利", "西班牙",
           "巴西", "新加坡"],
    "3":  ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "法国",
           "泰国", "加拿大"],
    "4":  ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "法国",
           "俄罗斯", "加拿大", "澳大利亚", "意大利", "西班牙"],
    "35": ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "法国",
           "德国", "俄罗斯", "印度", "泰国", "加拿大", "澳大利亚", "意大利", "西班牙",
           "新加坡"],
    "36": ["中国大陆"],
    "46": ["中国大陆", "中国香港", "韩国", "英国"],
}

# 站点 player.js 里的线路品牌名（LINE_META），换线路列表就显示这些
_LINE_NAME = {
    "youzi": "佛爷", "ffm3u8": "非凡", "dyttm3u8": "高清", "lzm3u8": "量子",
    "jsm3u8": "迅捷", "wsym3u8": "备用", "rym3u8": "如意短剧", "ruyi": "如意备用",
    "ikm3u8": "爱坤", "zuidam3u8": "最大", "modum3u8": "魔都", "z360m3u8": "快",
    "xiguam3u8": "西瓜", "snm3u8": "索尼", "tpm3u8": "淘片", "tpiframe": "淘片网页版",
    "360zy": "快备用",
}

# ===================== 正则 =====================
_RE_LIST_NUM = re.compile(r'共\s*<span class="pghi">([\d,]+)</span>\s*页', re.I)
_RE_HEAD_NUM2 = re.compile(r'<span style="font-size:12px">共\s*([\d,]+)\s*部</span>', re.I)
_RE_CARD_A = re.compile(r'<a class="card" href="(/detail/(\d+)\.html)"', re.I)
_RE_KCARD = re.compile(r'<a class="kcard" href="/play\.php\?id=(\d+)&[^"]*"', re.I)
_RE_KPAGER = re.compile(r'<span class="cur">\s*\d+\s*/\s*(\d+)\s*</span>', re.I)

_RE_H1 = re.compile(r'<h1>([\s\S]*?)</h1>', re.I)
_RE_META = re.compile(r'<div class="meta">([\s\S]*?)</div>', re.I)
_RE_PEOPLE = re.compile(r'<div class="people">([\s\S]*?)</div>', re.I)
_RE_CONTENT_DIV = re.compile(r'<div class="content" id="content">([\s\S]*?)</div>', re.I)
_RE_DETAIL_EP = re.compile(r'<a href="(/detail/\d+-\d+-\d+\.html)"><b>([^<]+)</b></a>', re.I)

_RE_VOD_HEAD = re.compile(r'const\s+VOD\s*=\s*\{')

_RE_TAG = re.compile(r'<[^>]+>')


def _clean(s):
    if not s:
        return ""
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = _RE_TAG.sub('', s)
    s = (s.replace('&nbsp;', ' ').replace('\xa0', ' ')
          .replace('&amp;', '&').replace('&quot;', '"')
          .replace('&#39;', "'").replace('&apos;', "'")
          .replace('&lt;', '<').replace('&gt;', '>')
          .replace('&ldquo;', '“').replace('&rdquo;', '”')
          .replace('&hellip;', '…').replace('&mdash;', '—')
          .replace('&middot;', '·'))
    s = re.sub(r'[ \t\r\f\v]+', ' ', s)
    s = re.sub(r'\n{2,}', '\n', s)
    return s.strip()


def _unescape_js(s):
    """把 JS 字符串里残余的 \u0026 / \" 之类还原"""
    if not s:
        return ""
    s = (s.replace('\\u0026', '&').replace('\\\\u0026', '&')
          .replace('\\u0022', '"').replace('\\u003C', '<').replace('\\u003E', '>')
          .replace('\\/', '/'))
    return s


class Spider(Spider):

    # ------------------------------------------------------------ 基础
    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self._session = None
        self._cache = {}
        self.site_url = HOST

    def getName(self):
        return "咸鱼影视"

    def init(self, extend=""):
        try:
            ext = json.loads(extend) if extend else {}
        except Exception:
            ext = {}
        self.site_url = (ext.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass

    def close(self):
        self.destroy()

    # ------------------------------------------------------------ 网络
    def _fetch(self, url, timeout=25):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                try:
                    text = rsp.content.decode("utf-8", "ignore")
                except Exception:
                    text = ""
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fetch_iso(self, url, timeout=25):
        """独立、不带 cookie 的请求
        /kids.php 会给会话打 xykids=1，之后整站都被锁成儿童模式（列表页全变成儿童内容），
        所以儿童专区必须用一次性干净会话去抓，不能污染主会话。"""
        h = {"User-Agent": UA, "Referer": self.site_url + "/"}
        try:
            import requests as _rq2
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
            s = _rq2.Session()
            try:
                s.trust_env = False
            except Exception:
                pass
            try:
                r = s.get(url, headers=h, timeout=timeout, verify=False)
            except Exception:
                r = s.get(url, headers=h, timeout=timeout)
            r.encoding = "utf-8"
            txt = r.text or ""
            try:
                s.close()
            except Exception:
                pass
            return txt
        except Exception as e:
            self.log("iso fetch FAIL %s -> %s" % (url, e))
            return self._fetch(url, timeout)

    def _clear_kids_cookie(self):
        """万一主会话里残留 xykids（儿童模式锁），清掉"""
        try:
            jar = getattr(getattr(self, "_sess", None), "cookies", None)
            if jar is None:
                return
            for c in list(jar):
                if c.name == "xykids":
                    jar.clear(c.domain, c.path, c.name)
        except Exception:
            pass

    def _fix(self, url):
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

    # ------------------------------------------------------------ 首页
    def homeContent(self, filter=False):
        result = {"class": CLASSES}
        if filter:
            fl = {}
            for c in CLASSES:
                tid = c["type_id"]
                if tid == "kids":
                    fl[tid] = []
                    continue
                rows = []
                subs = _SUB.get(tid) or []
                if subs:
                    rows.append({"key": "class", "name": "分类",
                                 "value": [{"n": "全部", "v": ""}] +
                                          [{"n": n, "v": v} for n, v in subs]})
                years = _YEARS.get(tid) or []
                if years:
                    rows.append({"key": "year", "name": "年份",
                                 "value": [{"n": "全部", "v": ""}] +
                                          [{"n": y, "v": y} for y in years]})
                areas = _AREAS.get(tid) or []
                if areas:
                    rows.append({"key": "area", "name": "地区",
                                 "value": [{"n": "全部", "v": ""}] +
                                          [{"n": a, "v": a} for a in areas]})
                fl[tid] = rows
            result["filters"] = fl
        return result

    def homeVideoContent(self):
        h = self._fetch(self.site_url + "/")
        v = self._parse_cards(h)
        self.log("home 最近更新: %d 条" % len(v))
        return {"list": v}

    # ------------------------------------------------------------ 卡片解析
    def _parse_cards(self, h):
        """通用列表卡片: <a class="card" href="/detail/{id}.html"> ... <b>副标题</b> <div class="nm">名</div>"""
        out = []
        seen = set()
        if not h:
            return out
        # “最近更新”分区（首页 h2 之后）以后的卡片顺序就是站点顺序
        idx = h.rfind("<h2>最近更新</h2>")
        if idx > 0:
            h = h[idx:]
        pos = [m.start() for m in _RE_CARD_A.finditer(h)]
        for i, p in enumerate(pos):
            e = pos[i + 1] if i + 1 < len(pos) else min(len(h), p + 2500)
            blk = h[p:e]
            m = _RE_CARD_A.match(h[p:])
            if not m:
                continue
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            im = re.search(r'<img[^>]*>', blk, re.I)
            pic = ""
            alt = ""
            if im:
                alt = re.search(r'alt="([^"]*)"', im.group(0), re.I)
                alt = alt.group(1).strip() if alt else ""
                src = re.search(r'src="([^"]*)"', im.group(0), re.I)
                pic = src.group(1).strip() if src else ""
            nm = re.search(r'<div class="nm">([\s\S]*?)</div>', blk, re.I)
            name = _clean(nm.group(1)) if nm else _clean(alt)
            rm = re.search(r'<div class="rm">([\s\S]*?)</div>', blk, re.I)
            sub = _clean(rm.group(1)) if rm else ""
            rem = re.search(r'<b>([\s\S]*?)</b>', blk, re.I)
            remarks = _clean(rem.group(1)) if rem else ""
            out.append({
                "vod_id": "/detail/%s.html" % vid,
                "vod_name": name,
                "vod_pic": self._fix(pic) if pic else DEFAULT_PIC,
                "vod_remarks": remarks or sub,
            })
        return out

    def _parse_kids(self, h):
        out = []
        seen = set()
        if not h:
            return out
        pos = [m.start() for m in _RE_KCARD.finditer(h)]
        for i, p in enumerate(pos):
            e = pos[i + 1] if i + 1 < len(pos) else min(len(h), p + 2500)
            blk = h[p:e]
            m = _RE_KCARD.match(h[p:])
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            im = re.search(r'<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"', blk, re.I)
            if not im:
                im2 = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"', blk, re.I)
                alt = im2.group(2) if im2 else ""
                pic = im2.group(1) if im2 else ""
            else:
                alt, pic = im.group(1), im.group(2)
            nm = re.search(r'<div class="kname">([\s\S]*?)</div>', blk, re.I)
            name = _clean(nm.group(1)) if nm else _clean(alt)
            kep = re.search(r'<span class="kep">([\s\S]*?)</span>', blk, re.I)
            remarks = _clean(kep.group(1)) if kep else ""
            out.append({
                "vod_id": "/detail/%s.html" % vid,
                "vod_name": name,
                "vod_pic": self._fix(pic) if pic else DEFAULT_PIC,
                "vod_remarks": remarks,
            })
        return out

    def _page_info(self, h):
        """返回 (总页数, 总条数)"""
        pages = 1
        total = 0
        m = _RE_LIST_NUM.search(h or "")
        if m:
            try:
                pages = max(1, int(m.group(1).replace(",", "")))
            except Exception:
                pages = 1
        m = _RE_HEAD_NUM2.search(h or "")
        if m:
            try:
                total = int(m.group(1).replace(",", ""))
            except Exception:
                total = 0
        if not total:
            hm = re.search(r'共\s*([\d,]+)\s*部', h or "")
            if hm:
                try:
                    total = int(hm.group(1).replace(",", ""))
                except Exception:
                    total = 0
        return pages, total

    # ------------------------------------------------------------ 分类
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        ext = dict(extend or {})
        for k in list(ext.keys()):
            if ext[k] in ("", None, "全部"):
                del ext[k]

        tid = str(tid)

        # 儿童专区：/kids.php?p=N
        if tid == "kids":
            url = "%s/kids.php?p=%d" % (self.site_url, page)
            if page <= 1:
                url = self.site_url + "/kids.php"
            h = self._fetch_iso(url)
            v = self._parse_kids(h)
            m = _RE_KPAGER.search(h or "")
            pages = int(m.group(1)) if m else max(1, page)
            tm = re.search(r'共\s*([\d,]+)\s*部', h or "")
            total = 0
            if tm:
                try:
                    total = int(tm.group(1).replace(",", ""))
                except Exception:
                    total = 0
            self.log("kids p%d -> %d 条, %d 页, %d 部" % (page, len(v), pages, total))
            return {"list": v, "page": page, "pagecount": pages,
                    "limit": 24, "total": total or (pages * 24 if v else 0)}

        # 站点“分类”行选的是另一个 list id
        sub = str(ext.pop("class", "") or "").strip()
        list_id = sub or tid

        qs = []
        if ext.get("year"):
            qs.append("y=" + urllib.parse.quote(str(ext["year"])))
        if ext.get("area"):
            qs.append("area=" + urllib.parse.quote(str(ext["area"])))
        url = "%s/list/%s-%d.html" % (self.site_url, list_id, page)
        if qs:
            url += "?" + "&".join(qs)
        self._clear_kids_cookie()
        h = self._fetch(url)
        v = self._parse_cards(h)
        pages, total = self._page_info(h)
        if pages < page:
            pages = page
        self.log("category %s -> %d 条, %d/%d 页" % (url, len(v), page, pages))
        return {"list": v, "page": page, "pagecount": pages,
                "limit": 24, "total": total or (pages * 24 if v else 0)}

    # ------------------------------------------------------------ 搜索
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        kw = urllib.parse.quote(str(key or "").strip())
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 50, "total": 0}
        self._clear_kids_cookie()
        h = self._fetch("%s/?wd=%s" % (self.site_url, kw))
        v = self._parse_cards(h)
        hm = re.search(r'共\s*([\d,]+)\s*[部条]', h or "")
        total = 0
        if hm:
            try:
                total = int(hm.group(1).replace(",", ""))
            except Exception:
                total = 0
        self.log("search %s -> %d 条" % (kw, len(v)))
        return {"list": v, "page": 1, "pagecount": 1,
                "limit": 50, "total": total or len(v)}

    # ------------------------------------------------------------ 详情
    def _vod_json(self, h):
        """从播放页抓 const VOD = {...}（带字符串感知的括号配对，避免正则截断）"""
        if not h:
            return None
        m = _RE_VOD_HEAD.search(h)
        if not m:
            return None
        i = m.end() - 1          # 指向 '{'
        depth = 0
        in_str = False
        esc = False
        for j in range(i, min(len(h), i + 200000)):
            ch = h[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    raw = h[i: j + 1]
                    try:
                        return json.loads(raw)
                    except Exception:
                        return None
        return None

    def _eps_from_html(self, h):
        """兜底：直接从详情页的 /detail/{id}-{ep}-{line}.html 取选集（只有默认线路）"""
        m = _RE_DETAIL_EP.findall(h or "")
        if not m:
            return []
        eps = []
        for href, name in m:
            eps.append((_clean(name), self._fix(href)))
        return eps

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        m = re.search(r'/detail/(\d+)\.html', vid)
        if m:
            vod_id = m.group(1)
        else:
            m = re.search(r'(\d{5,})', vid)
            vod_id = m.group(1) if m else ""
        if not vod_id:
            return {"list": []}

        # 播放页（第1集/默认线路）一次拿全：名称/副标题/年份/地区/语言/类型/导演/主演/评分/简介/全部线路
        play_url = "%s/detail/%s-1-0.html" % (self.site_url, vod_id)
        j = self._vod_json(self._fetch(play_url))
        if not j:
            # 没有可播放集（如预告片），退回详情页
            h = self._fetch("%s/detail/%s.html" % (self.site_url, vod_id))
            if not h:
                return {"list": []}
            name = ""
            hm = _RE_H1.search(h)
            if hm:
                name = _clean(hm.group(1))
            if not name:
                tm = re.search(r'<title>([\s\S]*?)</title>', h, re.I)
                name = _clean(tm.group(1).split('_')[0]) if tm else vod_id
            # meta 里的 span 依次是 年份 / 地区 / 语言 / 类型(可多个) / 状态(金色)
            meta = _RE_META.search(h)
            vals = []
            remarks = ""
            if meta:
                for attrs, txt in re.findall(r'<span([^>]*)>([\s\S]*?)</span>', meta.group(1)):
                    t = _clean(txt)
                    if not t:
                        continue
                    if "gold" in attrs:
                        remarks = t
                    else:
                        vals.append(t)
            year = vals[0] if len(vals) > 0 else ""
            area = vals[1] if len(vals) > 1 else ""
            lang = vals[2] if len(vals) > 2 else ""
            cls = ",".join(vals[3:])
            director = ""
            actor = ""
            for p in _RE_PEOPLE.findall(h):
                t = _clean(p)
                if t.startswith("导演"):
                    director = t.split("：", 1)[-1].strip()
                elif t.startswith("主演"):
                    actor = t.split("：", 1)[-1].strip()
            content = ""
            cm = _RE_CONTENT_DIV.search(h)
            if cm:
                content = _clean(cm.group(1))
            if not content:
                dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', h, re.I)
                if dm:
                    content = _clean(dm.group(1))
            eps = self._eps_from_html(h)
            if not eps:
                return {"list": []}
            return {"list": [{
                "vod_id": "/detail/%s.html" % vod_id,
                "vod_name": name,
                "vod_pic": DEFAULT_PIC,
                "vod_remarks": remarks or "正片",
                "type_name": cls,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX,
                "vod_play_from": "默认线路",
                "vod_play_url": "#".join("%s$%s" % (n, u) for n, u in eps),
            }]}

        # ---- 有内嵌 VOD：完整线路 & 选集直链 ----
        name = _clean(j.get("name") or "")
        pic = _unescape_js(j.get("pic") or "")
        remarks = _clean(j.get("remarks") or "")
        cls = _clean(j.get("type_name") or "") or _clean(j.get("class") or "")
        year = _clean(j.get("year") or "")
        area = _clean(j.get("area") or "")
        lang = _clean(j.get("lang") or "")
        actor = _clean(j.get("actor") or "")
        director = _clean(j.get("director") or "")
        score = _clean(j.get("score") or "")
        content = _clean(j.get("content") or "")
        if score in ("0.0", "0", ""):
            score = ""

        from_list = []
        url_list = []
        lines = j.get("lines") or []
        for i, ln in enumerate(lines):
            raw_name = str(ln.get("name") or "").strip()
            label = _LINE_NAME.get(raw_name) or raw_name or ("线路%d" % (i + 1))
            if label in from_list:
                label = "%s%d" % (label, i + 1)
            eps = ln.get("eps") or []
            items = []
            for k, ep in enumerate(eps):
                t = _clean(ep.get("t") or "") or ("第%02d集" % (k + 1))
                u = _unescape_js(ep.get("u") or "")
                if not u:
                    continue
                items.append("%s$%s" % (t, self._fix(u)))
            if not items:
                continue
            from_list.append(label)
            url_list.append("#".join(items))

        if not from_list:
            return {"list": []}

        return {"list": [{
            "vod_id": "/detail/%s.html" % vod_id,
            "vod_name": name or vod_id,
            "vod_pic": pic or DEFAULT_PIC,
            "vod_remarks": remarks or "正片",
            "type_name": cls,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_content": (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX,
            "vod_play_from": "$$$".join(from_list),
            "vod_play_url": "$$$".join(url_list),
        }]}

    # ------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags):
        sv = str(id or "").strip()
        # A. 选集里给的就是直链（m3u8 / mp4）
        if sv.startswith("http") and (".m3u8" in sv.lower() or ".mp4" in sv.lower()):
            return {"parse": 0, "playUrl": "", "url": sv, "header": self._hdr()}

        # B. 给的是 /detail/{id}-{ep}-{line}.html → 从播放页取该线该集
        m = re.search(r'/detail/(\d+)-(\d+)-(\d+)\.html', sv)
        if m:
            page = self._fix(sv)
            cache_key = page
            cached = self._cache.get(cache_key)
            if cached and time.time() - cached[0] < 600:
                return cached[1]
            h = self._fetch(page)
            j = self._vod_json(h)
            if j:
                line = int(m.group(3))
                ep = int(m.group(2))
                lines = j.get("lines") or []
                if 0 <= line < len(lines):
                    eps = lines[line].get("eps") or []
                    if 0 < ep <= len(eps):
                        u = _unescape_js(eps[ep - 1].get("u") or "")
                        if u:
                            res = {"parse": 0, "playUrl": "", "url": self._fix(u),
                                   "header": self._hdr()}
                            self._cache[cache_key] = (time.time(), res)
                            return res
            res = {"parse": 1, "playUrl": "", "url": page, "header": self._hdr()}
            self._cache[cache_key] = (time.time(), res)
            return res

        # C. 其它：交给 TVBox 嗅探
        return {"parse": 1, "playUrl": "", "url": self._fix(sv), "header": self._hdr()}

    def _hdr(self):
        return {"User-Agent": UA, "Referer": self.site_url + "/"}

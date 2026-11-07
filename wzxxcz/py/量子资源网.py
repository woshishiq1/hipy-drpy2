# coding=utf-8
"""
量子资源网 cj.lziapi.com | TVBox Python 爬虫 
关键:
  - MacCMS(苹果CMS) 结构: /index.php/vod/type|detail|search/...
  - 分类筛选: /index.php/vod/type/id/1/class/剧情/area/美国/year/2026.html
  - 详情页三线路按站点顺序: 量子liangzi地址 -> 量子lzm3u8地址 -> http下载
  - liangzi share 页 (lzcdn*/share/xxx) 自动提取 var main 得到真实 m3u8
  - lzm3u8 / http 直链直接 parse:0 播放
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
                print("[liangzi]", *a)
            except Exception:
                pass


HOST = "https://cj.lziapi.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://p.lztutu.com/upload/vod/20240101-1/default.webp"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "46", "type_name": "短剧"},
    {"type_id": "52", "type_name": "AI漫剧"},
    {"type_id": "35", "type_name": "电影解说"},
    {"type_id": "36", "type_name": "体育"},
]

# 影片类型(class)筛选, 与站点各分类子类一致
_CLASS_MAP = {
    "1": ["全部", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片", "战争片",
          "记录片", "伦理片", "预告片"],
    "2": ["全部", "国产剧", "香港剧", "韩国剧", "欧美剧", "台湾剧", "日本剧",
          "海外剧", "泰国剧"],
    "3": ["全部", "大陆综艺", "港台综艺", "日韩综艺", "欧美综艺"],
    "4": ["全部", "国产动漫", "日韩动漫", "欧美动漫", "港台动漫", "海外动漫", "动画片"],
    "46": ["全部", "短剧"],
    "52": ["全部", "AI漫剧"],
    "35": ["全部", "电影解说"],
    "36": ["全部", "足球", "篮球", "网球", "斯诺克"],
}

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "大陆", "v": "大陆"},
    {"n": "美国", "v": "美国"}, {"n": "英国", "v": "英国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "香港", "v": "香港"},
    {"n": "中国台湾", "v": "中国台湾"}, {"n": "台湾", "v": "台湾"},
    {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
    {"n": "澳大利亚", "v": "澳大利亚"}, {"n": "西班牙", "v": "西班牙"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "其他", "v": "其他"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_LETTERS = [{"n": "字母", "v": ""}] + \
           [{"n": c, "v": c} for c in
            list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _CLASS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
    ]


# ===================== 正则 =====================
# 列表卡片: <a class="videoName" ... href="...detail/id/xxx.html" ...>名称<i>备注</i></a>
_RE_CARD = re.compile(
    r'<a\s+class="videoName"[^>]*?href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>'
    r'([^<]+)(?:<i>([^<]*)</i>)?', re.S | re.I)

# 详情页元信息: <p>字段：值</p>
_RE_META = re.compile(r'<p>(片名|别名|豆瓣|状态|类型|导演|演员|年代|地区|语言|TAG标签|更新时间)：([\s\S]*?)</p>', re.I)
_RE_POSTER = re.compile(
    r'<div class="left"><img src="([^"]+)"', re.I)
_RE_CONTENT = re.compile(
    r'<div class="vod_content">([\s\S]*?)</div>', re.I)

# 详情页线路区块: <h4><div>标题</div></h4> ... <div class="playlist wbox xxx">
_RE_BLOCK = re.compile(
    r'<h4><div>([^<]*?)</div></h4>\s*<hr>\s*'
    r'<div class="playlist wbox ([\w-]+)">([\s\S]*?)</div>', re.I)
# 每一集: checkbox value="名称$链接"
_RE_EP = re.compile(r'value="([^"$]+)\$([^"]+)"', re.I)

# share 页真实地址: var main = "/xxx/index.m3u8?sign=..."
_RE_SHARE_MAIN = re.compile(r'var\s+main\s*=\s*["\']([^"\']+)["\']', re.I)


class Spider(Spider):

    def getName(self):
        return "量子资源"

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
        self.default_pic = self.extend.get("pic") or DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=30, headers=None):
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
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        for href, vid, name, remark in _RE_CARD.findall(html):
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({
                "vod_id":      "/index.php/vod/detail/id/%s.html" % vid,
                "vod_name":    self._clean(name)[:100],
                "vod_pic":     self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = re.search(r'当前1?/?(\d+)/(\d+)页', html) or \
            re.search(r'当前\d+/(\d+)页', html) or \
            re.search(r'共(\d+)条数据,当前\d+/(\d+)页', html)
        if m:
            try:
                return int(m.group(m.lastindex))
            except Exception:
                pass
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
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

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部", "字母"):
                del extend[k]

        path = "/index.php/vod/type/id/%s/page/%d.html" % (tid, page)
        segs = []
        if extend.get("class"):
            segs += ["class", extend["class"]]
        if extend.get("area"):
            segs += ["area", extend["area"]]
        if extend.get("year"):
            segs += ["year", extend["year"]]
        if extend.get("letter"):
            segs += ["letter", extend["letter"]]
        if segs:
            parts = path.replace(".html", "").split("/")
            path = "/".join(parts + [urllib.parse.quote(str(s)) for s in segs]) + ".html"

        url = self.site_url + path
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 50, "total": pagecount * 50,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (
            self.site_url, page, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 50, "total": 999,
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

        # ===== 元信息 =====
        meta = {}
        for k, v in _RE_META.findall(html):
            meta[k] = self._clean(v)

        name = meta.get("片名", "")
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("详情介绍")[0])
        name = re.sub(r"\s*\(【?\d{4}】?\)\s*$", "", name).strip() or vod_id

        pic = self.default_pic
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 副标题 = 别名
        subtitle = meta.get("别名", "")

        # ===== 简介 =====
        content = ""
        m = _RE_CONTENT.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + (content or name)

        # ===== 剧集(三线路, 与站点顺序一致) =====
        groups = []      # [(标题, [(集名, url), ...])]
        try:
            for block_title, block_key, body in _RE_BLOCK.findall(html):
                eps = []
                for ep_name, ep_url in _RE_EP.findall(body):
                    ep_url = ep_url.replace("&amp;", "&")
                    if not ep_url.startswith("http"):
                        ep_url = self._fix_url(ep_url)
                    if ep_name and ep_url:
                        eps.append((ep_name, ep_url))
                if eps:
                    groups.append((block_title, eps))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        self.log("  线路: %s" % {t: len(v) for t, v in groups})

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        for title, eps in groups:
            play_from.append(title)
            play_url.append("#".join("%s$%s" % (n, u) for n, u in eps))

        # remarks: 状态 + 更新时间
        remarks = " / ".join(
            x for x in (meta.get("状态", ""), meta.get("更新时间", "")) if x)
        score = meta.get("豆瓣", "").replace(" 分", "")

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": meta.get("演员", ""),
            "vod_director": meta.get("导演", ""),
            "vod_area": meta.get("地区", ""),
            "vod_year": meta.get("年代", ""),
            "vod_remarks": remarks or ("%d条线路" % len(groups)),
            "vod_score": score,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        raw = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % raw)

        now = int(time.time())
        if raw in self._play_cache:
            ts, res = self._play_cache[raw]
            if now - ts < 600:
                return res

        low = raw.lower()
        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # ===== 直链 m3u8 / mp4 (lzm3u8 / http下载线路) =====
        if ".m3u8" in low or ".mp4" in low:
            res = {"parse": 0, "playUrl": "", "url": raw, "header": header}
            self._play_cache[raw] = (now, res)
            self.log("  => 直链: %s" % raw[:160])
            return res

        # ===== liangzi share 页: 提取 var main 拼真实 m3u8 =====
        html = self._fetch(raw, headers={
            "User-Agent": UA, "Referer": raw, "Accept": "*/*"})
        m = _RE_SHARE_MAIN.search(html or "")
        if m:
            main_path = m.group(1).replace("&amp;", "&")
            if main_path.startswith("http"):
                real = main_path
            else:
                # share 页的相对路径基于 share 页所在 host
                p = urllib.parse.urlparse(raw)
                real = "%s://%s%s" % (p.scheme, p.netloc, main_path)
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real,
                "header": {
                    "User-Agent": UA,
                    "Referer": "%s://%s/" % (p.scheme, p.netloc),
                },
            }
            self._play_cache[raw] = (now, res)
            self.log("  => share m3u8: %s" % real[:160])
            return res

        # 兜底: 交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": raw, "header": header}
        self._play_cache[raw] = (now, res)
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

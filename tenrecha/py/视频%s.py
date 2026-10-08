# -*- coding: utf-8 -*-
# 骚女档案馆 Spider（影视仓 / OK影视 / WebHomeTV / PickTV 通用）
# 站点: https://xn--4ru826c.sndag137.cc/sn/aaa.php
# 结构: 自定义系统（路由模仿 MacCMS）
#   - 首页"最近更新"20条 / 分类 /vod/type/id/{tid}/page/{pg}.html / 搜索 /vod/search/wd/{kw}/page/{pg}.html
#   - 详情页内嵌 xgplayer HlsJsPlayer "url" 直链 m3u8（无防盗链、无 AES）
# 命名: 骚女档案馆_sndag137.cc_spider.py

import re
import json
import time
import random
import base64

try:
    from urllib.parse import urljoin, quote, urlparse, parse_qs
except Exception:
    from urllib.parse import urljoin, quote, urlparse, parse_qs

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

if not HAS_REQUESTS:
    import urllib.request
    import urllib.error

UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# ---------- 站点常量 ----------
SITE_HOST = "xn--4ru826c.sndag137.cc"
SITE_BASE = "https://" + SITE_HOST
API_PREFIX = "/sn/aaa.php"

CATS = [
    {"type_id": "9780", "type_name": "国产"},
    {"type_id": "9781", "type_name": "有码"},
    {"type_id": "9782", "type_name": "无码"},
    {"type_id": "9783", "type_name": "字幕"},
    {"type_id": "9784", "type_name": "欧美"},
    {"type_id": "9785", "type_name": "动漫"},
    {"type_id": "9786", "type_name": "制服诱惑"},
    {"type_id": "9787", "type_name": "巨乳美乳"},
    {"type_id": "9788", "type_name": "熟女人妻"},
    {"type_id": "9789", "type_name": "强奸乱伦"},
    {"type_id": "9790", "type_name": "学生少女"},
    {"type_id": "9806", "type_name": "传媒"},
    {"type_id": "9807", "type_name": "三级"},
    {"type_id": "9808", "type_name": "黑料"},
]

# ---------- HTTP 层（requests 优先，无则 urllib 降级） ----------
class _Http(object):
    def __init__(self):
        self.timeout = 15
        self.headers = {
            "User-Agent": UA,
            "Referer": SITE_BASE + "/",
            "Accept": "*/*",
        }
        if HAS_REQUESTS:
            self.s = requests.Session()
            self.s.headers.update(self.headers)
            self.session = self.s
            self.sess = self.s

    def get_text(self, url, retry=3):
        if HAS_REQUESTS:
            last = None
            for i in range(retry):
                try:
                    r = self.s.get(url, timeout=self.timeout)
                    if r.status_code == 200:
                        return r.text
                    last = "HTTP " + str(r.status_code)
                except Exception as e:
                    last = repr(e)
                time.sleep(0.6 * (i + 1))
            raise RuntimeError("GET %s failed: %s" % (url, last))
        last = None
        for i in range(retry):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return resp.read().decode("utf-8", "ignore")
            except Exception as e:
                last = repr(e)
            time.sleep(0.6 * (i + 1))
        raise RuntimeError("GET %s failed: %s" % (url, last))

    def get_bytes(self, url, retry=3):
        if HAS_REQUESTS:
            last = None
            for i in range(retry):
                try:
                    r = self.s.get(url, timeout=self.timeout)
                    if r.status_code == 200:
                        return r.content
                    last = "HTTP " + str(r.status_code)
                except Exception as e:
                    last = repr(e)
                time.sleep(0.6 * (i + 1))
            raise RuntimeError("GET %s failed: %s" % (url, last))
        last = None
        for i in range(retry):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return resp.read()
            except Exception as e:
                last = repr(e)
            time.sleep(0.6 * (i + 1))
        raise RuntimeError("GET %s failed: %s" % (url, last))


# ---------- 页面解析 ----------
_VIDEO_ITEM_RE = re.compile(
    r'<div class="video-item">.*?'
    r'data-src="([^"]+)"[^>]*>.*?'
    r'vod/detail/id/(\d+)\.html"[^>]*>(.*?)</a>',
    re.S,
)

_TAG_STRIP_RE = re.compile(r"<[^>]+>")

_DATE_RE = re.compile(r'bg-black rounded-large text-white">([^<]+)</div>')

_TAG_RE = re.compile(
    r'<li class="mr-4 mb-3 flex rounded group">\s*'
    r'<a class="flex rounded[^"]*"[^>]*href="[^"]*vod/search/wd/[^"]*"[^>]*>'
    r'#?\s*<strong class="font-normal">([^<]+)</strong>',
    re.S,
)

_M3U8_RE = re.compile(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"')

_TITLE_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)

_BREADCRUMB_RE = re.compile(r'<a[^>]*href="[^"]*vod/type/id/(\d+)\.html"[^>]*>([^<]+)</a>')

_HOME_SECTION_RE = re.compile(
    r'<h2 class="text-2xl md:text-5xl[^"]*"[^>]*>([^<]+)</h2>.*?</div>\s*'
    r'<ul class="video-items[^"]*">(.*?)</ul>',
    re.S,
)


def _parse_video_items(html):
    """解析 video-item 卡片列表，返回 [dict,...]"""
    out = []
    for m in _VIDEO_ITEM_RE.finditer(html):
        pic = m.group(1).strip()
        vid = m.group(2)
        # 封面规范化：占位图/空 → 留空（壳显示默认图）；相对路径 → 补全为站点绝对 URL
        if not pic or pic.startswith("/style/") or pic.startswith("data:"):
            pic = ""
        elif not pic.startswith("http"):
            pic = SITE_BASE + pic
        # 标题可能含 <b> 关键词高亮标签，剥掉
        name = _TAG_STRIP_RE.sub("", m.group(3))
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue
        # 该卡片块内找日期
        block_start = html.rfind('<div class="video-item">', 0, m.start())
        block_end = m.end()
        block = html[block_start:block_end]
        dm = _DATE_RE.search(block)
        remarks = dm.group(1).strip() if dm else ""
        item = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
        }
        out.append(item)
    # 去重
    seen = set()
    uniq = []
    for it in out:
        if it["vod_id"] not in seen:
            seen.add(it["vod_id"])
            uniq.append(it)
    return uniq


class Spider(object):
    """骚女档案馆"""

    _detail_cache = {}
    _detail_cache_ts = {}

    def __init__(self):
        self.http = _Http()
        self.s = self.http.s if HAS_REQUESTS else None
        self.session = self.s
        self.sess = self.s

    # ---------- 生命周期 ----------
    def getDependence(self):
        return ""

    def init(self, extend=""):
        try:
            if isinstance(extend, dict):
                pass
            elif extend:
                json.loads(extend)
        except Exception:
            pass
        return ""

    def destroy(self):
        return ""

    def action(self, action):
        return ""

    def manualVideoCheck(self):
        return False

    # ---------- 通用请求 ----------
    def _get(self, path):
        url = SITE_BASE + API_PREFIX + path if path.startswith("/") else path
        if not path.startswith("http"):
            url = SITE_BASE + API_PREFIX + path
        return self.http.get_text(url)

    # ---------- 首页 ----------
    def homeContent(self, filter=None):
        cats = [dict(c) for c in CATS]
        return {"class": cats, "filters": {}}

    def homeVideoContent(self):
        try:
            html = self._get("/")
            items = _parse_video_items(html)
            if not items:
                html2 = self._get("/vod/type/id/9782/page/1.html")
                items = _parse_video_items(html2)
            if not items:
                html3 = self._get("/vod/type/id/9780.html")
                items = _parse_video_items(html3)
            return {"list": items[:40]}
        except Exception:
            return {"list": []}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = str(pg) if pg is not None else "1"
            if pg in ("", "0", "None"):
                pg = "1"
            path = "/vod/type/id/%s/page/%s.html" % (str(tid), pg)
            if pg == "1":
                path = "/vod/type/id/%s.html" % str(tid)
            html = self._get(path)
            items = _parse_video_items(html)
            return {"list": items, "page": int(pg)}
        except Exception:
            return {"list": [], "page": int(pg) if str(pg).isdigit() else 1}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = str(pg) if pg is not None else "1"
            if pg in ("", "0", "None"):
                pg = "1"
            kw = quote(key)
            path = "/vod/search/wd/%s/page/%s.html" % (kw, pg)
            if pg == "1":
                path = "/vod/search/wd/%s.html" % kw
            html = self._get(path)
            items = _parse_video_items(html)
            return {"list": items}
        except Exception:
            return {"list": []}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            vid = ids
            if isinstance(ids, (list, tuple)):
                vid = ids[0]
            vid = str(vid)
            # 兼容传入完整 URL
            m = re.search(r"vod/detail/id/(\d+)", vid)
            if m:
                vid = m.group(1)
            cache = Spider._detail_cache.get(vid)
            now = time.time()
            if cache and now - Spider._detail_cache_ts.get(vid, 0) < 1800:
                return {"list": [cache]}
            html = self._get("/vod/detail/id/%s.html" % vid)
            # 标题：遍历 h1，跳过 logo 图（含 <img 的），取第一个真实标题
            name = ""
            for tm in _TITLE_RE.finditer(html):
                raw = _TAG_STRIP_RE.sub("", tm.group(1))
                raw = re.sub(r"\s+", " ", raw).strip()
                if raw and "logo" not in raw.lower():
                    name = raw
                    break
            if not name:
                # 兜底：页面 <title> 去掉站点后缀
                ttm = re.search(r"<title>([^<]*)</title>", html)
                if ttm:
                    name = re.sub(r"_\u9a9a\u5973\u6863\u6848\u9986\s*$", "", ttm.group(1).strip())
            if not name:
                name = "视频%s" % vid
            # 播放地址（可能多个 → 选集）
            urls = []
            for u in _M3U8_RE.findall(html):
                u = u.strip()
                if u not in urls:
                    urls.append(u)
            if not urls:
                return {"list": [{"vod_id": vid, "vod_name": name}]}
            # 封面：优先播放器 poster（真实封面），其次完整域名 data-src（跳过 /upload/ 相对路径 logo）
            pic = ""
            pm = re.search(r'poster":\s*"([^"]+)"', html)
            if pm:
                pic = pm.group(1).strip()
            if not pic or not pic.startswith("http"):
                pm2 = re.search(r'data-src="(https?://[^"]+)"', html)
                if pm2:
                    pic = pm2.group(1).strip()
            if pic and not pic.startswith("http"):
                pic = ""
            # 标签
            tags = [t.strip() for t in _TAG_RE.findall(html) if t.strip()]
            # 分类（面包屑）
            bm = _BREADCRUMB_RE.search(html)
            type_id = bm.group(1) if bm else ""
            type_name = bm.group(2).strip() if bm else ""
            # 构建选集
            play_urls = []
            if len(urls) == 1:
                play_urls.append("%s$%s" % (name, urls[0]))
            else:
                for i, u in enumerate(urls, 1):
                    play_urls.append("第%d集$%s" % (i, u))
            detail = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_play_from": "直链",
                "vod_play_url": "#".join(play_urls),
                "vod_content": ("标签：" + "、".join(tags)) if tags else "",
            }
            if type_id:
                detail["vod_class"] = type_name
            Spider._detail_cache[vid] = detail
            Spider._detail_cache_ts[vid] = now
            return {"list": [detail]}
        except Exception:
            return {"list": []}

    # ---------- 播放 ----------
    def playerContent(self, flag, ids, vipFlags=None):
        try:
            url = ids
            if isinstance(ids, (list, tuple)):
                url = ids[0]
            url = str(url).strip()
            # 兼容传入详情 id
            m = re.search(r"vod/detail/id/(\d+)", url)
            if m:
                html = self._get("/vod/detail/id/%s.html" % m.group(1))
                mu = _M3U8_RE.search(html)
                if not mu:
                    return {"parse": 0, "url": ""}
                url = mu.group(1).strip()
            if not url:
                return {"parse": 0, "url": ""}
            return {
                "parse": 0,
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": SITE_BASE + "/",
                },
            }
        except Exception:
            return {"parse": 0, "url": ""}

    # ---------- 本地代理（兜底：m3u8 文本代理，相对分片转绝对） ----------
    def localProxy(self, param):
        try:
            args = parse_qs(param)
            url = args.get("url", [""])[0]
            if not url:
                return [404, "text/plain", b"no url", {}]
            data = self.http.get_bytes(url)
            if url.endswith(".m3u8") or b"#EXTM3U" in data[:200]:
                text = data.decode("utf-8", "ignore")
                base = url[: url.rfind("/") + 1]
                out_lines = []
                for line in text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if line.startswith("http"):
                            out_lines.append(line)
                        else:
                            out_lines.append(urljoin(base, line))
                    else:
                        out_lines.append(line)
                data = ("\n".join(out_lines)).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", data, {}]
            return [200, "application/octet-stream", data, {}]
        except Exception:
            return [404, "text/plain", b"proxy error", {}]

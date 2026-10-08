# coding=utf-8
"""
Auete 影视网 TVBox Python Spider (V1.6 全子分类版)
站点: https://www.aeete.com
特点:
  - 分类与网站结构 100% 一致（子分类全部展开）
  - 无虚拟筛选
  - 简介统一加前缀
  - 播放地址: base64decode 解码出 m3u8 直链
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
            timeout = kw.pop('timeout', 20)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[auete]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ==================== 常量 ====================
HOST = "https://www.aeete.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/statics/picture/loading.gif"

# ⭐ 简介固定前缀
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ⭐ 分类：与网站 nav-tag-list 完全一致
CLASSES = [
    # 电影
    {"type_id": "Movie/xjp",  "type_name": "喜剧片"},
    {"type_id": "Movie/dzp",  "type_name": "动作片"},
    {"type_id": "Movie/aqp",  "type_name": "爱情片"},
    {"type_id": "Movie/khp",  "type_name": "科幻片"},
    {"type_id": "Movie/kbp",  "type_name": "恐怖片"},
    {"type_id": "Movie/jsp",  "type_name": "惊悚片"},
    {"type_id": "Movie/zzp",  "type_name": "战争片"},
    {"type_id": "Movie/jqp",  "type_name": "剧情片"},
    # 电视剧
    {"type_id": "Tv/neidi",   "type_name": "国产剧"},
    {"type_id": "Tv/oumei",   "type_name": "美剧"},
    {"type_id": "Tv/hanju",   "type_name": "韩剧"},
    {"type_id": "Tv/riju",    "type_name": "日剧"},
    {"type_id": "Tv/yataiju", "type_name": "泰剧"},
    {"type_id": "Tv/wangju",  "type_name": "网剧"},
    {"type_id": "Tv/taiju",   "type_name": "台剧"},
    {"type_id": "Tv/tvbgj",   "type_name": "港剧"},
    {"type_id": "Tv/yingju",  "type_name": "英剧"},
    {"type_id": "Tv/waiju",   "type_name": "外剧"},
    {"type_id": "Tv/aigcju",  "type_name": "AIGC剧"},
    # 综艺
    {"type_id": "Zy/guozong", "type_name": "国综"},
    {"type_id": "Zy/hanzong", "type_name": "韩综"},
    {"type_id": "Zy/meizong", "type_name": "美综"},
    # 动漫
    {"type_id": "Dm/donghua", "type_name": "动画"},
    {"type_id": "Dm/riman",   "type_name": "日漫"},
    {"type_id": "Dm/guoman",  "type_name": "国漫"},
    {"type_id": "Dm/meiman",  "type_name": "美漫"},
    {"type_id": "Dm/aimanju", "type_name": "AI漫剧"},
]


# ==================== 正则 ====================
_RE_LI     = re.compile(r'<li\s+data-href="([^"]+)"[^>]*>([\s\S]*?)</li>', re.S | re.I)
_RE_ALT    = re.compile(r'<img[^>]*?\balt="([^"]*)"', re.I)
_RE_SRC    = re.compile(r'<img[^>]*?\b(?:data-src|src)="([^"]*)"', re.I)
_RE_HDTAG  = re.compile(r'<span\s+class="hdtag">([^<]*)</span>', re.I)

_RE_H1    = re.compile(r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC   = re.compile(r'<div class="detail-poster">\s*<img[^>]*?src="([^"]*)"', re.S | re.I)
_RE_DESC  = re.compile(r'<p class="detail-des">([\s\S]*?)</p>', re.S | re.I)
_RE_SCORE = re.compile(r'<span class="detail-rating">[\s\S]*?([\d.]+)\s*分', re.S | re.I)
_RE_LABEL = re.compile(
    r'<span class="detail-label">◎([^：<]+)：</span>\s*<b[^>]*>([\s\S]*?)</b>',
    re.S | re.I)

_RE_PLAY_BLOCK = re.compile(
    r'<div class="card mb-3 play-card"[^>]*>[\s\S]*?<b>([^<]+)</b>[\s\S]*?'
    r'<ul class="episode-list">([\s\S]*?)</ul>',
    re.S | re.I)

_RE_EPISODE = re.compile(
    r'<li[^>]*>\s*<a[^>]*title="([^"]*)"[^>]*href="([^"]+)"[^>]*>([^<]*)</a>',
    re.S | re.I)

_RE_B64_NOW = re.compile(r'var\s+now\s*=\s*base64decode\("([^"]+)"\)', re.I)
_RE_M3U8    = re.compile(r'(https?://[^"\'\\\s<>]+\.m3u8[^"\'\\\s<>]*)', re.I)
_RE_PAGECOUNT = re.compile(r'共\s*(\d+)\s*页')


class Spider(Spider):

    def getName(self):
        return "Auete影视"

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

    def _fix(self, url):
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

    # -------------------- 首页 --------------------
    def homeContent(self, filter=False):
        self.log("homeContent: 返回 %d 个分类" % len(CLASSES))
        return {"class": CLASSES}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html)
        self.log("home: %d 条" % len(videos))
        return {"list": videos}

    # -------------------- 列表页 --------------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_LI.finditer(html):
            href = m.group(1).replace("&amp;", "&")
            block = m.group(2)
            if href in seen:
                continue
            seen.add(href)
            alt_m = _RE_ALT.search(block)
            src_m = _RE_SRC.search(block)
            hd_m  = _RE_HDTAG.search(block)
            name = self._clean(alt_m.group(1)) if alt_m else ""
            pic  = self._fix(src_m.group(1)) if src_m else ""
            hd   = self._clean(hd_m.group(1)) if hd_m else ""
            videos.append({
                "vod_id":      href,
                "vod_name":    name or href.split("/")[-2],
                "vod_pic":     pic or DEFAULT_PIC,
                "vod_remarks": hd,
            })
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page <= 1:
            url = "%s/%s/index.html" % (self.site_url, tid)
        else:
            url = "%s/%s/index%d.html" % (self.site_url, tid, page)

        self.log("category: tid=%s pg=%s url=%s" % (tid, page, url))
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        self.log("  解析到 %d 条" % len(videos))

        pagecount = 9999
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pass

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 20, "total": pagecount * 20,
        }

    # -------------------- 搜索 --------------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/auete4so.php?searchword=%s" % (self.site_url, keyword)
        if page > 1:
            url += "&page=%d" % page
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page, "pagecount": 999,
            "limit": 20, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # -------------------- 详情 --------------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1)).strip("《》")
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])

        pic = DEFAULT_PIC
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix(m.group(1))
        else:
            m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
            if m:
                pic = self._fix(m.group(1))

        # ⭐ 简介 + 前缀
        content = ""
        m = _RE_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        else:
            m = re.search(r'<meta\s+name="Description"\s+content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        director = actor = area = year = ""
        for label, val in _RE_LABEL.findall(html):
            label = label.strip()
            val = self._clean(val)
            if "导演" in label:
                director = val
            elif "主演" in label:
                actor = val
            elif "地区" in label:
                area = val
            elif "年份" in label or "上映" in label:
                year = val

        play_from = []
        play_url = []
        for line_title, block in _RE_PLAY_BLOCK.findall(html):
            line_title = self._clean(line_title)
            m2 = re.search(r'』([^』]+)$', line_title)
            line_name = (m2.group(1) if m2 else line_title).strip()
            eps = []
            for ep_title, ep_href, ep_text in _RE_EPISODE.findall(block):
                ep_name = self._clean(ep_title) or self._clean(ep_text)
                ep_href = ep_href.replace("&amp;", "&")
                if ep_href.startswith("/"):
                    ep_href = self.site_url + ep_href
                if ep_name and ep_href:
                    eps.append((ep_name, ep_href))
            if eps:
                play_from.append(line_name)
                play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        self.log("  lines: %s" % [(f, u.count("#") + 1) for f, u in zip(play_from, play_url)])

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_score": score,
            "vod_remarks": "%d条线路" % len(play_from),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------------------- 播放 --------------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real_url = ""

        if html:
            m = _RE_B64_NOW.search(html)
            if m:
                try:
                    real_url = base64.b64decode(m.group(1)).decode("utf-8", "ignore").strip()
                    self.log("  b64 -> %s" % real_url[:160])
                except Exception as e:
                    self.log("  b64 解码失败: %s" % e)
            if not real_url:
                m2 = _RE_M3U8.search(html)
                if m2:
                    real_url = m2.group(1)
                    self.log("  fallback m3u8 -> %s" % real_url[:160])

        if real_url and ".m3u8" in real_url.lower():
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        self._play_cache[play_page] = (now, res)
        return res

    # -------------------- 图片代理 --------------------
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
            url = self._fix(url)
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
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

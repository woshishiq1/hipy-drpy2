#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JK领域 https://8n78s7s7.jksolsotoday.buzz
"""
import json
import re
import time
from urllib.parse import urljoin, unquote, quote

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.parse as urlparse

SITE = "https://8n78s7s7.jksolsotoday.buzz"
UA = "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
REFERER = SITE + "/gogo/"

# 原站分类保留，便于兼容站点入口。
CATS = {
    "2": "国产视频", "3": "国产主播", "4": "91大神", "5": "热门事件",
    "6": "传媒自拍", "7": "日本有码", "8": "日本无码", "9": "日韩主播",
    "10": "动漫肉番", "11": "女同性恋", "12": "中文字幕", "13": "强奸乱伦",
    "14": "熟女人妻", "15": "制服诱惑", "16": "AV解说", "17": "女星换脸",
    "23": "中文字幕", "35": "国产视频", "57": "日本有码", "58": "欧美精品",
    "423": "中文视频", "424": "麻豆视频", "437": "香蕉视频", "441": "糖心VLOG",
    "444": "欧美精品",
}

# 明确排除未成年人相关关键词，避免把不安全内容纳入返回结果。
UNSAFE_TERMS = ("幼女", "萝莉", "初中", "高中", "未成年", "未满18", "学生妹", "学生娘", "少女", "00后")

class _Resp:
    def __init__(self, text="", content=b"", status=200):
        self.text, self.content, self.status_code = text, content, status

class _Http:
    def __init__(self):
        self.session = requests.Session() if HAS_REQUESTS else None
    def _headers(self, extra=None):
        h = {"User-Agent": UA, "Referer": REFERER, "Accept": "text/html,application/xhtml+xml"}
        if extra: h.update(extra)
        return h
    def get(self, url, headers=None, timeout=15):
        h = self._headers(headers)
        if HAS_REQUESTS:
            r = self.session.get(url, headers=h, timeout=timeout, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
        return _Resp(b.decode("utf-8", "replace"), b)
    def post(self, url, data=None, headers=None, timeout=15):
        h = self._headers(headers)
        if HAS_REQUESTS:
            r = self.session.post(url, data=data or {}, headers=h, timeout=timeout, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r
        body = urlparse.urlencode(data or {}).encode()
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r: b = r.read()
        return _Resp(b.decode("utf-8", "replace"), b)


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", s).strip()

def _abs(u):
    return urljoin(SITE + "/", (u or "").replace("\\/", "/").strip())

def _page_url(tid, page):
    return SITE + "/vodtype/%s-%d/" % (tid, max(1, int(page)))

class Spider:
    name = "JK领域"
    version = "1.1.0"
    def __init__(self):
        self.http = _Http(); self.s = self.http.session; self.session = self.s; self.sess = self.s
        self.extend = ""; self._cache = {}; self._last = 0
    def getDependence(self): return []
    def init(self, extend=""):
        self.extend = extend if isinstance(extend, str) else ""
        self.http = _Http(); self.s = self.http.session; self.session = self.s; self.sess = self.s
    def destroy(self): pass
    def manualVideoCheck(self): return False
    def isVideoFormat(self, url): return ".m3u8" in str(url).lower() or ".mp4" in str(url).lower()
    def getName(self): return self.name

    def _fetch(self, url, retry=2):
        for i in range(retry + 1):
            try:
                r = self.http.get(url, timeout=15)
                if getattr(r, "text", "") and len(r.text) > 200: return r.text
            except Exception: pass
            if i < retry: time.sleep(0.4)
        return ""

    def _parse_cards(self, html, allow_unsafe=False):
        out, seen = [], set()
        # 站点把部分卡片放在 HTML 注释中；按 li/邻近窗口解析，不能只匹配可见文本。
        for m in re.finditer(r'href=["\']([^"\']*?/vodplay/(\d+)-1-(\d+)/?)["\']', html, re.I):
            href, vid, nid = m.groups()
            if vid in seen: continue
            start = max(0, m.start() - 600); end = min(len(html), m.end() + 2600)
            block = html[start:end]
            title = ""
            # 优先取标题链接 title，其次取 class=mo-situ-name 的 title/文本。
            tm = re.search(r'class=["\'][^"\']*mo-situ-name[^"\']*["\'][^>]*title=["\'](.*?)["\']', block, re.I | re.S)
            if not tm:
                tm = re.search(r'class=["\'][^"\']*mo-situ-name[^"\']*["\'][^>]*>(.*?)</a>', block, re.I | re.S)
            if tm: title = _clean(tm.group(1))
            if not title:
                tm = re.search(r'href=["\'][^"\']*?/vodplay/%s-1-1/?["\'][^>]*title=["\'](.*?)["\']' % vid, block, re.I | re.S)
                if tm: title = _clean(tm.group(1))
            if not title:
                # 某些首页卡片只在封面链接 title 属性中给出标题。
                tm = re.search(r'href=["\'][^"\']*?/vodplay/%s-1-1/?["\'][^>]*title=["\'](.*?)["\']' % vid, block, re.I | re.S)
                if tm: title = _clean(tm.group(1))
            if not title: continue
            title = re.sub(r'\s*(?:立即播放|播放)\s*$', '', title).strip()
            if not title: continue
            # 站点存在明显未成年人指向词，默认过滤；不做绕过或收集。
            if not allow_unsafe and any(x in title for x in UNSAFE_TERMS): continue
            seen.add(vid)

            # ==================== 封面获取（修复无封面问题） ====================
            pic = ""
            # 1) 优先懒加载真实图：data-original / data-src
            pm = re.search(r'(?:data-original|data-src)=["\']([^"\']+)', block, re.I)
            if pm:
                pic = _abs(pm.group(1))

            # 2) 回退到标准 <img src="...">，优先匹配图片扩展名
            if not pic:
                pm = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\']*)?)["\']', block, re.I)
                if pm:
                    pic = _abs(pm.group(1))

            # 3) 更宽松的 src / background-image
            if not pic:
                pm = re.search(r'src=["\']([^"\']+)', block, re.I)
                if pm:
                    url = pm.group(1).strip()
                    # 过滤脚本、样式、图标、data URI
                    if not url.endswith(('.js', '.css', '.svg', '.ico')) and not url.startswith('data:'):
                        pic = _abs(url)

            if not pic:
                pm = re.search(r'background-image\s*:\s*url\(["\']?(.*?)["\']?\)', block, re.I)
                if pm:
                    pic = _abs(pm.group(1))
            # ==================== 封面获取结束 ====================

            date = ""
            dm = re.search(r'class=["\'][^"\']*time[^"\']*["\'][^>]*>(.*?)</span>', block, re.I | re.S)
            if dm: date = _clean(dm.group(1))
            out.append({"vod_id": _abs(href), "vod_name": title, "vod_pic": pic,
                        "vod_remarks": date, "vod_year": date[:2] if date else "", "vod_content": ""})
        return out

    def _home_videos(self):
        html = self._fetch(SITE + "/gogo/")
        return self._parse_cards(html)[:60]
    def homeContent(self, filter=None):
        classes = [{"type_id": k, "type_name": v} for k, v in CATS.items()]
        return {"class": classes, "filters": {}, "list": self._home_videos()}
    def homeVideoContent(self): return {"list": self._home_videos()}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try: page = max(1, int(str(pg)))
        except Exception: page = 1
        html = self._fetch(_page_url(str(tid), page))
        items = self._parse_cards(html)
        pm = re.search(r'/vodtype/%s-(\d+)/[^"\']*["\'][^>]*>尾页' % re.escape(str(tid)), html, re.I)
        if not pm: pm = re.search(r'/vodtype/%s-(\d+)/' % re.escape(str(tid)), html)
        try: pagecount = int(pm.group(1)) if pm else page
        except Exception: pagecount = page
        return {"list": items, "page": page, "pagecount": pagecount, "limit": 30, "total": pagecount * 30}

    def _norm_id(self, ids):
        if isinstance(ids, (list, tuple)): ids = ids[0] if ids else ""
        s = unquote(str(ids)).strip().strip('"\'')
        if s.startswith("["):
            try: return self._norm_id(json.loads(s))
            except Exception: pass
        m = re.search(r'/vodplay/(\d+-\d+-\d+)', s)
        if m: return SITE + "/vodplay/" + m.group(1) + "/"
        m = re.search(r'(\d+)', s)
        return SITE + "/vodplay/" + m.group(1) + "-1-1/" if m else s

    def detailContent(self, ids):
        url = self._norm_id(ids); html = self._fetch(url)
        title = ""; pic = ""; content = ""
        tm = re.search(r'<span[^>]*class=["\'][^"\']*(?:mo-pnxs|wrap-arow)[^"\']*["\'][^>]*>(.*?)</span>', html, re.I | re.S)
        if tm: title = _clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>(.*?)</title>', html, re.I | re.S); title = _clean(tm.group(1)) if tm else ""
            title = re.split(r'详情介绍|在线观看|迅雷下载', title)[0].strip(" -")

        # ==================== 详情封面获取（同步增强） ====================
        # 1) 懒加载
        pm = re.search(r'(?:data-original|data-src)=["\']([^"\']+)', html, re.I)
        if pm:
            pic = _abs(pm.group(1))
        # 2) 标准 img src（优先图片格式）
        if not pic:
            pm = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\']*)?)["\']', html, re.I)
            if pm:
                pic = _abs(pm.group(1))
        # 3) 更宽松回退
        if not pic:
            pm = re.search(r'<img[^>]+src=["\']([^"\']+)', html, re.I)
            if pm:
                url = pm.group(1).strip()
                if not url.endswith(('.js', '.css', '.svg', '.ico')) and not url.startswith('data:'):
                    pic = _abs(url)
        # ==================== 详情封面结束 ====================

        dm = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S)
        if dm: content = _clean(dm.group(1))
        vod = {"vod_id": url, "vod_name": title, "vod_pic": pic, "type_name": "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": content, "vod_remarks": "",
               "vod_play_from": "乐播云", "vod_play_url": "正片$" + url}
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        # MacCMS 搜索表单是 POST；搜索分页路径由页面返回的分页链接决定。
        try: page = max(1, int(str(pg)))
        except Exception: page = 1
        path = "/vodsearch/-------------/"
        r = self.http.post(SITE + path, {"wd": str(key)}, timeout=15)
        items = self._parse_cards(getattr(r, "text", ""))
        # 页面通常将真实分页链接写成 /vodsearch/关键词-页码/ 或内部编码；
        # 无法确认时不伪造页码，第一页结果仍可靠返回。
        return {"list": items, "page": page, "pagecount": 1}

    def _play_url(self, url):
        html = self._fetch(url)
        m = re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>', html, re.I | re.S)
        if not m: m = re.search(r'player_data\s*=\s*(\{.*?\})', html, re.I | re.S)
        if not m: return ""
        try:
            d = json.loads(m.group(1).replace('\\/', '/'))
            u = d.get("url", "")
            return _abs(u) if u else ""
        except Exception: return ""
    def playerContent(self, flag, ids, vipFlags=None):
        try:
            u = str(ids)
            if not re.search(r'\.m3u8(?:\?|$)', u, re.I): u = self._play_url(self._norm_id(ids))
            return {"parse": 0, "url": u, "header": {"User-Agent": UA, "Referer": REFERER},
                    "format": "application/x-mpegURL"}
        except Exception:
            return {"parse": 0, "url": "", "header": {"User-Agent": UA, "Referer": REFERER}}

    def localProxy(self, param):
        try:
            if isinstance(param, str): param = json.loads(param)
            url = param.get("url", "") if isinstance(param, dict) else str(param)
            r = self.http.get(url, timeout=20)
            body = getattr(r, "content", b"")
            if not body and getattr(r, "text", ""): body = r.text.encode()
            low = url.lower()
            mime = "application/vnd.apple.mpegurl" if ".m3u8" in low else ("video/mp2t" if ".ts" in low else "application/octet-stream")
            if mime.startswith("application/vnd"):
                text = body.decode("utf-8", "replace")
                text = re.sub(r'(?m)^(/[^#\s][^\r\n]*)', lambda m: urljoin(url, m.group(1)), text)
                body = text.encode()
            return [200, mime, body, {"User-Agent": UA, "Referer": REFERER}]
        except Exception as e:
            return [500, "text/plain", str(e).encode(), {}]
    def action(self, action): return json.dumps({"code": 0, "msg": "ok"}, ensure_ascii=False)

if __name__ == "__main__":
    s = Spider(); s.init("")
    print(s.homeContent(False))

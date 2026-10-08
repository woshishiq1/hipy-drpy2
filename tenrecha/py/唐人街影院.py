# -*- coding: utf-8 -*-
# TVBox 播放源：唐人街影院（www.trvod.com / www.trjvod.com）
# 站点类型：苹果CMS V10（海螺模板）
# 接口：homeContent / homeVideoContent / categoryContent / detailContent / searchContent / playerContent
# 播放链路：详情页 -> 播放页 player_aaaa JSON 内 url 字段（百分号编码）-> unquote 得 m3u8 直链
# 依赖：优先 requests；环境无 requests 时自动降级 urllib 标准库，无第三方依赖
# 兼容：有 base.spider 基类的 TVBox（qiusunshine 系）自动继承；无基类环境独立运行
# 备注：主域 www.trvod.com 在中国大陆网络被 DNS 污染/SNI 阻断，默认优先走同站镜像 www.trjvod.com；
#       镜像或主域任一可用即可，init 的 extend 可传 host=xxx 或 JSON {"host":"xxx"} 覆盖域名

import re
import json
import sys

try:
    sys.path.append('..')
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = object

try:
    import requests
except Exception:
    requests = None

from urllib.parse import unquote, quote

# 首选可用镜像，主域做回退（顺序即请求顺序）
HOSTS = ["www.trjvod.com", "www.trvod.com"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
TIMEOUT = 10


class Spider(_BaseSpider):
    def __init__(self):
        self.hosts = list(HOSTS)
        self.host = self.hosts[0]
        self.ref = ""
        self.cache = {}
        self.session = requests.Session() if requests is not None else None
        if self.session is not None:
            self.session.headers.update({
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })

    # ---------- 可选能力（部分 TVBox 会调用）----------

    def getName(self):
        return "唐人街影院"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return bool(url) and not url.startswith("http")

    def manualVideoCheck(self):
        pass

    # ---------- 内部工具 ----------

    def _url(self, path):
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return "https://%s%s" % (self.host, path)

    def _abs(self, s):
        """把相对/协议相对地址补成完整 https 地址。"""
        s = (s or "").strip()
        if not s:
            return ""
        if s.startswith("//"):
            return "https:" + s
        if s.startswith("/"):
            return "https://%s%s" % (self.host, s)
        if s.startswith("http"):
            return s
        return "https://%s/%s" % (self.host, s)

    def _http_get(self, url, timeout):
        """GET 并返回文本；失败抛异常。requests 可用时优先，否则 urllib 兜底。"""
        if self.session is not None:
            r = self.session.get(url, timeout=timeout)
            if not r.ok:
                raise RuntimeError("HTTP %s for %s" % (r.status_code, url))
            try:
                r.encoding = "utf-8"
            except Exception:
                pass
            return r.text
        import ssl
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as resp:
            data = resp.read()
            enc = resp.headers.get_content_charset() or "utf-8"
            try:
                return data.decode(enc)
            except Exception:
                return data.decode("utf-8", "ignore")

    def _get(self, path, timeout=TIMEOUT):
        """按 hosts 顺序带域名回退的 GET。返回 (最终URL, 正文)。"""
        last = None
        for h in self.hosts:
            url = self._abs_url_on(h, path)
            try:
                text = self._http_get(url, timeout)
                self.host = h
                return url, text
            except Exception as e:
                last = e
        raise (last if last else RuntimeError("all hosts failed"))

    def _abs_url_on(self, h, path):
        """把 path（相对或已带域名）重写到指定域名 h 上。"""
        if path.startswith("http"):
            for b in self.hosts:
                if b in path:
                    path = path.replace(b, h)
                    break
            return path
        if not path.startswith("/"):
            path = "/" + path
        return "https://%s%s" % (h, path)

    @staticmethod
    def _clean(s):
        return re.sub(r"\s+", " ", s or "").strip()

    @staticmethod
    def _extract_js_object(text, start):
        """从 start 位置的 '{' 起做括号配对，返回完整 JS 对象字面量字符串。"""
        brace = text.find("{", start)
        if brace == -1:
            return None
        depth = 0
        in_str = False
        esc = False
        for k in range(brace, len(text)):
            c = text[k]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return text[brace:k + 1]
        return None

    @staticmethod
    def _unquote_url(s):
        s = (s or "").strip()
        if s.startswith("%"):
            try:
                return unquote(s)
            except Exception:
                return s
        return s

    # ---------- 分类 ----------

    def _build_class(self):
        """固定分类树（来自站点导航实测）。父类为聚合页，子类为分页列表。"""
        items = [
            ("1", "电影"), ("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"),
            ("9", "科幻片"), ("10", "恐怖片"),
            ("2", "连续剧"), ("13", "国产剧"), ("14", "港台剧"),
            ("15", "日韩剧"), ("16", "欧美剧"), ("31", "海外剧"),
            ("3", "综艺"), ("4", "动漫"), ("53", "短剧"), ("59", "体育"),
        ]
        return [{"type_id": tid, "type_name": name} for tid, name in items]

    # ---------- 列表解析 ----------

    def _parse_list(self, html):
        """解析列表卡片：li.vodlist_item > a.vodlist_thumb（含 balist_thumb 兼容）。"""
        out = []
        seen = set()
        for m in re.finditer(
            r'<a[^>]*class="[^"]*vodlist_thumb[^"]*"[^>]*>.*?</a>', html, re.S):
            a = m.group(0)
            href = re.search(r'href="([^"]*)"', a)
            title = re.search(r'title="([^"]*)"', a)
            pic = re.search(r'data-original="([^"]*)"', a) or re.search(r'data-background="([^"]*)"', a)
            if not href or not title:
                continue
            vid = re.search(r'vod/detail/id/(\d+).html', href.group(1))
            if not vid:
                continue
            key = vid.group(1)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "vod_id": key,
                "vod_name": title.group(1),
                "vod_pic": self._abs(pic.group(1)) if pic else "",
                "vod_remarks": "",
            })
        if not out:
            for m in re.finditer(
                r'<a[^>]*class="[^"]*balist_thumb[^"]*"[^>]*title="([^"]*)"[^>]*href="([^"]*)"[^>]*data-background="([^"]*)"',
                html):
                vid = re.search(r'vod/detail/id/(\d+).html', m.group(2))
                if not vid:
                    continue
                key = vid.group(1)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "vod_id": key,
                    "vod_name": m.group(1),
                    "vod_pic": self._abs(m.group(3)),
                    "vod_remarks": "",
                })
        return out

    @staticmethod
    def _last_page(html):
        """从 ul.page 拿到最大页码；无分页返回 1。"""
        pages = []
        for m in re.finditer(r'/page/(\d+)\.html', html):
            pages.append(int(m.group(1)))
        if not pages:
            return 1
        return max(pages)

    # ---------- 标准接口 ----------

    def init(self, extend=""):
        """extend 支持 host=xxx 或 JSON {"host":"xxx"} 覆盖默认域名。"""
        if not extend:
            return
        host = None
        s = extend.strip()
        if s.startswith("{"):
            try:
                host = (json.loads(s) or {}).get("host")
            except Exception:
                host = None
        if not host:
            m = re.search(r"(?:host|url)\s*[=:]\s*([^\s\"']+)", extend)
            if m:
                host = m.group(1).strip()
        if host:
            host = str(host).replace("https://", "").replace("http://", "").rstrip("/")
            if host:
                self.hosts = [host] + [h for h in HOSTS if h != host]
                self.host = host

    def homeContent(self, filter=False):
        return {
            "class": self._build_class(),
            "list": [],
            "filters": {},
        }

    def homeVideoContent(self):
        try:
            _, html = self._get("/")
        except Exception:
            return {"list": []}
        lst = self._parse_list(html)
        return {"list": lst[:80]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        if not isinstance(pg, int):
            try:
                pg = int(pg or 1)
            except Exception:
                pg = 1
        if pg < 1:
            pg = 1
        path = "/index.php/vod/type/id/%s/page/%s.html" % (tid, pg)
        try:
            _, html = self._get(path)
        except Exception:
            return {"page": pg, "pagecount": 1, "limit": 36, "total": 0, "list": []}
        lst = self._parse_list(html)
        total_page = self._last_page(html)
        total = len(lst) if total_page == 1 else total_page * 36
        return {"page": pg, "pagecount": total_page, "limit": 36, "total": total, "list": lst}

    def detailContent(self, ids):
        # ids 可能是数字 id 或详情页 URL 或列表
        if isinstance(ids, list):
            ids = ids[0] if ids else ""
        m = re.search(r"(\d+)", str(ids))
        if not m:
            return {"list": []}
        vid = m.group(1)
        try:
            _, html = self._get("/index.php/vod/detail/id/%s.html" % vid)
        except Exception:
            return {"list": []}

        # ---- 标题 ----
        name = ""
        mh = re.search(r'<h2 class="title">([^<]+)</h2>', html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mo = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            if mo:
                name = self._clean(mo.group(1))

        # ---- 封面 ----
        pic = ""
        mp = re.search(r'<meta property="og:image" content="([^"]*)"', html)
        if mp:
            pic = self._abs(mp.group(1))
        if not pic:
            mm = re.search(r'data-original="([^"]+)"', html)
            if mm:
                pic = self._abs(mm.group(1))

        # ---- 简介 ----
        content = ""
        md = re.search(r'class="content_desc[^"]*"[^>]*>(.*?)</(?:div|span)>', html, re.S)
        if md:
            content = self._clean(re.sub(r"<[^>]+>", "", md.group(1)))
        if not content:
            md = re.search(r'<span class="text_detail[^"]*"[^>]*>(.*?)</span>', html, re.S)
            if md:
                content = self._clean(re.sub(r"<[^>]+>", "", md.group(1)))
        if not content:
            md = re.search(r'<meta name="description" content="([^"]*)"', html)
            if md:
                content = self._clean(md.group(1))

        # ---- 线路名（#NumTab a[alt]）----
        sources = [self._clean(x) for x in re.findall(r'<a[^>]*alt="([^"]+)"', html)]
        if not sources:
            sources = [self._clean(x) for x in re.findall(r'<a[^>]*class="wo"[^>]*>\s*<i[^>]*></i>\s*([^<]+)', html)]
        sources = [s for s in sources if s]

        # ---- 选集（play_list_box 按线路分块，块与线路名按序对应）----
        blocks = re.findall(
            r'<div class="play_list_box[^"]*"[^>]*>(.*?)(?=<div class="play_list_box|$)', html, re.S)
        play_from = []
        play_url = []
        if not blocks:
            # 兜底：全页所有 vod/play 链接按线路聚合
            links = re.findall(
                r'href="(/index.php/vod/play/id/\d+/sid/(\d+)/nid/\d+\.html)"[^>]*>([^<]+)<', html)
            grouped = {}
            for href, sid, ep in links:
                grouped.setdefault(sid, []).append((self._clean(ep), href))
            play_from = sources or list(grouped.keys())
            for sid in grouped:
                eps = list(grouped[sid])
                play_url.append("#".join("%s$%s" % (ep, self._url(href)) for ep, href in eps))
        else:
            for i, blk in enumerate(blocks):
                src_name = sources[i] if i < len(sources) else "线路%d" % (i + 1)
                eps = []
                seen_ep = set()
                for href, ep in re.findall(r'href="(/index.php/vod/play/[^"]+)"[^>]*>([^<]+)<', blk):
                    ep = self._clean(ep)
                    if not ep or ep in seen_ep:
                        continue
                    seen_ep.add(ep)
                    eps.append("%s$%s" % (ep, self._url(href)))
                if eps:
                    play_from.append(src_name)
                    play_url.append("#".join(eps))

        if not play_url:
            return {"list": []}
        vod = {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg=1):
        try:
            path = "/index.php/vod/search.html?wd=%s" % quote(str(key))
            _, html = self._get(path)
        except Exception:
            return {"list": []}
        lst = self._parse_list(html)
        return {"list": lst}

    def playerContent(self, flag, ids, vipFlags=""):
        # ids 为播放页 URL（如 .../vod/play/id/xxx/sid/1/nid/1.html）
        url = self._url(str(ids))
        try:
            _, html = self._get(url)
        except Exception:
            return {}
        # player_aaaa = {...} JSON：用括号配对截取完整对象（JS 内可含 ; 需精确配对）
        m = re.search(r'player_aaaa\s*=\s*(\{)', html)
        data = None
        if m:
            obj = self._extract_js_object(html, m.start(1))
            if obj:
                try:
                    data = json.loads(obj)
                except Exception:
                    data = None
        if not data:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', html)
            if m2:
                return {"parse": 1, "playUrl": self._unquote_url(m2.group(1)),
                        "header": "Referer: %s" % url}
            return {}
        raw = data.get("url") or ""
        play = self._unquote_url(raw)
        if play.startswith("//"):
            play = "https:" + play
        if play.startswith("http"):
            return {"parse": 0, "playUrl": play, "header": "Referer: %s" % url}
        # url 为空或非直链时把播放页交给播放器嗅探
        if "/vod/play/" in url:
            return {"parse": 1, "playUrl": url, "header": "Referer: %s" % url}
        return {}

    def destroy(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
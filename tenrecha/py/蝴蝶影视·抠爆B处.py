import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
from urllib.parse import quote, urljoin, unquote, urlparse, parse_qs
import posixpath
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"


class Spider(SpiderBase):
    NEED_CLEAN = True

    def __init__(self):
        super(Spider, self).__init__()
        self.defaultDomains = [
            "https://t3g15u7s.kbbshape.buzz",
            "https://kbbshape.buzz"
        ]
        self.siteUrl = self.defaultDomains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self._init_opener()

        self.classes = [
            {"type_id": "1", "type_name": "百万资源"},
            {"type_id": "18", "type_name": "大地资源"},
            {"type_id": "61", "type_name": "森林资源"},
            {"type_id": "132", "type_name": "杏吧资源"},
            {"type_id": "268", "type_name": "奶香香资源"},
            {"type_id": "296", "type_name": "奥斯卡资源"},
            {"type_id": "382", "type_name": "黄色仓库"},
            {"type_id": "423", "type_name": "麻豆资源"}
        ]
        self.filters = {}

    def _init_opener(self, proxy_url=None):
        handlers = [
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        ]
        if proxy_url:
            handlers.append(urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url
            }))
        self.opener = urllib.request.build_opener(*handlers)

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        if self.options.get("proxy"):
            self._init_opener(self.options.get("proxy"))

        cached_domain = self.getCache("spider_active_domain_kbb")
        if cached_domain and str(cached_domain).startswith("http"):
            self.siteUrl = str(cached_domain).strip().rstrip("/")
        else:
            self._check_drift_domain()
        return True

    def getName(self):
        return "蝴蝶影视·抠爆B处"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    def _check_drift_domain(self):
        cand_domains = []
        custom_domain = self.options.get("domain") or self.options.get("host")
        if custom_domain:
            if not str(custom_domain).startswith("http"):
                custom_domain = "https://" + str(custom_domain).strip()
            cand_domains.append(str(custom_domain).rstrip("/"))
        for d in self.defaultDomains:
            if d not in cand_domains:
                cand_domains.append(d)

        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        for domain in cand_domains:
            try:
                req = urllib.request.Request(domain, headers=headers)
                with self.opener.open(req, timeout=4) as resp:
                    if resp.getcode() == 200:
                        self.siteUrl = domain
                        self.setCache("spider_active_domain_kbb", domain)
                        return
            except Exception:
                continue

    def _fetch(self, target_url, referer="", timeout=12):
        if not target_url:
            return {"code": 0, "text": "", "raw": b""}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close"
        }

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=timeout) as resp:
                    code = resp.getcode()
                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "raw": raw}
            except Exception:
                if attempt == 0:
                    self._check_drift_domain()
                    if target_url.startswith("http"):
                        p = urllib.parse.urlparse(target_url)
                        target_url = self.siteUrl + p.path + ("?" + p.query if p.query else "")
                else:
                    return {"code": -1, "text": "", "raw": b""}
        return {"code": -1, "text": "", "raw": b""}

    @staticmethod
    def _clean(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return s.strip()

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def _parse_list(self, html):
        items = []
        if not html:
            return items

        blocks = re.findall(
            r'<div class="item">\s*<a[^>]+href="/voddetail/(\d+)/"[^>]*>(.*?)</a>',
            html, re.S)
        if not blocks:
            blocks = re.findall(
                r'<a[^>]+href="/voddetail/(\d+)/"[^>]*>(.*?)</a>', html, re.S)

        for vid, b in blocks:
            m_t = re.search(r'<strong class="title"[^>]*>(.*?)</strong>', b, re.S)
            name = self._clean(m_t.group(1)) if m_t else ""
            if not name:
                m_at = re.search(r'title="([^"]*)"', b)
                if m_at:
                    name = self._clean(m_at.group(1))
            if not name:
                m_img = re.search(r'<img[^>]+alt="([^"]*)"', b)
                if m_img:
                    name = self._clean(m_img.group(1))
            if not name:
                name = vid

            m_p = re.search(r'<img[^>]+class="thumb[^"]*"[^>]+src="([^"]+)"', b)
            if not m_p:
                m_p = re.search(r'<img[^>]+src="([^"]+)"', b)
            pic = m_p.group(1) if m_p else ""
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = urljoin(self.siteUrl + "/", pic)

            m_r = re.search(r'<div class="duration">([^<]+)</div>', b)
            remark = m_r.group(1).strip() if m_r else ""
            if not remark:
                m_hd = re.search(r'<span class="is-hd">([^<]+)</span>', b)
                if m_hd:
                    remark = m_hd.group(1).strip()

            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic if pic else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=No+Pic",
                "vod_remarks": remark or "超清",
                "style": {"type": "rect", "ratio": 0.75}
            })
        return items

    def homeVideoContent(self):
        res = self._fetch(self.siteUrl + "/gao/")
        html = res.get("text", "")
        if not html or len(html) < 500:
            res = self._fetch(self.siteUrl + "/")
            html = res.get("text", "")
        return {"list": self._parse_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        page = str(pg or "1")
        if page == "1":
            url = f"{self.siteUrl}/vodtype/{tid}/"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}/"

        res = self._fetch(url)
        html = res.get("text", "")
        items = self._parse_list(html)

        pagecount = page
        nums = re.findall(r'/vodtype/%s-(\d+)/' % re.escape(str(tid)), html)
        if not nums:
            nums = re.findall(r'/vodtype/%s/(\d+)/' % re.escape(str(tid)), html)
        if nums:
            pagecount = max(int(n) for n in nums)
        else:
            m_pg = re.search(r'共\s*(\d+)\s*页', html)
            if m_pg:
                pagecount = int(m_pg.group(1))

        return {
            "list": items,
            "page": int(page),
            "pagecount": int(pagecount) if str(pagecount).isdigit() else 1,
            "limit": 20,
            "total": 9999
        }

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0].split("$")[0].split("@@")[0].strip()
        play_id = f"{vid}-1-1"

        title, pic, content, remark = "", "", "", ""
        try:
            res = self._fetch(f"{self.siteUrl}/voddetail/{vid}/")
            html = res.get("text", "")
            if html and len(html) > 500:
                m = re.search(r'<div class="headline">\s*<h1[^>]*>(.*?)</h1>', html, re.S)
                if not m:
                    m = re.search(r'<h1(?![^>]*class="htitle")[^>]*>(.*?)</h1>', html, re.S)
                if m:
                    title = self._clean(m.group(1))
                else:
                    m = re.search(r'<title>(.*?)</title>', html, re.S)
                    if m:
                        title = self._clean(m.group(1)).split("-")[0].split("详情")[0].strip()

                m = re.search(r'<div class="img-wrap">\s*<img[^>]+src="([^"]+)"', html, re.S)
                if not m:
                    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if m:
                    pic = m.group(1)
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    elif pic and not pic.startswith("http"):
                        pic = urljoin(self.siteUrl + "/", pic)

                m = re.search(r'描述:\s*<em>(.*?)</em>', html, re.S)
                if m:
                    content = self._clean(m.group(1))
                m = re.search(r'<div class="duration">([^<]+)</div>', html)
                if m:
                    remark = m.group(1).strip()
                if not remark:
                    m = re.search(r'类别:\s*<a[^>]*>([^<]+)</a>', html)
                    if m:
                        remark = m.group(1).strip()
        except Exception:
            pass

        if not title:
            title = "精彩视频 " + vid

        desc_lines = [
            "【🔥 官方交流群: %s】" % self.tgGroup,
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "• 影片名称: %s" % title,
            "• 当前活跃节点: %s" % self.siteUrl,
            "• 播放模式: 广告动态清洗 + 零嗅探极速秒播",
            "• 剧情简介: %s" % (content or "暂无详细描述")
        ]
        escaped_desc = "\n".join(desc_lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": pic,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": remark or "超清直链",
            "vod_content": escaped_desc,
            "vod_play_from": "🦋蝴蝶极速专线",
            "vod_play_url": "正片$" + play_id
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        try:
            k = quote(str(key or "").strip())
        except Exception:
            k = str(key or "")
        url = f"{self.siteUrl}/vodsearch/{k}-------------.html"
        res = self._fetch(url)
        html = res.get("text", "")
        return {"list": self._parse_list(html), "page": int(pg or 1), "pagecount": 1, "limit": 20, "total": 20}

    @staticmethod
    def _norm_url(u):
        if not u:
            return ""
        u = u.replace("\\/", "/").replace("\\u002f", "/").replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        return u.strip()

    def _extract_player_url(self, html):
        if not html:
            return ""
        m = re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_data\s*=\s*(\{.*\})', html, re.S)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                u = data.get("url", "")
                if u:
                    return self._norm_url(u)
            except Exception:
                try:
                    loose = raw.replace("\\/", "/")
                    data = json.loads(loose)
                    u = data.get("url", "")
                    if u:
                        return self._norm_url(u)
                except Exception:
                    pass
            mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if mu:
                return self._norm_url(mu.group(1))

        mu = re.search(r'(https?:\\?/\\?/[^"\'\s]+\.m3u8[^"\'\s]*)', html)
        if mu:
            return self._norm_url(mu.group(1))
        return ""

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        play_url = play_url.strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        if play_url.startswith("http") and ".m3u8" in play_url.lower():
            return self._play_response(play_url)

        pid = play_url
        if not re.match(r"^\d+-\d+-\d+$", pid):
            pid = f"{play_url}-1-1"

        res = self._fetch(f"{self.siteUrl}/vodplay/{pid}/")
        real = self._extract_player_url(res.get("text", ""))
        if real:
            return self._play_response(real)

        return {
            "parse": 1,
            "url": f"{self.siteUrl}/vodplay/{pid}/",
            "header": {"User-Agent": self._ua, "Referer": self.siteUrl + "/"}
        }

    def _play_response(self, m3u8_url):
        header = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl
        }
        if self.NEED_CLEAN:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(m3u8_url),
                "header": header
            }
        return {
            "parse": 0,
            "url": m3u8_url,
            "header": header
        }

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = parse_qs(urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self._fetch(target, referer=self.siteUrl + "/", timeout=15)
            content = res.get("raw", b"")
            if not content:
                return [502, "text/plain", b"fetch failed"]

            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: " + type(e).__name__).encode("utf-8")]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        is_img = self._is_fake_image_stream(text)

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        main_dir = self._resolve_main_dir(lines, source_url, is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if removed > 0 and (kept == 0 or removed > kept):
            out = [self._rewrite_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    @staticmethod
    def _is_fake_image_stream(text):
        IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VID = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_img = has_vid = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("?")[0].split("#")[0].lower()
            if p.endswith(VID):
                has_vid = True
            elif p.endswith(IMG):
                has_img = True
        return has_img and not has_vid

    def _resolve_main_dir(self, lines, source_url, is_img):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        counter = {}
        for line in lines:
            if not line or line.startswith("#"):
                continue
            p = urlparse(urljoin(source_url, line)).path
            d = posixpath.dirname(p)
            if d and d != "/":
                counter[d + "/"] = counter.get(d + "/", 0) + 1
        if counter:
            top_dir, top_n = max(counter.items(), key=lambda kv: kv[1])
            total = sum(counter.values())
            if total > 0 and top_n / total >= 0.5:
                return top_dir

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            ku = m.group(1)
            kp = urlparse(ku if ku.startswith("http") else urljoin(source_url, ku)).path
            kd = posixpath.dirname(kp)
            if kd and kd != "/":
                return kd + "/"
        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
        segments = []
        pending = []
        removed = kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                mp = urlparse(media).path
                if mp.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urljoin(source_url, line))
        return segments, removed, kept

    def _rewrite_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def action(self, action):
        return {"msg": "🦋 蝴蝶影视·抠爆B处运行正常"}

    def liveContent(self):
        return ""

    def destroy(self):
        self.options = {}
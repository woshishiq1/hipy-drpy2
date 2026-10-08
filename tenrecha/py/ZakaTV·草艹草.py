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
            "https://mqxppthlr.ccctv01.top",
            "https://26091309.ccctv1.top",
            "https://ccctv1.top"
        ]
        self.siteUrl = self.defaultDomains[0]
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self._init_opener()

        self.classes = [
            {"type_id": "21", "type_name": "视频②区"},
            {"type_id": "40", "type_name": "国产视频"},
            {"type_id": "41", "type_name": "中文字幕"},
            {"type_id": "42", "type_name": "国产传媒"},
            {"type_id": "43", "type_name": "日本有码"},
            {"type_id": "44", "type_name": "日本无码"},
            {"type_id": "45", "type_name": "欧美无码"},
            {"type_id": "46", "type_name": "美女主播"},
            {"type_id": "47", "type_name": "激情动漫"},
            {"type_id": "48", "type_name": "明星换脸"},
            {"type_id": "50", "type_name": "女优明星"},
            {"type_id": "51", "type_name": "SM调教"},
            {"type_id": "52", "type_name": "网红头条"},
            {"type_id": "53", "type_name": "极品媚黑"},
            {"type_id": "54", "type_name": "人妖系列"},
            {"type_id": "55", "type_name": "VR视角"},
            {"type_id": "56", "type_name": "伦理三级"},
            {"type_id": "57", "type_name": "女同性恋"},
            {"type_id": "58", "type_name": "AV解说"},
            {"type_id": "59", "type_name": "清纯素女"}
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

        cached_domain = self.getCache("spider_active_domain_ccc")
        if cached_domain and str(cached_domain).startswith("http"):
            self.siteUrl = str(cached_domain).strip().rstrip("/")
        else:
            self._check_drift_domain()
        return True

    def getName(self):
        return "ZakaTV·草艹草"

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
                        self.setCache("spider_active_domain_ccc", domain)
                        return
            except Exception:
                continue

    def _decode_html(self, src):
        if not src:
            return ""
        m = re.search(r'atob\("([^"]+)"\)', src)
        if not m:
            return src
        try:
            step1 = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            try:
                data = json.loads(step1)
                return bytes(data).decode("utf-8", errors="ignore")
            except Exception:
                return step1
        except Exception:
            return src

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
                    text = self._decode_html(text)
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

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def _parse_list(self, html):
        items = []
        seen = set()
        blocks = re.findall(r'<li>(.*?)</li>', html, re.S)
        for b in blocks:
            m = re.search(r'/voddetail/(\d+)\.html', b)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            t = re.search(r'<h5>\s*<a[^>]*>(.*?)</a>', b, re.S)
            name = ""
            if t:
                name = re.sub(r'<[^>]+>', '', t.group(1)).strip()
            if not name:
                t2 = re.search(r'<img[^>]*alt="([^"]*)"', b)
                name = (t2.group(1) if t2 else "").strip()

            p = re.search(r'data-src="([^"]+)"', b) or re.search(r'<img[^>]*src="([^"]+)"', b)
            pic = (p.group(1) if p else "").strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = urljoin(self.siteUrl + "/", pic)

            items.append({
                "vod_id": vid,
                "vod_name": name or ("视频" + vid),
                "vod_pic": pic if pic else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=No+Pic",
                "vod_remarks": "超清",
                "style": {"type": "rect", "ratio": 0.75}
            })
        return items

    def homeVideoContent(self):
        res = self._fetch(self.siteUrl + "/")
        return {"list": self._parse_list(res.get("text", ""))}

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        page = int(pg or 1) if str(pg).isdigit() else 1
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"

        res = self._fetch(url)
        items = self._parse_list(res.get("text", ""))
        return {
            "list": items,
            "page": page,
            "pagecount": 9999,
            "limit": 20,
            "total": 999999
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
        url = f"{self.siteUrl}/voddetail/{vid}.html"
        res = self._fetch(url)
        html = res.get("text", "")

        name = ""
        m = re.search(r'<div class="breadcrumbs">(.*?)</div>', html, re.S)
        if m:
            spans = re.findall(r'<span[^>]*>(.*?)</span>', m.group(1), re.S)
            if spans:
                name = re.sub(r'<[^>]+>', '', spans[-1]).strip()
        if not name:
            m = re.search(r'<div class="detail-poster">.*?<img[^>]*alt="([^"]+)"', html, re.S)
            if m:
                name = m.group(1).strip()
        if not name:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                t = re.sub(r'[-|_]\s*草[艹艸]草.*$', '', t).strip()
                name = t

        pic = ""
        for pp in [r'<div class="detail-poster">.*?<img src="([^"]+)"',
                   r'<img[^>]*src="([^"]+)"[^>]*alt=']:
            m = re.search(pp, html, re.S)
            if m:
                pic = m.group(1).strip()
                break
        if pic.startswith("//"):
            pic = "https:" + pic
        elif pic and not pic.startswith("http"):
            pic = urljoin(self.siteUrl + "/", pic)

        content = ""
        m = re.search(r'(?:简介|剧情)[:：]?\s*</?[^>]*>(.*?)</', html, re.S)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        play_page = f"{self.siteUrl}/vodplay/{vid}-1-1.html"
        m = re.search(r'href="(/vodplay/[^"]+)"', html)
        if m:
            play_page = urljoin(self.siteUrl, m.group(1))

        desc_lines = [
            "【🔥 官方交流群: %s】" % self.tgGroup,
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "• 影片名称: %s" % (name or vid),
            "• 当前活跃节点: %s" % self.siteUrl,
            "• 播放模式: 广告动态清洗 + 零嗅探极速秒播",
            "• 剧情简介: %s" % (content or "暂无详细描述")
        ]
        escaped_desc = "\n".join(desc_lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        vod = {
            "vod_id": raw,
            "vod_name": name or ("视频" + vid),
            "vod_pic": pic,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": "超清直链",
            "vod_content": escaped_desc,
            "vod_play_from": "📺Zaka极速专线",
            "vod_play_url": "正片$" + play_page
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1) if str(pg).isdigit() else 1
        kw = quote(str(key or "").strip())
        if page <= 1:
            url = f"{self.siteUrl}/vod/search.html?wd={kw}"
        else:
            url = f"{self.siteUrl}/vod/search/{kw}----------{page}---.html"
        res = self._fetch(url)
        items = self._parse_list(res.get("text", ""))
        return {"list": items, "page": page, "pagecount": 1, "limit": 20, "total": 20}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def _extract_play_url(self, play_page):
        res = self._fetch(play_page)
        html = res.get("text", "")
        if not html:
            return ""
        m = re.search(r'data-user-name=["\']([^"\']+)"', html)
        if not m:
            m2 = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html)
            return m2.group(1) if m2 else ""
        val = m.group(1)
        if "$" in val:
            val = val.split("$", 1)[1]
        return val.strip()

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        play_url = play_url.strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        if play_url.startswith("http") and (".m3u8" in play_url or ".mp4" in play_url):
            return self._play_response(play_url)

        real = self._extract_play_url(play_url)
        if real:
            if real.startswith("//"):
                real = "https:" + real
            return self._play_response(real)

        return {
            "parse": 1,
            "url": play_url,
            "header": {"User-Agent": self._ua, "Referer": self.siteUrl + "/"}
        }

    def _play_response(self, m3u8_url):
        header = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl
        }
        if self.NEED_CLEAN and ".m3u8" in m3u8_url.lower():
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

    def _is_fake_image_stream(self, text):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_v = has_i = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_v = True
            elif path.endswith(IMAGE_EXT):
                has_i = True
        return has_i and not has_v

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
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

        if not is_image_stream:
            for line in lines:
                if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                    continue
                m = re.search(r'URI="([^"]+)"', line)
                if not m:
                    continue
                key_uri = m.group(1)
                kp = urlparse(key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)).path
                kd = posixpath.dirname(kp)
                if kd and kd != "/":
                    return kd + "/"

        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
        segments, pending = [], []
        removed = kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_path = urlparse(media_url).path
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
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

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

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
                    continue
                child = urljoin(source_url, line)
                out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if removed > 0 and (kept == 0 or removed > kept):
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

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

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: %s" % type(e).__name__).encode("utf-8")]

    def action(self, action):
        return {"msg": "📺ZakaTV·草艹草运行正常"}

    def liveContent(self):
        return ""

    def destroy(self):
        self.options = {}
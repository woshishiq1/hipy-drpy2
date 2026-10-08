# coding: utf-8
# ============================================================
# 站点信息（法则24）
# 名称：草艹草
# 主域名：https://mqxppthlr.ccctv01.top
# 备用域名：https://26091309.ccctv1.top（永久地址 ccctv1.top）
# 发布页：无（页面内 "永久地址" 直接给出 ccctv1.top）
# 内容类型：成人视频（MacCMS + DPlayer + HLS）
# 架构：PHP/MacCMS，所有页面 HTML 经 atob+字节数组 混淆
# 播放：/vodplay/{id}-1-1.html，<mark id="bfz" data-user-name="第1集$m3u8">
# 广告：m3u8 混入广告目录分片，NEED_CLEAN=True 走五层管线
# 最后验证：2026-09-13
# ============================================================
import json
import base64
import re
from urllib.parse import quote, urljoin, unquote, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # ---- 由 m3u8_analyzer 取证结论决定 ----
    # 取证：可疑广告目录 /20260830/i2vAQKIt/1000kb/hls/（18个）混入正片
    NEED_CLEAN = True

    def __init__(self):
        self.extend = ""
        self.host = "https://mqxppthlr.ccctv01.top"
        self.hosts = [
            "https://mqxppthlr.ccctv01.top",
            "https://26091309.ccctv1.top",
        ]
        self._cached_host = None

        # 分类（首页导航，零网络硬编码）
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
            {"type_id": "59", "type_name": "清纯素女"},
        ]
        self.filters = {}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }

    # ---------------- 基础 ----------------
    def getName(self):
        return "草艹草"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络（法则16）
        self.extend = extend or ""

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------------- 反混淆 ----------------
    def _decode_html(self, src):
        """站点所有页面经 atob + 字节数组 混淆，需还原为真实 HTML"""
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

    # ---------------- 网络 ----------------
    def _fetch_text(self, url, referer=None):
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            r = self.fetch(url, headers=h, timeout=15)
            if r and getattr(r, "status_code", 0) == 200:
                txt = getattr(r, "text", "") or ""
                if not txt and getattr(r, "content", None):
                    txt = r.content.decode("utf-8", errors="ignore")
                return self._decode_html(txt)
        except Exception as e:
            self.log({"fetch": "err", "url": url, "error": type(e).__name__})
        return ""

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        # 零网络（法则16）
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_text(self.host + "/")
        if not html:
            return {"list": []}
        return {"list": self._parse_list(html)}

    # ---------------- 分类 ----------------
    def _parse_list(self, html):
        items = []
        seen = set()
        # 卡片：<li><a class="thumbnail video_link" href="/voddetail/ID.html"><img src="..."></a>
        #       <div class="video-info"><h5><a class="video_link" href="/voddetail/ID.html">标题</a></h5></div></li>
        blocks = re.findall(r'<li>(.*?)</li>', html, re.S)
        for b in blocks:
            m = re.search(r'/voddetail/(\d+)\.html', b)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            # 标题
            t = re.search(r'<h5>\s*<a[^>]*>(.*?)</a>', b, re.S)
            name = ""
            if t:
                name = re.sub(r'<[^>]+>', '', t.group(1)).strip()
            if not name:
                t2 = re.search(r'<img[^>]*alt="([^"]*)"', b)
                name = (t2.group(1) if t2 else "").strip()
            # 图片：优先 data-src，其次 src
            p = re.search(r'data-src="([^"]+)"', b) or re.search(r'<img[^>]*src="([^"]+)"', b)
            pic = (p.group(1) if p else "").strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            items.append({
                "vod_id": vid,
                "vod_name": name or ("视频" + vid),
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return items

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            r = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    r[k.strip()] = v.strip()
            return r
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page <= 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"
        html = self._fetch_text(url)
        items = self._parse_list(html) if html else []
        return {
            "list": items,
            "page": page,
            "pagecount": 9999,
            "limit": 20,
            "total": 999999,
        }

    # ---------------- 详情 ----------------
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

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0]
        url = f"{self.host}/voddetail/{vid}.html"
        html = self._fetch_text(url)
        if not html or len(html) < 500:
            return self._skeleton(raw)

        # 标题多级兜底：优先面包屑末段 > 封面 alt > <title> 去站名后缀
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
                # title 形如 "分类名+标题-站名-关键词..."，按最后一个 '-' 前的站名前段清洗不稳，
                # 保守做法：保留原文，仅去除常见站名后缀
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

        content = ""
        m = re.search(r'(?:简介|剧情)[:：]?\s*</?[^>]*>(.*?)</', html, re.S)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        play_page = f"{self.host}/vodplay/{vid}-1-1.html"
        m = re.search(r'href="(/vodplay/[^"]+)"', html)
        if m:
            play_page = urljoin(self.host, m.group(1))

        vod = {
            "vod_id": raw,
            "vod_name": name or ("视频" + vid),
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_page,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        kw = quote(str(key or ""))
        # MacCMS 搜索：/vod/search.html?wd=kw ；分页 /vod/search/{kw}----------{pg}---.html
        if page <= 1:
            url = f"{self.host}/vod/search.html?wd={kw}"
        else:
            url = f"{self.host}/vod/search/{kw}----------{page}---.html"
        html = self._fetch_text(url)
        items = self._parse_list(html) if html else []
        return {"list": items, "page": page}

    # ---------------- 播放 ----------------
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def _extract_play_url(self, play_page):
        """播放页：解码混淆 HTML，提取 <mark id="bfz" data-user-name="第1集$m3u8">"""
        html = self._fetch_text(play_page)
        if not html:
            return ""
        m = re.search(r'data-user-name=["\']([^"\']+)"', html)
        if not m:
            # 兜底：直接找 m3u8/mp4
            m2 = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html)
            return m2.group(1) if m2 else ""
        val = m.group(1)
        if "$" in val:
            val = val.split("$", 1)[1]
        return val.strip()

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        ua = self.headers.get("User-Agent", "")
        play_url = str(id).strip()

        # id 可能是 "播放$xxx" 或直接是 play_page
        if "$" in play_url:
            play_url = play_url.split("$", 1)[1]

        # 已是直链
        if play_url.startswith("http") and (".m3u8" in play_url or ".mp4" in play_url):
            if ".m3u8" in play_url and self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": ua}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

        # 播放页 -> 提取真实 m3u8
        real = self._extract_play_url(play_url)
        if real:
            if real.startswith("//"):
                real = "https:" + real
            if ".m3u8" in real and self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(real),
                        "header": {"User-Agent": ua}}
            return {"parse": 0, "url": real, "header": {"User-Agent": ua}}

        # 降级嗅探
        return {"parse": 1, "url": play_url,
                "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    # ---------------- m3u8 五层过滤（法则30） ----------------
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
        import posixpath
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            kp = urlparse(key_uri if key_uri.startswith("http")
                          else urljoin(source_url, key_uri)).path
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
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True, "action": "keep_suffix_as_is"})

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
            self.log({"stage": "clean", "fallback": "no_filter",
                      "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

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
                qs = __import__("urllib.parse", fromlist=["parse"]).parse_qs(urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            r = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=20)
            if not r or getattr(r, "status_code", 0) != 200:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(r, "content", b"") or b""
            if not content and getattr(r, "text", ""):
                content = r.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: %s" % type(e).__name__).encode("utf-8")]
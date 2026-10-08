# -*- coding: utf-8 -*-
"""
遮天 · SeverePorn
https://severeporn.com  (KVS)
播放: get_file 直链 MP4（2K/HD/SD），同站 CDN，无需第三方嵌入
"""
import re
import sys
from html import unescape
from urllib.parse import quote

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def __init__(self):
            pass

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
    HAS_REQ = True
except Exception:
    HAS_REQ = False


class Spider(BaseSpider):
    host = "https://severeporn.com"
    session = None
    timeout = 10

    # 固定入口 + 分类由页面动态补充
    BASE_CATS = [
        ("/", "首页"),
        ("/latest-updates/", "最新"),
        ("/top-rated/", "高分"),
        ("/most-popular/", "最热"),
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._ensure_session()

    def _ensure_session(self):
        if not HAS_REQ:
            return
        if self.session is None:
            self.session = requests.Session()
            self.session.verify = False
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def getName(self):
        return "SeverePorn"

    def init(self, extend=""):
        extend = (extend or "").strip()
        if extend.startswith("http"):
            self.host = extend.rstrip("/")
        self._ensure_session()
        return True

    def destroy(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in [".mp4", ".m3u8", "get_file"])

    def manualVideoCheck(self):
        return False

    def _get(self, url, timeout=None):
        timeout = timeout or self.timeout
        if not url.startswith("http"):
            url = self.host.rstrip("/") + (url if url.startswith("/") else "/" + url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            if HAS_REQ and self.session is not None:
                r = self.session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    r.encoding = "utf-8"
                    return r.text
        except Exception as e:
            print("[SeverePorn] get", e)
        return ""

    def _pic(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            url = self.host.rstrip("/") + url
        return url

    def _cards(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(
            r'<div class="item\s*"[^>]*>\s*<a href="(https://severeporn\.com/video/(\d+)/[^"]*/)"[^>]*title="([^"]*)"[\s\S]*?</a>\s*</div>',
            html,
        ):
            href, vid, title = m.group(1), m.group(2), unescape(m.group(3)).strip()
            if vid in seen:
                continue
            block = m.group(0)
            pic = ""
            pm = re.search(r'data-original="(https?://[^"]+)"', block)
            if not pm:
                pm = re.search(r'data-webp="(https?://[^"]+)"', block)
            if pm:
                pic = pm.group(1)
            dur = ""
            dm = re.search(r'class="duration"[^>]*>\s*([^<\s]+)', block)
            if dm:
                dur = dm.group(1).strip()
            hd = ""
            if "is-2k" in block:
                hd = "2K"
            elif "is-hd" in block:
                hd = "HD"
            remarks = " ".join(x for x in (hd, dur) if x)
            seen.add(vid)
            # 保留完整带 slug 的路径，短路径 /video/id/ 会 404
            path = href.replace(self.host, "")
            videos.append(
                {
                    "vod_id": path,
                    "vod_name": title[:100] or vid,
                    "vod_pic": self._pic(pic),
                    "vod_remarks": remarks or "Severe",
                }
            )
        if not videos:
            # 宽松匹配
            for m in re.finditer(
                r'href="(https://severeporn\.com/video/(\d+)/[^"]*/)"[^>]*title="([^"]*)"',
                html,
            ):
                href, vid, title = m.group(1), m.group(2), unescape(m.group(3)).strip()
                if vid in seen:
                    continue
                seen.add(vid)
                path = href.replace(self.host, "")
                videos.append(
                    {
                        "vod_id": path,
                        "vod_name": title[:100] or vid,
                        "vod_pic": "",
                        "vod_remarks": "Severe",
                    }
                )
        return videos

    def _extract_sources(self, html):
        """从 kt_player flashvars 提取 2K/HD/SD，高清优先"""
        sources = []
        if not html:
            return sources
        # 配对 url + text
        pairs = []
        # video_url + video_url_text
        m = re.search(
            r"video_url:\s*'([^']+)'[\s\S]{0,120}?video_url_text:\s*'([^']+)'",
            html,
        )
        if m:
            pairs.append((m.group(2), m.group(1)))
        for i in ("", "2", "3", "4"):
            key = "video_alt_url" + i
            m = re.search(
                rf"{key}:\s*'([^']+)'[\s\S]{{0,120}}?{key}_text:\s*'([^']+)'",
                html,
            )
            if m:
                pairs.append((m.group(2), m.group(1)))
        # contentUrl 兜底
        m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
        if m and not pairs:
            pairs.append(("HD", m.group(1)))

        # 去重、排序：2K > 1080 > HD > SD
        def rank(lab):
            u = lab.upper()
            if "2K" in u or "2160" in u or "FHD" in u or "1080" in u:
                return 0
            if "HD" in u or "720" in u:
                return 1
            if "SD" in u or "480" in u:
                return 3
            return 2

        seen = set()
        for lab, url in pairs:
            url = url.replace("\\/", "/").strip()
            if not url or url in seen:
                continue
            if "preview" in url:
                continue
            seen.add(url)
            sources.append((lab.strip() or "MP4", url))
        sources.sort(key=lambda x: rank(x[0]))
        return sources

    def homeContent(self, filter=False):
        html = self._get("/")
        classes = [{"type_id": p, "type_name": n} for p, n in self.BASE_CATS]
        if html:
            for path, name in re.findall(
                r'href="https://severeporn\.com/(categories/[^"]+/)"[^>]*>\s*([^<]+)',
                html,
            ):
                full = "/" + path
                name = unescape(name).strip()
                if name and not any(c["type_id"] == full for c in classes):
                    classes.append({"type_id": full, "type_name": name})
        return {"class": classes, "list": self._cards(html)}

    def homeVideoContent(self):
        return self.categoryContent("/", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        tid = str(tid or "/")
        if tid == "/":
            path = "/" if page <= 1 else "/latest-updates/%d/" % page
        else:
            path = tid if tid.startswith("/") else "/" + tid
            if page > 1:
                path = path.rstrip("/") + "/%d/" % page
        html = self._get(path)
        videos = self._cards(html)
        # 页数
        pages = [int(x) for x in re.findall(r"/(\d+)/?(?:\"|'|\s)", html or "") if x.isdigit() and int(x) < 5000]
        pagecount = max(pages) if pages else (page + (1 if videos else 0))
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": 24,
            "total": 99999 if videos else 0,
        }

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, list) else ids).strip()
        if raw.startswith("http"):
            url = raw
        elif raw.startswith("/"):
            url = self.host.rstrip("/") + raw
        else:
            vid = re.sub(r"\D", "", raw) or raw
            url = self.host + "/video/%s/" % vid

        html = self._get(url)
        # 短链无内容时跟 canonical
        if (not html or "video_url" not in html) and "/video/" in url:
            m = re.search(r'rel="canonical"\s+href="(https://severeporn\.com/video/[^"]+)"', html or "")
            if not m:
                # 用首页搜索 id
                vid = re.search(r"/video/(\d+)", url)
                if vid:
                    tip = self._get("/latest-updates/")
                    m2 = re.search(
                        rf'href="(https://severeporn\.com/video/{vid.group(1)}/[^"]*/)"',
                        tip or "",
                    )
                    if m2:
                        html = self._get(m2.group(1))
                        url = m2.group(1)
            else:
                html = self._get(m.group(1))
                url = m.group(1)
        title, cover, content, remarks = "", "", "", ""
        if html:
            m = re.search(r'property="og:title"\s+content="([^"]+)"', html)
            if m:
                title = unescape(m.group(1)).strip()
            if not title:
                m = re.search(r"<title>([^<]+)", html)
                if m:
                    title = unescape(m.group(1)).split("|")[0].strip()
            m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
            if m:
                cover = m.group(1)
            if not cover:
                m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', html)
                if m:
                    cover = m.group(1)
            m = re.search(r'property="og:description"\s+content="([^"]+)"', html)
            if m:
                content = unescape(m.group(1)).strip()
            m = re.search(r'"duration"\s*:\s*"([^"]+)"', html)
            if m:
                remarks = m.group(1)
            # 分类标签
            tags = re.findall(r'href="https://severeporn\.com/categories/[^"]+"[^>]*>([^<]+)', html)
            if tags:
                content = (content + " | " + ", ".join(unescape(t).strip() for t in tags[:8])).strip(" |")

        sources = self._extract_sources(html)
        if not sources:
            # 嗅探详情页
            play_from = ["嗅探"]
            play_url = ["播放$%s" % url]
        else:
            play_from = [lab for lab, _ in sources]
            play_url = ["正片$%s" % u for _, u in sources]

        return {
            "list": [{
                "vod_id": raw,
                "vod_name": (title or raw)[:100],
                "vod_pic": self._pic(cover),
                "vod_content": content[:400],
                "vod_remarks": remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        url = (id or "").strip().replace("\\/", "/")
        header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "*/*",
        }
        if url.startswith("http") and (".mp4" in url or "get_file" in url):
            return {"parse": 0, "jx": 0, "url": url, "header": header}
        # 详情页再解
        if "severeporn.com" in url:
            html = self._get(url)
            srcs = self._extract_sources(html)
            if srcs:
                return {"parse": 0, "jx": 0, "url": srcs[0][1], "header": header}
            return {"parse": 1, "jx": 0, "url": url, "header": header}
        return {"parse": 1, "jx": 0, "url": url, "header": header}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        key = (key or "").strip()
        if not key:
            return {"list": []}
        path = "/search/%s/" % quote(key)
        if page > 1:
            path = "/search/%s/%d/" % (quote(key), page)
        return {"list": self._cards(self._get(path)), "page": page}

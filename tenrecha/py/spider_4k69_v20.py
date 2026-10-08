#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遮天TVBox九秘大师 · 4k69.com v20.0
修复：正确的URL格式 ?link1=videos&page=category&id=XXX + 女优ID格式修复

【正确的URL格式】
最新视频: ?link1=videos&page=latest&page_id=1
分类:     ?link1=videos&page=category&id=BBW&page_id=1
工作室:   ?link1=videos&page=studio&id=Brazzers&page_id=1
女优:     ?link1=videos&page=pornstar&id=Riley+Reid&page_id=1
"""

import sys
import re
import json
import time
import base64
import random
import requests
from urllib import parse
from html import unescape

sys.path.append("..")
from base.spider import Spider


class YuanTianShu:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    ua_pool = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ]

    ad_patterns = [
        re.compile(r"https?://[^/\s]*ad[^/\s]*/[^\"\s]*\.ts", re.I),
        re.compile(r"https?://[^/\s]*advert[^/\s]*/[^\"\s]*\.ts", re.I),
        re.compile(r"https?://[^/\s]*banner[^/\s]*/[^\"\s]*\.ts", re.I),
        re.compile(r"https?://[^/\s]*tracker[^/\s]*/[^\"\s]*\.ts", re.I),
        re.compile(r"https?://[^/\s]*pop[^/\s]*/[^\"\s]*\.ts", re.I),
    ]

    RES_MAP = {
        "2160": "4K",
        "1080": "1080P",
        "720": "720P",
        "480": "480P",
        "360": "360P",
    }

    CATEGORIES = [
        ("3D", "3D"), ("4K", "4K"), ("69", "69"), ("ASMR", "ASMR"),
        ("Amateur", "Amateur"), ("Anal", "Anal"), ("Asian", "Asian"),
        ("BBW", "BBW"), ("BDSM", "BDSM"), ("Big-Ass", "Big Ass"),
        ("Big-Tits", "Big Tits"), ("Blonde", "Blonde"), ("Blowjob", "Blowjob"),
        ("Brunette", "Brunette"), ("Creampie", "Creampie"), ("Cumshot", "Cumshot"),
        ("Double-Penetration", "Double Penetration"), ("Ebony", "Ebony"),
        ("Fetish", "Fetish"), ("Gangbang", "Gangbang"), ("Group", "Group"),
        ("Hentai", "Hentai"), ("Interracial", "Interracial"), ("Japanese", "Japanese"),
        ("Latina", "Latina"), ("Lesbian", "Lesbian"), ("MILF", "MILF"),
        ("Masturbation", "Masturbation"), ("Orgy", "Orgy"), ("Outdoor", "Outdoor"),
        ("POV", "POV"), ("Pornstar", "Pornstar"), ("Public", "Public"),
        ("Redhead", "Redhead"), ("Rough", "Rough"), ("Solo", "Solo"),
        ("Squirt", "Squirt"), ("Teen", "Teen"), ("Threesome", "Threesome"),
        ("Toys", "Toys"), ("Vintage", "Vintage"), ("Webcam", "Webcam"),
    ]

    STUDIOS = [
        ("Brazzers", "Brazzers"), ("BangBros", "BangBros"),
        ("Naughty-America", "Naughty America"), ("Reality-Kings", "Reality Kings"),
        ("Tushy", "Tushy"), ("Blacked", "Blacked"), ("Vixen", "Vixen"),
        ("Digital-Playground", "Digital Playground"), ("Mofos", "Mofos"),
        ("TeamSkeet", "TeamSkeet"),
    ]

    PORNSTARS = [
        ("Riley-Reid", "Riley Reid"), ("Mia-Malkova", "Mia Malkova"),
        ("Lana-Rhoades", "Lana Rhoades"), ("Abella-Danger", "Abella Danger"),
        ("Angela-White", "Angela White"),
    ]

    def __init__(self):
        self.siteUrl = "https://4k69.com"
        self._init_session()
        self._cache = {}

    def _init_session(self):
        try:
            h = dict(self.headers)
            h["User-Agent"] = random.choice(self.ua_pool)
            self.session.get(self.siteUrl, headers=h, timeout=15)
            time.sleep(1)
            h["Referer"] = self.siteUrl + "/"
            self.session.get("%s/?link1=videos&page=latest&page_id=1" % self.siteUrl, headers=h, timeout=15)
            self.session.cookies.set("age_verify", "1")
            self.session.cookies.set("ads_pageview", "1")
        except Exception as e:
            print("[源天书] 定龙脉失败: %s" % e)

    def fetch(self, url, headers=None, retry=3, delay=1):
        h = {**self.headers, **(headers or {})}
        h["User-Agent"] = random.choice(self.ua_pool)
        h["Referer"] = self.siteUrl + "/"
        last_err = None
        for i in range(retry):
            try:
                resp = self.session.get(url, headers=h, timeout=15)
                resp.encoding = "utf-8"
                if resp.status_code == 403 and len(resp.text) < 10000:
                    if "Just a moment" in resp.text or "challenges.cloudflare" in resp.text:
                        print("[源天书] CF拦截: %s" % url)
                        return ""
                if resp.status_code == 200:
                    if "\x00" in resp.text[:100]:
                        return ""
                    return resp.text
                elif resp.status_code in [403, 429, 503]:
                    time.sleep(delay * (i + 1) * 2)
            except Exception as e:
                last_err = e
            if i < retry - 1:
                time.sleep(delay * (i + 1))
        print("[源天书] 寻神源失败 [%s]: %s" % (url, last_err))
        return ""

    def _clean_m3u8(self, content):
        if not content:
            return content
        lines = content.split("\n")
        cleaned = []
        skip_next = False
        for line in lines:
            stripped = line.strip()
            is_ad = any(p.search(stripped) for p in self.ad_patterns)
            if is_ad:
                skip_next = True
                continue
            if skip_next and stripped.startswith("#EXTINF"):
                skip_next = False
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _full_url(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return parse.urljoin(self.siteUrl, path)


class Spider(YuanTianShu, Spider):

    def init(self, extend=""):
        return True

    def homeContent(self, filter):
        classes = [
            {"type_id": "latest", "type_name": "最新视频"},
            {"type_id": "trending", "type_name": "热门推荐"},
            {"type_id": "top", "type_name": "排行榜"},
        ]
        for slug, name in self.CATEGORIES:
            classes.append({"type_id": "categories|%s" % slug, "type_name": name})
        for slug, name in self.STUDIOS:
            classes.append({"type_id": "studios|%s" % slug, "type_name": name})
        for slug, name in self.PORNSTARS:
            classes.append({"type_id": "pornstars|%s" % slug, "type_name": name})
        return {"class": classes}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 20}
        try:
            if tid in ["latest", "trending", "top"]:
                if tid == "trending":
                    result["pagecount"] = 3
                url = "%s/?link1=videos&page=%s&page_id=%s" % (self.siteUrl, tid, pg)
                html = self.fetch(url, delay=1)
                if html:
                    result["list"] = self._extract_videos(html)
                    if tid == "trending" and int(pg) >= 3:
                        result["pagecount"] = int(pg)
                return result

            parts = tid.split("|")
            if len(parts) == 2:
                main_type, sub_id = parts
            else:
                main_type, sub_id = tid, tid

            url = self._build_category_url(main_type, sub_id, pg)
            html = self.fetch(url, delay=2)

            if html and len(html) > 5000:
                result["list"] = self._extract_videos(html)
                if not result["list"]:
                    result["pagecount"] = int(pg)
                    return result
                next_page = int(pg) + 1
                has_next = ('page_id=%s"' % next_page in html or
                            "page_id=%s'" % next_page in html or
                            'page_id=%s' % next_page in html)
                result["pagecount"] = 999 if has_next else int(pg)
            else:
                print("[categoryContent] 获取失败: %s" % url)
                result["pagecount"] = int(pg)
        except Exception as e:
            print("[categoryContent] 者字秘兜底: %s" % e)
            result["pagecount"] = int(pg)
        return result

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0] if ids else ""
        if not vid:
            return result

        html = ""
        strategies = [
            ("%s/?link1=watch&id=%s" % (self.siteUrl, vid), 2),
            ("%s/watch/%s" % (self.siteUrl, vid), 2),
            ("%s/?link1=watch&id=%s.html" % (self.siteUrl, vid.replace(".html", "")), 2),
            ("%s/watch/%s.html" % (self.siteUrl, vid.replace(".html", "")), 2),
            ("%s/api/video?id=%s" % (self.siteUrl, vid), 1),
        ]

        for url, delay in strategies:
            try:
                text = self.fetch(url, delay=delay)
                if text and len(text) > 5000:
                    html = text
                    break
            except:
                continue

        if not html:
            return result

        title = "未知视频"
        try:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                title = m.group(1).strip().replace(" - 4K69.com", "").replace("4K69.com", "").strip()
                title = unescape(title)
        except:
            pass

        all_sources = {}
        dlink_sources = self._extract_dlinks(html)
        all_sources.update(dlink_sources)

        if not all_sources:
            extractors = [
                lambda h: self._extract_jsonld(h),
                lambda h: self._extract_cdn(h, "4kporno"),
                lambda h: self._extract_cdn(h, "okcdn"),
                lambda h: self._extract_source_tag(h),
                lambda h: self._extract_generic_video(h),
                lambda h: self._extract_video_tag(h),
                lambda h: self._extract_data_attrs(h),
            ]
            for extractor in extractors:
                try:
                    urls = extractor(html)
                    for u in urls:
                        if u:
                            q = self._detect_quality(u)
                            if q not in all_sources:
                                all_sources[q] = u
                except:
                    continue

        expanded = dict(all_sources)
        for url in list(all_sources.values()):
            m = re.search(r'_(\d+)m\.mp4', url)
            if m:
                current_res = m.group(1)
                for res, quality in self.RES_MAP.items():
                    if quality not in expanded:
                        new_url = url.replace("_%sm.mp4" % current_res, "_%sm.mp4" % res)
                        if new_url != url:
                            expanded[quality] = new_url

        episodes = []
        quality_order = ["4K", "2160P", "1080P", "HD", "720P", "480P", "360P", "SD", "AUTO", "未知"]
        for q in quality_order:
            if q in expanded:
                episodes.append("%s$%s" % (q, self._full_url(expanded[q])))
        for q, url in expanded.items():
            if q not in quality_order:
                episodes.append("%s$%s" % (q, self._full_url(url)))

        play_url_str = "#".join(episodes) if episodes else ""

        source_type = "视频源"
        all_urls = list(expanded.values())
        if any("4kporno" in u for u in all_urls):
            source_type = "4K直链"
        elif any("okcdn" in u for u in all_urls):
            source_type = "4K直链"

        result["list"].append({
            "vod_id": vid,
            "vod_name": title,
            "vod_play_from": source_type,
            "vod_play_url": play_url_str,
            "vod_content": title,
        })

        return result

    def playerContent(self, flag, id, vipFlags):
        try:
            if not id:
                return {"parse": 0, "url": "", "header": ""}
            if id.startswith("http://127.0.0.1"):
                return {"parse": 0, "url": id, "header": ""}

            header = "User-Agent=%s&Referer=%s/" % (random.choice(self.ua_pool), self.siteUrl)

            if "4kporno" in id or "okcdn" in id:
                return {"parse": 0, "url": id, "header": header}
            if "embed" in id:
                return {"parse": 1, "url": id, "header": ""}
            if ".m3u8" in id:
                return {"parse": 0, "url": id, "header": header}
            if any(id.endswith(ext) for ext in [".mp4", ".flv", ".mkv", ".ts"]):
                return {"parse": 0, "url": id, "header": header}

            return {"parse": 0, "url": id, "header": header}
        except Exception as e:
            return {"parse": 0, "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg), "pagecount": 1}
        try:
            urls_to_try = [
                "%s/?link1=search&q=%s&page=%s" % (self.siteUrl, parse.quote(key), pg),
                "%s/?link1=videos&page=latest&tag=%s&page_id=%s" % (self.siteUrl, parse.quote(key), pg),
                "%s/?link1=videos&page=latest&category=%s&page_id=%s" % (self.siteUrl, parse.quote(key), pg),
            ]
            html = ""
            for url in urls_to_try:
                html = self.fetch(url, delay=2)
                if html and len(html) > 5000:
                    break

            if html:
                result["list"] = self._extract_videos(html)
                has_next = 'page_id=%s"' % (int(pg) + 1) in html
                if not has_next:
                    result["pagecount"] = int(pg)
        except Exception as e:
            print("[searchContent] 异常: %s" % e)
        return result

    def localProxy(self, param):
        try:
            import http.server
            import socketserver
            from urllib.parse import parse_qs, urlparse

            class ProxyHandler(http.server.BaseHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass

                def do_GET(self):
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query)

                    if parsed.path == "/proxy":
                        try:
                            real_url = base64.b64decode(params.get("url", [""])[0]).decode()
                            referer = base64.b64decode(params.get("ref", [""])[0]).decode()

                            h = {
                                "User-Agent": random.choice(self.ua_pool),
                                "Referer": referer,
                                "Accept": "*/*",
                            }
                            resp = requests.get(real_url, headers=h, stream=True, timeout=15)

                            content_type = resp.headers.get("Content-Type", "")

                            if "mpegurl" in content_type or real_url.endswith(".m3u8"):
                                content = resp.text
                                cleaned = self._clean_m3u8(content)
                                self.send_response(200)
                                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                                self.end_headers()
                                self.wfile.write(cleaned.encode())
                            else:
                                self.send_response(resp.status_code)
                                for key, val in resp.headers.items():
                                    if key.lower() not in ["content-encoding", "transfer-encoding", "content-length"]:
                                        self.send_header(key, val)
                                self.end_headers()
                                for chunk in resp.iter_content(8192):
                                    self.wfile.write(chunk)
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(str(e).encode())
                    else:
                        self.send_response(404)
                        self.end_headers()

            import threading
            def run_proxy():
                with socketserver.TCPServer(("127.0.0.1", 9979), ProxyHandler) as httpd:
                    httpd.serve_forever()

            t = threading.Thread(target=run_proxy, daemon=True)
            t.start()

            return [200, "application/json", json.dumps({
                "proxy": "http://127.0.0.1:9979",
                "status": "running"
            })]
        except Exception as e:
            return [500, "application/json", json.dumps({"error": str(e)})]

    def isVideoFormat(self, url):
        if "4kporno" in url or "okcdn" in url:
            return True
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".flv", ".mkv", ".ts"])

    def manualVideoCheck(self):
        return False

    def _build_category_url(self, main_type, sub_id, pg):
        base = self.siteUrl
        if main_type == "pornstars":
            sub_id = sub_id.replace("-", "+")
        if main_type == "categories":
            page_type = "category"
        elif main_type == "studios":
            page_type = "studio"
        elif main_type == "pornstars":
            page_type = "pornstar"
        else:
            page_type = "category"
        return "%s/?link1=videos&page=%s&id=%s&page_id=%s" % (base, page_type, sub_id, pg)

    def _extract_dlinks(self, html):
        sources = {}
        if not html:
            return sources
        dlinks = re.findall(r'[?&]dlink=([A-Za-z0-9+/=]+)', html)
        dlinks += re.findall(r'dlink[=:]\s*["\']([A-Za-z0-9+/=]+)["\']', html)
        for dlink in dlinks:
            try:
                decoded = base64.b64decode(dlink).decode('utf-8')
                if not decoded.startswith("http"):
                    continue
                m = re.search(r'_(\d+)m\.mp4', decoded)
                if m:
                    res = m.group(1)
                    quality = self.RES_MAP.get(res, "%sP" % res)
                else:
                    quality = "未知"
                if quality not in sources:
                    sources[quality] = decoded
            except:
                continue
        return sources

    def _extract_videos(self, html):
        videos = []
        if not html or len(html) < 500:
            return videos
        try:
            all_ids = list(dict.fromkeys(
                re.findall(r'4k69\.com/watch/([^"\'\s<>]+)', html)
            ))
            for vid_id in all_ids[:50]:
                try:
                    pattern = r'<a[^>]*href=["\'][^"\']*watch/%s["\'][^>]*>.*?</a>' % re.escape(vid_id)
                    block_match = re.search(pattern, html, re.S)
                    if not block_match:
                        continue
                    block = block_match.group(0)
                    pic = ""
                    pic_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
                    if pic_m:
                        pic = pic_m.group(1)
                    title = ""
                    title_m = re.search(r'alt=["\']([^"\']*)["\']', block)
                    if title_m:
                        title = title_m.group(1)
                    if not title:
                        title_m2 = re.search(r'title=["\']([^"\']*)["\']', block)
                        if title_m2:
                            title = title_m2.group(1)
                    videos.append({
                        "vod_id": vid_id,
                        "vod_name": unescape(title.strip()),
                        "vod_pic": pic,
                        "vod_remarks": "4K"
                    })
                except:
                    continue
        except Exception as e:
            print("[_extract_videos] 精确模式失败: %s" % e)
        if not videos:
            try:
                for m in re.finditer(
                    r'<a[^>]*href=["\'][^"\']*watch/([^"\'\s<>]+)["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']',
                    html, re.S
                ):
                    videos.append({
                        "vod_id": m.group(1),
                        "vod_name": unescape(m.group(3).strip()),
                        "vod_pic": m.group(2),
                        "vod_remarks": "4K"
                    })
            except Exception as e:
                print("[_extract_videos] 宽松模式失败: %s" % e)
        if not videos:
            try:
                for m in re.finditer(r'href=["\'][^"\']*watch/([^"\'\s<>]+)["\'][^>]*>([^<]+)</a>', html, re.S):
                    vid = m.group(1)
                    title = m.group(2).strip()
                    if title and len(title) > 2:
                        videos.append({
                            "vod_id": vid,
                            "vod_name": unescape(title),
                            "vod_pic": "",
                            "vod_remarks": "4K"
                        })
            except Exception as e:
                print("[_extract_videos] 极简模式失败: %s" % e)
        return videos

    def _extract_jsonld(self, html):
        urls = []
        try:
            m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
            if m:
                data = json.loads(m.group(1))
                url = data.get("contentUrl", "")
                if url:
                    urls.append(url)
        except:
            pass
        return urls

    def _extract_cdn(self, html, cdn_name):
        return re.findall(r'https?://[^"\'\s<>]*%s[^"\'\s<>]*' % cdn_name, html)

    def _extract_source_tag(self, html):
        return re.findall(r'<source[^>]+src=["\']?([^"\']+)["\']?', html)

    def _extract_generic_video(self, html):
        m = re.search(r'https?://[^"\'\s<>]+\.(?:mp4|m3u8)(?:\?[^"\'\s<>]*)?', html)
        return [m.group(0)] if m else []

    def _extract_video_tag(self, html):
        m = re.search(r'<video[^>]+src=["\']?([^"\']+)["\']?', html, re.I)
        return [m.group(1)] if m else []

    def _extract_data_attrs(self, html):
        return re.findall(r'data-(?:src|url)=["\']?(https?://[^"\']+)["\']?', html)

    def _detect_quality(self, url):
        if not url:
            return "未知"
        url_lower = url.lower()
        m = re.search(r'_(\d+)m\.mp4', url_lower)
        if m:
            res = m.group(1)
            return self.RES_MAP.get(res, "%sP" % res)
        m = re.search(r'[?&]type=(\d+)', url_lower)
        if m:
            type_map = {"4": "4K", "3": "1080P", "5": "HD", "2": "720P", "1": "480P", "0": "360P", "7": "AUTO", "6": "SD"}
            return type_map.get(m.group(1), "%sP" % m.group(1))
        if "2160" in url_lower or "4k" in url_lower:
            return "4K"
        elif "1080" in url_lower:
            return "1080P"
        elif "720" in url_lower:
            return "720P"
        elif "480" in url_lower:
            return "480P"
        return "未知"


if __name__ == "__main__":
    spider = Spider()
    print(json.dumps(spider.homeContent({}), ensure_ascii=False, indent=2))

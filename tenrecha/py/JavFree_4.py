#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavFree.stream TVBox Spider v4.7
境界: 仙台秘境 · 第三重天·圆满归真 (临+斗+兵+皆+阵+列+前+者)
特征: CDN女优头像检测 + fallback作品封面 + 作品集数 + 多线路优选
作者: 遮天TVBox九秘大师
"""

import sys
import re
import json
import time
import math
import base64
import threading
import urllib.request
from urllib.parse import quote

sys.path.append("..")
from base.spider import Spider


class JavFree(Spider):
    """
    【仙台秘境 · 第三重天·圆满归真】

    核心修复: 女优头像并发检测，CDN不可用时自动fallback到作品封面
    """

    siteUrl = "https://javfree.stream"
    cdnUrl = "https://cdn.javfree.stream"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    actressPageSize = 100
    videoPageSize = 24

    categories = [
        {"type_id": "latest", "type_name": "最新"},
        {"type_id": "popular?period=daily", "type_name": "热门(每日)"},
        {"type_id": "category/ppv", "type_name": "PPV"},
        {"type_id": "category/censored", "type_name": "有码"},
        {"type_id": "category/reduce-mosaic", "type_name": "薄码"},
        {"type_id": "category/uncensored", "type_name": "无码"},
        {"type_id": "actresses", "type_name": "女优"},
    ]

    def __init__(self):
        self.session = None

    def getName(self):
        return "JavFree"

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        return any(url.lower().endswith(x) for x in [".m3u8", ".mp4", ".ts"])

    def manualVideoCheck(self):
        return False

    def _fetch(self, url, headers=None):
        h = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "identity",
            "Referer": self.siteUrl + "/zh/",
            "Cookie": "jf_lang_redirected=1; jf_lang=zh",
        }
        if headers:
            h.update(headers)

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                if attempt == 2:
                    print(f"[者字秘] 三次重试失败: {url} | {e}")
                    return ""
                time.sleep(1 * (attempt + 1))
        return ""

    def _fetch_json(self, url):
        text = self._fetch(url)
        if not text:
            return None
        try:
            return json.loads(text)
        except:
            return None

    def _check_pic_available(self, url, timeout=2):
        """
        检测图片URL是否可用（HEAD请求）
        """
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Referer": self.siteUrl,
            }, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except:
            return False

    def _check_pics_concurrent(self, urls, timeout=2):
        """
        并发检测多个图片URL是否可用
        返回: {index: True/False}
        """
        results = {}
        threads = []

        def _check(index, url):
            results[index] = self._check_pic_available(url, timeout)

        for i, url in enumerate(urls):
            t = threading.Thread(target=_check, args=(i, url))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout + 1)

        return results

    def _extract_code(self, text):
        if not text:
            return ""
        patterns = [
            r'^([A-Z]{1,6}-\d{2,4}(?:-[A-Z0-9]+)?)',
            r'^([A-Z0-9]+-\d+(?:-[A-Z0-9]+)*)',
            r'^([A-Z]{2,}-PPV-\d+)',
            r'^(\d+[A-Z]{2,}-\d+)',
        ]
        for pat in patterns:
            m = re.match(pat, text.upper())
            if m:
                return m.group(1)
        return text.split("-")[0].upper() if "-" in text else text.upper()

    def _build_pic_url(self, code):
        if not code:
            return ""
        return f"{self.cdnUrl}/videos/{code}/cover.jpg"

    def homeContent(self, filter):
        return {"class": self.categories}

    def homeVodContent(self):
        try:
            html = self._fetch(f"{self.siteUrl}/zh/popular?period=daily")
            if not html:
                return {"list": []}

            videos = []
            seen = set()

            code_matches = re.findall(r'data-video-code="([^"]+)"', html)
            for code in code_matches[:12]:
                if code not in seen:
                    seen.add(code)
                    videos.append({
                        "vod_id": code,
                        "vod_name": code,
                        "vod_pic": self._build_pic_url(code),
                        "vod_remarks": "热门"
                    })

            return {"list": videos}
        except Exception as e:
            print(f"[前字秘] 首页推荐异常: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)

        # ═══════════════════════════════════════
        # 列字秘 · 女优列表页 —— API分页 + 头像检测
        # ═══════════════════════════════════════
        if tid == "actresses":
            api_page = math.ceil(pg * self.videoPageSize / self.actressPageSize)

            url = f"{self.siteUrl}/api/actresses?page={api_page}&limit={self.actressPageSize}"
            data = self._fetch_json(url)

            if not data or not data.get("actresses"):
                return {"list": [], "page": pg, "pagecount": pg}

            try:
                actresses = data["actresses"]
                pagination = data.get("pagination", {})
                total = pagination.get("total", len(actresses))
                api_pages = pagination.get("pages", 1)

                total_tvbox_pages = math.ceil(total / self.videoPageSize)

                global_index = (pg - 1) * self.videoPageSize
                api_start = (api_page - 1) * self.actressPageSize
                local_start = global_index - api_start
                local_end = local_start + self.videoPageSize

                page_actresses = actresses[local_start:local_end]

                if len(page_actresses) < self.videoPageSize and api_page < api_pages:
                    next_url = f"{self.siteUrl}/api/actresses?page={api_page + 1}&limit={self.actressPageSize}"
                    next_data = self._fetch_json(next_url)
                    if next_data and next_data.get("actresses"):
                        need = self.videoPageSize - len(page_actresses)
                        page_actresses.extend(next_data["actresses"][:need])

                # 构建CDN头像URL列表
                cdn_urls = []
                for a in page_actresses:
                    slug = a.get("slug", "")
                    cdn_url = f"{self.cdnUrl}/actresses/{slug}.jpg"
                    cdn_urls.append(cdn_url)

                # 并发检测CDN头像可用性
                pic_available = self._check_pics_concurrent(cdn_urls, timeout=2)

                videos = []
                for i, a in enumerate(page_actresses):
                    slug = a.get("slug", "")
                    name = a.get("display_name") or a.get("name", slug)
                    video_count = a.get("video_count", 0)
                    fallback_url = a.get("fallback_photo_url", "")

                    # 选择图片: CDN头像可用就用，否则用fallback作品封面
                    if pic_available.get(i, False):
                        pic = cdn_urls[i]
                    elif fallback_url:
                        pic = fallback_url
                    else:
                        pic = ""

                    videos.append({
                        "vod_id": f"actress/{slug}",
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": f"{video_count} 个视频" if video_count else ""
                    })

                return {
                    "list": videos,
                    "page": pg,
                    "pagecount": total_tvbox_pages,
                    "limit": self.videoPageSize,
                    "total": total
                }

            except Exception as e:
                print(f"[列字秘] 女优列表API解析异常: {e}")
                return {"list": [], "page": pg, "pagecount": pg}

        # ═══════════════════════════════════════
        # 列字秘 · 女优详情页
        # ═══════════════════════════════════════
        if tid.startswith("actress/"):
            slug = tid.replace("actress/", "")

            url = f"{self.siteUrl}/api/actresses/{slug}"
            data = self._fetch_json(url)

            if not data:
                return {"list": [], "page": 1, "pagecount": 1}

            try:
                name = data.get("display_name") or data.get("name", slug)

                # 检测女优头像
                cdn_url = f"{self.cdnUrl}/actresses/{slug}.jpg"
                fallback_url = data.get("fallback_photo_url", "")
                if self._check_pic_available(cdn_url, timeout=2):
                    pic = cdn_url
                elif fallback_url:
                    pic = fallback_url
                else:
                    pic = ""

                videos = data.get("videos", [])

                result = []
                for v in videos:
                    code = v.get("code", "")
                    title = v.get("title", code)
                    thumbnail = v.get("thumbnail_url", "")
                    if not thumbnail and code:
                        thumbnail = self._build_pic_url(code)

                    result.append({
                        "vod_id": code,
                        "vod_name": title,
                        "vod_pic": thumbnail,
                        "vod_remarks": ""
                    })

                return {
                    "list": result,
                    "page": 1,
                    "pagecount": 1,
                    "limit": len(result),
                    "total": len(result)
                }

            except Exception as e:
                print(f"[列字秘] 女优详情API解析异常: {e}")
                return {"list": [], "page": 1, "pagecount": 1}

        # ═══════════════════════════════════════
        # 普通视频分类 / 标签
        # ═══════════════════════════════════════
        if tid.startswith("tag/"):
            url = f"{self.siteUrl}/zh/{tid}?page={pg}"
        elif "?" in tid:
            url = f"{self.siteUrl}/zh/{tid}&page={pg}"
        else:
            url = f"{self.siteUrl}/zh/{tid}?page={pg}&sort=latest"

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": pg}

        videos = []
        try:
            seen = set()

            code_matches = re.findall(r'data-video-code="([^"]+)"', html)
            for code in code_matches:
                if code not in seen:
                    seen.add(code)
                    videos.append({
                        "vod_id": code,
                        "vod_name": code,
                        "vod_pic": self._build_pic_url(code),
                        "vod_remarks": ""
                    })

            if not videos:
                video_links = re.findall(r'href="(/zh/video/[A-Za-z0-9-]+)"', html)
                video_links = list(dict.fromkeys(video_links))
                for vid_path in video_links:
                    slug = vid_path.replace("/zh/video/", "")
                    code = self._extract_code(slug)
                    if code and code not in seen:
                        seen.add(code)
                        videos.append({
                            "vod_id": slug,
                            "vod_name": code,
                            "vod_pic": self._build_pic_url(code),
                            "vod_remarks": ""
                        })

            if not videos:
                cover_codes = re.findall(
                    r'https://cdn\.javfree\.stream/videos/([A-Z0-9-]+)/cover\.(?:jpg|webp)',
                    html
                )
                for code in cover_codes:
                    if code not in seen:
                        seen.add(code)
                        videos.append({
                            "vod_id": code,
                            "vod_name": code,
                            "vod_pic": self._build_pic_url(code),
                            "vod_remarks": ""
                        })

        except Exception as e:
            print(f"[斗字秘] 列表解析异常: {e}")

        if not videos:
            return {"list": [], "page": pg, "pagecount": pg}

        pagecount = pg + 1 if len(videos) >= self.videoPageSize else pg
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.videoPageSize,
            "total": 9999
        }

    def detailContent(self, ids):
        vid = ids[0]

        # ═══════════════════════════════════════
        # 列字秘 · 女优详情页 —— 作品列表（集数形式）
        # ═══════════════════════════════════════
        if vid.startswith("actress/"):
            slug = vid.replace("actress/", "")

            # 检测头像
            cdn_url = f"{self.cdnUrl}/actresses/{slug}.jpg"

            data = self._fetch_json(f"{self.siteUrl}/api/actresses/{slug}")

            name = slug.replace("-", " ").title()
            codes = []
            if data:
                name = data.get("display_name") or data.get("name", name)
                fallback_url = data.get("fallback_photo_url", "")
                if self._check_pic_available(cdn_url, timeout=2):
                    pic = cdn_url
                elif fallback_url:
                    pic = fallback_url
                else:
                    pic = ""

                videos = data.get("videos", [])
                for v in videos:
                    code = v.get("code", "")
                    if code:
                        codes.append(code)

            play_urls = []
            for code in codes:
                player_url = f"{self.siteUrl}/player/?code={code}"
                play_urls.append(f"{code}${player_url}")

            vod_play_url = "#".join(play_urls) if play_urls else ""

            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": f"{len(codes)} 个作品" if codes else "女优",
                    "vod_content": f"{name} 的作品列表" if codes else f"{name} 暂无作品",
                    "vod_play_from": "作品列表" if codes else "JavFree",
                    "vod_play_url": vod_play_url
                }]
            }

        # ═══════════════════════════════════════
        # 普通视频详情页
        # ═══════════════════════════════════════
        code = self._extract_code(vid)
        url = f"{self.siteUrl}/zh/video/{vid}"
        html = self._fetch(url)

        if not html or (html.find("video-card") < 0 and html.find("playerShell") < 0 and html.find("VideoObject") < 0):
            search_html = self._fetch(f"{self.siteUrl}/zh/search?q={code}")
            if search_html:
                video_links = re.findall(r'href="(/zh/video/[A-Za-z0-9-]+)"', search_html)
                if video_links:
                    vid = video_links[0].replace("/zh/video/", "")
                    url = f"{self.siteUrl}/zh/video/{vid}"
                    html = self._fetch(url)

        if not html:
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": code,
                    "vod_pic": self._build_pic_url(code),
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "JavFree",
                    "vod_play_url": f"第1集${self.siteUrl}/player/?code={code}"
                }]
            }

        try:
            title = code
            pic = self._build_pic_url(code)
            desc = ""
            actor = ""
            studio = ""
            tags = []

            schema = re.search(
                r'<script type="application/ld\+json"[^>]*>(\{.*?VideoObject.*?\})</script>',
                html,
                re.DOTALL
            )
            if schema:
                try:
                    data = json.loads(schema.group(1))
                    title = data.get("name", title)
                    desc = data.get("description", "")
                    pic_url = data.get("thumbnailUrl", [pic])
                    if isinstance(pic_url, list) and pic_url:
                        pic = pic_url[0].replace(".webp", ".jpg").replace("?v=seo-webp-cover", "")
                    elif isinstance(pic_url, str):
                        pic = pic_url.replace(".webp", ".jpg").replace("?v=seo-webp-cover", "")

                    actors = data.get("actor", [])
                    if actors:
                        actor = ", ".join([a.get("name", "") for a in actors if a.get("name")])

                    prod = data.get("productionCompany", {})
                    if prod:
                        studio = prod.get("name", "")

                    keywords = data.get("keywords", "")
                    if keywords:
                        tags = [t.strip() for t in str(keywords).split(",") if t.strip()]
                except Exception as e:
                    print(f"[斗字秘] Schema解析异常: {e}")

            player_url = f"{self.siteUrl}/player/?code={code}"

            remarks = ""
            if studio and actor:
                remarks = f"{studio} · {actor}"
            elif studio:
                remarks = studio
            elif actor:
                remarks = actor
            elif tags:
                remarks = ", ".join(tags[:3])

            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "vod_content": desc,
                    "vod_play_from": "JavFree",
                    "vod_play_url": f"第1集${player_url}"
                }]
            }

        except Exception as e:
            print(f"[斗+兵字秘] 详情解析异常: {e}")
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": code,
                    "vod_pic": self._build_pic_url(code),
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "JavFree",
                    "vod_play_url": f"第1集${self.siteUrl}/player/?code={code}"
                }]
            }

    def playerContent(self, flag, id, vipFlags):
        if not id.startswith("http"):
            return {"parse": 0, "url": id, "header": ""}

        if "/player/?code=" not in id:
            return {"parse": 0, "url": id, "header": ""}

        html = self._fetch(id)
        if not html:
            return {"parse": 1, "url": id, "header": ""}

        try:
            sources_match = re.search(r'var sources\s*=\s*(\[.*?\]);', html, re.DOTALL)
            if sources_match:
                sources = json.loads(sources_match.group(1))

                best_source = None
                for src in sources:
                    if src.get("type") == "hls" and src.get("url"):
                        if not src.get("backup_only", False):
                            best_source = src
                            break

                if not best_source:
                    for src in sources:
                        if src.get("type") == "hls" and src.get("url"):
                            best_source = src
                            break

                if not best_source:
                    for src in sources:
                        if src.get("type") in ["iframe", "embed"] and src.get("url"):
                            return {"parse": 1, "url": src["url"], "header": ""}

                if best_source:
                    m3u8 = best_source["url"]
                    header = f"Referer={self.siteUrl}/&User-Agent={quote(self.ua)}"
                    return {"parse": 0, "url": m3u8, "header": header}

            m3u8_match = re.search(
                r'(https://cdn\.javfree\.stream/videos/[A-Z0-9-]+/master\.m3u8\?token=[^\s"\'<>]+)',
                html
            )
            if m3u8_match:
                m3u8 = m3u8_match.group(1)
                header = f"Referer={self.siteUrl}/&User-Agent={quote(self.ua)}"
                return {"parse": 0, "url": m3u8, "header": header}

            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                return {"parse": 1, "url": iframe_match.group(1), "header": ""}

        except Exception as e:
            print(f"[兵字秘] 播放解析异常: {e}")

        return {"parse": 1, "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg)
        url = f"{self.siteUrl}/zh/search?q={quote(key)}&page={pg}"
        html = self._fetch(url)

        if not html:
            return {"list": [], "page": pg}

        videos = []
        try:
            seen = set()

            code_matches = re.findall(r'data-video-code="([^"]+)"', html)
            for code in code_matches:
                if code not in seen:
                    seen.add(code)
                    videos.append({
                        "vod_id": code,
                        "vod_name": code,
                        "vod_pic": self._build_pic_url(code),
                        "vod_remarks": "SEARCH"
                    })

            if not videos:
                video_links = re.findall(r'href="(/zh/video/[A-Za-z0-9-]+)"', html)
                video_links = list(dict.fromkeys(video_links))
                for vid_path in video_links:
                    slug = vid_path.replace("/zh/video/", "")
                    code = self._extract_code(slug)
                    if code and code not in seen:
                        seen.add(code)
                        videos.append({
                            "vod_id": slug,
                            "vod_name": code,
                            "vod_pic": self._build_pic_url(code),
                            "vod_remarks": "SEARCH"
                        })

        except Exception as e:
            print(f"[列字秘] 搜索异常: {e}")

        return {"list": videos, "page": pg}

    def localProxy(self, param):
        try:
            import urllib.parse

            params = {}
            if isinstance(param, str) and param.startswith("?"):
                for kv in param[1:].split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        params[k] = urllib.parse.unquote(v)

            url = params.get("url", "")
            referer = params.get("referer", self.siteUrl)

            try:
                real_url = base64.b64decode(url).decode("utf-8")
            except:
                real_url = url

            try:
                real_ref = base64.b64decode(referer).decode("utf-8")
            except:
                real_ref = referer

            if not real_url:
                return [404, "application/json", json.dumps({"error": "no url"})]

            headers = {
                "User-Agent": self.ua,
                "Referer": real_ref or self.siteUrl,
                "Accept": "*/*",
            }

            req = urllib.request.Request(real_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                data = resp.read()

                if "mpegurl" in content_type or real_url.endswith(".m3u8"):
                    text = data.decode("utf-8", errors="ignore")
                    lines = text.split("\n")
                    cleaned = []
                    skip = False
                    for line in lines:
                        l = line.strip()
                        if any(kw in l.lower() for kw in ["ad", "advert", "tracking", "analytics"]):
                            skip = True
                            continue
                        if skip and l.startswith("#EXTINF"):
                            skip = False
                            continue
                        cleaned.append(line)
                    data = "\n".join(cleaned).encode("utf-8")

                return [200, content_type, data]

        except Exception as e:
            return [500, "application/json", json.dumps({"error": str(e)})]


class Spider(JavFree):
    pass

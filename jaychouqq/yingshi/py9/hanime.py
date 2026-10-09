import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
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
    def __init__(self):
        super(Spider, self).__init__()
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.defaultHost = "https://www.hanime101.com"
        self.siteUrl = self.defaultHost
        self.siteName = "Hanime1"
        self.entryPath = "/enter"
        self.cacheKey = "hanime1_dynamic_site_url"
        self.mirrorPool = [
            "https://www.hanime101.com",
            "https://hanime1.me",
            "https://www.hanime1.me",
            "https://hanime1.com"
        ]
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        cached_site = self.getCache(self.cacheKey)
        if cached_site and str(cached_site).startswith("http"):
            self.siteUrl = str(cached_site).strip().rstrip("/")
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "Hanime1·动态发布自愈版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    def _check_host_alive(self, base_url):
        target = "%s%s" % (base_url.rstrip("/"), self.entryPath)
        res = self._fetch(target, check_host=False)
        return res.get("code") == 200

    def _refresh_site_url(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            text = ""
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                try:
                    raw = e.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
            except Exception:
                continue

            if not text:
                continue

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and (self.siteName in unquoted or "hanime" in unquoted.lower()):
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name = item.get("name", "").strip()
                            if self.siteName.lower() in name.lower():
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    if self._check_host_alive(base):
                                        self.siteUrl = base
                                        self.setCache(self.cacheKey, base)
                                        return True
                except Exception:
                    continue

        for fallback in self.mirrorPool:
            if self._check_host_alive(fallback):
                self.siteUrl = fallback
                self.setCache(self.cacheKey, fallback)
                return True

        return False

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + self.entryPath),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        domain_retried = False

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 451, 500, 502, 503) and check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache(self.cacheKey)
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                return {"code": e.code, "text": "", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache(self.cacheKey)
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        classes = [
            {"type_id": "裏番", "type_name": "里番"},
            {"type_id": "泡麵番", "type_name": "泡面番"},
            {"type_id": "Motion Anime", "type_name": "Motion Anime"},
            {"type_id": "3DCG", "type_name": "3DCG"},
            {"type_id": "2.5D", "type_name": "2.5D"},
            {"type_id": "2D動畫", "type_name": "2D动画"},
            {"type_id": "AI生成", "type_name": "AI生成"},
            {"type_id": "MMD", "type_name": "MMD"},
            {"type_id": "Cosplay", "type_name": "Cosplay"},
            {"type_id": "新番預告", "type_name": "新番预告"}
        ]

        sort_filter = {
            "key": "sort",
            "name": "排序",
            "value": [
                {"n": "最新上傳", "v": "最新上傳"},
                {"n": "本日排行", "v": "本日排行"},
                {"n": "本週排行", "v": "本週排行"},
                {"n": "本月排行", "v": "本月排行"}
            ]
        }

        filters = {}
        for c in classes:
            filters[c["type_id"]] = [sort_filter]

        return {
            "class": classes,
            "filters": filters
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg and str(pg).isdigit() else 1
        sort_val = ""
        if extend and isinstance(extend, dict):
            sort_val = extend.get("sort", "")

        query_params = {
            "genre": tid,
            "page": str(page)
        }
        if sort_val:
            query_params["sort"] = sort_val

        query_str = urllib.parse.urlencode(query_params)
        req_path = "/search?%s" % query_str

        res = self._fetch(req_path)
        html_text = res.get("text", "")

        vod_list = []
        card_blocks = re.findall(r'<a[^>]*href=["\'](?:https?://[^/]+)?(/watch\?v=\d+)[^"\']*["\'][^>]*>(.*?)</a>', html_text, re.I | re.S)

        seen_ids = set()
        for href, inner_html in card_blocks:
            v_id_match = re.search(r'v=(\d+)', href)
            if not v_id_match:
                continue
            vod_id = v_id_match.group(1)
            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)

            title_match = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', inner_html, re.I)
            if not title_match:
                title_match = re.search(r'<div[^>]*class=["\'][^"\']*(?:title|caption|text)[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)

            raw_title = ""
            if title_match:
                raw_title = title_match.group(1)
                raw_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                raw_title = html_lib.unescape(raw_title)

            img_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', inner_html, re.I)
            vod_pic = img_match.group(1).strip() if img_match else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            duration_match = re.search(r'<div[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)
            raw_duration = re.sub(r'<[^>]+>', '', duration_match.group(1)).strip() if duration_match else ""

            vod_remarks = ("🦋 蝴蝶影视 | %s" % raw_duration) if raw_duration else "🦋 蝴蝶影视"

            if raw_title:
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": raw_title,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks
                })

        page_count = page
        max_page_matches = re.findall(r'[?&]page=(\d+)', html_text)
        if max_page_matches:
            found_pages = [int(p) for p in max_page_matches]
            page_count = max(max(found_pages), page + 1)
        elif len(vod_list) >= 12:
            page_count = page + 1

        return {
            "page": page,
            "pagecount": page_count,
            "limit": len(vod_list) if vod_list else 20,
            "total": page_count * 20,
            "list": vod_list
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else str(ids)
        watch_path = "/watch?v=%s" % vod_id

        res = self._fetch(watch_path)
        html_text = res.get("text", "")

        title_m = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.I)
        if not title_m:
            title_m = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.I | re.S)
        vod_name = html_lib.unescape(title_m.group(1).strip()) if title_m else "Hanime_%s" % vod_id

        pic_m = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic

        desc_m = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.I)
        if not desc_m:
            desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.I)
        raw_desc = html_lib.unescape(desc_m.group(1).strip()) if desc_m else ""

        episodes_1080 = ["正片$/watch?v=%s@1080p" % vod_id]
        episodes_720 = ["正片$/watch?v=%s@720p" % vod_id]
        episodes_480 = ["正片$/watch?v=%s@480p" % vod_id]
        seen_eps = set([str(vod_id)])

        playlist_box = re.search(r'<div[^>]*class=["\'][^"\']*playlist-scroll-node[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', html_text, re.I | re.S)
        scope_html = playlist_box.group(1) if playlist_box else html_text

        related = re.findall(r'<a[^>]*href=["\'](?:https?://[^/]+)?(/watch\?v=\d+)[^"\']*["\'][^>]*>(.*?)</a>', scope_html, re.I | re.S)
        ep_counter = 1
        for r_href, r_body in related:
            r_id_m = re.search(r'v=(\d+)', r_href)
            if not r_id_m:
                continue
            r_id = r_id_m.group(1)
            if r_id in seen_eps:
                continue
            seen_eps.add(r_id)

            t_m = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', r_body, re.I)
            clean_name = html_lib.unescape(t_m.group(1).strip()) if t_m else ""
            if not clean_name:
                clean_name = "第%02d集" % ep_counter

            episodes_1080.append("%s$/watch?v=%s@1080p" % (clean_name, r_id))
            episodes_720.append("%s$/watch?v=%s@720p" % (clean_name, r_id))
            episodes_480.append("%s$/watch?v=%s@480p" % (clean_name, r_id))
            ep_counter += 1
            if len(episodes_1080) >= 40:
                break

        play_from = "🦋 1080P超清$$$🦋 720P高清$$$🦋 480P标清"
        play_url = "%s$$$%s$$$%s" % ("#".join(episodes_1080), "#".join(episodes_720), "#".join(episodes_480))

        full_desc = (
            "【🔥 官方交流群: https://t.me/tvshare23】\n"
            "【当前发布域名: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.siteUrl, raw_desc if raw_desc else "Hanime 动漫原画精品。")

        return {
            "list": [
                {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "type_name": "动漫",
                    "vod_year": "2026",
                    "vod_area": "日本",
                    "vod_actor": "🦋 TG群: @tvshare23",
                    "vod_director": "🦋 蝴蝶影视",
                    "vod_content": full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                    "vod_play_from": play_from,
                    "vod_play_url": play_url
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        target_res = ""
        raw_target = id
        if "@" in raw_target:
            parts = raw_target.split("@")
            raw_target = parts[0]
            target_res = parts[1].lower()

        res = self._fetch(raw_target)
        html_text = res.get("text", "")

        play_stream_url = ""
        header = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/"
        }

        src_matches = re.findall(r'<source[^>]*src=["\']([^"\']+)["\']', html_text, re.I)
        if src_matches:
            p1080 = [u for u in src_matches if "1080p" in u.lower()]
            p720 = [u for u in src_matches if "720p" in u.lower()]
            p480 = [u for u in src_matches if "480p" in u.lower()]

            if target_res == "1080p" and p1080:
                play_stream_url = p1080[0]
            elif target_res == "720p" and p720:
                play_stream_url = p720[0]
            elif target_res == "480p" and p480:
                play_stream_url = p480[0]
            else:
                if p1080:
                    play_stream_url = p1080[0]
                elif p720:
                    play_stream_url = p720[0]
                elif p480:
                    play_stream_url = p480[0]
                else:
                    play_stream_url = src_matches[0]

        if not play_stream_url:
            all_mp4 = re.findall(r'["\'](https?:[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
            if all_mp4:
                play_stream_url = all_mp4[0]

        return {
            "parse": 0,
            "playUrl": "",
            "url": play_stream_url,
            "header": header
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        page = int(pg) if pg and str(pg).isdigit() else 1
        query_params = {
            "query": str(key).strip(),
            "page": str(page)
        }
        query_str = urllib.parse.urlencode(query_params)
        req_path = "/search?%s" % query_str

        vod_list = []
        try:
            res = self._fetch(req_path)
            html_text = res.get("text", "")
            card_blocks = re.findall(r'<a[^>]*href=["\'](?:https?://[^/]+)?(/watch\?v=\d+)[^"\']*["\'][^>]*>(.*?)</a>', html_text, re.I | re.S)

            seen_ids = set()
            for href, inner_html in card_blocks:
                v_id_match = re.search(r'v=(\d+)', href)
                if not v_id_match:
                    continue
                vod_id = v_id_match.group(1)
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)

                title_match = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', inner_html, re.I)
                if not title_match:
                    title_match = re.search(r'<div[^>]*class=["\'][^"\']*(?:title|caption|text)[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)

                raw_title = ""
                if title_match:
                    raw_title = title_match.group(1)
                    raw_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                    raw_title = html_lib.unescape(raw_title)

                img_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', inner_html, re.I)
                vod_pic = img_match.group(1).strip() if img_match else ""
                if vod_pic.startswith("//"):
                    vod_pic = "https:" + vod_pic

                duration_match = re.search(r'<div[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)
                raw_duration = re.sub(r'<[^>]+>', '', duration_match.group(1)).strip() if duration_match else ""

                vod_remarks = ("🦋 蝴蝶影视 | %s" % raw_duration) if raw_duration else "🦋 蝴蝶影视"

                if raw_title:
                    vod_list.append({
                        "vod_id": vod_id,
                        "vod_name": raw_title,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
        except Exception:
            vod_list = []

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": len(vod_list) if vod_list else 20,
            "total": 100,
            "list": vod_list
        }

    def action(self, action):
        if action == "toast":
            return {"msg": "当前有效发布域: %s" % self.siteUrl}
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
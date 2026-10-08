#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        def setCache(self, key, value): "fail"
        def delCache(self, key): "fail"


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        # 发布导航站双活入口与默认兜底主站
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.defaultHost = "https://zh.xhamster1.art"
        self.siteUrl = self.defaultHost
        self.siteName = "xhamster"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

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

        # 启动优先从本地持久化缓存读取最新解析到的有效主站
        cached_site = self.getCache("xhamster_dynamic_site_url")
        if cached_site and cached_site.startswith("http"):
            self.siteUrl = cached_site.strip().rstrip("/")
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "xHamster·动态发布自愈版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    # 核心：复用 X99 导航站 Base64+URL二次反解与矩阵探测引擎，精准提取 xhamster
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

            # 扫描并反解页面内嵌入的长 Base64 数据块
            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and self.siteName.lower() in unquoted.lower():
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name = item.get("name", "").strip().lower()
                            if name == self.siteName.lower():
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                # 提取根域名并发送轻量验活
                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/newest", check_host=False)
                                    if chk.get("code") == 200:
                                        self.siteUrl = base
                                        self.setCache("xhamster_dynamic_site_url", base)
                                        return True
                except Exception:
                    continue

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
            "Referer": referer if referer else (self.siteUrl + "/newest"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        last_err = ""
        domain_retried = False

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
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
                if e.code in (404, 451, 502, 503) and check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("xhamster_dynamic_site_url")
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
                    self.delCache("xhamster_dynamic_site_url")
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
        result = {
            "class": [
                {"type_name": "🔥 最新视频", "type_id": "/newest"},
                {"type_name": "🏆 最佳视频", "type_id": "/best"},
                {"type_name": "👀 最多观看", "type_id": "/most-viewed"},
                {"type_name": "⭐ 每周最佳", "type_id": "/best/weekly"},
                {"type_name": "👑 每月最佳", "type_id": "/best/monthly"},
                {"type_name": "4K 色情", "type_id": "/categories/4k"},
                {"type_name": "高清视频 HD", "type_id": "/categories/hd"},
                {"type_name": "虚拟现实 VR", "type_id": "/categories/vr"},
                {"type_name": "18岁", "type_id": "/categories/18-years-old"},
                {"type_name": "3P", "type_id": "/categories/threesome"},
                {"type_name": "中国人 🇨🇳", "type_id": "/categories/chinese"},
                {"type_name": "亚洲人", "type_id": "/categories/asian"},
                {"type_name": "人妻", "type_id": "/categories/housewives"},
                {"type_name": "人母", "type_id": "/categories/milf"},
                {"type_name": "俄罗斯人 🇷🇺", "type_id": "/categories/russian"},
                {"type_name": "共享妻子", "type_id": "/categories/cuckold"},
                {"type_name": "内射", "type_id": "/categories/creampie"},
                {"type_name": "出轨", "type_id": "/categories/cheating"},
                {"type_name": "卡通 / 动漫", "type_id": "/categories/hentai"},
                {"type_name": "印尼人 🇮🇩", "type_id": "/categories/indonesian"},
                {"type_name": "印度人 🇮🇳", "type_id": "/categories/indian"},
                {"type_name": "变性色情 ⚧", "type_id": "/categories/transgender"},
                {"type_name": "口交", "type_id": "/categories/blowjob"},
                {"type_name": "口爆", "type_id": "/categories/cum-in-mouth"},
                {"type_name": "台湾人 🇹🇼", "type_id": "/categories/taiwanese"},
                {"type_name": "合集", "type_id": "/categories/compilation"},
                {"type_name": "同性恋 ♿", "type_id": "/categories/gay"},
                {"type_name": "后入式", "type_id": "/categories/doggy-style"},
                {"type_name": "哥伦比亚人 🇨🇴", "type_id": "/categories/colombian"},
                {"type_name": "处女 18+", "type_id": "/categories/first-time"},
                {"type_name": "复古", "type_id": "/categories/vintage"},
                {"type_name": "多对一群交", "type_id": "/categories/gangbang"},
                {"type_name": "大奶子", "type_id": "/categories/big-tits"},
                {"type_name": "大屁股", "type_id": "/categories/big-ass"},
                {"type_name": "大肉棒", "type_id": "/categories/big-dick"},
                {"type_name": "大黑屌", "type_id": "/categories/bbc"},
                {"type_name": "天然巨乳", "type_id": "/categories/natural-tits"},
                {"type_name": "女主调教", "type_id": "/categories/femdom"},
                {"type_name": "女同", "type_id": "/categories/lesbian"},
                {"type_name": "女性自慰", "type_id": "/categories/masturbation"},
                {"type_name": "女性色情 ♀", "type_id": "/categories/for-women"},
                {"type_name": "女牛仔", "type_id": "/categories/cowgirl"},
                {"type_name": "奶奶 / 老熟女", "type_id": "/categories/granny"},
                {"type_name": "妻子", "type_id": "/categories/wife"},
                {"type_name": "娇小", "type_id": "/categories/petite"},
                {"type_name": "学生 18+", "type_id": "/categories/college"},
                {"type_name": "宝贝", "type_id": "/categories/babes"},
                {"type_name": "家庭主妇", "type_id": "/categories/housewife"},
                {"type_name": "家庭自制", "type_id": "/categories/homemade"},
                {"type_name": "射精", "type_id": "/categories/cumshots"},
                {"type_name": "尼泊尔人 🇳🇵", "type_id": "/categories/nepali"},
                {"type_name": "怀孕", "type_id": "/categories/pregnant"},
                {"type_name": "情侣", "type_id": "/categories/couples"},
                {"type_name": "成人动漫", "type_id": "/categories/anime"},
                {"type_name": "成熟", "type_id": "/categories/mature"},
                {"type_name": "按摩", "type_id": "/categories/massage"},
                {"type_name": "捆绑 SM", "type_id": "/categories/bdsm"},
                {"type_name": "故事", "type_id": "/categories/story"},
                {"type_name": "无码", "type_id": "/categories/uncensored"},
                {"type_name": "日本 AV", "type_id": "/categories/jav"},
                {"type_name": "日本人 🇯🇵", "type_id": "/categories/japanese"},
                {"type_name": "明星", "type_id": "/categories/celebrity"},
                {"type_name": "欧洲人", "type_id": "/categories/european"},
                {"type_name": "毛发浓密", "type_id": "/categories/hairy"},
                {"type_name": "泰国人 🇹🇭", "type_id": "/categories/thai"},
                {"type_name": "特写", "type_id": "/categories/close-up"},
                {"type_name": "粗暴性爱", "type_id": "/categories/rough-sex"},
                {"type_name": "素人", "type_id": "/categories/amateur"},
                {"type_name": "美国人 🇺🇸", "type_id": "/categories/american"},
                {"type_name": "美女", "type_id": "/categories/beauty"},
                {"type_name": "群交", "type_id": "/categories/group-sex"},
                {"type_name": "老熟女", "type_id": "/categories/old-mature"},
                {"type_name": "肛交", "type_id": "/categories/anal"},
                {"type_name": "胖美女", "type_id": "/categories/bbw"},
                {"type_name": "舔阴", "type_id": "/categories/cunnilingus"},
                {"type_name": "色情作品", "type_id": "/categories/erotica"},
                {"type_name": "菲律宾女人 🇵🇭", "type_id": "/categories/filipino"},
                {"type_name": "裸体", "type_id": "/categories/nudity"},
                {"type_name": "越南人 🇻🇳", "type_id": "/categories/vietnamese"},
                {"type_name": "足交", "type_id": "/categories/footjob"},
                {"type_name": "重口味", "type_id": "/categories/hardcore"}
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def _extract_balanced_array(self, text, start_idx):
        if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "[":
            return None
        depth = 0
        in_str = False
        escaped = False
        i = start_idx
        while i < len(text):
            ch = text[i]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        return text[start_idx:i + 1]
            i += 1
        return None

    def _pick_str(self, obj, keys):
        if not isinstance(obj, dict):
            return ""
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _parse_json_list(self, html_text):
        cards = []
        seen = set()

        anchors = []
        for key in ('"videoThumbProps":[', '"videoListProps":[', '"items":['):
            pos = html_text.find(key)
            if pos != -1:
                anchors.append(html_text.find("[", pos))

        for anchor in anchors:
            arr_text = self._extract_balanced_array(html_text, anchor)
            if not arr_text:
                continue
            try:
                data = json.loads(arr_text)
            except Exception:
                continue
            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue

                page_url = self._pick_str(item, ("pageURL", "pageUrl", "url"))
                if not page_url:
                    continue

                path = page_url
                if path.startswith("http"):
                    m = re.search(r"/videos/[^/?#]+", path)
                    if m:
                        path = m.group(0)
                if not path.startswith("/videos/"):
                    continue
                if path in seen:
                    continue

                img = self._pick_str(item, ("thumbURL", "thumbUrl", "imageURL", "imageUrl"))
                if not img:
                    img = self._pick_str(item.get("cover"), ("thumbURL", "thumbUrl", "imageURL", "url"))
                if img.startswith("//"):
                    img = "https:" + img

                title = self._pick_str(item, ("title", "name"))
                if not title:
                    clean_slug = path.rsplit("-", 1)[0].rsplit("/", 1)[-1].replace("-", " ")
                    title = clean_slug.capitalize() if clean_slug else ""

                dur = item.get("duration")
                if isinstance(dur, (int, float)) and dur > 0:
                    total = int(dur)
                    remarks = "%d:%02d" % (total // 60, total % 60)
                else:
                    remarks = "HD"

                seen.add(path)

                payload = {"url": path, "title": html_lib.unescape(title)}
                b64_info = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

                cards.append({
                    "vod_id": "pkg_" + b64_info,
                    "vod_name": html_lib.unescape(title),
                    "vod_pic": img,
                    "vod_remarks": remarks,
                    "style": {"type": "rect", "ratio": 1.78},
                })

            if cards:
                return cards

        return cards

    def _parse_vod_list(self, html_text):
        if not html_text:
            return []

        cards = self._parse_json_list(html_text)
        if cards:
            return cards

        cards = []
        seen = set()
        for block in re.findall(r"<img[^>]+>", html_text, re.I):
            m_src = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', block, re.I)
            if not m_src:
                continue
            img = m_src.group(1).strip()
            if img.startswith("//"):
                img = "https:" + img
            if not img.startswith("http"):
                continue

            m_alt = re.search(r'alt=["\']([^"\']+)["\']', block, re.I)
            title = html_lib.unescape(m_alt.group(1).strip()) if m_alt else ""
            if not title:
                continue

            if img in seen:
                continue
            seen.add(img)

            cards.append({
                "vod_id": "",
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": "HD",
                "style": {"type": "rect", "ratio": 0.75},
            })

        if not cards:
            cards.append({
                "vod_id": "",
                "vod_name": "加载失败",
                "vod_pic": "https://dummyimage.com/400x225/111827/ffffff.png&text=No+Image",
                "vod_remarks": "",
                "style": {"type": "rect", "ratio": 0.75},
            })

        return cards

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        page_num = int(pg) if str(pg).isdigit() else 1

        path = str(tid).strip()
        if path.endswith("/"):
            path = path[:-1]

        if "/search/" in path:
            sep = "&" if "?" in path else "?"
            req_url = "%s%spage=%d" % (path, sep, page_num)
        else:
            req_url = "%s/%d" % (path, page_num) if page_num > 1 else path

        res = self._fetch(req_url)
        cards = self._parse_vod_list(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 12 else page_num,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_path = ""
        cached_title = ""

        if str(raw_id).startswith("pkg_"):
            try:
                b64_str = raw_id[4:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                pkg = json.loads(base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8"))
                target_path = pkg.get("url", "")
                cached_title = pkg.get("title", "")
            except Exception:
                target_path = raw_id
        else:
            target_path = str(raw_id).strip()

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        vod_name = cached_title
        if not vod_name:
            m_schema = re.search(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']', html_text)
            if m_schema:
                cand = m_schema.group(1).strip()
                if cand and cand != "VideoObject":
                    vod_name = html_lib.unescape(cand)

        if not vod_name:
            h1_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
            if h1_m:
                clean_h1 = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
                if clean_h1:
                    vod_name = html_lib.unescape(clean_h1)

        if not vod_name:
            name_m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
            if name_m:
                raw_title = html_lib.unescape(name_m.group(1).strip())
                for brand in ["- xHamster", "| xHamster", "xHamster"]:
                    raw_title = raw_title.replace(brand, "")
                vod_name = raw_title.strip(" -|_")

        if not vod_name:
            vod_name = "xHamster 极速正片"

        vod_pic = ""
        pic_m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if not pic_m:
            pic_m = re.search(r'poster:\s*["\']([^"\']+)["\']', html_text)
        if pic_m:
            vod_pic = pic_m.group(1).strip()

        stream_url = ""
        m_hls = re.search(r'https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*', html_text)
        if m_hls:
            stream_url = m_hls.group(0).replace("\\/", "/")

        if not stream_url:
            m_mp4 = re.search(r'https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*', html_text)
            if m_mp4:
                stream_url = m_mp4.group(0).replace("\\/", "/")

        play_lines = []
        if stream_url:
            play_lines.append("自适应原画$%s" % stream_url)

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "【当前发布域名: %s】\n"
            "【资源路径】: %s\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "xHamster 官方 CDN 多码率直连专线"
        ) % (self.tgGroup, self.siteUrl, target_path)

        escaped_desc = full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": html_lib.unescape(vod_name),
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "HD原画",
                "vod_content": escaped_desc,
                "vod_play_from": "xHamster专线",
                "vod_play_url": "#".join(play_lines) if play_lines else "正片$http://127.0.0.1"
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()

        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl
        }

        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": headers,
            "contentType": "application/x-mpegURL" if ".m3u8" in play_url else "video/mp4",
            "format": "hls" if ".m3u8" in play_url else "mp4",
            "position": 1
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        page_num = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(str(key).strip())

        search_url = "/search/videos/%s?page=%d" % (encoded_key, page_num)
        res = self._fetch(search_url)
        cards = self._parse_vod_list(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 12 else page_num,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def action(self, action):
        if action == "toast":
            return {"msg": "当前有效主站: %s" % self.siteUrl}
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}

# coding=utf-8
import re
import json
import requests
import base64
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):

    def init(self, extend=""):
        self.name = "JavGG"
        self.hosts = [
            "https://javgg.co",
            "https://javgg.net",
            "https://javgg.club"
        ]
        self.host = "https://javgg.co"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://javgg.co/",
            "Connection": "keep-alive"
        }
        self.proxies = None
        # 有代理取消注释
        # self.proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

    def getName(self):
        return "JavGG"

    def get_html(self, url, timeout=12):
        for h in self.hosts:
            try:
                real_url = url
                if self.host in url:
                    real_url = url.replace(self.host, h)
                elif not url.startswith("http"):
                    real_url = h.rstrip("/") + "/" + url.lstrip("/")
                r = requests.get(
                    real_url,
                    headers={**self.header, "Referer": h + "/"},
                    timeout=timeout,
                    verify=False,
                    proxies=self.proxies,
                    allow_redirects=True
                )
                if r.status_code == 200 and len(r.text) > 1500:
                    self.host = h
                    self.header["Referer"] = h + "/"
                    return r.text
            except:
                continue
        return ""

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def clean_text(self, text):
        if not text:
            return ""
        return re.sub(r'\s+', ' ', str(text)).strip()

    def get_pic(self, html, vod_id=""):
        # 多种方式尝试提取封面
        patterns = [
            r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\'][^>]*(?:alt=["\'][^"\']*' + re.escape(vod_id) + r'[^"\']*["\'])?',
            r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'data-src=["\']([^"\']+)["\']',
            r'src=["\']([^"\']+(?:cover|poster|thumb|jav)[^"\']*)["\']'
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                pic = self.fix_url(m.group(1))
                if pic and ("http" in pic) and not pic.endswith(".svg"):
                    return pic
        return ""

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "最新", "type_id": "home"},
                {"type_name": "无码", "type_id": "tag/hd-uncensored"},
                {"type_name": "有码", "type_id": "tag/censored"},
                {"type_name": "英字", "type_id": "tag/english-subtitle"},
                {"type_name": "中字", "type_id": "tag/chinese-subtitle"},
                {"type_name": "素人", "type_id": "tag/amateur-jav"},
                {"type_name": "中出", "type_id": "genre/creampie"},
                {"type_name": "巨乳", "type_id": "genre/big-tits"},
                {"type_name": "人妻", "type_id": "genre/married-woman"},
                {"type_name": "美少女", "type_id": "genre/beautiful-girl"},
                {"type_name": "熟女", "type_id": "genre/mature-woman"},
                {"type_name": "4K", "type_id": "genre/4k"}
            ],
            "list": []
        }
        html = self.get_html(self.host)
        if html:
            # 尝试成对提取 图片 + 番号
            items = re.findall(
                r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\'][^>]*>.*?(?:href=["\'][^"\']*?/jav/([a-zA-Z0-9\-_]+)/?["\'][^>]*>\s*([A-Z0-9\-_]+)|/jav/([a-zA-Z0-9\-_]+)/)',
                html, re.I | re.S
            )
            seen = set()
            for it in items:
                try:
                    pic = self.fix_url(it[0])
                    vod_id = (it[1] or it[3] or "").strip("-_").lower()
                    name = it[2] if it[2] else vod_id
                    if not vod_id or len(vod_id) < 4 or vod_id in seen:
                        continue
                    seen.add(vod_id)
                    result["list"].append({
                        "vod_id": vod_id,
                        "vod_name": self.clean_text(name) or vod_id.upper(),
                        "vod_pic": pic if "http" in pic else "",
                        "vod_remarks": ""
                    })
                except:
                    continue

            # 兜底：只提取番号
            if len(result["list"]) < 5:
                patterns = [
                    r'href=["\']([^"\']*?/jav/([a-zA-Z0-9\-_]+)/?)["\'][^>]*>\s*([A-Z0-9\-_]+)',
                    r'/jav/([a-zA-Z0-9\-_]+)/["\'][^>]*>\s*([A-Z0-9\-_]+)'
                ]
                for pat in patterns:
                    for it in re.findall(pat, html, re.I | re.S):
                        try:
                            if len(it) >= 2:
                                vod_id = it[1]
                                name = it[2] if len(it) > 2 else vod_id
                                vod_id = re.sub(r'[^a-zA-Z0-9\-_]', '', str(vod_id)).strip("-_").lower()
                                if not vod_id or len(vod_id) < 4 or vod_id in seen:
                                    continue
                                seen.add(vod_id)
                                result["list"].append({
                                    "vod_id": vod_id,
                                    "vod_name": self.clean_text(name) or vod_id.upper(),
                                    "vod_pic": "",
                                    "vod_remarks": ""
                                })
                        except:
                            continue
                    if len(result["list"]) >= 20:
                        break
        return json.dumps(result, ensure_ascii=False)

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 9999, "limit": 40, "total": 999999}
        if tid == "home":
            url = self.host if str(pg) == "1" else f"{self.host}/page/{pg}/"
        else:
            url = f"{self.host}/{tid}/" if str(pg) == "1" else f"{self.host}/{tid}/page/{pg}/"
        html = self.get_html(url)
        if html:
            items = re.findall(
                r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\'][^>]*>.*?(?:href=["\'][^"\']*?/jav/([a-zA-Z0-9\-_]+)/?["\'][^>]*>\s*([A-Z0-9\-_]+)|/jav/([a-zA-Z0-9\-_]+)/)',
                html, re.I | re.S
            )
            seen = set()
            for it in items:
                try:
                    pic = self.fix_url(it[0])
                    vod_id = (it[1] or it[3] or "").strip("-_").lower()
                    name = it[2] if it[2] else vod_id
                    if not vod_id or len(vod_id) < 4 or vod_id in seen:
                        continue
                    seen.add(vod_id)
                    result["list"].append({
                        "vod_id": vod_id,
                        "vod_name": self.clean_text(name) or vod_id.upper(),
                        "vod_pic": pic if "http" in pic else "",
                        "vod_remarks": ""
                    })
                except:
                    continue

            if len(result["list"]) < 5:
                patterns = [
                    r'href=["\']([^"\']*?/jav/([a-zA-Z0-9\-_]+)/?)["\'][^>]*>\s*([A-Z0-9\-_]+)',
                    r'/jav/([a-zA-Z0-9\-_]+)/["\'][^>]*>\s*([A-Z0-9\-_]+)'
                ]
                for pat in patterns:
                    for it in re.findall(pat, html, re.I | re.S):
                        try:
                            if len(it) >= 2:
                                vod_id = it[1]
                                name = it[2] if len(it) > 2 else vod_id
                                vod_id = re.sub(r'[^a-zA-Z0-9\-_]', '', str(vod_id)).strip("-_").lower()
                                if not vod_id or len(vod_id) < 4 or vod_id in seen:
                                    continue
                                seen.add(vod_id)
                                result["list"].append({
                                    "vod_id": vod_id,
                                    "vod_name": self.clean_text(name) or vod_id.upper(),
                                    "vod_pic": "",
                                    "vod_remarks": ""
                                })
                        except:
                            continue
        return json.dumps(result, ensure_ascii=False)

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            url = f"{self.host}/jav/{vod_id}/"
            html = self.get_html(url)
            if html:
                title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
                title = self.clean_text(title_m.group(1)) if title_m else vod_id.upper()
                pic = self.get_pic(html, vod_id)

                play_from = []
                play_url = []
                servers = re.findall(r'(?:Server|server)\s*([A-Z]{2})', html, re.I) or ["VH", "TB", "SW"]
                for s in servers:
                    play_from.append(s)
                    play_url.append(f"{s}${url}#{s}")

                if not play_from:
                    play_from = ["JavGG"]
                    play_url = [f"正片${url}"]

                result["list"].append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_content": "",
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url": "$$$".join(play_url)
                })
        except:
            pass
        return json.dumps(result, ensure_ascii=False)

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        url = f"{self.host}/?s={quote(key)}"
        if str(pg) != "1":
            url = f"{self.host}/page/{pg}/?s={quote(key)}"
        html = self.get_html(url)
        if html:
            items = re.findall(
                r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\'][^>]*>.*?(?:href=["\'][^"\']*?/jav/([a-zA-Z0-9\-_]+)/?["\'][^>]*>\s*([A-Z0-9\-_]+)|/jav/([a-zA-Z0-9\-_]+)/)',
                html, re.I | re.S
            )
            seen = set()
            for it in items:
                try:
                    pic = self.fix_url(it[0])
                    vod_id = (it[1] or it[3] or "").strip("-_").lower()
                    name = it[2] if it[2] else vod_id
                    if not vod_id or len(vod_id) < 4 or vod_id in seen:
                        continue
                    seen.add(vod_id)
                    result["list"].append({
                        "vod_id": vod_id,
                        "vod_name": self.clean_text(name) or vod_id.upper(),
                        "vod_pic": pic if "http" in pic else "",
                        "vod_remarks": ""
                    })
                except:
                    continue
        return json.dumps(result, ensure_ascii=False)

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "url": id, "header": json.dumps(self.header)}
        try:
            if any(x in id.lower() for x in [".m3u8", ".mp4", "streamwish", "vidhide", "filemoon", "dood"]):
                result["parse"] = 0 if (".m3u8" in id or ".mp4" in id) else 1
                return json.dumps(result, ensure_ascii=False)

            if "javcode.net" in id:
                m = re.search(r'javcode\.net/(?:rg|download)/([A-Za-z0-9+/=]+)', id)
                if m:
                    decoded = self.b64decode_safe(m.group(1))
                    if decoded:
                        result["url"] = decoded if decoded.startswith("http") else self.fix_url(decoded)
                return json.dumps(result, ensure_ascii=False)

            if "/jav/" in id or not id.startswith("http"):
                url = id if id.startswith("http") else f"{self.host}/jav/{id.split('#')[0].strip('/')}/"
                html = self.get_html(url)
                if html:
                    m3u8 = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html, re.I)
                    if m3u8:
                        result["url"] = m3u8.group(1)
                        result["parse"] = 0
                        return json.dumps(result, ensure_ascii=False)
                    iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
                    if iframe:
                        result["url"] = self.fix_url(iframe.group(1))
                        return json.dumps(result, ensure_ascii=False)
                result["url"] = url
        except:
            pass
        return json.dumps(result, ensure_ascii=False)

    def localProxy(self, param):
        return [200, "text/plain", ""]
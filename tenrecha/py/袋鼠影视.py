# -*- coding: utf-8 -*-
import sys
import re
import requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://dsystv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "袋鼠影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "电视剧"},
                {"type_id": "3", "type_name": "综艺"},
                {"type_id": "4", "type_name": "动漫"},
                {"type_id": "44", "type_name": "短剧"}
            ]
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        url = self.host + ("/frim/index" + str(tid) + ".html" if str(pg) == "1" else "/search.php?searchtype=5&tid=" + str(tid) + "&page=" + str(pg))
        html = self.get(url)
        return {
            "page": int(pg),
            "pagecount": 999,
            "limit": 24,
            "total": 999999,
            "list": self.parseList(html)
        }

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(self.host + "/movie/index" + vid + ".html")
        name = self.clean(self.match(html, r'<h1[^>]*>(.*?)</h1>') or self.match(html, r'<meta property="og:title" content="(.*?)"'))
        name = name.replace("全集在线观看 - 国产剧 | 袋鼠影视", "").replace("全集在线观看 - 袋鼠影视", "").replace("《", "").replace("》", "").strip()
        pic = self.fix(self.match(html, r'<meta property="og:image" content="(.*?)"') or self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+(?:data-original|data-src)=["\']([^"\']+)') or self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+src=["\']([^"\']+)'))
        desc = self.clean(self.match(html, r'<div class="plot"[^>]*>\s*<p>(.*?)</p>') or self.match(html, r'<meta property="og:description" content="(.*?)"'))
        actor = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">主演：')
        director = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">导演：')
        year = self.clean(self.match(html, r'年份：</span>([^<]+)'))
        area = self.clean(self.match(html, r'地区：</span>([^<]+)'))
        lang = self.clean(self.match(html, r'语言：</span>([^<]+)'))
        cate = self.clean(self.match(html, r'类型：</span><a[^>]*>(.*?)</a>'))
        remarks = self.clean(self.match(html, r'<span class="note textbg">(.*?)</span>'))
        tabs = re.findall(r'<a class="option"[\s\S]*?title=["\']([^"\']+)["\'][\s\S]*?</a>', html)
        panels = re.findall(r'<div[^>]+class=["\']playlist[^"\']*["\'][^>]*>\s*<ul[^>]*>([\s\S]*?)</ul>', html, re.S)
        play_from = []
        play_url = []
        for i, p in enumerate(panels):
            eps = []
            for m in re.finditer(r'<a[^>]+title=["\']([^"\']+)["\'][^>]+href=["\']([^"\']*?/play/[^"\']+)["\']', p):
                t = self.clean(m.group(1))
                u = self.fix(m.group(2))
                if t and u:
                    eps.append(t + "$" + u)
            if not eps:
                for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/[^"\']+)["\'][^>]*>(.*?)</a>', p):
                    t = self.clean(m.group(2))
                    u = self.fix(m.group(1))
                    if t and u:
                        eps.append(t + "$" + u)
            if eps:
                key = self.clean(tabs[i]) if i < len(tabs) else "线路" + str(i + 1)
                if key not in play_from:
                    play_from.append(key)
                    play_url.append("#".join(eps))
        if not play_url:
            eps = []
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/' + vid + r'-[^"\']+)["\'][^>]*>(.*?)</a>', html):
                t = self.clean(m.group(2)) or "播放"
                u = self.fix(m.group(1))
                if t and u:
                    eps.append(t + "$" + u)
            if eps:
                play_from.append("默认")
                play_url.append("#".join(eps))
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "type_name": cate,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        html = ""
        try:
            r = requests.post(self.host + "/search.php", headers=self.headers, data={"searchword": key}, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
        except Exception:
            html = ""
        data = self.parseList(html)
        if not data:
            html = self.get(self.host + "/search.php?searchword=" + quote(key) + "&page=" + str(pg))
            data = self.parseList(html)
        return {"list": data, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        html = self.get(id)
        url = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']')
        url = unquote(url) if url else id
        return {"parse": 0 if self.isVideoFormat(url) else 1, "playUrl": "", "url": url, "header": self.headers}

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""

    def clean(self, text):
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", text or "").replace("&nbsp;", " ")).strip()

    def fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*videopic[^"\']*["\'][^>]+href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\']([\s\S]{0,1200}?)</a>', html or "", re.S):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            item = m.group(0) + m.group(3)
            name = self.clean(m.group(2))
            pics = re.findall(r'(?:data-original|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            if not pics:
                pics = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            pic = ""
            for p in pics:
                if "load.gif" not in p and "nopic" not in p and "logo" not in p and "templets" not in p:
                    pic = self.fix(p)
                    break
            remarks = self.clean(self.match(item, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>') or self.match(item, r'<span[^>]+class=["\'][^"\']*textbg[^"\']*["\'][^>]*>(.*?)</span>'))
            if name:
                res.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\'][\s\S]{0,1200}?<img[^>]+([^>]+)>', html or "", re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                img = m.group(3)
                pic = self.match(img, r'(?:data-original|data-src)=["\']([^"\']+)["\']') or self.match(img, r'src=["\']([^"\']+)["\']')
                if "load.gif" in pic or "templets" in pic:
                    pic = ""
                res.append({
                    "vod_id": vid,
                    "vod_name": self.clean(m.group(2)),
                    "vod_pic": self.fix(pic),
                    "vod_remarks": ""
                })
        return res
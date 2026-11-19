#!/usr/bin/python
# coding=utf-8
# 黄色仓库-hsck.tv TVBox Python Spider v1.0.0
# 入口: https://www.hsck.net (https 301 到当前 9976hsck.cc 镜像, 2026-11-14 实测为 444.9976hsck.cc,
#   333.9976hsck.cc 仍存活作备用; 注意 http://www.hsck.net/ 只回 423 字节 JS 跳转壳, 必须走 https)
# 播放链: 详情页 /v5/{id}-1-1.html 取 AK='64位hex' -> POST /static/count.php
#   (form: id,sid=1,nid=1,tk,x=200,y=300,dt=1500,sw=1080,sh=1920,g=1)
#   -> {"ok":true,"u":"base64(m3u8)"} -> 解码出 cdn2020.com 的 m3u8 直链, parse 0
# 境界: 轮海为体(静态直取)+四极为用(AK token + count.php 握手解密); 路由器实测: 轮海 Lv.0
# 2026-11-14 本机实测: 分类 12 个全通(每页 40 条), 详情 AK 正常, count.php 200,
#   m3u8 200(743 分片), 首分片 Range 206; 搜索 AV 出 36 条
# 注意: 列表页顶部混有站外广告卡片(外链 href), 只认 /v5/ 开头的站内视频; 部分 CDN 子域名可能回 451, 属站方/线路问题
import re, json, base64, requests
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.entry = "https://www.hsck.net"
        self.mirrors = ["https://444.9976hsck.cc", "https://333.9976hsck.cc"]
        self.host = ""
        self.header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}
        self.session = requests.Session()
        self.session.headers.update(self.header)
        self.classes = [{"type_id": "1", "type_name": "日韩AV"}, {"type_id": "2", "type_name": "国产系列"}, {"type_id": "3", "type_name": "欧美"}, {"type_id": "4", "type_name": "成人动漫"}, {"type_id": "7", "type_name": "日本骑兵"}, {"type_id": "8", "type_name": "中文字幕"}, {"type_id": "9", "type_name": "骑兵中文字幕"}, {"type_id": "10", "type_name": "步兵无码"}, {"type_id": "15", "type_name": "国产视频"}, {"type_id": "21", "type_name": "欧美成人"}, {"type_id": "22", "type_name": "日本成人动漫"}, {"type_id": "26", "type_name": "DMM无码"}]

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        formats = [".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi"]
        return any(f in url.lower() for f in formats)

    def manualVideoCheck(self):
        return False

    def _resolve_host(self):
        if self.host:
            return self.host
        try:
            r = requests.get(self.entry, headers=self.header, timeout=10, allow_redirects=False)
            loc = r.headers.get("Location", "")
            if r.status_code in (301, 302, 307, 308) and loc.startswith("http"):
                self.host = loc.rstrip("/")
                return self.host
        except Exception:
            pass
        for m in self.mirrors:
            try:
                r = requests.get(m + "/", headers=self.header, timeout=10)
                if r.status_code == 200 and len(r.text) > 10000 and "黄色仓库" in r.text:
                    self.host = m
                    return self.host
            except Exception:
                continue
        self.host = self.mirrors[0]
        return self.host

    def _get(self, path, timeout=15):
        host = self._resolve_host()
        last = ""
        for _ in range(3):
            try:
                r = self.session.get(host + path, timeout=timeout)
                if r.status_code == 200:
                    r.encoding = r.apparent_encoding or "utf-8"
                    return r.text
                last = ""
            except Exception as e:
                last = str(e)
            try:
                import time
                time.sleep(1)
            except Exception:
                pass
        return last

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self._resolve_host() + url
        return url

    def _parse_list(self, html):
        videos = []
        seen = set()
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select('a[href^="/v5/"]'):
                try:
                    href = a.get("href", "")
                    m = re.search(r"/v5/(\d+)-1-1\.html", href)
                    if not m:
                        continue
                    vid = m.group(1)
                    if vid in seen:
                        continue
                    seen.add(vid)
                    title = (a.get("title") or "").strip()
                    if not title:
                        h4 = a.find_parent("li")
                        if h4 is not None:
                            t = h4.select_one("h4.title a")
                            if t is not None:
                                title = t.get_text(strip=True)
                    pic = a.get("data-original") or ""
                    if not pic:
                        img = a.select_one("img")
                        if img is not None:
                            pic = img.get("data-original") or img.get("src") or ""
                    dur = ""
                    sp = a.select_one("span.pic-text")
                    if sp is not None:
                        dur = sp.get_text(strip=True)
                    if title:
                        videos.append({"vod_id": vid, "vod_name": title, "vod_pic": self._fix_url(pic), "vod_remarks": dur})
                except Exception:
                    continue
            if videos:
                return videos
        except Exception:
            pass
        pos = 0
        while True:
            i = html.find('/v5/', pos)
            if i < 0:
                break
            m = re.match(r"/v5/(\d+)-1-1\.html", html[i:i + 40])
            if not m:
                pos = i + 4
                continue
            vid = m.group(1)
            if vid in seen:
                pos = i + 4
                continue
            seen.add(vid)
            seg = html[max(0, i - 600):i + 600]
            tm = re.search(r'title="([^"]+)"', seg)
            pm = re.search(r'data-original="([^"]+)"', seg)
            dm = re.search(r'<span class="pic-text text-right">([^<]+)</span>', seg)
            title = tm.group(1).strip() if tm else ""
            if title:
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": self._fix_url(pm.group(1) if pm else ""), "vod_remarks": dm.group(1).strip() if dm else ""})
            pos = i + 4
        return videos

    def _page_count(self, html, tid):
        m = re.search(r'<span class="num">\d+/(\d+)</span>', html)
        if m:
            return int(m.group(1))
        pages = [int(x) for x in re.findall(r"/vodtype/%s-(\d+)\.html" % tid, html)]
        if pages:
            return max(pages)
        return 1

    def getName(self):
        return "黄色仓库-hsck.tv"

    def homeContent(self, filter=False):
        html = self._get("/")
        videos = self._parse_list(html) if html else []
        return {"class": self.classes, "list": videos}

    def homeVideoContent(self):
        html = self._get("/")
        videos = self._parse_list(html) if html else []
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        html = self._get("/vodtype/%s-%s.html" % (tid, pg))
        videos = self._parse_list(html) if html else []
        return {"list": videos, "page": pg, "pagecount": self._page_count(html, tid) if html else 1, "limit": len(videos), "total": 0}

    def detailContent(self, ids):
        vid = ids[0]
        html = self._get("/v5/%s-1-1.html" % vid)
        title = ""
        if html:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()
                title = title.replace(" - 黄色仓库-hsck.tv", "").replace(" - 黄色仓库", "").strip()
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_play_from": "默认", "vod_play_url": "第1集$%s" % vid}]}

    def searchContent(self, key, quick, pg="1"):
        html = self._get("/vodsearch/-------------.html?wd=" + quote(key))
        videos = self._parse_list(html) if html else []
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        vid = id
        host = self._resolve_host()
        detail_url = host + "/v5/%s-1-1.html" % vid
        html = self._get("/v5/%s-1-1.html" % vid)
        if not html:
            return {"parse": 0, "url": "", "header": ""}
        m = re.search(r"AK='([0-9a-f]{64})'", html)
        if not m:
            return {"parse": 0, "url": "", "header": ""}
        try:
            r = self.session.post(host + "/static/count.php", data={"id": vid, "sid": "1", "nid": "1", "tk": m.group(1), "g": "1", "x": "200", "y": "300", "dt": "1500", "sw": "1080", "sh": "1920"}, headers={"Referer": detail_url, "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, timeout=15)
            j = r.json()
            u = j.get("u", "")
            if not u:
                return {"parse": 0, "url": "", "header": ""}
            play_url = base64.b64decode(u).decode("utf-8", errors="ignore")
            if not play_url.startswith("http") or ".m3u8" not in play_url:
                return {"parse": 0, "url": "", "header": ""}
            return {"parse": 0, "url": play_url, "header": "User-Agent=%s&Referer=%s" % (self.header["User-Agent"], detail_url)}
        except Exception:
            return {"parse": 0, "url": "", "header": ""}

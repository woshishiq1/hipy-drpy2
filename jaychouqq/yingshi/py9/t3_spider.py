# -*- coding: utf-8 -*-
# t3.18j61.cc -> py影视 Spider (苹果CMS站, 纯 HTML 解析)
# 2026-10-06-v1
import sys
import json
import re
import urllib.request
import urllib.parse
import ssl
import gzip

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.site_url = "https://t3.18j61.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://t3.18j61.cc/",
            "Connection": "close",
        }
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    # ---------- 基础请求 ----------
    def _fetch(self, url, timeout=15):
        req = urllib.request.Request(url, headers=self.headers, method="GET")
        with urllib.request.urlopen(req, context=self.ssl_ctx,
                                    timeout=timeout) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding", "").lower()
            if "gzip" in enc:
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            # 解码
            for cs in ("utf-8", "gbk", "gb2312"):
                try:
                    return raw.decode(cs)
                except Exception:
                    continue
            return raw.decode("utf-8", errors="ignore")

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return urllib.parse.urljoin(self.site_url, url)

    # ---------- 解析 ----------
    def _parse_cards(self, html):
        # <a href="/v/56835-1-1/" title="..."> ... <img ... src="..." data-original="..."> ... <span>备注</span>
        cards = []
        seen = set()
        pat = re.compile(
            r'<a\s+href="(/v/(\d+)-1-1/)"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*?(?:data-original="([^"]+)"|src="([^"]+)").*?'
            r'<span>([^<]*)</span>',
            re.S)
        for m in pat.finditer(html):
            href, vid, title, cover1, cover2, remarks = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            cover = cover1 or cover2 or ""
            cards.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self._abs(cover.strip()),
                "vod_remarks": remarks.strip(),
            })
        return cards

    def _parse_episodes(self, html, vid):
        # 分集: <a href="/v/56840-1-2/">2</a>
        eps = []
        for m in re.finditer(r'href="(/v/%s-1-(\d+)/)"[^>]*>([^<]{1,20})</a>'
                             % re.escape(str(vid)), html):
            href, nid, name = m.groups()
            name = name.strip() or ("第%s集" % nid)
            eps.append("第%s集$%s-1-%s" % (nid, vid, nid))
        # 去重保序
        seen, uniq = set(), []
        for e in eps:
            if e not in seen:
                seen.add(e)
                uniq.append(e)
        if not uniq:
            uniq = ["正片$%s-1-1" % vid]
        return uniq

    # ================= Spider 接口 =================
    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "国产"},
            {"type_id": "11", "type_name": "国产自拍"},
            {"type_id": "15", "type_name": "国产AV"},
            {"type_id": "16", "type_name": "福利姬"},
            {"type_id": "12", "type_name": "吃瓜黑料"},
            {"type_id": "2", "type_name": "日韩"},
            {"type_id": "19", "type_name": "无码中字"},
            {"type_id": "21", "type_name": "中文字幕"},
            {"type_id": "22", "type_name": "JAV无码"},
            {"type_id": "3", "type_name": "欧美"},
            {"type_id": "24", "type_name": "欧美大片"},
            {"type_id": "4", "type_name": "伦理"},
            {"type_id": "27", "type_name": "港台三级"},
            {"type_id": "5", "type_name": "动漫"},
            {"type_id": "30", "type_name": "3D动漫"},
            {"type_id": "6", "type_name": "另类"},
            {"type_id": "9", "type_name": "成人AI"},
            {"type_id": "36", "type_name": "AI短剧"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.site_url + "/vod/")
            cards = self._parse_cards(html)[:12]
            if cards:
                return {"list": cards}
        except Exception:
            pass
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg <= 1:
            url = "%s/t/%s/" % (self.site_url, tid)
        else:
            url = "%s/t/%s-%d/" % (self.site_url, tid, pg)
        try:
            html = self._fetch(url)
        except Exception as e:
            return {"list": [], "page": pg, "pagecount": pg,
                    "limit": 40, "total": 0}
        cards = self._parse_cards(html)
        return {"list": cards, "page": pg, "pagecount": pg + 1,
                "limit": 40, "total": pg * 40 + len(cards)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid or not vid.isdigit():
            return {"list": []}
        try:
            html = self._fetch("%s/v/%s-1-1/" % (self.site_url, vid))
        except Exception:
            return {"list": []}
        # 标题
        m = re.search(r"<title>([^<]*)</title>", html)
        title = (m.group(1).split(" - ")[0].split(" 第")[0].strip()
                 if m else ("视频 %s" % vid))
        # 封面
        cover = ""
        m = re.search(r'"thumbnailUrl":"([^"]+)"', html)
        if m:
            cover = m.group(1)
        else:
            m = re.search(r'<img[^>]*data-original="([^"]+)"', html)
            if m:
                cover = m.group(1)
        # 简介
        desc = ""
        m = re.search(r'"description":"([^"]*)"', html)
        if m:
            desc = m.group(1)[:500]
        eps = self._parse_episodes(html, vid)
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._abs(cover),
            "vod_content": desc,
            "vod_play_from": "在线播放",
            "vod_play_url": "#".join(eps),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        vid = str(id).strip()
        url = ""
        try:
            # id 格式: 56840-1-1
            if not vid.startswith("http") and not vid.startswith("/"):
                vid = "/v/%s/" % vid
            html = self._fetch(self._abs(vid))
            m = re.search(r'"contentUrl":"([^"]+\.m3u8[^"]*)"', html)
            if m:
                url = m.group(1)
            else:
                m = re.search(r'(https?://[^"\s]+\.m3u8[^"\s]*)', html)
                if m:
                    url = m.group(1)
        except Exception:
            url = ""
        return {"parse": 0, "url": url,
                "header": {"User-Agent": self.headers["User-Agent"],
                           "Referer": self.site_url + "/"}}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        try:
            q = urllib.parse.quote(key)
            if pg <= 1:
                url = "%s/s/wd/%s/" % (self.site_url, q)
            else:
                url = "%s/s/wd/%s/%d/" % (self.site_url, q, pg)
            html = self._fetch(url)
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1,
                    "limit": 0, "total": 0}
        cards = self._parse_cards(html)
        return {"list": cards, "page": pg, "pagecount": pg + 1,
                "limit": len(cards), "total": len(cards)}

    def action(self, action):
        return None

    def liveContent(self):
        return {}

    def localProxy(self, params):
        return [200, "text/plain", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or ".m3u8?" in url

    def destroy(self):
        pass

#!/usr/bin/python
# coding=utf-8
import re, json
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.name = "星空五月天"
        self.host = "https://d8v8rjm9.bbmm277.sbs"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

    def init(self, extend=""):
        return None

    def getName(self):
        return self.name

    def setExtendInfo(self, extend):
        return None

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeLayout(self):
        return 0

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
        return re.sub(r'\s+', ' ', text).strip()

    def fetch_html(self, url):
        try:
            r = self.fetch(url, headers=self.header, timeout=15)
            if not r:
                return ""
            if isinstance(r, bytes):
                return r.decode("utf-8", "ignore")
            if isinstance(r, str):
                return r
            if hasattr(r, "read") and callable(r.read):
                try:
                    body = r.read()
                    return body.decode("utf-8", "ignore") if isinstance(body, bytes) else str(body)
                except:
                    return str(r)
            if hasattr(r, "text"):
                if callable(r.text):
                    try:
                        v = r.text()
                        return v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v)
                    except:
                        return str(r)
                if isinstance(r.text, bytes):
                    return r.text.decode("utf-8", "ignore")
                return str(r.text)
            return str(r)
        except Exception:
            return ""

    def homeContent(self, filter):
        cats = [
            {"type_id": "1", "type_name": "国产"}, {"type_id": "2", "type_name": "网红"},
            {"type_id": "3", "type_name": "萝莉"}, {"type_id": "4", "type_name": "大秀"},
            {"type_id": "5", "type_name": "探花"}, {"type_id": "6", "type_name": "自拍"},
            {"type_id": "7", "type_name": "乱伦"}, {"type_id": "8", "type_name": "强奸"},
            {"type_id": "9", "type_name": "传媒"}, {"type_id": "10", "type_name": "反差婊"},
            {"type_id": "11", "type_name": "网爆门"}, {"type_id": "12", "type_name": "偷拍"},
            {"type_id": "13", "type_name": "福利姬"}, {"type_id": "14", "type_name": "吃瓜"},
            {"type_id": "15", "type_name": "大学生"}, {"type_id": "16", "type_name": "人兽"},
            {"type_id": "17", "type_name": "人妖"}, {"type_id": "18", "type_name": "OnlyFans"},
            {"type_id": "20", "type_name": "喷水"}, {"type_id": "21", "type_name": "裸贷"},
            {"type_id": "22", "type_name": "性虐"}, {"type_id": "23", "type_name": "AI换脸"},
            {"type_id": "24", "type_name": "无码"}, {"type_id": "25", "type_name": "中字"},
            {"type_id": "26", "type_name": "欧美"}, {"type_id": "27", "type_name": "动漫"},
            {"type_id": "28", "type_name": "三级片"}, {"type_id": "29", "type_name": "AV解说"},
            {"type_id": "30", "type_name": "兄弟姐妹"}, {"type_id": "31", "type_name": "禁忌母子"},
            {"type_id": "32", "type_name": "狂操小姨"}, {"type_id": "33", "type_name": "猛干嫂子"},
            {"type_id": "34", "type_name": "野外车震"}, {"type_id": "35", "type_name": "夫妻交换"},
            {"type_id": "36", "type_name": "淫荡儿媳"}, {"type_id": "37", "type_name": "学生下海"},
            {"type_id": "38", "type_name": "瑜伽裤"}, {"type_id": "39", "type_name": "兽耳系列"},
            {"type_id": "40", "type_name": "多人群P"}, {"type_id": "41", "type_name": "Cosplay"},
        ]
        html = self.fetch_html(self.host + "/")
        return {"class": cats, "list": self._parse_list(html), "filters": {}}

    def homeVideoContent(self):
        html = self.fetch_html(self.host + "/")
        return {"list": self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        if page == 1:
            url = f"{self.host}/videotype/{tid}.html"
        else:
            url = f"{self.host}/videotype/{tid}/page/{page}.html"
        html = self.fetch_html(url)
        items = self._parse_list(html)
        pages = [int(x) for x in re.findall(r'/page/(\d+)\.html', html) if x.isdigit()] if html else []
        if pages:
            pagecount = max(pages)
        elif html and ("下一页" in html or "下一頁" in html or 'class="next"' in html or ">下一页</a>" in html):
            pagecount = page + 1
        elif len(items) > 0:
            pagecount = page + 1
        else:
            pagecount = page
        if pagecount < page:
            pagecount = page
        return {"list": items, "page": page, "pagecount": pagecount, "limit": len(items), "total": pagecount * 24}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or "")
        detail_url = f"{self.host}/videos/{vid}.html"
        html = self.fetch_html(detail_url)
        if not html:
            return {"list": []}
        title = ""
        h1m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if h1m:
            title = self.clean_text(re.sub(r'<[^>]+>', '', h1m.group(1)))
        if not title:
            tm = re.search(r'<title>(.*?)</title>', html, re.S)
            if tm:
                title = tm.group(1).replace("_免费AV视频电影-星空资源", "").replace("-星空资源", "").strip()
        pic = ""
        pm = re.search(r'<div class="poster">\s*<img[^>]+src="([^"]+)"', html, re.S)
        if pm:
            pic = self.fix_url(pm.group(1))
        if not pic:
            pm = re.search(r'data-src="(https?://[^"]+)"', html)
            if pm:
                pic = pm.group(1)
        desc = ""
        dm = re.search(r'<div class="article-content">\s*(.*?)\s*</div>', html, re.S)
        if dm:
            desc = self.clean_text(re.sub(r'<[^>]+>', '', dm.group(1)))
        lines = re.findall(r'<li><a href="(/videosplay/[^"]+\.html)">([^<]*)</a></li>', html)
        if not lines:
            return {"list": [{"vod_id": vid, "vod_name": title or f"视频{vid}", "vod_pic": pic, "vod_content": desc, "vod_play_from": "", "vod_play_url": ""}]}
        froms, urls, seen = [], [], set()
        first_play_url = ""
        for href, name in lines:
            play_url = self.fix_url(href)
            if play_url in seen:
                continue
            seen.add(play_url)
            froms.append(name.strip() or "默认线路")
            urls.append(f"正片${play_url}")
            if not first_play_url:
                first_play_url = play_url
        if first_play_url:
            try:
                play_html = self.fetch_html(first_play_url)
                if play_html:
                    mm = re.search(r'var\s+player_data\s*=\s*(\{[^;]+\});', play_html, re.S)
                    if mm:
                        pd = json.loads(mm.group(1))
                        m3u8 = pd.get("url", "")
                        if m3u8:
                            froms.insert(0, "直链")
                            urls.insert(0, f"正片${m3u8}")
            except:
                pass
        vod = {
            "vod_id": vid,
            "vod_name": title or f"视频{vid}",
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "#".join(urls),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg):
        page = max(1, int(pg or 1))
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}"
        if page > 1:
            url = f"{self.host}/vodsearch/-------------{page}.html?wd={quote(key)}"
        html = self.fetch_html(url)
        return {"list": self._parse_list(html), "page": page, "pagecount": 1, "limit": 24, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or "")
        if self.isVideoFormat(value):
            return {"parse": 0, "url": value, "header": self.header}
        html = self.fetch_html(value)
        if not html:
            return {"parse": 1, "url": value, "header": self.header}
        mm = re.search(r'var\s+player_data\s*=\s*(\{[^;]+\});', html, re.S)
        if mm:
            try:
                pd = json.loads(mm.group(1))
                m3u8 = pd.get("url", "")
                if m3u8:
                    return {"parse": 0, "url": m3u8, "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}
            except:
                pass
        mm = re.search(r'"url"\s*:\s*"(https?://[^"]+\.(?:m3u8|mp4|ts))"', html)
        if mm:
            return {"parse": 0, "url": mm.group(1), "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}
        return {"parse": 1, "url": value, "header": self.header}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4|ts)(?:\?|$)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    def _parse_list(self, html):
        if not html:
            return []
        items, seen = [], set()
        cards = re.findall(r'<div class="card">(.*?)</div>\s*</div>', html, re.S)
        for card in cards:
            am = re.search(r'<a class="pic" href="(/videos/(\d+)\.html)"[^>]*title="([^"]*)"', card)
            if not am:
                continue
            vid = am.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            title = am.group(3).strip()
            pic = ""
            pm = re.search(r'background-image:url\(([^)]+)\)', card)
            if pm:
                pic = self.fix_url(pm.group(1))
            remarks = ""
            bm = re.search(r'<span class="badge">([^<]*)</span>', card)
            if bm:
                remarks = bm.group(1).strip()
            if not remarks:
                sm = re.search(r'<div class="sub">\s*([^<]+)', card)
                if sm:
                    remarks = self.clean_text(sm.group(1))
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remarks})
        return items

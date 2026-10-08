import re
import json
from html import unescape
from urllib import request, parse
from urllib.parse import urljoin


class Spider:
    def __init__(self):
        self.siteUrl = "https://zcl.ssm4.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": self.siteUrl + "/",
        }

    def getName(self):
        return "爽水妹"

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "21", "type_name": "女神学生"},
            {"type_id": "22", "type_name": "美女直播"},
            {"type_id": "23", "type_name": "人妻系列"},
            {"type_id": "24", "type_name": "强纳聚麀"},
            {"type_id": "25", "type_name": "自拍偷拍"},
            {"type_id": "26", "type_name": "制服诱惑"},
            {"type_id": "27", "type_name": "巨乳系列"},
            {"type_id": "28", "type_name": "自慰系列"},
            {"type_id": "29", "type_name": "国产视频"},
            {"type_id": "30", "type_name": "无码视频"},
            {"type_id": "31", "type_name": "有码视频"},
            {"type_id": "32", "type_name": "中文字幕"},
            {"type_id": "33", "type_name": "日韩精品"},
            {"type_id": "34", "type_name": "欧美精品"},
            {"type_id": "35", "type_name": "动漫精品"},
            {"type_id": "36", "type_name": "三级伦理"},
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return self.listParse(self.fetch(self.siteUrl + "/ssm/"))

    def categoryContent(self, tid, pg, filter, extend):
        if str(pg) == "1":
            url = self.siteUrl + "/vodtype/%s.html" % tid
        else:
            url = self.siteUrl + "/vodtype/%s-%s.html" % (tid, pg)
        html = self.fetch(url)
        result = self.listParse(html)
        pages = re.findall(r"/vodtype/%s-(\d+)\.html" % tid, html)
        pagecount = max([int(p) for p in pages]) if pages else 1
        result.update({"page": int(pg), "pagecount": pagecount, "limit": 60, "total": pagecount * 60})
        return result

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = ids[0]
        else:
            vid = str(ids).split(",")[0]
        vid = str(vid).strip()
        path = vid if vid.startswith("/") else "/" + vid
        if not path.endswith(".html"):
            path += ".html"
        url = urljoin(self.siteUrl, path)
        html = self.fetch(url)
        m = re.search(r"const rawUrl\s*=\s*'([^']+)'", html)
        play = m.group(1) if m else ""
        tm = re.search(r"<title>正在播放\s*(.*?)</title>", html, re.S)
        title = unescape(tm.group(1).strip()) if tm else vid
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": title,
            "vod_play_from": "爽水妹",
            "vod_play_url": "正片$" + play,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick):
        url = self.siteUrl + "/s/index.html?wd=" + parse.quote(key)
        return self.listParse(self.fetch(url))

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.siteUrl + "/",
            },
        }

    def localProxy(self, param):
        if isinstance(param, str):
            param = json.loads(param)
        url = param.get("url") or param.get("u")
        if not url:
            return [404, "text/plain", b""]
        req = request.Request(url, headers=self.headers)
        try:
            with request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                return [resp.status, resp.headers.get("Content-Type", "application/octet-stream"), body]
        except Exception:
            return [502, "text/plain", b""]

    def manualVideoCheck(self):
        pass

    def fetch(self, url):
        req = request.Request(url, headers=self.headers)
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:
                pass
        return raw.decode("utf-8", "ignore")

    def listParse(self, html):
        blocks = re.split(r"<li\b", html)
        videos = []
        seen = set()
        for b in blocks:
            m = re.search(r'<a\b[^>]*class="[^"]*v-playBtn[^"]*"[^>]*>', b)
            if not m:
                continue
            tag = m.group(0)
            hm = re.search(r'href="\s*([^"]+?)\s*"', tag)
            if not hm:
                continue
            href = hm.group(1).strip()
            tm = re.search(r'title="([^"]*)"', tag)
            title = unescape(tm.group(1)).strip() if tm else ""
            if not title:
                am = re.search(r'<img\b[^>]*alt="([^"]*)"', b)
                title = unescape(am.group(1)).strip() if am else ""
            im = re.search(r'<img\b[^>]*src="([^"]+)"', b)
            pic = im.group(1) if im else ""
            rm = re.search(r'<span class="fr">([^<]*)</span>', b)
            rem = rm.group(1).strip() if rm else ""
            vid = href.lstrip("/").replace(".html", "")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": rem,
            })
        return {"list": videos}

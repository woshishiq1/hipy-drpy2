import re
import json
from urllib.parse import urljoin
from urllib3.exceptions import InsecureRequestWarning
import requests
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class Spider:

    def __init__(self):
        self.siteUrl = "https://ephilv.mjsp3.lol"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": self.siteUrl + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.classes = [
            {"type_id": "1", "type_name": "乱伦"},
            {"type_id": "2", "type_name": "出轨"},
            {"type_id": "3", "type_name": "制服"},
            {"type_id": "4", "type_name": "自慰"},
            {"type_id": "5", "type_name": "偷拍"},
            {"type_id": "20", "type_name": "自拍"},
            {"type_id": "21", "type_name": "国产"},
            {"type_id": "22", "type_name": "同性"},
            {"type_id": "23", "type_name": "日韩"},
            {"type_id": "24", "type_name": "欧美"},
            {"type_id": "25", "type_name": "三级"},
            {"type_id": "26", "type_name": "动漫"},
        ]

    def getName(self):
        return "秘境视频"

    def init(self, extend=""):
        pass

    def isReal(self, text):
        return ("vodtype" in text) or ("maccms" in text)

    def fetch(self, url):
        for _ in range(3):
            try:
                r = requests.get(url, headers=self.headers, timeout=20, verify=False)
                if r.status_code == 200 and self.isReal(r.text):
                    return r.text
            except Exception:
                pass
        return ""

    def homeContent(self, filter):
        return {
            "class": self.classes,
            "filters": {},
        }

    def homeVideoContent(self):
        return self.categoryContent("23", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        if int(pg) <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{pg}.html"
        html = self.fetch(url)
        videos = []
        for m in re.finditer(
            r'href="/(\d+)\.html" title="([^"]+)" data-original="([^"]+)"', html
        ):
            vid, title, pic = m.group(1), m.group(2), m.group(3)
            if pic.startswith("//"):
                pic = "https:" + pic
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        pages = [int(x) for x in re.findall(rf"/vodtype/{tid}-(\d+)\.html", html)]
        pagecount = max(pages) if pages else int(pg)
        return {
            "list": videos,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0]
        elif isinstance(ids, tuple):
            vid = ids[0]
        else:
            vid = str(ids).split(",")[0]
        html = self.fetch(f"{self.siteUrl}/{vid}.html")
        m = re.search(r"const rawUrl = '([^']+)'", html)
        play = m.group(1) if m else ""
        mt = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html)
        name = re.sub(r"<[^>]+>", "", mt.group(1)).strip() if mt else vid
        mp = re.search(r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*pic', html)
        pic = mp.group(1) if mp else ""
        if pic.startswith("//"):
            pic = "https:" + pic
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "秘境线路",
            "vod_play_url": f"正片${play}" if play else "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False):
        from urllib.parse import quote
        url = f"{self.siteUrl}/index.php/vod/search/wd/{quote(key)}.html"
        html = self.fetch(url)
        videos = []
        for m in re.finditer(
            r'href="/(\d+)\.html" title="([^"]+)" data-original="([^"]+)"', html
        ):
            pic = m.group(3)
            if pic.startswith("//"):
                pic = "https:" + pic
            videos.append({
                "vod_id": m.group(1),
                "vod_name": m.group(2),
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return {"list": videos, "page": 1}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": json.dumps({
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.siteUrl + "/",
            }),
        }

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = {}
        url = param.get("url", "")
        try:
            r = requests.get(url, headers=self.headers, timeout=20, verify=False)
            return [r.status_code, r.headers.get("Content-Type", "application/octet-stream"), r.content]
        except Exception:
            return [500, "text/plain", b""]

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
import sys
sys.path.append("..")
from base.spider import BaseSpider
import json
import re
import base64
import urllib.parse
from lxml import html


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://kie.gdd4.pics"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": self.siteUrl + "/",
        }

    def getName(self):
        return "GDD视频"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        classes = [
            {"type_id": "21", "type_name": "女神学生"},
            {"type_id": "22", "type_name": "美女直播"},
            {"type_id": "23", "type_name": "人妻系列"},
            {"type_id": "24", "type_name": "强奸乱伦"},
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
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            result["list"] = []
        return result

    def homeVideoContent(self, filter=None):
        url = self.siteUrl + "/cn/home/web/index.php"
        try:
            rsp = self.fetch(url, headers=self.headers)
            items = self.parseList(rsp.text)
        except Exception:
            items = []
        return {"list": items}

    def categoryContent(self, tid, pg, filter, extend):
        if pg == "1":
            url = self.siteUrl + "/cn/home/web/index.php/vod/type/id/%s.html" % tid
        else:
            url = self.siteUrl + "/cn/home/web/index.php/vod/type/id/%s/page/%s.html" % (tid, pg)
        rsp = self.fetch(url, headers=self.headers)
        items = self.parseList(rsp.text)
        pages = re.findall(r"/type/id/%s/page/(\d+)\.html" % tid, rsp.text)
        totalPg = max([int(x) for x in pages]) if pages else int(pg) + 1
        result = {
            "list": items,
            "page": pg,
            "pagecount": totalPg,
            "limit": 30,
            "total": totalPg * 30,
        }
        return result

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = ids[0]
        else:
            vid = ids
        try:
            raw = base64.b64decode(vid.encode()).decode()
            parts = raw.split("|")
            play_url = parts[0]
            title = parts[1] if len(parts) > 1 else ""
            pic = parts[2] if len(parts) > 2 else ""
        except Exception:
            play_url = vid
            title = ""
            pic = ""
        url = self.siteUrl + play_url if play_url.startswith("/") else play_url
        rsp = self.fetch(url, headers=self.headers)
        m3u8 = ""
        m = re.search(r"var player_data=(\{.*?\})\s*</script>", rsp.text, re.S)
        if m:
            try:
                pd = json.loads(m.group(1))
                m3u8 = pd.get("url", "").replace("\\/", "/")
            except Exception:
                pass
        if not m3u8:
            m2 = re.search(r"(https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*)", rsp.text)
            if m2:
                m3u8 = m2.group(1)
        if not title:
            doc = html.fromstring(rsp.text)
            th = [t.strip() for t in doc.xpath("//h1//text()") if t.strip()]
            if th:
                title = th[0]
        if not title:
            title = "GDD视频"
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "type_name": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": title,
        }
        vod["vod_play_from"] = "GDD线路"
        vod["vod_play_url"] = "正片$%s" % (play_url if play_url else vid)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = self.siteUrl + "/cn/home/web/index.php/vod/search.html?wd=" + urllib.parse.quote(key)
        rsp = self.fetch(url, headers=self.headers)
        return {"list": self.parseList(rsp.text)}

    def playerContent(self, flag, id, vipFlags):
        url = self.siteUrl + id if id.startswith("/") else id
        rsp = self.fetch(url, headers=self.headers)
        m3u8 = ""
        m = re.search(r"var player_data=(\{.*?\})\s*</script>", rsp.text, re.S)
        if m:
            try:
                pd = json.loads(m.group(1))
                m3u8 = pd.get("url", "").replace("\\/", "/")
            except Exception:
                pass
        if not m3u8:
            m2 = re.search(r"(https?://[^\s\"\'<>]+\.m3u8[^\s\"\'<>]*)", rsp.text)
            if m2:
                m3u8 = m2.group(1)
        header = {"User-Agent": self.headers["User-Agent"], "Referer": url}
        return {"parse": 0, "playUrl": "", "url": m3u8, "header": header}

    def localProxy(self, param):
        return [200, "video/MP2T", b""]

    def parseList(self, text):
        doc = html.fromstring(text)
        items = []
        for a in doc.xpath("//ul[contains(@class,'videos')]/li//a[contains(@href,'/vod/play/')]"):
            href = a.get("href") or ""
            title = (a.get("title") or "").strip()
            if not title:
                ts = [t.strip() for t in a.xpath(".//span[contains(@class,'video-title')]//text()") if t.strip()]
                title = ts[0] if ts else ""
            if not title:
                title = (a.text_content() or "").strip()[:60]
            imgs = a.xpath(".//img/@src")
            pic = imgs[0] if imgs else ""
            remark = ""
            rs = [t.strip() for t in a.xpath(".//span[contains(@class,'video-overlay')]//text()") if t.strip()]
            if rs:
                remark = rs[0]
            if not href.startswith("http"):
                href = "https://kie.gdd4.pics" + href
            path = href.replace("https://kie.gdd4.pics", "")
            vid = base64.b64encode(("%s|%s|%s" % (path, title, pic)).encode()).decode()
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        out = []
        seen = set()
        for it in items:
            if it["vod_id"] in seen:
                continue
            seen.add(it["vod_id"])
            out.append(it)
        return out

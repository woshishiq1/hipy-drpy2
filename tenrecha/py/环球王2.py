import sys
sys.path.append("..")
import json, re, urllib.parse
from urllib.parse import urljoin
import requests
try:
    from base.spider import Spider as BaseSpider
except:
    class BaseSpider:
        def init(self, extend=""): pass

class Spider(BaseSpider):
    siteUrl = "https://www.huanqiwang2.cc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://www.huanqiwang2.cc/"
    }

    def getName(self):
        return "环球王2"

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.verify = False

    def homeContent(self, filter):
        classes = self.classes()
        try:
            r = self.session.get(self.siteUrl + "/a/", timeout=15)
            r.encoding = r.apparent_encoding
            items = self.parseList(r.text)
        except:
            items = []
        return {"class": classes, "list": items}

    def classes(self):
        return [
            {"type_id": "244", "type_name": "163资源"},
            {"type_id": "266", "type_name": "AV解说"},
            {"type_id": "254", "type_name": "国产自拍"},
            {"type_id": "255", "type_name": "熟女人妻"},
            {"type_id": "256", "type_name": "萝莉少女"},
            {"type_id": "257", "type_name": "百合剧情"},
            {"type_id": "258", "type_name": "美乳巨乳"},
            {"type_id": "259", "type_name": "强歼爬灰聚麀"},
            {"type_id": "260", "type_name": "抖音视频"},
            {"type_id": "261", "type_name": "韩国主播"},
            {"type_id": "262", "type_name": "网红头条"},
            {"type_id": "358", "type_name": "少妇资源"},
            {"type_id": "369", "type_name": "高清有码"},
            {"type_id": "368", "type_name": "动漫精选"},
            {"type_id": "367", "type_name": "学生妹"},
            {"type_id": "366", "type_name": "中文字幕"},
            {"type_id": "365", "type_name": "高清无码"},
            {"type_id": "364", "type_name": "黑料网曝"},
            {"type_id": "363", "type_name": "主播网红"},
            {"type_id": "362", "type_name": "爬灰聚麀系列"},
            {"type_id": "361", "type_name": "国产精品"},
            {"type_id": "360", "type_name": "偷拍自拍"},
            {"type_id": "329", "type_name": "裤子资源"},
            {"type_id": "330", "type_name": "日本有码"},
            {"type_id": "331", "type_name": "无码中文"},
            {"type_id": "332", "type_name": "有码中文"},
            {"type_id": "333", "type_name": "日本无码"},
            {"type_id": "334", "type_name": "国产视频"},
            {"type_id": "335", "type_name": "欧美高清"},
            {"type_id": "336", "type_name": "动漫剧情"},
            {"type_id": "119", "type_name": "不卡资源"},
            {"type_id": "120", "type_name": "国产视频2"},
            {"type_id": "121", "type_name": "中文字幕2"},
            {"type_id": "122", "type_name": "国产传媒"},
            {"type_id": "123", "type_name": "日本有码2"},
            {"type_id": "124", "type_name": "日本无码2"},
            {"type_id": "125", "type_name": "欧美无码"},
            {"type_id": "126", "type_name": "强干爬灰聚麀"},
            {"type_id": "127", "type_name": "制服诱惑"},
            {"type_id": "128", "type_name": "国产主播"},
            {"type_id": "129", "type_name": "激情动漫"},
            {"type_id": "286", "type_name": "兔儿资源"},
            {"type_id": "304", "type_name": "精品推荐"},
            {"type_id": "305", "type_name": "主播秀色"},
            {"type_id": "306", "type_name": "日本有码3"},
            {"type_id": "307", "type_name": "日本无码3"},
            {"type_id": "308", "type_name": "中文字幕3"},
            {"type_id": "309", "type_name": "童颜巨乳"},
            {"type_id": "310", "type_name": "性感人妻"},
            {"type_id": "311", "type_name": "强歼爬灰聚麀2"},
            {"type_id": "312", "type_name": "欧美情色"},
            {"type_id": "313", "type_name": "三级伦理"},
            {"type_id": "370", "type_name": "森林资源"},
            {"type_id": "371", "type_name": "精品推荐2"},
            {"type_id": "372", "type_name": "国产情色"},
            {"type_id": "373", "type_name": "亚洲无码"},
            {"type_id": "374", "type_name": "亚洲有码"},
            {"type_id": "375", "type_name": "中文字幕4"},
            {"type_id": "376", "type_name": "强*爬灰聚麀"},
            {"type_id": "377", "type_name": "欧美精品"},
            {"type_id": "378", "type_name": "萝莉少女2"},
            {"type_id": "379", "type_name": "日本精品"},
            {"type_id": "380", "type_name": "Cosplay"}
        ]

    def parseList(self, html):
        items = []
        for m in re.finditer(r'<a class="vod-item" href="([^"]+)"[^>]*>\s*<div class="vod-thumb">\s*<img[^>]+data-original="([^"]*)"[^>]*alt="([^"]*)"[^>]*>\s*</div>\s*<div class="vod-name">([^<]*)</div>', html):
            href, pic, alt, name = m.groups()
            vid = urljoin(self.siteUrl, href)
            title = name.strip() or alt.strip()
            if not title:
                continue
            if pic.startswith("//"):
                pic = "https:" + pic
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": pic})
        return items

    def categoryContent(self, tid, pg, filter, extend):
        if int(pg) <= 1:
            url = self.siteUrl + "/a/index.php/vod/type/id/%s.html" % tid
        else:
            url = self.siteUrl + "/a/index.php/vod/type/id/%s/page/%s.html" % (tid, pg)
        r = self.session.get(url, timeout=15)
        r.encoding = r.apparent_encoding
        html = r.text
        items = self.parseList(html)
        pages = [int(x) for x in re.findall(r'/page/(\d+)\.html', html)]
        pagecount = max(pages) if pages else 1
        return {"list": items, "page": int(pg), "pagecount": pagecount, "limit": 12, "total": pagecount * 12}

    def detailContent(self, ids):
        url = ids[0]
        r = self.session.get(url, timeout=15)
        r.encoding = r.apparent_encoding
        html = r.text
        title = ""
        mh = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if mh:
            title = mh.group(1).strip()
        if not title:
            mt = re.search(r'<title>([^<]+)</title>', html)
            if mt:
                title = mt.group(1).strip().split("|")[0].strip()
        pic = ""
        mpi = re.search(r'<img[^>]+data-original="([^"]+)"', html)
        if mpi:
            pic = mpi.group(1)
            if pic.startswith("//"):
                pic = "https:" + pic
        plays = re.findall(r'href="([^"]*vod/play/[^"]+)"[^>]*>([^<]*)</a>', html)
        groups = {}
        for u, t in plays:
            name = t.strip() or "HD"
            groups.setdefault(name, [])
            groups[name].append(urljoin(self.siteUrl, u))
        play_from = "$$$".join(groups.keys())
        play_url = "$$$".join(["#".join(["第%s集$%s" % (i + 1, u) for i, u in enumerate(v)]) for v in groups.values()])
        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }
        return {"list": [vod]}

    def searchContent(self, key, quick):
        url = self.siteUrl + "/a/index.php/vod/search/wd/" + urllib.parse.quote(key) + ".html"
        r = self.session.get(url, timeout=15)
        r.encoding = r.apparent_encoding
        return {"list": self.parseList(r.text)}

    def playerContent(self, flag, id, vipFlags):
        r = self.session.get(id, timeout=15)
        r.encoding = r.apparent_encoding
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', r.text, re.S)
        if m:
            data = json.loads(m.group(1))
            play_url = data.get("url", "")
            if data.get("encrypt") == 1:
                try:
                    import base64
                    play_url = base64.b64decode(play_url).decode("utf-8")
                except:
                    pass
            if play_url.startswith("//"):
                play_url = "https:" + play_url
            header = json.dumps({"User-Agent": self.headers["User-Agent"], "Referer": id})
            return {"parse": 0, "playUrl": "", "url": play_url, "header": header}
        return {"parse": 0, "playUrl": "", "url": id, "header": json.dumps(self.headers)}

    def localProxy(self, param):
        try:
            params = dict(urllib.parse.parse_qsl(param))
            url = params.get("url", "")
            r = self.session.get(url, timeout=15)
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            body = r.content
            if b"#EXTM3U" in body[:200] or "mpegurl" in ctype:
                text = r.content.decode("utf-8", "ignore")
                lines = []
                for line in text.splitlines():
                    s = line.strip()
                    if s and not s.startswith("#"):
                        line = urljoin(url, s)
                    lines.append(line)
                body = "\n".join(lines).encode("utf-8")
                ctype = "application/vnd.apple.mpegurl"
            return [200, ctype, body]
        except:
            return [404, "text/plain", b""]

    def isVideoFormat(self, url):
        return re.search(r'\.(m3u8|mp4|flv|mkv|ts)(\?|$)', url, re.I) is not None

    def manualVideoCheck(self):
        return False
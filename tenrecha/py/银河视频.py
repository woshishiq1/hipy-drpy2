import sys, json, re, base64
from urllib.parse import urljoin
try:
    from base.spider import Spider, BaseSpider
except Exception as e:
    class BaseSpider:
        def init(self, extend=""):
            pass
        def homeContent(self, filter):
            pass
        def homeVideoContent(self):
            pass
        def categoryContent(self, tid, pg, filter, extend):
            pass
        def detailContent(self, ids):
            pass
        def searchContent(self, key, quick, pg="1"):
            pass
        def playerContent(self, flag, id, vipFlags):
            pass
        def localProxy(self, param):
            pass
        def isVideoFormat(self, url):
            pass
        def manualVideoCheck(self):
            pass
        def getName(self):
            pass
    Spider = BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.domain = "https://www.yhsp5.yachts"
        self.prefix = "/cn/home/web"
        self.session = None

    def getName(self):
        return "银河视频"

    def init(self, extend=""):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.domain + self.prefix + "/"
        })

    def fetch(self, url):
        try:
            r = self.session.get(url, timeout=20, verify=False)
            r.raise_for_status()
            return r.text
        except Exception:
            return ""

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
            {"type_id": "36", "type_name": "三级伦理"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        url = urljoin(self.domain, self.prefix + "/index.php")
        html = self.fetch(url)
        return self._parse_list(html)

    def categoryContent(self, tid, pg, filter, extend):
        if pg == "1":
            url = urljoin(self.domain, self.prefix + "/index.php/vod/type/id/" + tid + ".html")
        else:
            url = urljoin(self.domain, self.prefix + "/index.php/vod/type/id/" + tid + "/page/" + pg + ".html")
        html = self.fetch(url)
        result = self._parse_list(html)
        result["page"] = int(pg)
        result["pagecount"] = 9999
        result["limit"] = 30
        result["total"] = 999999
        next_page = re.search(r'href=["\'][^"\']*type/id/' + tid + r'/page/(\d+)\.html["\']', html)
        if next_page:
            result["pagecount"] = int(next_page.group(1))
        return result

    def _parse_list(self, html):
        videos = []
        lis = re.findall(r'<li[^>]*>(.*?)</li>', html, re.S | re.I)
        for li in lis:
            href_match = re.search(r'href=["\'](/[^"\']*vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)["\']', li)
            if not href_match:
                continue
            vid = href_match.group(2)
            href = href_match.group(1)
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', li)
            if not img_match:
                img_match = re.search(r'<img[^>]+data-original=["\']([^"\']+)["\']', li)
            pic = img_match.group(1) if img_match else ""
            if pic and pic.startswith("/"):
                pic = urljoin(self.domain, pic)
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', li)
            title = alt_match.group(1) if alt_match else ""
            if not title:
                title_match = re.search(r'>([^<]+)</a>', li)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if title and vid:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return {"list": videos}

    def detailContent(self, ids):
        vid = ids[0]
        detail_url = urljoin(self.domain, self.prefix + "/index.php/vod/detail/id/" + vid + ".html")
        html = self.fetch(detail_url)
        if not html:
            play_url = urljoin(self.domain, self.prefix + "/index.php/vod/play/id/" + vid + "/sid/1/nid/1.html")
            html = self.fetch(play_url)
        title = ""
        pic = ""
        if html:
            h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
            if h1:
                title = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
            if not title:
                tmatch = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
                if tmatch:
                    title = tmatch.group(1).split("-")[0].strip()
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:pic|thumb|cover)[^"\']*["\']', html, re.S | re.I)
            if img_match:
                pic = img_match.group(1)
                if pic.startswith("/"):
                    pic = urljoin(self.domain, pic)
        if not title:
            title = vid
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "线路1",
            "vod_play_url": "第1集${0}".format(vid)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = urljoin(self.domain, self.prefix + "/index.php/vod/search/wd/" + key + ".html")
        if pg != "1":
            url = urljoin(self.domain, self.prefix + "/index.php/vod/search/wd/" + key + "/page/" + pg + ".html")
        html = self.fetch(url)
        return self._parse_list(html)

    def playerContent(self, flag, id, vipFlags):
        vid = id
        play_url = urljoin(self.domain, self.prefix + "/index.php/vod/play/id/" + vid + "/sid/1/nid/1.html")
        html = self.fetch(play_url)
        real_url = ""
        if html:
            player_match = re.search(r'var\s+player_aaaa\s*=\s*({.+?})', html, re.S)
            if player_match:
                try:
                    player_json = json.loads(player_match.group(1))
                    url_enc = player_json.get("url", "")
                    enc = player_json.get("encrypt", 0)
                    if enc == 2:
                        real_url = base64.b64decode(url_enc).decode("utf-8")
                    elif enc == 1:
                        real_url = base64.b64decode(url_enc).decode("utf-8")
                    else:
                        real_url = url_enc
                except Exception:
                    real_url = ""
            if not real_url:
                iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.S | re.I)
                if iframe:
                    real_url = iframe.group(1)
            if not real_url:
                video = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.S | re.I)
                if video:
                    real_url = video.group(1)
            if not real_url:
                m3u8 = re.search(r'(https?://[^"\']+\.m3u8)', html)
                if m3u8:
                    real_url = m3u8.group(1)
        header = json.dumps({
            "User-Agent": self.session.headers.get("User-Agent", ""),
            "Referer": play_url
        })
        return {"parse": 0, "playUrl": "", "url": real_url, "header": header}

    def localProxy(self, param):
        return [200, "video/MP2T", ""]

    def isVideoFormat(self, url):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".ts"])

    def manualVideoCheck(self):
        return True

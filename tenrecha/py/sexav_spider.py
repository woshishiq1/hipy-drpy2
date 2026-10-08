import re
import json
import requests
from urllib.parse import quote

class Spider:
    def __init__(self):
        self.base = "https://gucj-jxex-sugi.sexav-107.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-User": "?1",
        })
        self.cats = [
            ("国产视频", "163", [
                ("国产视频-国产视频", "163"), ("国产视频-国产自拍", "48"),
                ("国产视频-抖阴视频", "231"), ("国产视频-主播大秀", "236"),
                ("国产视频-网曝黑料", "232"), ("国产视频-AV解说", "233"),
            ]),
            ("国产传媒", "2", [
                ("国产传媒-国产传媒", "2"), ("国产传媒-综合传媒", "227"),
                ("国产传媒-麻豆合集", "38"), ("国产传媒-葫芦影业", "109"),
                ("国产传媒-天美传媒", "111"), ("国产传媒-果冻传媒", "112"),
                ("国产传媒-91制片厂", "131"), ("国产传媒-蜜桃传媒", "113"),
                ("国产传媒-精东影业", "114"), ("国产传媒-皇家华人", "115"),
                ("国产传媒-SWAG", "116"), ("国产传媒-兔子先生", "120"),
                ("国产传媒-大象传媒", "125"), ("国产传媒-乌鸦传媒", "126"),
                ("国产传媒-糖心VLOG", "128"), ("国产传媒-星空传媒", "130"),
            ]),
            ("日本有码", "1", [
                ("日本有码-日本有码", "1"), ("日本有码-丝袜美腿", "36"),
                ("日本有码-绝美少女", "53"), ("日本有码-日本口爆", "58"),
                ("日本有码-萝莉少女", "234"), ("日本有码-强奸乱伦", "6"),
                ("日本有码-日本巨乳", "7"), ("日本有码-制服诱惑", "9"),
                ("日本有码-中文字幕", "13"), ("日本有码-日本素人", "16"),
                ("日本有码-高潮喷吹", "52"), ("日本有码-日本重口味", "59"),
                ("日本有码-名优精品", "63"), ("日本有码-日本人妖", "79"),
                ("日本有码-日本新人", "81"), ("日本有码-日本调教", "11"),
                ("日本有码-日本出轨", "12"),
            ]),
            ("日本无码", "5", [
                ("日本无码-日本无码", "5"), ("日本无码-人妻熟女", "10"),
                ("日本无码-巨乳无码", "32"), ("日本无码-制服无码", "35"),
            ]),
            ("女优专区", "87", [
                ("女优专区-波多野结衣", "89"), ("女优专区-三上悠亚", "87"),
                ("女优专区-河北彩花", "230"), ("女优专区-葵司", "90"),
                ("女优专区-桃乃木香奈", "93"), ("女优专区-松本一香", "103"),
                ("女优专区-篠田優", "205"), ("女优专区-川上奈奈美", "215"),
            ]),
            ("番号专区", "225", [
                ("番号专区-综合番号", "225"), ("番号专区-200GANA", "142"),
                ("番号专区-259LUXU", "146"), ("番号专区-300MIUM", "143"),
                ("番号专区-300MAAN", "149"), ("番号专区-MIAA", "190"),
                ("番号专区-SSIS", "191"), ("番号专区-STARS", "186"),
            ]),
            ("国模私拍", "45", [
                ("国模私拍-国模私拍", "45"), ("国模私拍-空姐模特", "67"),
            ]),
            ("国产精选", "17", [
                ("国产精选-国产精品", "17"), ("国产精选-国产剧情", "18"),
                ("国产精选-国产学生", "69"), ("国产精选-人妻熟女", "70"),
                ("国产精选-国产OL", "74"), ("国产精选-国产名人", "75"),
            ]),
        ]

    def getDependence(self):
        return ""

    def init(self, extend):
        try:
            if isinstance(extend, str):
                extend = json.loads(extend)
        except Exception:
            pass
        return None

    def homeContent(self, filter):
        classes = []
        filters = {}
        for parent_name, parent_id, children in self.cats:
            classes.append({"type_id": parent_id, "type_name": parent_name})
            filters[parent_id] = [{
                "key": "child",
                "name": "子分类",
                "init": children[0][1],
                "value": [{"n": cn, "v": cid} for cn, cid in children]
            }]
        try:
            html = self._fetch(self.base + "/ssss")
            videos = self._parse_list(html)
        except Exception:
            videos = []
        return {"class": classes, "filters": filters, "list": videos}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.base + "/ssss")
            videos = self._parse_list(html)
        except Exception:
            videos = []
        return {"page": 1, "pagecount": 1, "limit": 50, "total": len(videos), "list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            child_id = extend.get("child", tid) if extend else tid
        except Exception:
            child_id = tid
        if pg == 1:
            url = f"{self.base}/t/{child_id}/"
        else:
            url = f"{self.base}/t/{child_id}-{pg}/"
        try:
            html = self._fetch(url)
            videos = self._parse_list(html)
            pagecount = self._parse_pagecount(html)
        except Exception:
            videos = []
            pagecount = 1
        return {"page": int(pg), "pagecount": pagecount, "limit": 50, "total": pagecount * 50, "list": videos}

    def detailContent(self, ids):
        vid = ids[0]
        try:
            html = self._fetch(f"{self.base}/voddetail/{vid}/")
            vod = self._parse_detail(html, vid)
        except Exception:
            vod = None
        if vod is None:
            return {"list": []}
        return {"list": [vod]}

    def searchContent(self, key, quick):
        try:
            html = self._fetch(f"{self.base}/s/wd/{quote(key)}/")
            videos = self._parse_list(html)
        except Exception:
            videos = []
        return {"page": 1, "pagecount": 1, "limit": 25, "total": len(videos), "list": videos}

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._fetch(f"{self.base}/v/{id}/")
            m = re.search(r'player_aaaa\s*=\s*({.*?})\s*[;<\n]', html, re.S)
            if m:
                cfg = json.loads(m.group(1))
                real_url = cfg.get("url", "").replace("\\/", "/")
            else:
                real_url = ""
        except Exception:
            real_url = ""
        return {
            "parse": 0,
            "jx": 0,
            "url": real_url,
            "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.base + "/"},
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return None

    def destroy(self):
        return None

    def _fetch(self, url):
        resp = self.session.get(url, timeout=15, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _parse_list(self, html):
        videos = []
        seen = set()
        pattern = re.compile(
            r'<section[^>]*class="item-box"[^>]*>.*?'
            r'<a[^>]*href="(/voddetail/(\d+)/)"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*src="([^"]*)"[^>]*>.*?'
            r'</section>',
            re.S
        )
        for m in pattern.finditer(html):
            vod_id = m.group(2)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = m.group(3).strip()
            img = m.group(4)
            if img.startswith("//"):
                img = "https:" + img
            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": "",
            })
        return videos

    def _parse_pagecount(self, html):
        m = re.search(r'/t/\d+-(\d+)/[^>]*>尾页', html)
        if m:
            return int(m.group(1))
        m = re.search(r'共(\d+)页', html)
        if m:
            return int(m.group(1))
        return 1

    def _parse_detail(self, html, vid):
        title = vid
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if h1_m:
            title = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
        else:
            title_m = re.search(r'<title>(?:在线播放)?(.*?)\s*\|', html)
            if title_m:
                title = title_m.group(1).strip()
        img_m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', html)
        img = img_m.group(1) if img_m else ""
        desc_m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        desc = desc_m.group(1) if desc_m else ""
        play_url = f"正片${vid}"
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": img,
            "vod_content": desc,
            "vod_play_from": "在线播放",
            "vod_play_url": play_url,
        }

# 作者：蜗牛大叔
from base.spider import Spider
import re, html, json, base64
from urllib.parse import unquote, quote

class Spider(Spider):
    def getName(self):
        return "蘑菇影视"
    def init(self, extend=""):
        self.host = "https://moguvodw.com"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
    def homeContent(self, filter):
        cats = [
            ("电影", "/vodtype/1.html"),
            ("电视剧", "/vodtype/2.html"),
            ("综艺", "/vodtype/3.html"),
            ("动漫", "/vodtype/4.html"),
            ("短剧", "/vodtype/21.html"),
            ("记录片", "/vodtype/23.html"),
        ]
        classes = [{"type_name": n, "type_id": t} for n, t in cats]
        return {"class": classes, "list": [], "filters": {}}
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) or 1
        url = self.host + tid if pg <= 1 else self.host + tid[:-5] + '-{}.html'.format(pg)
        r = self.fetch(url, headers=self.headers).text
        cards = re.findall(r'<a[^>]+class="hl-item-thumb[^"]*"[^>]+href="(/voddetail/\d+\.html)"[^>]+title="([^"]+)"[^>]+data-original="([^"]+)"', r)
        vods = [{"vod_id": c[0], "vod_name": html.unescape(c[1]), "vod_pic": c[2], "vod_remarks": ""} for c in cards]
        return {"list": vods, "page": pg, "pagecount": 9999, "limit": 90, "total": 999999}
    def detailContent(self, ids):
        vid = ids[0]
        url = self.host + vid if vid.startswith('/') else self.host + '/' + vid
        r = self.fetch(url, headers=self.headers).text
        title = re.search(r'<title>(.*?)</title>', r)
        title = html.unescape(title.group(1)).split('-')[0].strip() if title else ""
        pic = re.search(r'data-original="(https?[^"]+)"', r)
        pic = pic.group(1) if pic else ""
        desc = re.search(r'name="description"[^>]+content="([^"]*)"', r)
        desc = html.unescape(desc.group(1)) if desc else ""
        lines = re.findall(r'<li[^>]+data-href="(/vodplay/\d+-(\d+)-\d+\.html)"[^>]*>.*?<span[^>]*>([^<]+)</span>', r, re.S)
        plays = re.findall(r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]{1,20})</a>', r)
        vurls, vfrom = [], []
        for href, sid, name in lines:
            name = name.strip()
            eps = ["{}${}".format(n.strip(), h) for h, vid2, vsid, nid, n in plays if vsid == sid and n.strip()]
            if eps:
                vurls.append("#".join(eps))
                vfrom.append(name)
        vod = {"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_content": desc,
               "vod_play_from": "$$$".join(vfrom), "vod_play_url": "$$$".join(vurls)}
        return {"list": [vod]}
    def playerContent(self, flag, id, vipFlags):
        url = self.host + id if id.startswith('/') else self.host + '/' + id
        r = self.fetch(url, headers=self.headers).text
        pa = re.search(r'player_aaaa\s*=\s*(\{.*?\});?</script>', r, re.S)
        if pa:
            try:
                j = json.loads(pa.group(1))
                enc = str(j.get('encrypt', '0'))
                u = j.get('url', '')
                if enc == '2':
                    u = unquote(base64.b64decode(unquote(u)).decode('utf-8', errors='ignore'))
                    u = unquote(u)
                elif enc == '1':
                    u = unquote(u)
                if u.startswith('//'):
                    u = 'https:' + u
                if u and ('.m3u8' in u or '.mp4' in u):
                    return {"parse": 0, "url": u, "header": self.headers}
            except:
                pass
        return {"parse": 0, "url": "", "header": self.headers}
    def searchContent(self, key, quick, pg="1"):
        url = self.host + "/vodsearch/-------------.html?wd=" + quote(key)
        r = self.fetch(url, headers=self.headers).text
        cards = re.findall(r'<a[^>]+class="hl-item-thumb[^"]*"[^>]+href="(/voddetail/\d+\.html)"[^>]+title="([^"]+)"[^>]+data-original="([^"]+)"', r)
        vods = [{"vod_id": c[0], "vod_name": html.unescape(c[1]), "vod_pic": c[2], "vod_remarks": ""} for c in cards]
        return {"list": vods, "page": int(pg) or 1}
    def isVideoFormat(self, url):
        return 1 if '.m3u8' in url else 0
    def manualVideoCheck(self):
        return 1
    def localProxy(self, param):
        return None

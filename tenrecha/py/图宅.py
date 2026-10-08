import sys, re, json, requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from base.spider import Spider

requests.packages.urllib3.disable_warnings()

class Spider(Spider):
    def getName(self): return "图宅"
    
    def init(self, extend=""):
        super().init(extend)
        self.siteUrl = "https://down.nigx.cn/tuzac.com"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36'}
        self.sess = requests.Session()
        self.sess.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))

    def fetch(self, url):
        try: return self.sess.get(url, headers=self.headers, timeout=10, verify=False)
        except: return None

    def homeContent(self, filter):
        cats = [
            {"type_name":"最新","type_id":"newest"},
            {"type_name":"女神","type_id":"tags/女神"},
            {"type_name":"美胸","type_id":"tags/美胸"},
            {"type_name":"AI","type_id":"tags/ai美女"},
            {"type_name":"黑丝","type_id":"tags/黑丝"},
            {"type_name":"大尺度","type_id":"tags/大尺度"},
            {"type_name":"无圣光","type_id":"tags/无圣光"},
            {"type_name":"萝莉","type_id":"tags/萝莉"},
            {"type_name":"Cosplay","type_id":"tags/Cosplay"},
            {"type_name":"私房","type_id":"tags/私房"},
            {"type_name":"尤物","type_id":"tags/尤物"}
        ]
        return {'class': cats}

    def categoryContent(self, tid, pg, filter, extend):
        return self.postList(f"{self.siteUrl}/{tid}/{pg}", int(pg))

    def postList(self, url, pg):
        r = self.fetch(url)
        l = []
        if r and r.ok:
            for m in re.finditer(r'<article[^>]*>(.*?)</article>', r.text, re.S):
                t = m.group(1)
                href = re.search(r'href=["\']([^"\']+)["\']', t)
                img = re.search(r'data-src=["\']([^"\']+)["\']', t) or re.search(r'src=["\']([^"\']+)["\']', t)
                title = re.search(r'title=["\']([^"\']+)["\']', t)
                note = re.search(r'teaser-file-info"[^>]*>(.*?)<', t, re.S)
                if href:
                    u = href.group(1)
                    p = img.group(1) if img else ""
                    if p.startswith("//"): p = "https:" + p
                    l.append({
                        'vod_id': self.siteUrl + u if u.startswith("/") else u,
                        'vod_name': title.group(1) if title else "未知",
                        'vod_pic': p,
                        'vod_remarks': note.group(1).strip() if note else "",
                        'style': {"type": "rect", "ratio": 1.33}
                    })
        return {'list': l, 'page': pg, 'pagecount': pg + 1 if len(l) else pg, 'limit': 20, 'total': 9999}

    def detailContent(self, ids):
        return {'list': [{'vod_id': ids[0], 'vod_name': '', 'type_name': '美图', 'vod_play_from': '图宅', 'vod_play_url': '点击浏览$' + ids[0]}]}

    def searchContent(self, key, quick, pg=1):
        return self.postList(f"{self.siteUrl}/search/{pg}?term={key}", int(pg))

    def playerContent(self, flag, id, vipFlags):
        imgs = []
        r = self.fetch(id)
        if r and r.ok:
            h = r.text
            imgs += self.getImgs(h)
            pgs = re.findall(r'/(\d+)(?:\.html|")', re.search(r'<div id="pager".*?</div>', h, re.S).group(0)) if 'id="pager"' in h else []
            max_pg = max(map(int, pgs)) if pgs else 1
            base = id[:-5] if id.endswith('.html') else id
            for i in range(2, min(max_pg, 30) + 1):
                r2 = self.fetch(f"{base}/{i}.html")
                if r2: imgs += self.getImgs(r2.text)
        return {"parse": 0, "url": "pics://" + "&&".join(sorted(list(set(imgs)), key=imgs.index)) if imgs else "", "header": ""}

    def getImgs(self, h):
        b = re.search(r'<div class="file-detail">(.*?)<div id="pager"', h, re.S) or re.search(r'<div class="file-detail">(.*?)<div class="related-file">', h, re.S)
        t = b.group(1) if b else h
        return [("https:" + x if x.startswith("//") else x) for x in re.findall(r'<img[^>]+data-src=["\']([^"\']+)["\']', t)]

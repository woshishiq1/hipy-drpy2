import json, re, urllib.parse, sys, os, threading
_orig = os.getcwd
def _poc():
    try: return _orig()
    except: return "/data/data/com.termux/files/usr/lib"
os.getcwd = _poc
_ts = threading.Thread.start
def _tp(self):
    if self._target: self._target(*self._args, **self._kwargs)
threading.Thread.start = _tp
sys.path[0] = "/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/dist-packages"
import requests

class Spider:
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
    NAME = "\u82b1\u5343\u8272"
    HOST = "https://eetftz.hqs2.homes"
    CATS = {"20":"\u4e9a\u6d32\u60c5\u8272","21":"\u5236\u670d\u5e08\u751f","22":"\u5361\u901a\u52a8\u6f2b","23":"\u4e09\u7ea7\u4f26\u7406","24":"\u5f3a\u5978\u4e71\u4f26","25":"\u5077\u62cd\u81ea\u62cd","26":"\u4e2d\u6587\u5b57\u5e55","27":"\u6b27\u7f8e\u6027\u7231","28":"\u4eba\u59bb\u719f\u5973","29":"\u65e0\u7801\u4e13\u533a"}
    _s = None

    def _sess(self):
        if not self._s:
            self._s = requests.Session()
            self._s.headers.update({"User-Agent":self.UA,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"zh-CN,zh;q=0.9","Referer":self.HOST+"/"})
        return self._s

    def _get(self, url):
        try:
            r = self._sess().get(url, timeout=20, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except: return ""

    def _abs(self, p):
        if p.startswith("http"): return p
        if p.startswith("//"): return "https:"+p
        return self.HOST.rstrip("/")+"/"+p.lstrip("/")

    def _parse_items(self, html):
        items = []
        seen = set()
        for m in re.finditer(r'<a class="title" href="/(\d+)\.html">([^<]+)</a>', html):
            vid = m.group(1)
            if vid in seen: continue
            seen.add(vid)
            title = m.group(2).strip()
            pic_m = re.search(r'href="/' + vid + r'\.html"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.S)
            pic = pic_m.group(1) if pic_m else ""
            dt_m = re.search(r'href="/' + vid + r'\.html"[^>]*>.*?<span>([^<]+)</span>', html, re.S)
            dt = dt_m.group(1).strip() if dt_m else ""
            items.append({"vod_id":vid,"vod_name":title,"vod_pic":pic,"vod_remarks":dt,"vod_year":"","vod_area":"","vod_actor":"","vod_director":"","vod_content":""})
        return items

    def getDependence(self):
        return ""

    def init(self, extend=""):
        self._s = None
        return True

    def homeContent(self, filter=False):
        cls = [{"type_id":k,"type_name":v} for k,v in self.CATS.items()]
        flt = {k:[{"key":"sort","name":"\u6392\u5e8f","init":"","value":[{"n":"\u6700\u65b0","v":""},{"n":"\u6700\u70ed","v":"hot"}]}] for k in self.CATS}
        vl = []
        html = self._get(self.HOST+"/cn/home/web/")
        if html: vl = self._parse_items(html)[:20]
        return {"class":cls,"filters":flt,"list":vl}

    def homeVideoContent(self):
        vl = []
        html = self._get(self.HOST+"/cn/home/web/")
        if html: vl = self._parse_items(html)
        return {"page":1,"pagecount":1,"limit":20,"total":len(vl),"list":vl}

    def categoryContent(self, tid, pg=1, filter="", extend=""):
        pg = int(pg) if pg else 1
        if extend and "hot" in str(extend):
            url = self._abs("/label/hot.html")
        else:
            url = self._abs(f"/vodtype/{tid}.html") if pg==1 else self._abs(f"/vodtype/{tid}-{pg}.html")
        html = self._get(url)
        vl = self._parse_items(html) if html else []
        nxt = bool(re.search(rf'href="/vodtype/{re.escape(str(tid))}-{pg+1}\.html"', html)) if html else False
        return {"page":pg,"pagecount":pg+1 if nxt else pg,"limit":20,"total":len(vl),"list":vl}

    def detailContent(self, ids):
        if not isinstance(ids,(list,tuple)): ids=[ids]
        res = []
        for vid in ids:
            vid = str(vid).strip()
            html = self._get(self._abs(f"/{vid}.html"))
            if not html: continue
            tm = re.search(r'class="title main-head-title"[^>]*>([^<]+)', html)
            if not tm: tm = re.search(r'<title>([^<-]+)', html)
            title = tm.group(1).strip() if tm else ""
            pm = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
            pic = pm.group(1) if pm else ""
            cm = re.search(r'fa fa-flag"[^>]*></i>([^<]+)', html)
            vc = cm.group(1).strip() if cm else ""
            mm = re.search(r"const\s+rawUrl\s*=\s*'([^']+)'", html)
            mu = mm.group(1) if mm else ""
            if not mu:
                m2 = re.search(r'https?://[^\s$#"\'<>]+\.m3u8[^\s$#"\'<>]*', html)
                mu = m2.group(0) if m2 else ""
            vod = {"vod_id":vid,"vod_name":title,"vod_pic":pic,"vod_class":vc,"type_name":vc,"vod_year":"","vod_area":"","vod_actor":"","vod_director":"","vod_remarks":"","vod_content":"","vod_play_from":self.NAME,"vod_play_url":""}
            if mu: vod["vod_play_url"] = "$"+mu
            res.append(vod)
        return {"list":res}

    def searchContent(self, key, quick=False):
        k = urllib.parse.quote(str(key))
        html = self._get(self._abs(f"/s/{k}.html"))
        vl = self._parse_items(html) if html else []
        return {"page":1,"pagecount":1,"limit":20,"total":len(vl),"list":vl}

    def playerContent(self, flag, id, vipFlags=""):
        return {"parse":0,"jx":0,"url":id,"header":{"User-Agent":self.UA,"Referer":self.HOST+"/"},"format":"application/x-mpegURL"}

    def localProxy(self, param):
        return [404,"text/plain",""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        try:
            if self._s: self._s.close()
        except: pass

spider = Spider()

if __name__ == "__main__":
    print("=== "+spider.NAME+" ===")
    h = spider.homeContent()
    for c in h.get("class",[]):
        print("  ["+c["type_id"]+"] "+c["type_name"])
    print("Home videos:", len(h.get("list",[])))
    if h.get("list"):
        v = h["list"][0]
        print("  First:", v["vod_name"])
        d = spider.detailContent([v["vod_id"]])
        if d.get("list"):
            dd = d["list"][0]
            print("  Detail:", dd["vod_name"])
            print("  Play:", dd["vod_play_url"][:100])
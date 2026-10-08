import re
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "18J"

    def init(self, extend=""):
        self.host="https://18j.tv"
        self.headers={"User-Agent":"Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36","Referer":self.host+"/"}
        self.session=requests.Session()
        self.session.headers.update(self.headers)

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "Destroy"

    def _html(self, url):
        return self.session.get(url if url.startswith("http") else self.host+url,timeout=12).text

    def _text(self, s):
        return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",s or "")).strip()

    def _list(self, html):
        out=[]
        seen=set()
        blocks=re.findall(r'<div class="box">(.*?)</li>',html,re.S|re.I)
        for block in blocks:
            m=re.search(r'<a[^>]+href=["\'](/v/(\d+)/?)["\'][^>]*title=["\']([^"\']+)["\']',block,re.S|re.I)
            if not m or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            im=re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',block,re.S|re.I)
            tag=re.search(r'<div class="vodlist_img">.*?<span[^>]*>(.*?)</span>',block,re.S|re.I)
            out.append({"vod_id":m.group(2),"vod_name":self._text(m.group(3)),"vod_pic":im.group(1).strip() if im else "","vod_remarks":self._text(tag.group(1)) if tag else ""})
        return out

    def homeContent(self, filter):
        classes=[{"type_name":"国产","type_id":"1"},{"type_name":"日韩","type_id":"2"},{"type_name":"欧美","type_id":"3"},{"type_name":"伦理","type_id":"4"},{"type_name":"成人AI","type_id":"41"},{"type_name":"动漫","type_id":"5"},{"type_name":"另类","type_id":"6"}]
        try:
            vods=self._list(self._html("/"))
        except requests.RequestException:
            vods=[]
        return {"class":classes,"list":vods}

    def homeVideoContent(self):
        try:
            return {"list":self._list(self._html("/"))}
        except requests.RequestException:
            return {"list":[]}

    def categoryContent(self, tid, pg, filter, extend):
        pg=int(pg or 1)
        path="/t/{}/".format(tid) if pg==1 else "/t/{}/page/{}/".format(tid,pg)
        try:
            vods=self._list(self._html(path))
        except requests.RequestException:
            vods=[]
        return {"page":pg,"pagecount":pg+1 if vods else pg,"limit":len(vods),"total":999999 if vods else 0,"list":vods}

    def detailContent(self, ids):
        vid=str(ids[0]).strip()
        url=self.host+"/v/{}/".format(vid)
        try:
            html=self._html(url)
        except requests.RequestException:
            html=""
        name=re.search(r'<h1[^>]*class=["\'][^"\']*play-title[^"\']*["\'][^>]*>(.*?)</h1>',html,re.S|re.I)
        if not name:
            name=re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',html,re.I)
        pic=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',html,re.I)
        desc=re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',html,re.I)
        genre=re.search(r'["\']genre["\']\s*:\s*["\']([^"\']+)',html,re.I)
        date=re.search(r'["\']uploadDate["\']\s*:\s*["\'](\d{4})',html,re.I)
        vod={"vod_id":vid,"vod_name":self._text(name.group(1)) if name else vid,"vod_pic":pic.group(1) if pic else "","type_name":genre.group(1) if genre else "","vod_year":date.group(1) if date else "","vod_content":desc.group(1).strip() if desc else "","vod_play_from":"直连","vod_play_url":"播放${}".format(url)}
        return {"list":[vod]}

    def searchContent(self, key, quick, pg="1"):
        pg=int(pg or 1)
        wd=quote(str(key),safe="")
        path="/s/wd/{}/".format(wd) if pg==1 else "/s/wd/{}/page/{}/".format(wd,pg)
        try:
            vods=self._list(self._html(path))
        except requests.RequestException:
            vods=[]
        return {"page":pg,"pagecount":pg+1 if vods else pg,"limit":len(vods),"total":999999 if vods else 0,"list":vods}

    def playerContent(self, flag, id, vipFlags):
        page=str(id).strip()
        page=page if page.startswith("http") else self.host+"/v/{}/".format(page.strip("/").split("/")[-1])
        try:
            html=self._html(page)
        except requests.RequestException:
            html=""
        m=re.search(r'const\s+source\s*=\s*["\']([^"\']+)["\']',html,re.I)
        if not m:
            m=re.search(r'https?://[^"\'\s<>]+\.m3u8(?:\?[^"\'\s<>]*)?',html,re.I)
        url=m.group(1) if m and m.lastindex else m.group(0) if m else ""
        return {"parse":0 if url else 1,"playUrl":"","url":url or page,"header":self.headers}
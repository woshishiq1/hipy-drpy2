import re,requests
from urllib.parse import quote,unquote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider=object

class Spider(BaseSpider):
    def getName(self):
        return "糖心vlog"

    def init(self,extend=""):
        self.host="https://tangxinvlog.app"
        self.lang="/zh-tw"
        self.cdn="https://t.5gcdn.xyz/videos"
        self.ua="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Mobile Safari/537.36"
        self.headers={"User-Agent":self.ua,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"zh-TW,zh;q=0.9,en;q=0.8","Referer":self.host+self.lang+"/"}
        self.img_headers={"User-Agent":self.ua,"Referer":self.host+self.lang+"/","Accept":"image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8","Connection":"keep-alive"}
        self.http=requests.Session()
        self.img_session=requests.Session()
        self.img_cache={}
        self.bad_img=set()
        self.page_cache={}

    def isVideoFormat(self,url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def homeContent(self,filter):
        return {"class":self._classes(),"list":[]}

    def homeVideoContent(self):
        return {"list":[]}

    def categoryContent(self,tid,pg,filter,extend):
        pg=int(pg or 1)
        tid=unquote(str(tid or "latest")).strip()
        if tid in ["latest","最新"]:
            data=self._actors_all()
            return {"page":pg,"pagecount":1,"limit":len(data),"total":len(data),"list":data}
        if tid in ["recommend","推荐"]:
            data=self._tags_all()
            return {"page":pg,"pagecount":1,"limit":len(data),"total":len(data),"list":data}
        if tid.startswith("actor/"):
            slug=tid[6:]
            url=self.host+self.lang+"/a/"+quote(slug,safe="")+("/" if pg<=1 else "/"+str(pg))
            data=self._list(url)
            return {"page":pg,"pagecount":999 if data else pg,"limit":30,"total":999999,"list":data}
        if tid.startswith("tag/"):
            slug=tid[4:]
            url=self.host+self.lang+"/tag/"+quote(slug,safe="")+("/" if pg<=1 else "/"+str(pg))
            data=self._list(url)
            return {"page":pg,"pagecount":999 if data else pg,"limit":30,"total":999999,"list":data}
        url=self.host+self.lang+"/tag/"+quote(tid,safe="")+("/" if pg<=1 else "/"+str(pg))
        data=self._list(url)
        return {"page":pg,"pagecount":999 if data else pg,"limit":30,"total":999999,"list":data}

    def detailContent(self,ids):
        vid=str(ids[0]).strip()
        m=re.search(r"(\d+)",vid)
        vid=m.group(1) if m else vid
        h=self._get(self.host+self.lang+"/v/"+vid+"/")
        name=self._clean(self._m(h,r"<h1[^>]*>(.*?)</h1>")) or vid
        pic=self._m(h,r'<video[^>]+poster="([^"]+)"') or self.cdn+"/"+vid+"/cover.jpg"
        actor=self._clean(self._m(h,r'<a class="nickname"[^>]*>(.*?)</a>'))
        duration=self._clean(self._m(h,r'data-pagefind-meta="duration"[^>]*>(.*?)</span>'))
        date=self._clean(self._m(h,r'<time[^>]+datetime="([^"]+)"'))
        tags=",".join([self._clean(x) for x in re.findall(r'<a class="tag"[^>]*>\s*(.*?)\s*</a>',h,re.S|re.I)])
        vod={"vod_id":vid,"vod_name":name,"vod_pic":self._pic(pic,vid),"type_name":tags,"vod_year":date,"vod_actor":actor,"vod_remarks":duration or "m3u8","vod_content":" ".join([x for x in [actor,duration,date,tags] if x]),"vod_play_from":"直连","vod_play_url":"播放$"+vid}
        return {"list":[vod]}

    def searchContent(self,key,quick=False,pg="1"):
        k=str(key or "").strip().lower()
        data=[]
        for x in self._rss():
            if k in x.get("vod_name","").lower() or k in x.get("type_name","").lower():
                data.append(x)
            if len(data)>=50:
                break
        return {"list":data}

    def playerContent(self,flag,id,vipFlags):
        vid=str(id).strip()
        m=re.search(r"(\d+)",vid)
        vid=m.group(1) if m else vid
        return {"parse":0,"playUrl":"","url":self.cdn+"/"+vid+"/index.m3u8","header":{"User-Agent":self.ua,"Referer":self.host+self.lang+"/v/"+vid+"/","Origin":self.host}}

    def localProxy(self,param):
        try:
            u=unquote(param.get("url",""))
            if not u or u in self.bad_img:
                return [404,"text/plain",""]
            if u in self.img_cache:
                return self.img_cache[u]
            r=self.img_session.get(u,headers=self.img_headers,timeout=3)
            if r.status_code!=200 or not r.content:
                self.bad_img.add(u)
                return [404,"text/plain",""]
            ct=r.headers.get("content-type","image/jpeg")
            res=[200,ct,r.content]
            if len(self.img_cache)>80:
                self.img_cache.clear()
            self.img_cache[u]=res
            return res
        except Exception:
            self.bad_img.add(unquote(param.get("url","")))
            return [404,"text/plain",""]

    def _get(self,url):
        if url in self.page_cache:
            return self.page_cache[url]
        try:
            if hasattr(self,"fetch"):
                r=self.fetch(url,headers=self.headers)
                if isinstance(r,dict):
                    h=r.get("content") or r.get("body") or ""
                elif hasattr(r,"text"):
                    h=r.text
                elif hasattr(r,"content"):
                    h=r.content.decode("utf-8","ignore")
                else:
                    h=str(r or "")
                if h and "<Response [" not in h:
                    if len(self.page_cache)>40:
                        self.page_cache.clear()
                    self.page_cache[url]=h
                    return h
        except Exception:
            pass
        try:
            r=self.http.get(url,headers=self.headers,timeout=8)
            r.encoding="utf-8"
            h=r.text if r.status_code==200 else ""
            if h:
                if len(self.page_cache)>40:
                    self.page_cache.clear()
                self.page_cache[url]=h
            return h
        except Exception:
            return ""

    def _m(self,s,p):
        m=re.search(p,s or "",re.S|re.I)
        return m.group(1) if m else ""

    def _clean(self,s):
        s=re.sub(r"<!\[CDATA\[|\]\]>","",s or "")
        return re.sub(r"\s+"," ",re.sub(r"<.*?>","",s)).replace("&amp;","&").replace("&quot;",'"').replace("&#39;","'").strip()

    def _pic(self,u,vid=""):
        u=u or self.cdn+"/"+str(vid)+"/cover.jpg"
        try:
            p=self.getProxyUrl()
            return p+("&" if "?" in p else "?")+"url="+quote(u,safe="")
        except Exception:
            return u

    def _classes(self):
        h=self._get(self.host+self.lang+"/tag/")
        arr=[{"type_id":"latest","type_name":"最新"},{"type_id":"recommend","type_name":"推荐"}]
        for href,name in re.findall(r'<a href="/zh-tw/tag/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>',h,re.S|re.I):
            slug=unquote(href).strip("/")
            title=self._clean(name)
            if slug and title and title not in [x["type_name"] for x in arr]:
                arr.append({"type_id":"tag/"+slug,"type_name":title})
        return arr

    def _actors_all(self):
        h=self._get(self.host+self.lang+"/a/")
        arr=[]
        for href,name,num in re.findall(r'<a href="/zh-tw/a/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>\s*<span class="num"[^>]*>(.*?)</span>',h,re.S|re.I):
            slug=unquote(href).strip("/")
            title=self._clean(name)
            count=self._clean(num)
            if slug and title:
                arr.append({"vod_id":"actor/"+slug,"vod_name":title,"vod_pic":"","vod_remarks":count,"vod_tag":"folder"})
        return self._dedup(arr)

    def _tags_all(self):
        h=self._get(self.host+self.lang+"/tag/")
        arr=[]
        for href,name,num in re.findall(r'<a href="/zh-tw/tag/([^"]+)"[^>]*>\s*<span class="name"[^>]*>(.*?)</span>\s*<span class="num"[^>]*>(.*?)</span>',h,re.S|re.I):
            slug=unquote(href).strip("/")
            title=self._clean(name)
            count=self._clean(num)
            if slug and title:
                arr.append({"vod_id":"tag/"+slug,"vod_name":title,"vod_pic":"","vod_remarks":count,"vod_tag":"folder"})
        return self._dedup(arr)

    def _list(self,url):
        h=self._get(url)
        arr=[]
        for c in re.split(r'<article class="card"',h,re.I)[1:]:
            href=self._m(c,r'<a class="cover-link" href="([^"]+)"') or self._m(c,r'href="([^"]*/v/\d+/[^"]*)"')
            m=re.search(r"/v/(\d+)/",href)
            if not m:
                continue
            vid=m.group(1)
            name=self._clean(self._m(c,r'aria-label="([^"]+)"') or self._m(c,r'<img[^>]+alt="([^"]+)"') or self._m(c,r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>'))
            pic=self._m(c,r'<img[^>]+src="([^"]+)"') or self.cdn+"/"+vid+"/cover.jpg"
            mark=self._clean(self._m(c,r'<span class="duration"[^>]*>(.*?)</span>'))
            arr.append({"vod_id":vid,"vod_name":name or vid,"vod_pic":self._pic(pic,vid),"vod_remarks":mark})
            if len(arr)>=30:
                break
        return self._dedup(arr)

    def _rss(self):
        h=self._get(self.host+self.lang+"/rss.xml")
        arr=[]
        for it in re.findall(r"<item>(.*?)</item>",h,re.S|re.I):
            title=self._clean(self._m(it,r"<title>(.*?)</title>"))
            link=self._m(it,r"<link>(.*?)</link>")
            desc=self._clean(self._m(it,r"<description>(.*?)</description>"))
            date=self._clean(self._m(it,r"<pubDate>(.*?)</pubDate>"))
            m=re.search(r"/v/(\d+)/",link)
            if m:
                vid=m.group(1)
                arr.append({"vod_id":vid,"vod_name":title or vid,"vod_pic":self._pic(self.cdn+"/"+vid+"/cover.jpg",vid),"vod_remarks":date[:16] if date else "m3u8","type_name":desc})
            if len(arr)>=120:
                break
        return self._dedup(arr)

    def _dedup(self,arr):
        out=[]
        seen=set()
        for x in arr:
            k=x.get("vod_id")
            if k and k not in seen:
                seen.add(k)
                out.append(x)
        return out

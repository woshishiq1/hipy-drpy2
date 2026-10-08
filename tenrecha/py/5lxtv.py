#!/usr/bin/python
# -*- coding: utf-8 -*-
import re,json,requests,urllib.parse
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "5lxtv"

    def init(self, extend=""):
        self.host="https://5lxtv.com"
        self.headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"zh-CN,zh;q=0.9,en;q=0.8"}

    def _h(self,referer=None,stream=False):
        h=dict(self.headers)
        if referer:h["Referer"]=referer
        if stream:
            h["Accept"]="*/*"
            h["Origin"]=self.host
        return h

    def _get(self,url,referer=None):
        r=requests.get(url,headers=self._h(referer),timeout=15,verify=False)
        r.encoding="utf-8"
        return r.text

    def _fix(self,url):
        if not url:return ""
        if url.startswith("//"):return "https:"+url
        if url.startswith("/"):return self.host+url
        return url

    def _clean(self,s):
        return re.sub(r"\s+"," ",re.sub(r"<.*?>","",s or "")).strip()

    def _parse_list(self,html):
        vod=[]
        ids=set()
        blocks=re.findall(r'<a[^>]+href="(/videos/[^"]+)"[^>]*>([\s\S]*?)</a>',html)
        for href,block in blocks:
            href=self._fix(href)
            img=re.search(r'<img[^>]+src="([^"]+)"[^>]*>',block)
            alt=re.search(r'<img[^>]+alt="([^"]*)"',block)
            pic=self._fix(img.group(1)) if img else ""
            title=self._clean(alt.group(1)) if alt else ""
            if not title:
                ts=[self._clean(x) for x in re.findall(r'>([^<>]{2,120})<',block)]
                ts=[x for x in ts if x and not re.match(r'^\d+:\d+|^▶|^\d{4}-\d{2}-\d{2}$',x)]
                title=ts[-1] if ts else ""
            remark=""
            rm=re.findall(r'>([^<>]*(?:\d+:\d+|\d+:\d+:\d+|▶[^<>]*)[^<>]*)<',block)
            if rm:remark=" ".join([self._clean(x) for x in rm if self._clean(x)])[:30]
            if href and title and href not in ids:
                ids.add(href)
                vod.append({"vod_id":href,"vod_name":title,"vod_pic":pic,"vod_remarks":remark})
        if not vod:
            for m in re.finditer(r'href="(/videos/[^"]+)"[\s\S]{0,800}?<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"',html):
                href=self._fix(m.group(1))
                if href not in ids:
                    ids.add(href)
                    vod.append({"vod_id":href,"vod_name":self._clean(m.group(3)),"vod_pic":self._fix(m.group(2)),"vod_remarks":""})
        return vod

    def _parse_cats(self,html):
        arr=[]
        seen=set()
        bad=set(["/","/latest","/rankings","/channels","/actors","/tags","/favorites"])
        for m in re.finditer(r'<a[^>]+href="(/[^"/?#]+)"[^>]*class="[^"]*(?:group|relative|block)[^"]*"[\s\S]*?</a>',html):
            href=m.group(1)
            if href in bad or href.startswith("/videos"):continue
            block=m.group(0)
            img_alt=re.search(r'<img[^>]+alt="([^"]+)"',block)
            txt=[self._clean(x) for x in re.findall(r'>([^<>]{2,30})<',block)]
            txt=[x for x in txt if x and x.lower() not in ["channel","channels","creator","scandal"]]
            name=self._clean(img_alt.group(1)) if img_alt else (txt[-1] if txt else href.strip("/"))
            if href not in seen and re.match(r'^/[a-z0-9_-]+$',href):
                seen.add(href)
                arr.append({"type_name":name,"type_id":href.strip("/")})
        if not arr:
            arr=[{"type_name":"中文字幕","type_id":"chinese"},{"type_name":"偷拍盜攝","type_id":"selfie"},{"type_name":"黑料吃瓜","type_id":"scandal"},{"type_name":"獨家AV","type_id":"exclusive"},{"type_name":"綠帽NTR","type_id":"cuckold"},{"type_name":"FC2外流","type_id":"fc2"},{"type_name":"網紅UP主","type_id":"upzhu"}]
        return arr

    def homeContent(self,filter):
        chtml=self._get(self.host+"/channels")
        vhtml=self._get(self.host+"/latest")
        classes=[{"type_name":"最新","type_id":"latest"}]+self._parse_cats(chtml)+[{"type_name":"排行","type_id":"rankings"}]
        ids=[]
        clean=[]
        for c in classes:
            if c["type_id"] not in ids:
                ids.append(c["type_id"])
                clean.append(c)
        return {"class":clean,"list":self._parse_list(vhtml)}

    def homeVideoContent(self):
        html=self._get(self.host+"/latest")
        return {"list":self._parse_list(html)}

    def categoryContent(self,tid,pg,filter,extend):
        pg=str(pg or "1")
        path="/latest" if tid=="latest" else "/rankings" if tid=="rankings" else "/"+tid.strip("/")
        url=self.host+path+("?page="+pg if "?" not in path else "&page="+pg)
        html=self._get(url,self.host+"/channels")
        vod=self._parse_list(html)
        has_more=bool(re.search(r'page=%s|下一頁|下一页|Next|rel="next"'%(int(pg)+1),html))
        return {"page":int(pg),"pagecount":int(pg)+1 if has_more else int(pg),"limit":len(vod) or 30,"total":999999 if has_more else len(vod),"list":vod}

    def detailContent(self,ids):
        url=ids[0]
        html=self._get(url,self.host+"/latest")
        name=re.search(r'<h1[^>]*>([\s\S]*?)</h1>',html)
        pic=re.search(r'poster="([^"]+)"|<meta property="og:image" content="([^"]+)"',html)
        desc=[]
        for k in ["時長","观看","觀看","發布","女优","女優","標籤","标签"]:
            m=re.search(k+r'[\s\S]{0,120}?<[^>]+>([^<>]+)<',html)
            if m:desc.append(k+":"+self._clean(m.group(1)))
        vod={"vod_id":url,"vod_name":self._clean(name.group(1)) if name else "5lxtv","vod_pic":self._fix((pic.group(1) or pic.group(2)) if pic else ""),"type_name":"","vod_year":"","vod_area":"","vod_remarks":"","vod_actor":"","vod_director":"","vod_content":" ".join(desc),"vod_play_from":"5lxtv","vod_play_url":"播放$"+url}
        return {"list":[vod]}

    def searchContent(self,key,quick,pg="1"):
        q=urllib.parse.quote(key)
        url=self.host+"/search?q="+q+("&page="+str(pg) if str(pg)!="1" else "")
        html=self._get(url,self.host)
        return {"list":self._parse_list(html),"page":int(pg)}

    def _real_play(self,html):
        ps=[r'var\s+src\s*=\s*["\']([^"\']+playlist\.m3u8[^"\']*)["\']',r'var\s+src\s*=\s*["\']([^"\']+)["\']',r'loadSource\(["\']([^"\']+playlist\.m3u8[^"\']*)["\']\)',r'["\'](https?://[^"\']+playlist\.m3u8[^"\']*)["\']',r'(https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)']
        for p in ps:
            m=re.search(p,html)
            if m:
                return m.group(1).replace("\\/","/").replace("&amp;","&").strip()
        return ""

    def playerContent(self,flag,id,vipFlags):
        url=id
        html=self._get(url,self.host)
        play=self._real_play(html)
        if not play:return {"parse":1,"playUrl":"","url":url}
        return {"parse":0,"playUrl":"","url":play,"header":json.dumps(self._h(url,True))}
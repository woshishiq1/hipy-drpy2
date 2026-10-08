#!/usr/bin/python
# -*- coding: utf-8 -*-
import json
import re
import requests
import base64
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "教授"

    def init(self, extend=""):
        self.host="https://zrq.jsaa100.vip:8601"
        self.ua="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
        self.t="260210"
        self.group={}
        self.css=""
        self.path=""
        self.domain=""
        self.img_cache={}
        self.headers={"User-Agent":self.ua,"Referer":self.host+"/"}
        self.s=requests.Session()
        self.s.headers.update(self.headers)
        self.page_size=24
        self.real_pic_count=18
        self.workers=6
        self.dk={"e":"P","w":"D","T":"y","+":"J","l":"!","t":"L","E":"E","@":"2","d":"a","b":"%","q":"l","X":"v","~":"R","5":"r","&":"X","C":"j","]":"F","a":")","^":"m",",":"~","}":"1","x":"C","c":"(","G":"@","h":"h",".":"*","L":"s","=":",","p":"g","I":"Q","1":"7","_":"u","K":"6","F":"t","2":"n","8":"=","k":"G","Z":"]",")":"b","P":"}","B":"U","S":"k","6":"i","g":":","N":"N","i":"S","%":"+","-":"Y","?":"|","4":"z","*":"-","3":"^","[":"{","(":"c","u":"B","y":"M","U":"Z","H":"[","z":"K","9":"H","7":"f","R":"x","v":"&","!":";","M":"_","Q":"9","Y":"e","o":"4","r":"A","m":".","O":"o","V":"W","J":"p","f":"d",":":"q","{":"8","W":"I","j":"?","n":"5","s":"3","|":"T","A":"V","D":"w",";":"O"}
        self._load_group()

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or url.endswith(".mp4")

    def manualVideoCheck(self):
        return True

    def homeContent(self, filter):
        self._load_group()
        data=self._json(self.host+"/index.json?"+self.t)
        idx=data.get("index_videos",{})
        vals=list(idx.values()) if isinstance(idx,dict) else idx if isinstance(idx,list) else []
        classes=[]
        videos=[]
        for x in vals:
            if not isinstance(x,dict):
                continue
            tid=str(x.get("id",""))
            name=self._dec(x.get("name") or x.get("title") or tid)
            if tid and name:
                classes.append({"type_id":tid,"type_name":name})
            videos+=self._arr(x.get("videos"))
        if not videos and classes:
            videos=self._raw_category(classes[0]["type_id"],1)
        return {"class":classes,"filters":{},"list":self._vods(videos[:self.page_size])}

    def homeVideoContent(self):
        return self.homeContent(False).get("list",[])

    def categoryContent(self, tid, pg, filter, extend):
        data=self._json(self.host+"/type/"+str(tid)+"_"+str(pg)+".json?"+self.t)
        box=data.get("data",data) if isinstance(data,dict) else {}
        arr=self._arr(box.get("videos") or box.get("list") or box.get("data"))
        pc=int(box.get("page_count") or box.get("pagecount") or 999)
        return {"page":int(pg),"pagecount":pc,"limit":len(arr[:self.page_size]),"total":pc*len(arr) if arr else 0,"list":self._vods(arr[:self.page_size])}

    def detailContent(self, ids):
        vid=str(ids[0])
        data=self._json(self.host+"/video/"+vid+".json?"+self.t)
        v=data.get("video",data) if isinstance(data,dict) else {}
        sid=str(v.get("serial_number") or vid)
        name=self._dec(v.get("title") or v.get("name") or vid)
        remarks=str(v.get("date") or v.get("second") or "")
        genres=v.get("genres",[])
        acts=v.get("actresses",[])
        type_name=",".join([self._dec(i.get("name","")) if isinstance(i,dict) else self._dec(i) for i in genres]) if isinstance(genres,list) else ""
        actor=",".join([self._dec(i.get("name","")) if isinstance(i,dict) else self._dec(i) for i in acts]) if isinstance(acts,list) else ""
        vod={"vod_id":vid,"vod_name":name,"vod_pic":self._img(sid),"type_name":type_name,"vod_year":"","vod_area":"","vod_remarks":remarks,"vod_actor":actor,"vod_director":"","vod_content":name,"vod_play_from":"zrq","vod_play_url":name+"$"+sid}
        return {"list":[vod]}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg):
        data=self._json(self.host+"/search.json?search="+quote(key)+"&page="+str(pg))
        box=data.get("data",data) if isinstance(data,dict) else data
        arr=self._arr(box.get("videos") or box.get("list") or box.get("data") if isinstance(box,dict) else box)
        return {"page":int(pg),"pagecount":999,"limit":len(arr[:self.page_size]),"total":999999,"list":self._vods(arr[:self.page_size])}

    def playerContent(self, flag, id, vipFlags):
        self._load_group()
        domain=(self.domain or "zrq.jsaa100.vip:8601").replace("https://","").replace("http://","").strip("/")
        return {"parse":0,"url":"https://"+domain+"/m3u8/"+str(id)+"/index_domain.m3u8?"+self.t,"header":self.headers}

    def _raw_category(self, tid, pg):
        data=self._json(self.host+"/type/"+str(tid)+"_"+str(pg)+".json?"+self.t)
        box=data.get("data",data) if isinstance(data,dict) else {}
        return self._arr(box.get("videos") or box.get("list") or box.get("data"))

    def _load_group(self):
        if self.group:
            return
        g=self._json(self.host+"/data.json?0571")
        self.group=g if isinstance(g,dict) else {}
        self.css=str(self.group.get("css_domain") or self.host).rstrip("/")
        self.path=str(self.group.get("path") or "").strip("/")
        self.domain=str(self.group.get("novel_domain") or self.group.get("index_domain") or self.host).strip("/")

    def _vods(self, arr):
        arr=[x for x in arr if isinstance(x,dict)]
        pics={}
        sids=[str(x.get("serial_number") or x.get("id") or "") for x in arr[:self.real_pic_count]]
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            fs={ex.submit(self._img,sid):sid for sid in sids if sid}
            for f in as_completed(fs):
                sid=fs[f]
                try:
                    pics[sid]=f.result()
                except Exception:
                    pics[sid]=self._placeholder()
        return [self._vod(x,pics) for x in arr]

    def _vod(self, x, pics=None):
        vid=str(x.get("id") or x.get("vod_id") or "")
        sid=str(x.get("serial_number") or vid)
        name=self._dec(x.get("title") or x.get("name") or vid)
        pic=pics.get(sid,self._placeholder()) if isinstance(pics,dict) else self._placeholder()
        return {"vod_id":vid,"vod_name":name,"vod_pic":pic,"vod_remarks":str(x.get("date") or x.get("second") or "")}

    def _pic_url(self, sid):
        self._load_group()
        pic=str(self.group.get("pic_domain") or "").rstrip("/")
        return pic+"/pic/"+str(sid)+"/thumbnail.css" if pic and sid else ""

    def _img(self, sid):
        if sid in self.img_cache:
            return self.img_cache[sid]
        url=self._pic_url(sid)
        if not url:
            return self._placeholder()
        try:
            r=requests.get(url,headers=self.headers,timeout=3,verify=False)
            b=r.content
            if len(b)<20:
                return self._placeholder()
            img=bytes([i ^ 0x88 for i in b])
            head=img[:12]
            mime="image/png" if head.startswith(b"\x89PNG") else "image/webp" if head.startswith(b"RIFF") else "image/jpeg"
            val="data:"+mime+";base64,"+base64.b64encode(img).decode()
            if len(self.img_cache)<120:
                self.img_cache[sid]=val
            return val
        except Exception:
            return self._placeholder()

    def _arr(self, x):
        if isinstance(x,list):
            return x
        if isinstance(x,dict):
            return list(x.values())
        return []

    def _placeholder(self):
        return (self.css+"/"+self.path+"/images/load320.png?0507").replace("//images","/images") if self.css else "https://inews.gtimg.com/newsapp_ls/0/13263837859/0"

    def _json(self, url):
        s=self._get(url).strip()
        if not s:
            return {}
        s=self._obj(s) if s.startswith("var ") or s.find("{")>0 else s
        try:
            return json.loads(s)
        except Exception:
            return {}

    def _obj(self, s):
        a=s.find("{")
        if a<0:
            return s
        q=False
        esc=False
        dep=0
        for i,ch in enumerate(s[a:],a):
            if q:
                if esc:
                    esc=False
                elif ch=="\\":
                    esc=True
                elif ch=='"':
                    q=False
            else:
                if ch=='"':
                    q=True
                elif ch=="{":
                    dep+=1
                elif ch=="}":
                    dep-=1
                    if dep==0:
                        return s[a:i+1]
        return s[a:]

    def _get(self, url):
        try:
            r=self.s.get(url,timeout=8,verify=False)
            r.encoding="utf-8"
            return r.text
        except Exception:
            return ""

    def _dec(self, s):
        s="".join([self.dk.get(i,i) for i in str(s or "")])
        def f(m):
            try:
                return chr(int(m.group(1)))
            except Exception:
                return m.group(0)
        return re.sub(r"&#(\d+);?",f,s).strip()
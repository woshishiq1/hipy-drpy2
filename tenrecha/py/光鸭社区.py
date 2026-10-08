import re,json,base64,requests,threading
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "光鸭社区"
    def init(self,extend=""):
        self.host="https://gy.lubao2.de5.net";self.sb="https://houhvngggkkcqcjmzafx.supabase.co";self.tmdb="https://api.tmdb.org";self.tmdb_img="https://images.tmdb.org/t/p";self.tmdb_key="2894d9a1baf7812b451de03c801b0281"
        self.key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhvdWh2bmdnZ2trY3Fjam16YWZ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc2Mjg2MjgsImV4cCI6MjA5MzIwNDYyOH0.FUUT9ETU-lP5iNqwK3i7nflwGLSBHM1b-qIs9CoVles"
        self.cookie="";self.page_size=40;self.default_pic="https://miaoda-edit-image.cdn.bcebos.com/b74i02x880e9/IMG-b7c60ycpg3r4.png";self.pic_cache={};self.pic_pending=set();self.pic_sem=threading.BoundedSemaphore(3);self.cache_file="/storage/emulated/0/Download/gy_tmdb_pic_cache.json";self.list_fields="id,title,cover_url,year,region,genres,category_id"
        self.headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36","Referer":self.host+"/","apikey":self.key,"Authorization":"Bearer "+self.key,"Accept":"application/json"}
        self.session=requests.Session();self.session.headers.update(self.headers)
        if extend:
            try:
                e=json.loads(extend);self.cookie=e.get("cookie","") or self.cookie;self.page_size=int(e.get("page_size",40) or 40);self.tmdb_key=e.get("tmdb_key",self.tmdb_key);self.tmdb=e.get("tmdb_api",self.tmdb);self.tmdb_img=e.get("tmdb_img",self.tmdb_img);self.default_pic=e.get("default_pic",self.default_pic);self.cache_file=e.get("cache_file",self.cache_file)
            except Exception:self.cookie=extend
        if self.cookie:self.headers["Cookie"]=self.cookie;self.session.headers.update({"Cookie":self.cookie})
        self._load_cache()
    def _load_cache(self):
        try:
            with open(self.cache_file,"r",encoding="utf-8") as f:self.pic_cache=json.load(f)
        except Exception:self.pic_cache={}
    def _save_cache(self):
        try:
            if len(self.pic_cache)%5==0:
                with open(self.cache_file,"w",encoding="utf-8") as f:json.dump(self.pic_cache,f,ensure_ascii=False,separators=(",",":"))
        except Exception:None
    def _get(self,path):
        try:
            r=self.session.get(self.sb+path,timeout=12);return r.json() if r.text else []
        except Exception:return []
    def _tmget(self,path,params):
        try:
            params.update({"api_key":self.tmdb_key,"language":"zh-CN"});r=requests.get(self.tmdb+path,params=params,headers={"User-Agent":self.headers["User-Agent"]},timeout=5);return r.json() if r.text else {}
        except Exception:return {}
    def _enc(self,o): return base64.urlsafe_b64encode(json.dumps(o,ensure_ascii=False,separators=(",",":")).encode()).decode().rstrip("=")
    def _dec(self,s):
        try:return json.loads(base64.urlsafe_b64decode((s+"="*(-len(s)%4)).encode()).decode())
        except Exception:return {"url":s}
    def _clean(self,s): return re.sub(r"\s+"," ",str(s or "")).replace("#","＃").replace("$","＄").strip()
    def _title(self,s):
        s=re.sub(r"\[tmdb-\d+\]","",str(s or ""),flags=re.I);s=re.sub(r"\[[^\]]+\]|【[^】]+】|\([^)]*\)|（[^）]*）"," ",s);s=re.sub(r"\b(19|20)\d{2}\b.*$","",s);s=re.sub(r"\.(2160p|1080p|720p|WEB-DL|BluRay|H265|H264|AAC|SONYHD).*$","",s,flags=re.I);return self._clean(s).strip(" ._-—")
    def _pkey(self,x):
        name=x.get("title") or "";year=str(x.get("year") or "");mid=re.search(r"tmdb-(\d+)",name,re.I);return mid.group(1) if mid else self._title(name)+year
    def _poster(self,x,search=False):
        pic=x.get("cover_url") or ""
        if pic:return pic
        if not search:return self.default_pic
        ck=self._pkey(x)
        if not ck:return self.default_pic
        if ck in self.pic_cache:return self.pic_cache[ck]
        if ck not in self.pic_pending:
            self.pic_pending.add(ck);threading.Thread(target=self._fill_poster,args=(dict(x),ck),daemon=True).start()
        return self.default_pic
    def _fill_poster(self,x,ck):
        self.pic_sem.acquire();p="";name=x.get("title") or "";year=str(x.get("year") or "");mid=re.search(r"tmdb-(\d+)",name,re.I)
        try:
            if mid:
                for t in ["movie","tv"]:
                    j=self._tmget("/3/%s/%s"%(t,mid.group(1)),{});p=j.get("poster_path") or j.get("backdrop_path") or ""
                    if p:break
            if not p:
                q=self._title(name);j=self._tmget("/3/search/multi",{"query":q,"year":year}) if q else {};rs=[i for i in j.get("results",[]) if i.get("poster_path")]
                if not rs and q:j=self._tmget("/3/search/multi",{"query":q});rs=[i for i in j.get("results",[]) if i.get("poster_path")]
                p=rs[0].get("poster_path","") if rs else ""
            self.pic_cache[ck]=self.tmdb_img+"/w500"+p if p else self.default_pic;self._save_cache()
        except Exception:self.pic_cache[ck]=self.default_pic
        self.pic_pending.discard(ck);self.pic_sem.release()
    def _cats_raw(self): return self._get("/rest/v1/categories?select=id,name&parent_id=is.null&order=sort_order.asc")
    def _cats(self): return [{"type_id":x.get("id",""),"type_name":x.get("name","")} for x in self._cats_raw() if x.get("id") and x.get("name")]
    def _cat_names(self): return {x.get("id",""):x.get("name","") for x in self._cats_raw() if x.get("id")}
    def _item(self,x,search=True):
        name=self._clean(x.get("title") or "光鸭资源");remark=" ".join([str(x.get("year") or ""),x.get("region") or ""]).strip()
        if not remark and x.get("genres"):remark="/".join(x.get("genres")[:2])
        return {"vod_id":x.get("id",""),"vod_name":name,"vod_pic":self._poster(x,search),"vod_remarks":remark}
    def _folder(self,name,count,kw,cid,pic=""): return {"vod_id":"folder:"+self._enc({"kw":kw,"cid":cid,"name":name}),"vod_name":"📁 %s  %s条"%(name,count),"vod_pic":pic or self.default_pic,"vod_remarks":"点击查看","vod_tag":"folder"}
    def _search_arr(self,key,limit=300,offset=0):
        q=quote("*"+str(key or "")+"*")
        return self._get("/rest/v1/resources?select=%s&status=eq.approved&title=ilike.%s&order=created_at.desc&limit=%s&offset=%s"%(self.list_fields,q,limit,offset)) if key else []
    def _list(self,path): return [self._item(x) for x in self._get(path) if x.get("id")]
    def homeContent(self,filter): return {"class":self._cats(),"filters":{},"list":self._list("/rest/v1/resources?select=%s&status=eq.approved&order=created_at.desc&limit=30"%self.list_fields)}
    def homeVideoContent(self): return {"list":self._list("/rest/v1/resources?select=%s&status=eq.approved&order=created_at.desc&limit=30"%self.list_fields)}
    def categoryContent(self,tid,pg,filter,extend):
        page=int(pg) if str(pg).isdigit() else 1;start=(page-1)*self.page_size
        if str(tid).startswith("folder:"):
            o=self._dec(str(tid)[7:]);arr=[x for x in self._search_arr(o.get("kw",""),500,0) if x.get("category_id")==o.get("cid")];lst=arr[start:start+self.page_size]
            return {"page":page,"pagecount":max(1,(len(arr)+self.page_size-1)//self.page_size),"limit":self.page_size,"total":len(arr),"list":[self._item(x) for x in lst if x.get("id")]}
        arr=self._get("/rest/v1/resources?select=%s&status=eq.approved&order=created_at.desc&category_id=eq.%s&limit=%s&offset=%s"%(self.list_fields,quote(str(tid)),self.page_size,start));total=start+len(arr)+(1 if len(arr)>=self.page_size else 0)
        return {"page":page,"pagecount":page+(1 if len(arr)>=self.page_size else 0),"limit":self.page_size,"total":total,"list":[self._item(x) for x in arr if x.get("id")]}
    def searchContent(self,key,quick,pg="1"):
        page=int(pg) if str(pg).isdigit() else 1;arr=self._search_arr(key,500,0);names=self._cat_names();groups={}
        for x in arr:
            cid=x.get("category_id") or "other";groups.setdefault(cid,[]).append(x)
        if page==1 and len(groups)>1:
            order=sorted(groups.items(),key=lambda kv:-len(kv[1]));return {"page":1,"pagecount":1,"limit":self.page_size,"total":len(arr),"list":[self._folder(names.get(cid,"其他"),len(v),key,cid,next((i.get("cover_url") for i in v if i.get("cover_url")),"")) for cid,v in order]}
        start=(page-1)*self.page_size;lst=arr[start:start+self.page_size]
        return {"page":page,"pagecount":max(1,(len(arr)+self.page_size-1)//self.page_size),"limit":self.page_size,"total":len(arr),"list":[self._item(x) for x in lst if x.get("id")]}
    def detailContent(self,ids):
        vid=ids[0] if ids else "";arr=self._get("/rest/v1/resources?select=*&id=eq.%s&limit=1"%quote(str(vid))) if vid and not str(vid).startswith("folder:") else []
        if not arr:return {"list":[]}
        x=arr[0];name=self._clean(x.get("title") or "光鸭资源");pic=self._poster(x,True);content=self._clean(x.get("description") or "");links=[]
        if x.get("pan_link"):links.append(("主链接",x.get("pan_link"),x.get("pan_password") or ""))
        for i,u in enumerate(x.get("backup_links") or []):
            if isinstance(u,dict):links.append((u.get("name") or "备用%d"%(i+1),u.get("url") or u.get("link") or "",u.get("password") or u.get("pwd") or ""))
            elif isinstance(u,str):links.append(("备用%d"%(i+1),u,""))
        if not links:links.append(("详情页",self.host+"/resource/"+vid,""))
        eps=[self._clean(n)+(" 提取码:"+p if p else "")+"$"+self._enc({"url":u,"pwd":p}) for n,u,p in links if u]
        return {"list":[{"vod_id":vid,"vod_name":name,"vod_pic":pic,"vod_year":str(x.get("year") or ""),"vod_area":x.get("region") or "","vod_content":content,"vod_play_from":"光鸭云盘","vod_play_url":"#".join(eps)}]}
    def playerContent(self,flag,id,vipFlags):
        o=self._dec(id);u=o.get("url",id) if isinstance(o,dict) else id
        if not u:return {"parse":1,"jx":0,"url":""}
        if re.search(r"\.(m3u8|mp4|mkv|flv|avi|mov)(\?|$)",u,re.I):return {"parse":0,"jx":0,"url":u,"header":json.dumps({"User-Agent":self.headers["User-Agent"],"Referer":self.host+"/"})}
        return {"parse":0,"jx":0,"url":"push://"+u if u.startswith("http") else u}
    def localProxy(self,params): return [404,"text/plain",""]
    def isVideoFormat(self,url): return bool(re.search(r"\.(m3u8|mp4|mkv|flv|avi|mov)(\?|$)",str(url),re.I))
    def manualVideoCheck(self): return False
    def destroy(self):
        try:
            with open(self.cache_file,"w",encoding="utf-8") as f:json.dump(self.pic_cache,f,ensure_ascii=False,separators=(",",":"))
        except Exception:None
        return None

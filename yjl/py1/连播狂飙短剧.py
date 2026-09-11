import re,json,requests,os
from urllib.parse import quote,unquote
from base.spider import Spider

AUTH_EMAIL=os.environ.get("DRAMA_EMAIL","test12345678@gmail.com")
AUTH_PASS=os.environ.get("DRAMA_PASS","Test123456!")

class Spider(Spider):
    def getName(self):return "狂飙短剧"
    def init(self,extend=""):
        self.host="https://ai.dramarush.tv"
        self.headers={"User-Agent":"Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 Chrome/131.0 Safari/537.36","Referer":self.host+"/zh/","Accept":"application/json,text/plain,*/*"}
        self.session=requests.Session();self.cache={};self.cursor={};self.seen_page={};self.eps={};self._logged_in=False;self._unlock_cache=set()
    def _login(self):
        if self._logged_in:return True
        if not AUTH_EMAIL or not AUTH_PASS:return False
        try:
            r=self.session.post(self.host+"/api/auth/sign-in/email",json={"email":AUTH_EMAIL,"password":AUTH_PASS},headers={**self.headers,"Content-Type":"application/json"},timeout=10)
            if r.status_code==200:self._logged_in=True;return True
        except Exception:pass
        return False
    def _post_api(self,name,data):
        try:
            r=self.session.post(self.host+"/api/trpc/"+name,json={"json":data},headers={**self.headers,"Content-Type":"application/json"},timeout=10)
            j=r.json();return j.get("result",{}).get("data",{}).get("json",{}) if not j.get("error") else {"_error":j["error"]}
        except Exception:return {}
    def _try_unlock(self,episode_id):
        if episode_id in self._unlock_cache:return True
        if not self._login():return False
        r=self._post_api("billing.unlockEpisode",{"episodeId":episode_id,"source":"COINS"})
        if r.get("coinBalance") is not None or r.get("balance") is not None:self._unlock_cache.add(episode_id);return True
        return not r.get("_error")
    def _enc(self,o):return quote(json.dumps({"json":o},ensure_ascii=False,separators=(",",":")),safe="")
    def _api(self,name,data=None):
        try:
            url=self.host+"/api/trpc/"+name+("?input="+self._enc(data) if data is not None else "")
            return self.session.get(url,headers=self.headers,timeout=12).json().get("result",{}).get("data",{}).get("json",{})
        except Exception:return {} if data is not None else []
    def _fix(self,u):return self.host+u if u and u.startswith("/") else u or ""
    def _img_min(self,u):
        if not u or "_minimize." in u:return u or ""
        q="";p=u
        if "?" in u:p,q=u.split("?",1);q="?"+q
        i=p.rfind(".")
        return (p[:i]+"_minimize.webp"+q) if i>p.rfind("/") else u
    def _pic(self,v,x):
        a=[v.get("cover"),v.get("poster"),x.get("vod_pic")]
        b=[]
        for u in a:
            if not u or "dc/img/828ed491f008e85d9caef01a.jpg" in u:continue
            if "cdn.shorttv.online/lsj/" in u:u=u.replace("https://cdn.shorttv.online/lsj/","https://raw.shorttv.online/lsj/")
            b.append(self._img_min(u))
        return b[0] if b else ""
    def _it(self,x):
        if not isinstance(x,dict):return {}
        v=x.get("drama") or x;vid=str(v.get("id") or x.get("id") or "")
        if not vid:return {}
        d={"vod_id":vid,"vod_name":v.get("title") or x.get("vod_name") or vid,"vod_pic":self._pic(v,x),"vod_remarks":str(v.get("totalEpisodes") or "").strip()+"集" if v.get("totalEpisodes") else x.get("vod_remarks","")}
        d["vod_content"]=v.get("description") or x.get("vod_content","");d["trailerUrl"]=self._fix(x.get("trailerUrl") or x.get("trailerUrl", ""));d["firstEpisodeId"]=x.get("firstEpisodeId") or ""
        return d
    def _items(self,d,mode="all",need_pic=False):
        arr=d.get("items",[]) if isinstance(d,dict) else d if isinstance(d,list) else []
        out=[];seen_id=set();seen_name=set()
        for x in arr:
            v=x.get("drama") if isinstance(x,dict) else {};tags=[str(t.get("name") or "") for t in v.get("tags",[]) if isinstance(t,dict)] if isinstance(v,dict) else []
            adult=any(t.startswith("adult-") or "不伦" in t or "偷情" in t for t in tags)
            if (mode=="adult" and not adult) or (mode=="normal" and adult):continue
            it=self._it(x);name=re.sub(r"\s+","",it.get("vod_name",""))
            if need_pic and not it.get("vod_pic"):continue
            if it.get("vod_id") and name and it["vod_id"] not in seen_id and name not in seen_name:
                seen_id.add(it["vod_id"]);seen_name.add(name);self.cache[it["vod_id"]]=it;out.append({k:it.get(k,"") for k in ["vod_id","vod_name","vod_pic","vod_remarks"]})
        return out
    def _fill(self,out,seen,items):
        for x in items:
            k=x.get("vod_id") or re.sub(r"\s+","",x.get("vod_name",""))
            if k and k not in seen:seen.add(k);out.append(x)
    def _rank(self,cache_key,pg,tab,kind,mode="all"):
        data={"limit":12,"tab":tab}
        if kind:data["contentKind"]=kind
        cur=self.cursor.get(cache_key,{}).get(pg)
        if pg>1 and not cur:return []
        if cur:data["cursor"]=cur
        d=self._api("rank.list",data)
        nxt=d.get("nextCursor") if isinstance(d,dict) else ""
        if nxt:self.cursor.setdefault(cache_key,{})[pg+1]=nxt
        return self._items(d,mode)
    def _browse(self,cache_key,pg,data,mode="all",need_pic=False,loops=1):
        cur=self.cursor.get(cache_key,{}).get(pg)
        if pg>1 and not cur:return []
        if cur:data["cursor"]=cur
        seen=self.seen_page.setdefault(cache_key,set());out=[];nxt=""
        for _ in range(loops):
            d=self._api("feed.browse",data);nxt=d.get("nextCursor") if isinstance(d,dict) else ""
            li=self._items(d,mode,need_pic)
            if not li and d and not d.get("items"):
                fb=dict({"limit":12,"categorySlug":data.get("categorySlug","")})
                d=self._api("feed.browse",fb);nxt=d.get("nextCursor") if isinstance(d,dict) else ""
                li=self._items(d,mode,need_pic)
            self._fill(out,seen,li)
            if len(out)>=12 or not nxt:break
            data["cursor"]=nxt
        if nxt:self.cursor.setdefault(cache_key,{})[pg+1]=nxt
        return out
    def _list(self,cache_key="t-5jxcit",pg=1,extra=None):
        pg=int(pg)
        tid=extra.get("tid",cache_key) if extra else cache_key
        ck_map={"t-eb9c3c":"MOVIE","t-k1gwip":"SERIES","t-5jxcit":"SHORT_DRAMA","t-hebbu9":"VARIETY","t-k3onqj":"ANIME"}
        mp={"t-5jxcit":{"contentKind":"SHORT_DRAMA"},"adult_short":{"contentKind":"SHORT_DRAMA"},"normal_short":{"contentKind":"SHORT_DRAMA"},"short_kind":{"contentKind":"SHORT_DRAMA"}}
        if tid in ck_map:mp[tid]={"contentKind":ck_map[tid]}
        if pg==1:self.cursor[cache_key]={};self.seen_page[cache_key]=set()
        mode="all" if tid=="adult_short" else "normal" if tid=="normal_short" else "all"
        kind=extra.get("kind","") if extra else ""
        if tid in ["recommend","all",""]:
            d=self._api("feed.recommend",{"limit":12})
            nxt=d.get("nextCursor") if isinstance(d,dict) else ""
            if nxt:self.cursor.setdefault(cache_key,{})[pg+1]=nxt
            seen=self.seen_page.setdefault(cache_key,set());out=[]
            self._fill(out,seen,self._items(d))
            return out
        if tid in ["rank","today"]:
            return self._rank(cache_key,pg,"hot" if tid=="rank" else "new",kind,mode)
        base=mp.get(tid,{"categorySlug":tid})
        cat=extra.get("cat","") if extra else ""
        region=extra.get("region","") if extra else ""
        kd=base.get("contentKind","")
        if cat or region:
            data=dict({"limit":12,"categorySlug":cat or region})
            if kd:data["contentKind"]=kd
            return self._browse(cache_key,pg,data,mode,tid=="normal_short",8 if tid in ["adult_short","normal_short"] else 1)
        if kd:
            return self._rank(cache_key,pg,"hot",kd,mode)
        return self._browse(cache_key,pg,dict({"limit":12},**base),mode,tid=="normal_short")
    def homeContent(self,filter):
        cls=[
            {"type_id":"t-5jxcit","type_name":"短剧"},
            {"type_id":"t-k1gwip","type_name":"长剧"},
            {"type_id":"t-eb9c3c","type_name":"电影"},
            {"type_id":"t-hebbu9","type_name":"综艺"},
            {"type_id":"t-k3onqj","type_name":"动漫"},
            {"type_id":"rank","type_name":"排行榜"},
            {"type_id":"today","type_name":"今日更新"},
            {"type_id":"adult_short","type_name":"成人短剧"},
            {"type_id":"normal_short","type_name":"正规短剧"},
        ]
        ft={
            "t-5jxcit":[
                {"key":"cat","name":"题材","value":[
                    {"n":"全部","v":""},
                    {"n":"逆袭","v":"revenge"},
                    {"n":"霸总","v":"ceo"},
                    {"n":"豪门","v":"hidden-marriage"},
                    {"n":"重生","v":"rebirth"},
                    {"n":"甜宠","v":"romance"},
                    {"n":"甜虐","v":"romanceangst"},
                    {"n":"男频爽剧","v":"malepower"},
                    {"n":"复仇爽剧","v":"revengedrama"},
                    {"n":"系统","v":"t-kv5ena"},
                ]},
                {"key":"cat","name":"题材","value":[
                    {"n":"古装","v":"ancient"},
                    {"n":"玄幻","v":"fantasy"},
                    {"n":"奇幻","v":"fantasydrama"},
                    {"n":"都市","v":"urban"},
                    {"n":"职场","v":"workplace"},
                    {"n":"校园","v":"campus"},
                    {"n":"青春","v":"youth"},
                    {"n":"双男主","v":"bldrama"},
                    {"n":"双女主","v":"gldrama"},
                    {"n":"女性向","v":"femalelead"},
                ]},
            ],
            "t-k1gwip":[
                {"key":"cat","name":"题材","value":[
                    {"n":"全部","v":""},
                    {"n":"古装","v":"ancient"},
                    {"n":"玄幻","v":"fantasy"},
                    {"n":"奇幻","v":"fantasydrama"},
                    {"n":"科幻","v":"scifi"},
                    {"n":"都市","v":"urban"},
                    {"n":"职场","v":"workplace"},
                    {"n":"校园","v":"campus"},
                    {"n":"青春","v":"youth"},
                    {"n":"家庭","v":"family"},
                    {"n":"宫廷权谋","v":"palacepower"},
                    {"n":"家族商战","v":"familybusiness"},
                ]},
                {"key":"cat","name":"题材","value":[
                    {"n":"医疗","v":"medical"},
                    {"n":"悬疑恋爱","v":"mysteryromance"},
                    {"n":"女性向","v":"femalelead"},
                    {"n":"双男主","v":"bldrama"},
                    {"n":"双女主","v":"gldrama"},
                    {"n":"悬疑","v":"mystery"},
                    {"n":"喜剧","v":"comedy"},
                    {"n":"犯罪","v":"crime"},
                    {"n":"爱情","v":"romance"},
                    {"n":"甜虐","v":"romanceangst"},
                    {"n":"惊悚","v":"thriller"},
                    {"n":"动作","v":"action"},
                ]},
            ],
            "t-eb9c3c":[
                {"key":"cat","name":"题材","value":[
                    {"n":"全部","v":""},
                    {"n":"动作","v":"action"},
                    {"n":"喜剧","v":"comedy"},
                    {"n":"犯罪","v":"crime"},
                    {"n":"悬疑","v":"mystery"},
                    {"n":"惊悚","v":"thriller"},
                    {"n":"恐怖","v":"horror"},
                    {"n":"末世灾难","v":"disaster"},
                    {"n":"科幻","v":"scifi"},
                    {"n":"爱情","v":"romance"},
                ]},
                {"key":"cat","name":"题材","value":[
                    {"n":"古装","v":"ancient"},
                    {"n":"玄幻","v":"fantasy"},
                    {"n":"都市","v":"urban"},
                    {"n":"家庭","v":"family"},
                    {"n":"职场","v":"workplace"},
                    {"n":"宫廷权谋","v":"palacepower"},
                    {"n":"双男主","v":"bldrama"},
                    {"n":"甜虐","v":"romanceangst"},
                    {"n":"校园","v":"campus"},
                ]},
            ],
            "t-hebbu9":[{"key":"cat","name":"类型","value":[
                {"n":"全部","v":""},
                {"n":"真人秀","v":"realityshow"},
                {"n":"体育","v":"sports"},
            ]}],
            "t-k3onqj":[
                {"key":"cat","name":"题材","value":[
                    {"n":"全部","v":""},
                    {"n":"玄幻","v":"fantasy"},
                    {"n":"奇幻","v":"fantasydrama"},
                    {"n":"双男主","v":"bldrama"},
                ]},
                {"key":"cat","name":"题材","value":[
                    {"n":"双女主","v":"gldrama"},
                    {"n":"热血","v":"malepower"},
                    {"n":"系统","v":"t-kv5ena"},
                ]},
            ],
            "rank":[{"key":"kind","name":"频道","value":[
                {"n":"全部","v":""},
                {"n":"短剧","v":"SHORT_DRAMA"},
                {"n":"长剧","v":"SERIES"},
                {"n":"电影","v":"MOVIE"},
                {"n":"综艺","v":"VARIETY"},
                {"n":"动漫","v":"ANIME"},
            ]}],
            "today":[{"key":"kind","name":"频道","value":[
                {"n":"全部","v":""},
                {"n":"短剧","v":"SHORT_DRAMA"},
                {"n":"长剧","v":"SERIES"},
                {"n":"电影","v":"MOVIE"},
                {"n":"综艺","v":"VARIETY"},
                {"n":"动漫","v":"ANIME"},
            ]}],
        }
        regions={"key":"region","name":"地区","value":[{"n":"全部","v":""},{"n":"国产剧","v":"t-zuvois"},{"n":"日剧","v":"t-ue8oql"},{"n":"港台剧","v":"hktwdrama"},{"n":"韩剧","v":"kdrama"},{"n":"泰剧","v":"thaidrama"},{"n":"海外剧","v":"globaldrama"}]}
        for tid in ["t-5jxcit","t-k1gwip","t-eb9c3c","t-hebbu9","t-k3onqj"]:
            ft.setdefault(tid,[]).append(regions)
        li=self._list("recommend") or self._list("t-5jxcit")
        return {"class":cls,"list":li,"filters":ft}
    def categoryContent(self,tid,pg,filter,extend):
        pg=int(pg)
        if isinstance(extend,str):
            try:extend=json.loads(extend)
            except:extend={}
        if not extend:extend={}
        cat=extend.get("cat","");region=extend.get("region","");kind=extend.get("kind","")
        cache_key=tid+"|"+cat+"|"+region+"|"+kind
        li=self._list(cache_key,pg,{"cat":cat,"region":region,"kind":kind,"tid":tid})
        has_next=bool(self.cursor.get(cache_key,{}).get(pg+1))
        return {"page":pg,"pagecount":pg+1 if has_next else pg,"limit":12,"total":pg*12+(12 if has_next else 0),"count":len(li),"list":li}
    def _episodes(self,vid):
        if vid in self.eps:return self.eps[vid]
        d=self._api("episode.watch",{"dramaId":vid,"index":1});arr=d.get("episodes",[]) if isinstance(d,dict) else []
        self.eps[vid]=arr;return arr
    def detailContent(self,ids):
        out=[]
        if not self.cache:self._list("t-5jxcit")
        for vid in ids:
            it=self.cache.get(vid) or {}
            m=re.search(r"(\d+)",it.get("vod_remarks",""));total=max(1,min(int(m.group(1)) if m else 12,80));eps=self._episodes(vid)
            if eps:play="#".join(["第%d集$%s/%d/%s"%(i,vid,i,(eps[i-1].get("id") if i-1<len(eps) and isinstance(eps[i-1],dict) else "")) for i in range(1,total+1)])
            else:play="第1集$%s/1/%s"%(vid,it.get("firstEpisodeId",""))
            out.append({"vod_id":vid,"vod_name":it.get("vod_name",vid),"vod_pic":it.get("vod_pic",""),"vod_remarks":it.get("vod_remarks",""),"vod_content":it.get("vod_content",""),"vod_play_from":"直连","vod_play_url":play})
        return {"list":out}
    def searchContent(self,key,quick,pg="1"):
        return {"page":int(pg),"list":[x for x in self._list("t-5jxcit") if key in x.get("vod_name","")]}
    def _unesc(self,s):return (s or "").replace("\\u0026","&").replace("\\/","/")
    def _media(self,h):
        h=self._unesc(h);m=re.search(r'<video[^>]+src="([^"]+)',h) or re.search(r'"(?:hlsUrl|playUrl|videoUrl|sourceUrl|mediaUrl|trailerUrl)"\s*:\s*"([^"]+?\.(?:m3u8|mp4)[^"]*)"',h) or re.search(r'https?://[^"\\\s<>]+?\.(?:mp4|m3u8)[^"\\\s<>]*',h)
        return self._fix(m.group(1) if m and m.lastindex else m.group(0) if m else "")
    def _eid(self,h):
        h=self._unesc(h);m=re.search(r'"episode"\s*:\s*\{[^{}]*"id"\s*:\s*"([^"]+)"',h) or re.search(r'"(?:episodeId|id)"\s*:\s*"(cms[a-z0-9]{10,})"',h)
        return m.group(1) if m else ""
    def _alive(self,u):
        try:
            r=self.session.get(u,headers={"User-Agent":self.headers["User-Agent"],"Referer":self.host+"/","Origin":self.host,"Range":"bytes=0-0"},timeout=3,stream=True,allow_redirects=False)
            return r.status_code in [200,206] and "text/html" not in r.headers.get("content-type","")
        except Exception:return False
    def playerContent(self,flag,id,vipFlags):
        parts=str(id).split("/");vid=parts[0] if parts else "";ep=parts[1] if len(parts)>1 else "1";eid=parts[2] if len(parts)>2 else ""
        url=""
        it=self.cache.get(vid) or {}
        try:non_first=int(ep)>1
        except Exception:non_first=True
        if eid:
            for u in ["https://raw.shorttv.online/uploads/direct/"+eid+"/video.mp4","https://cdn.shorttv.online/uploads/direct/"+eid+"/video.mp4","https://cdn.shorttv.online/uploads/hls/"+eid+"/master.m3u8","https://cdn.shorttv.online/lsj/hls/"+eid+"/master.m3u8","https://cdn.shorttv.online/dc/hls/"+eid+"/master.m3u8","https://raw.shorttv.online/uploads/hls/"+eid+"/master.m3u8"]:
                if self._alive(u):url=u;break
        if not url:
            try:
                d=self._api("episode.watch",{"dramaId":vid,"index":int(ep)})
                if d and isinstance(d,dict):
                    ep_obj=d.get("episode",{}) or {}
                    hls=ep_obj.get("hlsUrl","") or ""
                    locked=bool(ep_obj.get("locked")) or ep_obj.get("isFree") is False
                    if not hls and locked and eid:
                        if self._try_unlock(eid):
                            d=self._api("episode.watch",{"dramaId":vid,"index":int(ep)})
                            ep_obj=d.get("episode",{}) or {};hls=ep_obj.get("hlsUrl","") or ""
                    if not hls and locked and ep_obj.get("id"):
                        if self._try_unlock(ep_obj["id"]):
                            d=self._api("episode.watch",{"dramaId":vid,"index":int(ep)})
                            ep_obj=d.get("episode",{}) or {};hls=ep_obj.get("hlsUrl","") or ""
                    if hls:
                        hls=self._fix(hls) if hls.startswith("/") else hls
                        if self._alive(hls):url=hls
                    if not url:
                        eid2=ep_obj.get("id","") or ""
                        if eid2:
                            for u in ["https://raw.shorttv.online/uploads/direct/"+eid2+"/video.mp4","https://cdn.shorttv.online/uploads/direct/"+eid2+"/video.mp4","https://cdn.shorttv.online/uploads/hls/"+eid2+"/master.m3u8","https://cdn.shorttv.online/lsj/hls/"+eid2+"/master.m3u8","https://cdn.shorttv.online/dc/hls/"+eid2+"/master.m3u8","https://raw.shorttv.online/uploads/hls/"+eid2+"/master.m3u8"]:
                                if self._alive(u):url=u;break
            except Exception:pass
        if not url and not non_first:
            try:html=self.session.get(self.host+"/zh/watch/"+vid+"/"+ep,headers={"User-Agent":self.headers["User-Agent"],"Referer":self.host+"/zh/watch/"+vid+"/"+ep},timeout=12).text
            except Exception:html=""
            url=self._media(html)
        if not url and not non_first:
            eid3=self._eid(html) if html else ""
            if eid3:
                arr=["https://raw.shorttv.online/uploads/direct/"+eid3+"/video.mp4","https://cdn.shorttv.online/uploads/direct/"+eid3+"/video.mp4","https://cdn.shorttv.online/uploads/hls/"+eid3+"/master.m3u8","https://cdn.shorttv.online/lsj/hls/"+eid3+"/master.m3u8","https://cdn.shorttv.online/dc/hls/"+eid3+"/master.m3u8"]
                for u in arr:
                    if self._alive(u):url=u;break
        if not url and not non_first:
            url=self._fix(it.get("trailerUrl",""))
        return {"parse":0 if url else 1,"url":self._unesc(url),"header":json.dumps({"User-Agent":self.headers["User-Agent"],"Referer":self.host+"/zh/","Origin":self.host})}

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====

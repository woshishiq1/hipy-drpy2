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
        self.fallback=[{"vod_id":"cms5gkpmm08ic016polf4lbnq","vod_name":"鸭王争霸【已更新】","vod_pic":"https://raw.shorttv.online/images/2026-08-08/aa93208f-c3db-46f9-8a1b-8ac55fcc6298.jpg","vod_remarks":"8集","trailerUrl":"https://raw.shorttv.online/uploads/direct/cms5gkpmr08id016p43cfqk20/video.mp4"},{"vod_id":"cmsgx8rgr00lj010fi6lttg9c","vod_name":"斗破苍穹","vod_pic":"https://cdn.shorttv.online/images/2026-08-06/fca26c04-5a77-492c-a505-fa7440886090.jpg","vod_remarks":"7集","trailerUrl":"/api/media/centaurus/hls/cmsgx8rgu00lk010fjy2kas6p/h264/master.m3u8?tok=69dc75cf2fa24f54fe841a45a7768db4&ep=cmsgx8rgu00lk010fjy2kas6p"},{"vod_id":"cmse0xyci0d300130psgoy5c5","vod_name":"魔毒圣缘","vod_pic":"https://cdn.shorttv.online/images/2026-08-04/2a3f6dc2-7491-4d7e-a2bd-a4d88c092d0f.png","vod_remarks":"4集","trailerUrl":"https://raw.shorttv.online/uploads/direct/cmse0xycl0d310130rev3nav1/video.mp4"},{"vod_id":"cmscmdvbu0ddb0173a71sc57c","vod_name":"萌新三人行","vod_pic":"https://cdn.shorttv.online/images/2026-08-03/7be24fc7-0e0c-4587-b0ae-6b38d93aa5ec.jpg","vod_remarks":"4集","trailerUrl":"https://raw.shorttv.online/uploads/direct/cmscmdvbx0ddc0173yd1b2t9z/video.mp4"},{"vod_id":"cms6za7vq05sh010edvz48iun","vod_name":"精液救世，丧尸围城","vod_pic":"https://cdn.shorttv.online/images/2026-07-30/e1c33bf0-db83-45ce-8213-4a274a9c5b48.jpg","vod_remarks":"4集","trailerUrl":""},{"vod_id":"cms8rjowz00qo01cu1t7z6d8x","vod_name":"等不到的她","vod_pic":"https://cdn.shorttv.online/images/2026-07-31/e04ce57f-2e01-455c-8357-4f4e2de5fc30.jpg","vod_remarks":"5集","trailerUrl":""}]
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
    def _fallback_items(self):
        out=[];seen=set()
        for x in self.fallback:
            name=re.sub(r"\s+","",x["vod_name"])
            if name not in seen:seen.add(name);self.cache[x["vod_id"]]=x;out.append({k:x.get(k,"") for k in ["vod_id","vod_name","vod_pic","vod_remarks"]})
        return out
    def _list(self,cache_key="t-5jxcit",pg=1,extra=None):
        pg=int(pg)
        tid=extra.get("tid",cache_key) if extra else cache_key
        ck_map={"t-eb9c3c":"MOVIE","t-k1gwip":"SERIES","t-5jxcit":"SHORT_DRAMA","t-hebbu9":"VARIETY","t-k3onqj":"ANIME"}
        mp={"t-5jxcit":{"contentKind":"SHORT_DRAMA"},"adult_short":{"tagSlug":"adult"},"normal_short":{"contentKind":"SHORT_DRAMA"},"short_kind":{"contentKind":"SHORT_DRAMA"}}
        if tid in ck_map:mp[tid]={"contentKind":ck_map[tid]}
        if pg==1:self.cursor[cache_key]={};self.seen_page[cache_key]=set()
        cur=self.cursor.get(cache_key,{}).get(pg)
        if pg>1 and not cur:return []
        mode="all" if tid=="adult_short" else "normal" if tid=="normal_short" else "all";seen=self.seen_page.setdefault(cache_key,set());out=[];nxt=""
        if tid in ["recommend","all",""]:
            d=self._api("feed.recommend",{"limit":12});nxt=d.get("nextCursor") if isinstance(d,dict) else "";li=self._items(d)
            for x in li:
                k=x.get("vod_id") or re.sub(r"\s+","",x.get("vod_name",""))
                if k and k not in seen:seen.add(k);out.append(x)
        else:
            base=mp.get(tid,{"categorySlug":tid})
            cat=extra.get("cat","") if extra else ""
            region=extra.get("region","") if extra else ""
            kind=base.get("contentKind","")
            if cat:
                data=dict({"limit":12,"categorySlug":cat})
                if kind:data["contentKind"]=kind
            elif region:
                data=dict({"limit":12,"categorySlug":region})
                if kind:data["contentKind"]=kind
            else:
                data=dict({"limit":12},**base)
            if cur:data["cursor"]=cur
            loops=8 if tid in ["adult_short","normal_short"] else 1
            for _ in range(loops):
                d=self._api("feed.browse",data);nxt=d.get("nextCursor") if isinstance(d,dict) else ""
                li=self._items(d,mode,tid=="normal_short")
                if not li and (cat or region) and d and not d.get("items"):
                    fb=dict({"limit":12,"categorySlug":cat or region})
                    d=self._api("feed.browse",fb);nxt=d.get("nextCursor") if isinstance(d,dict) else ""
                    li=self._items(d,mode,tid=="normal_short")
                for x in li:
                    k=x.get("vod_id") or re.sub(r"\s+","",x.get("vod_name",""))
                    if k and k not in seen:seen.add(k);out.append(x)
                    if len(out)>=12:break
                if len(out)>=12 or not nxt:break
                data["cursor"]=nxt
        if nxt:self.cursor.setdefault(cache_key,{})[pg+1]=nxt
        return out
    def homeContent(self,filter):
        cls=[
            {"type_id":"adult_short","type_name":"成人短剧"},
            {"type_id":"normal_short","type_name":"正规短剧"},
            {"type_id":"t-5jxcit","type_name":"短剧"},
            {"type_id":"t-k1gwip","type_name":"长剧"},
            {"type_id":"t-eb9c3c","type_name":"电影"},
            {"type_id":"t-hebbu9","type_name":"综艺"},
            {"type_id":"t-k3onqj","type_name":"动漫"},
            {"type_id":"t-mqnyjd","type_name":"创作者"},
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
        }
        regions={"key":"region","name":"地区","value":[{"n":"全部","v":""},{"n":"国产剧","v":"t-zuvois"},{"n":"日剧","v":"t-ue8oql"},{"n":"港台剧","v":"hktwdrama"},{"n":"韩剧","v":"kdrama"},{"n":"泰剧","v":"thaidrama"},{"n":"海外剧","v":"globaldrama"}]}
        for tid in ["t-5jxcit","t-k1gwip","t-eb9c3c","t-hebbu9","t-k3onqj"]:
            ft.setdefault(tid,[]).append(regions)
        li=self._list("recommend") or self._list("t-5jxcit") or self._fallback_items()
        return {"class":cls,"list":li,"filters":ft}
    def categoryContent(self,tid,pg,filter,extend):
        pg=int(pg)
        if isinstance(extend,str):
            try:extend=json.loads(extend)
            except:extend={}
        if not extend:extend={}
        cat=extend.get("cat","");region=extend.get("region","")
        cache_key=tid+"|"+cat+"|"+region
        li=self._list(cache_key,pg,{"cat":cat,"region":region,"tid":tid})
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
            it=self.cache.get(vid) or next((x for x in self.fallback if x["vod_id"]==vid),{"vod_id":vid,"vod_name":vid,"vod_pic":"","vod_remarks":"12集","vod_content":""})
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
        it=self.cache.get(vid) or next((x for x in self.fallback if x["vod_id"]==vid),{})
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

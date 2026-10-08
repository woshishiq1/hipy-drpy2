# coding=utf-8
import json, ssl, re, base64, random, urllib.parse, time, hashlib
from base.spider import Spider
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class Spider(Spider):
    def getName(self): return "51短剧"

    def init(self, extend=""):
        self.publish = "https://51dj20.com/"
        self.ua = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/143.0 Mobile Safari/537.36"
        self.headers = {"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9", "Referer": self.publish}
        self.session = requests.Session()
        self.media_key = b"f5d965df75336270"
        self.media_iv = b"97b60394abc2fbe1"
        self.api_host = "https://api.51dj1.com"
        self.api_key = b"2acf7e91e9864673"
        self.api_iv = b"1c29882d3ddfcfd6"
        try: ssl._create_default_https_context = ssl._create_unverified_context
        except Exception: pass
        self.host = "https://ceiling.sysrycady.com/"
        self._resolve_domain()
        self.image_map = {}; self.image_id_map = {}
        try:
            with open("/storage/emulated/0/影视/AI/51短剧/51短剧图片映射.json", "r", encoding="utf-8") as f: raw = f.read()
            for x in self._walk(self._payload(raw), ["video_id", "title"]):
                title = str(x.get("title") or ""); cover = self._pic(x.get("cover") or x.get("cover_img") or x.get("cover_image"))
                if title and cover: self.image_map[title] = cover; self.image_id_map[str(x.get("video_id"))] = cover
            for title, cover in re.findall(r'\"title\"\s*:\s*\"([^\"]+)\"[\s\S]{0,300}?\"cover\"\s*:\s*\"([^\"]+)\"', raw):
                self.image_map.setdefault(title, self._pic(cover))
            print(f"[51短剧] 图片映射: 标题{len(self.image_map)}条, ID{len(self.image_id_map)}条")
        except Exception as e: print(f"[51短剧] 图片映射读取失败: {e}")
        self.classes = [{"type_id":"actor","type_name":"演员"},{"type_id":"drama","type_name":"剧集"},{"type_id":"drama_week","type_name":"剧集周榜"},{"type_id":"drama_month","type_name":"剧集月榜"},{"type_id":"aisd","type_name":"AI成人短剧"}]
        self.filters = {"actor":[{"key":"sort","name":"演员","value":[{"n":"热门","v":"hot"},{"n":"男演员","v":"2"},{"n":"女演员","v":"1"}]}],"drama":[{"key":"theme","name":"主题","value":[{"n":"全部","v":"0"},{"n":"成人","v":"1"},{"n":"AI漫剧","v":"46"},{"n":"51原创","v":"47"},{"n":"AI魔改短剧","v":"51"},{"n":"致富","v":"63"},{"n":"修仙","v":"59"},{"n":"厨神","v":"60"},{"n":"读心","v":"61"},{"n":"今古联通","v":"62"},{"n":"女性成长","v":"4"},{"n":"鉴宝","v":"64"},{"n":"亲情","v":"65"},{"n":"末世","v":"66"},{"n":"武侠","v":"67"},{"n":"萌宠","v":"68"},{"n":"萌宝","v":"69"},{"n":"真假千金","v":"70"},{"n":"青春","v":"18"},{"n":"现言","v":"3"},{"n":"奇幻","v":"5"},{"n":"战神","v":"6"},{"n":"宫斗","v":"7"},{"n":"古言","v":"8"},{"n":"玄幻","v":"9"},{"n":"脑洞","v":"10"},{"n":"权谋","v":"11"},{"n":"年代爱情","v":"12"},{"n":"种田","v":"15"},{"n":"悬疑","v":"13"},{"n":"民国爱情","v":"16"},{"n":"轻松喜剧","v":"17"},{"n":"志怪","v":"19"},{"n":"超能","v":"58"},{"n":"强制","v":"57"},{"n":"异世界","v":"56"},{"n":"NTR","v":"55"},{"n":"纯爱","v":"71"},{"n":"群像","v":"78"}]},{"key":"setting","name":"设定","value":[{"n":"全部","v":"0"},{"n":"后宫","v":"20"},{"n":"NTR","v":"55"},{"n":"反差","v":"38"},{"n":"淫妻","v":"74"},{"n":"少妇","v":"73"},{"n":"大男主","v":"20"},{"n":"大女主","v":"7"},{"n":"系统","v":"29"},{"n":"重生","v":"27"},{"n":"穿越","v":"28"},{"n":"神豪","v":"23"},{"n":"打脸虐渣","v":"25"},{"n":"马甲","v":"26"},{"n":"追妻/夫火葬场","v":"72"},{"n":"互相救赎","v":"22"},{"n":"甜宠","v":"88"},{"n":"双向奔赴","v":"48"},{"n":"传承觉醒","v":"38"},{"n":"家长里短","v":"37"},{"n":"破镜重圆","v":"36"},{"n":"虐恋","v":"35"},{"n":"霸总","v":"34"},{"n":"强者回归","v":"33"},{"n":"先婚后爱","v":"32"},{"n":"小人物","v":"31"},{"n":"逆袭","v":"39"},{"n":"伦理","v":"92"},{"n":"出轨","v":"98"},{"n":"偷情","v":"97"},{"n":"御姐","v":"89"},{"n":"萝莉","v":"88"},{"n":"替嫁","v":"82"},{"n":"团宠","v":"81"},{"n":"无CP","v":"80"}]},{"key":"background","name":"背景","value":[{"n":"全部","v":"0"},{"n":"校园","v":"54"},{"n":"架空","v":"53"},{"n":"民国","v":"52"},{"n":"职场","v":"45"},{"n":"年代","v":"44"},{"n":"现代","v":"40"},{"n":"都市","v":"41"},{"n":"古代","v":"42"},{"n":"乡村","v":"43"}]},{"key":"audience","name":"受众","value":[{"n":"全部","v":"0"},{"n":"男","v":"1"},{"n":"女","v":"2"}]},{"key":"time","name":"时间","value":[{"n":"全部","v":"0"},{"n":"7天内","v":"7"},{"n":"14天内","v":"14"},{"n":"30天内","v":"30"},{"n":"90天内","v":"90"}]},{"key":"recommend","name":"推荐","value":[{"n":"默认","v":"0"},{"n":"最新","v":"time"},{"n":"最热","v":"hits"},{"n":"原创","v":"original"}]}]}

        self.filters["actor"][0]["value"] += [{"n":"新人榜","v":"new"},{"n":"热度榜","v":"hot"},{"n":"推荐榜","v":"recommend"}]

    def _resolve_domain(self):
        try:
            h = self.session.get(self.publish, headers=self.headers, timeout=12, verify=False).text
            m = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)', h, re.I)
            if not m: return
            h = self.session.get(m.group(1), headers=self.headers, timeout=12, verify=False).text
            m = re.search(r'Base64\.decode\(["\']([^"\']+)["\']\)', h, re.I)
            if not m: return
            decoded = base64.b64decode(m.group(1)).decode("utf-8", "ignore")
            m = re.search(r"words\.random\(\)\s*\+\s*[\"']([^\"']+)[\"']", decoded, re.I)
            if not m: return
            suffix = m.group(1).strip()
            prefix = "".join(random.choice("abcdefghjkmnpqrstuvwxy23456789") for _ in range(5))
            self.host = "https://" + prefix + suffix.lstrip("/")
            if not self.host.endswith("/"): self.host += "/"
            self.headers["Referer"] = self.host
            print(f"[51短剧] 域名: {self.host}")
        except Exception as e: print(f"[51短剧] 域名解析失败: {e}")

    def _req(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
            return r.text if r.status_code == 200 else ""
        except Exception as e:
            print(f"[51短剧] 请求失败: {url} {e}")
            return ""

    def _payload(self, html):
        m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S | re.I)
        if not m: return None
        try:
            raw=json.loads(m.group(1).strip()); memo={}
            def get(i):
                if not isinstance(i,int) or i<0 or i>=len(raw): return i
                if i in memo: return memo[i]
                x=raw[i]
                if isinstance(x,list):
                    out=[]; memo[i]=out
                    for v in x: out.append(get(v))
                    return out
                if isinstance(x,dict):
                    out={}; memo[i]=out
                    for k,v in x.items(): out[k]=get(v)
                    return out
                memo[i]=x; return x
            return get(0)
        except Exception as e:
            print(f"[51短剧] Nuxt解析失败: {e}")
            return None

    def _walk(self, obj, keys):
        out, seen = [], set()
        def go(x):
            if isinstance(x, dict):
                if all(k in x for k in keys):
                    mark = str(x.get(keys[0])) + str(x.get(keys[1]))
                    if mark not in seen: seen.add(mark); out.append(x)
                for v in x.values(): go(v)
            elif isinstance(x, list):
                for v in x: go(v)
        go(obj); return out

    def _pic(self, x):
        if not isinstance(x, str): return ""
        url=x.replace("\\u002F", "/").replace("\\/", "/").replace("&amp;", "&").strip()
        if not url: return ""
        if url.startswith("//"): url = "https:" + url
        elif not url.startswith("http"): url = self._fix(url)
        try: return self.getProxyUrl()+"&url="+urllib.parse.quote(self.e64(url), safe="")+"&type=img"
        except Exception: return url

    def _media(self, x):
        if not isinstance(x, str): return ""
        url=x.replace("\\u002F", "/").replace("\\/", "/").replace("&amp;", "&").strip()
        if not url: return ""
        if url.startswith("//"): return "https:" + url
        if url.startswith("http"): return url
        return self._fix(url)

    def _num(self, n):
        try:
            n=int(float(str(n).replace(",","")))
            return str(round(n/10000,1)).rstrip(".0")+"W" if n>=10000 else str(n)
        except Exception: return ""

    def _xml(self, s):
        s = str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        q = chr(34)
        return s.replace(q, "\x26quot;")


    def _api_decrypt(self, obj):
        try:
            if isinstance(obj, str): obj=json.loads(obj)
            data=str(obj.get("data") or "").replace(" ","+")
            if not data: return obj if isinstance(obj, dict) else {}
            raw=base64.b64decode(data)
            txt=unpad(AES.new(self.api_key,AES.MODE_CBC,self.api_iv).decrypt(raw), AES.block_size).decode("utf-8","ignore")
            return json.loads(txt)
        except Exception as e:
            print(f"[51短剧] API解密失败: {e}")
            return {}

    def _api_post(self, path, data):
        try:
            hdr=dict(self.headers)
            hdr.update({"Accept":"application/json, text/plain, */*","Content-Type":"application/x-www-form-urlencoded","Origin":self.host.rstrip("/"),"Referer":self.host})
            body={"bundleId":"com.pwa.mater","version":"1.3.2","oauth_id":"7d05538c4b8a5e74e82f93c0dab0163c","oauth_type":"web","language":"zh","via":"pwa","token":"","trace_id":"7d05538c4b8a5e74e82f93c0dab0163c"}
            body.update(data or {})
            r=self.session.post(self.api_host.rstrip("/") + path, data=body, headers=hdr, timeout=15, verify=False)
            return self._api_decrypt(r.json()) if r.status_code == 200 else {}
        except Exception as e:
            print(f"[51短剧] API请求失败: {path} {e}")
            return {}

    def _danmaku_url(self, url):
        try:
            sid=(re.search(r"(?:id|video_id|playlet_id)=(\d+)", str(url)) or [None,""])[1]
            eid=(re.search(r"episode_id=(\d+)", str(url)) or [None,""])[1]
            if not sid or not eid: return ""
            return self.getProxyUrl()+"&type=danmu&vid="+urllib.parse.quote(str(sid))+"&eid="+urllib.parse.quote(str(eid))
        except Exception: return ""

    def _danmaku_xml(self, vid, eid):
        rows=[]
        data=self._api_post("/api/playlet/danmakuList", {"video_id":vid,"playlet_id":vid,"id":vid,"episode_id":eid,"page":1,"limit":500})
        try: rows=((data.get("data") or {}).get("list") or []) if isinstance(data, dict) else []
        except Exception: rows=[]
        ts=int(time.time())
        lines=['<?xml version="1.0" encoding="UTF-8"?><i>','<chatserver>51短剧</chatserver>','<chatid>'+self._xml(str(vid)+"_"+str(eid))+'</chatid>','<mission>0</mission>','<maxlimit>'+str(len(rows))+'</maxlimit>','<state>0</state>','<real_name>0</real_name>','<source>51dj</source>']
        n=0
        for x in rows:
            try:
                text=str(x.get("text") or x.get("content") or "")
                if not text: continue
                tm=max(0,float(x.get("time") or 0)); mode=int(x.get("mode") or 0)
                dm=5 if mode == 1 else (4 if mode == 2 else 1)
                c=str(x.get("color") or "#FFFFFF").strip().lstrip("#")[:6]
                color=int(c,16) if re.match(r"^[0-9a-fA-F]{6}$", c) else 16777215
                lines.append('<d p="%.3f,%d,25,%d,%d,0,51dj,%d">%s</d>' % (tm,dm,color,ts,n,self._xml(text)))
                n+=1
            except Exception: continue
        lines.append('</i>')
        print(f"[51短剧] 弹幕 {vid}/{eid}: {n} 条")
        return "\n".join(lines)

    def _vod(self, x, actor=False):
        title = str(x.get("title") or x.get("name") or x.get("video_title") or x.get("drama_name") or "")
        vid = x.get("actor_id") if actor else (x.get("video_id") or x.get("playlet_id") or x.get("id") or x.get("actor_id"))
        if not title or vid is None: return None
        if actor and x.get("actor_id") is not None:
            aid=str(x.get("actor_id")); pic=self._pic(x.get("avatar"))
            works=self._num(x.get("works")); fans=self._num(x.get("fans_count")); plays=self._num(x.get("play_count"))
            remark=("作品"+works if works else "演员作品") + ((" · 粉丝"+fans) if fans else "") + ((" · 播放"+plays) if plays else "")
            return {"vod_id":"actor_detail_"+aid,"vod_name":title,"vod_pic":pic,"vod_remarks":remark,"vod_tag":"folder","vod_play_from":"","vod_play_url":""}
        eid = x.get("episode_id") or ""
        play_id = self.host + "drama-play?id=" + str(vid) + ("&episode_id=" + str(eid) if eid else "")
        pic=self.image_id_map.get(str(vid)) or self.image_map.get(title) or self._pic(x.get("cover") or x.get("cover_img") or x.get("cover_image") or x.get("image") or x.get("poster") or x.get("thumb"))
        plays=str(x.get("play_count_text") or "") or self._num(x.get("play_count")); chase=self._num(x.get("chase_count")); status=str(x.get("serialize_status_text") or ("播放" if eid else ""))
        remark=(("播放"+plays) if plays else "") + ((" · 追剧"+chase) if chase else "")
        return {"vod_id":play_id,"vod_name":title,"vod_pic":pic,"vod_remarks":remark or status,"vod_tag":"video","vod_play_id":str(eid)}

    def _meta(self, html):
        data = self._payload(html)
        for x in self._walk(data, ["total","page","limit"]):
            total = int(x.get("total") or 0); limit = int(x.get("limit") or 20)
            return total, limit, max(1, (total + limit - 1) // limit)
        for x in self._walk(data, ["total","page"]):
            total = int(x.get("total") or 0); limit = 30
            return total, limit, max(1, (total + limit - 1) // limit)
        return 0, 20, 1

    def _load_filters(self):
        if getattr(self, "_filters_loaded", False): return
        self._filters_loaded = True
        try:
            data = self._payload(self._req(self.host + "rank-drama/week/"))
            found=[]
            def go(x):
                if isinstance(x, dict):
                    if isinstance(x.get("video_filter"), dict): found.append(x)
                    for v in x.values(): go(v)
                elif isinstance(x, list):
                    for v in x: go(v)
            go(data)
            opt = found[0] if found else {}
            vf = opt.get("video_filter") or {}
            fs=[]
            for k in ("theme","setting","background","audience","time","recommend"):
                b = vf.get(k)
                if not isinstance(b, dict): continue
                vals=[{"n":"全部","v":"0"}]; seen={"0"}
                for it in b.get("list") or []:
                    v=str(it.get("value","")); n=str(it.get("name",""))
                    if v and n and v not in seen: seen.add(v); vals.append({"n":n,"v":v})
                fs.append({"key":str(b.get("parameter") or k),"name":str(b.get("title") or k),"value":vals})
            if fs: self.filters["drama"] = fs
            af = opt.get("actor_filter")
            if isinstance(af, list):
                vals=[{"n":str(i.get("name")),"v":str(i.get("value"))} for i in af if i.get("name") and i.get("value") is not None]
                if vals: self.filters["actor"] = [{"key":"sort","name":"演员","value":vals}]
            print(f"[51短剧] 动态筛选: 剧集{len(self.filters.get('drama', []))}组")
        except Exception as e: print(f"[51短剧] 动态筛选失败: {e}")

    def _page(self, html, actor=False):
        data = self._payload(html); keys = ["actor_id","name"] if actor else ["video_id","title"]
        if not actor:
            html_pics=re.findall(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)', html, re.I)
        else: html_pics=[]
        arr = self._walk(data, keys) if data else []; result=[]; seen=set()
        if actor:
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[\s\S]{0,300}?</a>', html, re.I)
            actor_links = [u for u in links if ("/actor" in u or "actor_id" in u) and "explore-actor" not in u and "rank-actor" not in u]
        else: actor_links=[]
        for i,x in enumerate(arr):
            if actor:
                v=self._vod(x, True)
                if v and not v.get("vod_id"): v["vod_id"] = self._fix(actor_links[i]) if i < len(actor_links) else v.get("vod_id","")
            else:
                v=self._vod(x, False)
                if v and not v.get("vod_pic") and i < len(html_pics): v["vod_pic"] = self._fix(html_pics[i])
            if v and v["vod_id"] not in seen: seen.add(v["vod_id"]); result.append(v)
        return result

    def _fix(self, url):
        url=str(url or "").replace("\\u002F","/").replace("\\/","/")
        if url.startswith("http"): return url
        return self.host.rstrip("/") + "/" + url.lstrip("/")

    def _episode_rows(self, vid):
        try:
            m=re.search(r"id=(\d+)", str(vid)); sid=m.group(1) if m else str(vid)
            data=self._payload(self._req(self.host+"drama-detail/"+sid+"/"))
            candidates=self._walk(data,["video_id","title"]) or self._walk(data,["video_id","video_title"])
            for row in candidates:
                if str(row.get("video_id")) == str(sid) and isinstance(row.get("episodes"), list):
                    eps=[]
                    for e in row.get("episodes"):
                        if isinstance(e, dict) and e.get("id") is not None:
                            eps.append({"id":e.get("id"),"sort":e.get("sort") or 0,"title":e.get("title") or (str(row.get("title"))+"-第"+str(e.get("sort"))+"集")})
                    return sorted(eps, key=lambda x:int(x.get("sort") or 0))
        except Exception as e: print(f"[51短剧] 剧集列表失败: {e}")
        return []

    def _url(self, cid, pg, ext=None):
        pg=max(1,int(pg)); e=ext if isinstance(ext,dict) else {}
        if cid == "actor":
            sort=str(e.get("sort") or "popular")
            if sort == "1": base=self.host + "explore-actor/1/"
            elif sort == "2": base=self.host + "explore-actor/2/"
            elif sort in ("new","hot","recommend"): base=self.host + "rank-actor/" + sort + "/"
            else: base=self.host + "rank-actor/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama":
            vals=[str(e.get(k,0) or 0) for k in ("theme","setting","background","audience","time","recommend")]
            base=self.host + "explore-drama/" + "-".join(vals) + "/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama_week":
            base=self.host + "rank-drama/week/"; return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama_month":
            base=self.host + "rank-drama/month/"; return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "aisd":
            base=self.host + "drama/AISD/"; return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "explore":
            e=ext if isinstance(ext,dict) else {}; vals=[str(e.get(k,0) or 0) for k in ("theme","setting","background","audience","time","recommend")]
            u=self.host+"explore-drama/"+"-".join(vals)+"/"; return u if pg==1 else u+"page/"+str(pg)+"/"
        if cid == "male": return self.host+"explore-actor/2/"+("page/"+str(pg)+"/" if pg>1 else "")
        if cid == "female": return self.host+"explore-actor/1/"+("page/"+str(pg)+"/" if pg>1 else "")
        if cid in ("actor_recommend","actor_new","actor_hot"):
            kind={"actor_recommend":"recommend","actor_new":"new","actor_hot":"hot"}[cid]; return self.host+"rank-actor/"+kind+"/"+("page/"+str(pg)+"/" if pg>1 else "")
        if cid.startswith("drama_"):
            kind="week" if cid=="drama_week" else "month"; return self.host+"rank-drama/"+kind+"/"+("page/"+str(pg)+"/" if pg>1 else "")
        if cid == "aisd": return self.host+"drama/AISD/"+("page/"+str(pg)+"/" if pg>1 else "")
        if cid.startswith("actor$"): return self.host+"actor/"+cid.split("$",1)[1]+"/"
        return self.host

    def homeContent(self, filter):
        self._load_filters()
        return {"class":self.classes,"filters":self.filters,"list":[]}
    def homeVideoContent(self): return self.categoryContent("drama",1,{}, {"source":"week"})

    def categoryContent(self, cid, pg, filter, ext):
        try:
            pg=int(pg) if str(pg).isdigit() else 1
            if str(cid).startswith("actor_detail_") or str(cid).startswith("actor-detail$") or str(cid).startswith("actor$") or "/actor-detail/" in str(cid) or "/actor/" in str(cid):
                aid=re.search(r"actor_detail_(\d+)", str(cid)).group(1) if str(cid).startswith("actor_detail_") else (str(cid).split("$")[1] if "$" in str(cid) else (re.search(r"actor-detail/(\d+)", str(cid)) or re.search(r"actor/(\d+)", str(cid)) or re.search(r"(\d+)", str(cid))).group(1))
                url=self.host+"actor-detail/"+aid+"/"+("?page="+str(pg) if pg>1 else "")
                html=self._req(url)
                if not html: return {"list":[],"page":pg,"pagecount":1,"limit":20,"total":0}
                data=self._payload(html)
                arr=[]; seen=set()
                works=self._walk(data,["video_id","title"]) or self._walk(data,["video_id","video_title"])
                for x in works:
                    v=self._vod(x,False)
                    if v and v["vod_id"] not in seen: seen.add(v["vod_id"]); arr.append(v)
                total, limit, pagecount = self._meta(html)
                print(f"[51短剧] 演员二级 {cid} 第{pg}页: {len(arr)} 条, 共{total}条")
                return {"list":arr,"page":pg,"pagecount":pagecount,"limit":limit,"total":total or len(arr)}
            actor=cid == "actor"
            html=self._req(self._url(cid,pg,ext)); vods=self._page(html,actor)
            total, limit, pagecount = self._meta(html)
            if cid == "aisd" and vods:
                limit = limit or 30
                pagecount = max(pagecount, pg + 1) if len(vods) >= limit else pg
                total = max(total, pagecount * limit)
            print(f"[51短剧] 分类 {cid} 第{pg}页: {len(vods)} 条")
            return {"list":vods,"page":pg,"pagecount":pagecount,"limit":limit,"total":total or len(vods)}
        except Exception as e:
            print(f"[51短剧] 分类失败: {e}"); return {"list":[],"page":1,"pagecount":1,"limit":20,"total":0}

    def detailContent(self, ids):
        try:
            vid=str(ids[0])
            if vid.startswith("actor_detail_") or vid.startswith("actor-detail$") or vid.startswith("actor$") or "/actor-detail/" in vid or "/actor/" in vid:
                aid=re.search(r"actor_detail_(\d+)", vid).group(1) if vid.startswith("actor_detail_") else (vid.split("$")[1] if "$" in vid else (re.search(r"actor-detail/(\d+)", vid) or re.search(r"actor/(\d+)", vid) or re.search(r"(\d+)", vid)).group(1))
                url=self.host+"actor-detail/"+aid+"/"
                html=self._req(url)
                if not html: return {"list":[]}
                data=self._payload(html)
                arr=[]; seen=set()
                works=self._walk(data,["video_id","title"]) or self._walk(data,["video_id","video_title"])
                for x in works:
                    v=self._vod(x,False)
                    if v and v["vod_id"] not in seen: seen.add(v["vod_id"]); arr.append(v)
                print(f"[51短剧] 演员 {aid} 作品: {len(arr)} 条")
                return {"list":[{"vod_id":x["vod_id"],"vod_name":x["vod_name"],"vod_pic":x.get("vod_pic",""),"vod_remarks":"参演剧集","vod_tag":"video","vod_play_id":x.get("vod_play_id","")} for x in arr]}
            html=self._req(vid if vid.startswith("http") else self.host+"drama/"+vid+"/"); data=self._payload(html)
            items=self._walk(data,["episode_title","video_url"]); pics=self._walk(data,["video_id","title"]); roots=self._walk(data,["video_title","cover_img"]); pics= pics or roots
            detail_rows=[]
            if vid.startswith("http") and "drama-play" in vid: detail_rows=self._episode_rows(vid)
            if detail_rows:
                pics = pics or detail_rows
            info=pics[0] if pics else {}
            title=str(info.get("title") or info.get("video_title") or info.get("drama_name") or vid)
            pic=self.image_map.get(title) or self._pic(info.get("cover") or info.get("cover_img") or info.get("cover_image") or info.get("image") or info.get("poster") or info.get("thumb")) if info else self.image_map.get(title, "")
            desc=str(info.get("description") or info.get("video_desc") or info.get("content") or "")
            tags=info.get("tags") or info.get("tag") or []
            vod_class=",".join([str(t) for t in tags]) if isinstance(tags,list) else str(tags or "")
            plays=str(info.get("play_count_text") or "") or self._num(info.get("play_count")); chase=self._num(info.get("chase_count")); remarks=(("播放"+plays) if plays else "") + ((" · 追剧"+chase) if chase else "")
            urls=[]; seen=set()
            if detail_rows:
                m=re.search(r"id=(\d+)", vid); sid=m.group(1) if m else ""
                for x in detail_rows:
                    eid=x.get("id") or x.get("episode_id") or x.get("video_id")
                    u=self.host+"drama-play?id="+str(sid)+("&episode_id="+str(eid) if eid else "")
                    n=str(x.get("title") or x.get("episode_title") or x.get("video_title") or ("第"+str(x.get("sort"))+"集" if x.get("sort") else "播放"))
                    if u and u not in seen: seen.add(u); urls.append((n,u))
            else:
                for x in items:
                    u=self._media(x.get("video_url"))
                    if u and u not in seen: seen.add(u); urls.append((str(x.get("episode_title") or "正片"),u))
            return {"list":[{"vod_id":vid,"vod_name":title,"vod_pic":pic,"vod_remarks":remarks,"vod_class":vod_class,"vod_content":desc,"vod_play_from":"51短剧" if urls else "","vod_play_url":"#".join(n+"$"+u for n,u in urls)}]}
        except Exception as e: print(f"[51短剧] 详情失败: {e}"); return {"list":[]}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg=int(pg) if str(pg).isdigit() else 1
            q=urllib.parse.quote(str(key))
            u=self.host+"search-drama/"+q+"/"+("page/"+str(pg)+"/" if pg>1 else "")
            html=self._req(u); vods=self._page(html,False); total,limit,pagecount=self._meta(html)
            print(f"[51短剧] 搜索 {key} 第{pg}页: {len(vods)} 条")
            return {"list":vods,"page":pg,"pagecount":pagecount,"limit":limit,"total":total or len(vods)}
        except Exception as e:
            print(f"[51短剧] 搜索失败: {e}"); return {"list":[],"page":pg,"pagecount":1,"limit":20,"total":0}

    def playerContent(self, flag, id, vipFlags):
        try:
            url=str(id).replace("\\u002F","/").replace("\\/","/")
            dm_url=self._danmaku_url(url) if "drama-play" in url else ""
            if "drama-play" in url and not self.isVideoFormat(url):
                html=self._req(url); data=self._payload(html)
                em=re.search(r"episode_id=(\d+)", url); target=em.group(1) if em else ""
                best=""
                def go(x):
                    nonlocal best
                    if best: return
                    if isinstance(x, dict):
                        if str(x.get("id") or x.get("episode_id") or "") == target:
                            u=x.get("video_url") or x.get("play_url") or ""
                            if u: best=self._media(u); return
                        for v in x.values(): go(v)
                    elif isinstance(x, list):
                        for v in x: go(v)
                if target: go(data)
                if not best:
                    for x in self._walk(data,["episode_title","video_url"]):
                        u=self._media(x.get("video_url"))
                        if u: best=u; break
                if not best:
                    for x in self._walk(data,["video_title","video_url"]):
                        u=self._media(x.get("video_url"))
                        if u: best=u; break
                if best: url=best
                if not self.isVideoFormat(url):
                    m=re.search(r"https?:[^\"'<>\s]+\.(?:m3u8|mp4)[^\"'<>\s]*", html)
                    if m: url=m.group(0).replace("\\u002F","/").replace("\\/","/")
            ret={"parse":0,"url":url,"header":json.dumps(self.headers,ensure_ascii=False)}
            if dm_url: ret["danmaku"]=[{"name":"51短剧弹幕","url":dm_url}]
            return ret
        except Exception as e:
            print(f"[51短剧] 播放解析失败: {e}")
            return {"parse":0,"url":str(id),"header":json.dumps(self.headers,ensure_ascii=False)}
    def isVideoFormat(self, url): return bool(re.search(r'\.(m3u8|mp4|m4v|ts)(\?|$)',str(url),re.I))
    def e64(self, text):
        try: return base64.b64encode(str(text).encode("utf-8")).decode("utf-8")
        except Exception: return ""

    def d64(self, text):
        try: return base64.b64decode(str(text).encode("utf-8")).decode("utf-8")
        except Exception: return ""

    def localProxy(self, param):
        if param.get("type") == "danmu":
            try:
                vid=str(param.get("vid") or param.get("video_id") or "")
                eid=str(param.get("eid") or param.get("episode_id") or "")
                if not vid or not eid: return [404,"text/plain","",""]
                return [200,"application/xml; charset=utf-8",self._danmaku_xml(vid,eid),{"Cache-Control":"no-store"}]
            except Exception as e:
                print(f"[51短剧] 弹幕代理失败: {e}")
                return [404,"text/plain","",""]
        if param.get("type") != "img": return [404,"text/plain","",""]
        try:
            url=self.d64(param.get("url", ""))
            if not url: return [404,"text/plain","",""]
            r=self.session.get(url,headers=self.headers,timeout=15,verify=False)
            content=r.content
            try: content=unpad(AES.new(self.media_key,AES.MODE_CBC,self.media_iv).decrypt(content), AES.block_size)
            except Exception: pass
            ctype="image/jpeg"
            if content.startswith(b"\x89PNG"): ctype="image/png"
            elif content[:4] == b"RIFF" and content[8:12] == b"WEBP": ctype="image/webp"
            elif content.startswith(b"GIF"): ctype="image/gif"
            return [r.status_code,ctype,content,{}]
        except Exception as e:
            print(f"[51短剧] 图片代理失败: {e}")
            return [404,"text/plain","",""]

    def destroy(self):
        try: self.session.close()
        except Exception: pass
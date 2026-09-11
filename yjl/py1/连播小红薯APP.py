from base.spider import Spider
import json,random,string,time,requests,hashlib
from base64 import b64decode
from urllib.parse import quote,unquote,parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class Spider(Spider):
    def getName(self):
        return '小红薯APP'
    def init(self,extend=""):
        self.hs=['fhoumpjjih','dyfcbkggxn','rggwiyhqtg','bpbbmplfxc']
        self.ua='Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36;SuiRui/xhs/ver=1.2.6'
        self.did=self._did()
        self.session=requests.Session()
        self.token,self.phost,self.host=self._token()
        self.api_cache={}
        self.img_cache={}
        self.class_cache=[]
    def homeContent(self,filter):
        data=self._api('/api/video/queryClassifyList?mark=4')
        classes=[]
        for k in data.get('data',[]) if isinstance(data,dict) else []:
            tid=str(k.get('classifyId',''))
            name=k.get('classifyTitle','')
            if tid and name: classes.append({'type_name':name,'type_id':tid})
        if not classes: classes=[{'type_name':'推荐','type_id':'0'}]
        self.class_cache=classes
        res={'class':classes,'filters':{}}
        if classes:
            res['list']=self.categoryContent(classes[0]['type_id'],'1',False,{}).get('list',[])
        return res
    def homeVideoContent(self):
        tid=self.class_cache[0]['type_id'] if self.class_cache else '0'
        return {'list':self.categoryContent(tid,'1',False,{}).get('list',[])}
    def categoryContent(self,tid,pg,filter,extend):
        pg=str(pg or '1')
        paths=['/api/short/video/getShortVideos?classifyId=%s&videoMark=4&page=%s&pageSize=20'%(tid,pg),'/api/short/video/getShortVideos?videoMark=4&page=%s&pageSize=20'%(pg)] if str(tid)=='0' else ['/api/short/video/getShortVideos?classifyId=%s&videoMark=4&page=%s&pageSize=20'%(tid,pg)]
        arr=[]
        for p in paths:
            data=self._api(p)
            arr=data.get('data',[]) if isinstance(data.get('data',[]),list) else data.get('list',[])
            if arr: break
        return {'list':self._items(arr),'page':int(pg),'pagecount':9999,'limit':20,'total':999999}
    def detailContent(self,ids):
        vid=str(ids[0])
        data=self._api('/api/video/getVideoById?videoId=%s'%vid)
        if not data: return {'list':[{'vod_id':vid,'vod_name':vid,'vod_play_from':'小红书官方','vod_play_url':'播放$'}]}
        name=data.get('title') or data.get('vod_name') or vid
        auth=data.get('authKey','')
        path=data.get('videoUrl','') or data.get('playPath','') or data.get('url','')
        play='auth_key=%s&path=%s'%(auth,path) if auth and path else path
        vod={'vod_id':vid,'vod_name':name,'vod_pic':self._proxy(data.get('coverImg',''),'img'),'type_name':' '.join(data.get('tagTitles',[])) if isinstance(data.get('tagTitles',[]),list) else data.get('tagTitles',''),'vod_play_from':data.get('nickName') or '小红书官方','vod_play_url':name+'$'+play}
        return {'list':[vod]}
    def searchContent(self,key,quick,pg='1'):
        return {'list':[],'page':int(pg),'pagecount':1,'limit':20,'total':0}
    def playerContent(self,flag,id,vipFlags):
        h=self._headers()
        if h.get('aut'):
            h['Authorization']=h.pop('aut')
        if 'deviceid' in h: del h['deviceid']
        url=self.host+'/api/m3u8/decode/authPath?'+id if self.host and id.startswith('auth_key=') else id
        return {'parse':0,'playUrl':'','url':url,'header':h}
    def localProxy(self,param):
        tp,u=self._proxy_param(param)
        if not u: return [404,'text/plain','']
        ct,body=self._img_asset(u)
        return [200,ct or 'image/jpeg',body]
    def isVideoFormat(self,url):
        return False
    def manualVideoCheck(self):
        return False
    def _items(self,arr):
        res=[]
        for k in arr or []:
            vid=str(k.get('videoId') or k.get('id') or '')
            if not vid: continue
            res.append({'vod_id':vid,'vod_name':k.get('title') or vid,'vod_pic':self._proxy(k.get('coverImg',''),'img'),'vod_remarks':self._time(k.get('playTime')),'style':{'type':'rect','ratio':1.33}})
        return res
    def _api(self,path):
        if not self.host: return {}
        url=self.host+path if path.startswith('/') else path
        if url in self.api_cache: return self.api_cache[url]
        try:
            r=self.session.get(url,headers=self._headers(),timeout=12,verify=False)
            j=r.json()
            data=self._aes(j.get('encData','')) if isinstance(j,dict) and j.get('encData') else j
            if len(self.api_cache)>80: self.api_cache.clear()
            self.api_cache[url]=data
            return data
        except Exception:
            return {}
    def _token(self):
        for h in self.hs:
            for _ in range(3):
                domain='https://%s.%s.work'%(''.join(random.choices(string.ascii_lowercase+string.digits,k=random.randint(5,10))),h)
                try:
                    sign,t=self._sign()
                    hd={'User-Agent':self.ua,'deviceid':self.did,'t':t,'s':sign}
                    body={'deviceId':self.did,'tt':'U','code':'','chCode':'dafe13'}
                    r=self.session.post(domain+'/api/user/traveler',json=body,headers=hd,timeout=8,verify=False)
                    d=r.json().get('data',{})
                    if d.get('token') and d.get('imgDomain'): return d.get('token',''),d.get('imgDomain',''),domain
                except Exception:
                    continue
        return '','',''
    def _headers(self):
        sign,t=self._sign()
        h={'User-Agent':self.ua,'deviceid':self.did,'t':t,'s':sign}
        if self.token: h['aut']=self.token
        return h
    def _sign(self):
        t=str(int(time.time()*1000))
        return self._md5(t[3:8]),t
    def _aes(self,word):
        try:
            key=b64decode('SmhiR2NpT2lKSVV6STFOaQ==')
            return json.loads(unpad(AES.new(key,AES.MODE_CBC,key).decrypt(b64decode(word)),AES.block_size).decode('utf-8'))
        except Exception:
            return {}
    def _did(self):
        did=self.getCache('did')
        if not did:
            did=self._md5(str(int(time.time())))
            self.setCache('did',did)
        return did
    def _md5(self,text):
        return hashlib.md5(str(text).encode('utf-8')).hexdigest()
    def _time(self,seconds):
        try:
            s=int(seconds or 0)
            h=s//3600
            m=s%3600//60
            sec=s%60
            return '%02d:%02d:%02d'%(h,m,sec) if h else '%02d:%02d'%(m,sec)
        except Exception:
            return ''
    def _proxy(self,u,tp):
        if not u: return ''
        try:
            p=self.getProxyUrl()
            s='&' if '?' in p else '?'
            return p+s+'do=%s&type=%s&u=%s&url=%s'%(tp,tp,quote(u,safe=''),quote(u,safe=''))
        except Exception:
            return self._img_url(u)
    def _proxy_param(self,param):
        if isinstance(param,dict):
            if param.get('u') or param.get('url'): return param.get('do') or param.get('type') or 'img',unquote(param.get('u') or param.get('url') or '')
            q=parse_qs(param.get('query','') or param.get('params','') or '')
        else:
            q=parse_qs(str(param))
        return (q.get('do') or q.get('type') or ['img'])[0],unquote((q.get('u') or q.get('url') or [''])[0])
    def _img_url(self,u):
        if not u: return ''
        if u.startswith('http'): return u
        return (self.phost or '')+u
    def _img_asset(self,u):
        if u in self.img_cache: return self.img_cache[u]
        try:
            r=self.session.get(self._img_url(u),headers={'User-Agent':'Dalvik/2.1.0 (Linux; U; Android 11; M2012K10C Build/RP1A.200720.011)'},timeout=15,verify=False)
            body=self._img_decode(r.content,100,'2020-zq3-888')
            ct=(r.headers.get('Content-Type') or 'image/jpeg').split(';')[0]
            if len(self.img_cache)>160: self.img_cache.clear()
            self.img_cache[u]=(ct,body)
            return ct,body
        except Exception:
            return 'text/plain',b''
    def _img_decode(self,data,length,key):
        if len(data)>7 and (data[:3]==b'GIF' or data[:3]==b'\xff\xd8\xff' or data[1:8]==b'PNG\r\n\x1a\n'): return data
        kb=key.encode('utf-8')
        arr=bytearray(data)
        for i in range(min(length,len(arr))): arr[i]^=kb[i%len(kb)]
        return bytes(arr)

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

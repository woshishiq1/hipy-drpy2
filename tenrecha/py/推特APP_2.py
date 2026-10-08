from base.spider import Spider
import json,random,string,time,requests,hashlib
from base64 import b64decode
from urllib.parse import quote,unquote,parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class Spider(Spider):
    def getName(self):
        return '推特APP'
    def init(self,extend=""):
        self.hs=['wcyfhknomg','pdcqllfomw','alxhzjvean','bqeaaxzplt','hfbtpixjso']
        self.ua='Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36;SuiRui/twitter/ver=1.4.4'
        self.did=self._did()
        self.session=requests.Session()
        self.token,self.phost,self.host=self._token()
        self.api_cache={}
        self.img_cache={}
    def homeContent(self,filter):
        data=self._api('/api/video/classifyList')
        classes=[{'type_name':'精选','type_id':'jx'}]
        for i in data.get('data',[]):
            tid=str(i.get('classifyId',''))
            name=i.get('classifyTitle','')
            if tid and name: classes.append({'type_name':name,'type_id':tid})
        sort=[{'key':'fl','name':'分类','value':[{'n':'最近更新','v':'1'},{'n':'最多播放','v':'2'},{'n':'好评榜','v':'3'}]}]
        filters={c['type_id']:sort for c in classes if c['type_id']!='jx'}
        filters['jx']=[{'key':'type','name':'精选','value':[{'n':'日榜','v':'1'},{'n':'周榜','v':'2'},{'n':'月榜','v':'3'},{'n':'总榜','v':'4'}]}]
        return {'class':classes,'filters':filters}
    def homeVideoContent(self):
        return {'list':self.categoryContent('jx','1',False,{'type':'1'}).get('list',[])}
    def categoryContent(self,tid,pg,filter,extend):
        pg=str(pg or '1')
        ext=extend or {}
        if tid=='jx': path='/api/video/getRankVideos?pageSize=20&page=%s&type=%s'%(pg,ext.get('type','1'))
        elif 'click' in str(tid): path='/api/video/queryPersonVideoByType?pageSize=20&page=%s&userId=%s'%(pg,str(tid).replace('click',''))
        else: path='/api/video/queryVideoByClassifyId?pageSize=20&page=%s&classifyId=%s&sortType=%s'%(pg,tid,ext.get('fl','1'))
        data=self._api(path)
        arr=data.get('data',[]) if isinstance(data.get('data',[]),list) else data.get('videoList',[])
        return {'list':self._items(arr,'click' in str(tid)),'page':int(pg),'pagecount':9999,'limit':20,'total':999999}
    def detailContent(self,array):
        raw=str(array[0])
        click='click' in raw
        pp=raw.replace('click','').split('?',2)
        vid=pp[0] if len(pp)>0 else raw
        uid=pp[1] if len(pp)>1 else ''
        name=unquote(pp[2]) if len(pp)>2 else '推特APP'
        data=self._api('/api/video/can/watch?videoId=%s'%vid)
        url=data.get('playPath','') or data.get('url','') or data.get('playUrl','')
        director=name if click or not uid else '[a=cr:'+json.dumps({'id':uid+'click','name':name},ensure_ascii=False)+'/]'+name+'[/a]'
        vod={'vod_id':raw,'vod_name':name,'vod_pic':'','vod_director':director,'vod_content':name,'vod_play_from':'推特','vod_play_url':name+'$'+url}
        return {'list':[vod]}
    def searchContent(self,key,quick,pg='1'):
        data=self._api('/api/search/keyWord?pageSize=20&page=%s&searchWord=%s&searchType=1'%(pg,quote(key)))
        return {'list':self._items(data.get('videoList',[]),False),'page':int(pg),'pagecount':9999,'limit':20,'total':999999}
    def playerContent(self,flag,id,vipFlags):
        return {'parse':0,'playUrl':'','url':id,'header':self._headers()}
    def localProxy(self,param):
        tp,u=self._proxy_param(param)
        if not u: return [404,'text/plain','']
        ct,body=self._img_asset(u)
        return [200,ct or 'image/jpeg',body]
    def isVideoFormat(self,url):
        return False
    def manualVideoCheck(self):
        return False
    def _items(self,arr,clicked=False):
        res=[]
        for k in arr or []:
            cover=k.get('coverImg') or []
            pic=cover[0] if isinstance(cover,list) and cover else cover if isinstance(cover,str) else ''
            vid=str(k.get('videoId',''))
            uid=str(k.get('userId',''))
            nick=str(k.get('nickName',''))
            if not vid: continue
            vod_id='%s?%s?%s%s'%(vid,uid,quote(nick), 'click' if clicked else '')
            res.append({'vod_id':vod_id,'vod_name':k.get('title') or nick or vid,'vod_pic':self._proxy(pic,'img'),'vod_remarks':self._time(k.get('playTime')),'style':{'type':'rect','ratio':1.33}})
        return res
    def _api(self,path,post=None):
        url=self.host+path if path.startswith('/') else path
        key=('POST:' if post is not None else 'GET:')+url+json.dumps(post,sort_keys=True,ensure_ascii=False) if post is not None else 'GET:'+url
        if key in self.api_cache: return self.api_cache[key]
        try:
            r=self.session.post(url,json=post,headers=self._headers(),timeout=12,verify=False) if post is not None else self.session.get(url,headers=self._headers(),timeout=12,verify=False)
            j=r.json()
            data=self._aes(j.get('encData','')) if j.get('encData') else j
            if len(self.api_cache)>80: self.api_cache.clear()
            self.api_cache[key]=data
            return data
        except Exception:
            return {}
    def _token(self):
        for h in self.hs:
            domain='https://%s.%s.work'%(''.join(random.choices(string.ascii_lowercase+string.digits,k=random.randint(5,10))),h)
            try:
                sign,t=self._sign()
                hd={'User-Agent':self.ua,'Accept':'application/json','deviceid':self.did,'t':t,'s':sign}
                body={'deviceId':self.did,'tt':'U','code':'##X-4m6Goo4zzPi1hF##','chCode':'tt09'}
                r=self.session.post(domain+'/api/user/traveler',json=body,headers=hd,timeout=10,verify=False)
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
        return self._md5(t),t
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
            r=self.session.get(self._img_url(u),headers={'User-Agent':self.ua},timeout=15,verify=False)
            body=self._img_decode(r.content,100,'2020-zq3-888')
            ct=r.headers.get('Content-Type','image/jpeg')
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
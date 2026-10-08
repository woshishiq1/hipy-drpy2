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
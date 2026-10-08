# -*- coding: utf-8 -*-
import sys,re,json,html,urllib.parse,base64
sys.path.append('..')
try:
    from base.spider import Spider as _B
except ImportError:
    class _B:pass
try: import requests
except ImportError: requests=None
H="https://netflixgc.net"
U="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class Spider(_B):
    def init(self,e=""):
        self.s=requests.Session();self.s.headers.update({"User-Agent":U,"Accept-Language":"zh-CN,zh;q=0.9"})
    def getName(self):return"奈飞工厂"
    def isVideoFormat(self,u):return".m3u8"in u or".mp4"in u
    def manualVideoCheck(self):return False
    def _get(self,u):
        if not u.startswith('http'):u=H+u
        try:r=self.s.get(u,timeout=20);r.raise_for_status();r.encoding='utf-8';return r.text
        except Exception as e:print('[NETFLIXGC]',e);return''
    def _api(self,data):
        try:
            r=self.s.post(H+'/index.php/ds_api/vod',data=data,headers={'X-Requested-With':'XMLHttpRequest'},timeout=20);return r.json()
        except Exception as e:print('[API]',e);return{}
    def _items(self,d):
        out=[]
        for x in d.get('list',[]):
            out.append({'vod_id':str(x.get('vod_id','')),'vod_name':html.unescape(x.get('vod_name','')),'vod_pic':x.get('vod_pic',''),'vod_remarks':x.get('vod_remarks',''),'vod_content':html.unescape(x.get('vod_blurb',''))})
        return out
    def homeContent(self,filter=False):
        return {'class':[{'type_id':'1','type_name':'电影'},{'type_id':'2','type_name':'连续剧'},{'type_id':'24','type_name':'纪录片'},{'type_id':'3','type_name':'漫剧'},{'type_id':'23','type_name':'综艺'}]}
    def homeVideoContent(self):
        d=self._api({'type':'2','class':'','area':'','year':'','lang':'','version':'','state':'','letter':'','time':'','level':'0','weekday':'','by':'time','page':'1'})
        return {'list':self._items(d)[:40]}
    def categoryContent(self,tid,pg=1,filter=False,extend=None):
        d=self._api({'type':str(tid),'class':'','area':'','year':'','lang':'','version':'','state':'','letter':'','time':'','level':'0','weekday':'','by':'time','page':max(int(str(pg)),1)})
        return {'list':self._items(d),'page':d.get('page',pg),'pagecount':d.get('pagecount',1),'limit':d.get('limit',40),'total':d.get('total',0)}
    def _eps(self,h):
        out=[];seen=set()
        for m in re.finditer(r'href=["\'](/vodplay/[^"\']+?\.html)["\'][^>]*>(.*?)</a>',h,re.S|re.I):
            u=m.group(1);name=re.sub('<[^>]+>','',m.group(2)).strip()
            # 避免重复导航链接；只保留真实选集 href。
            if not re.search(r'/vodplay/\d+-\d+-\d+\.html$',u):continue
            if u not in seen:
                seen.add(u);out.append((name or '播放',u))
        return out
    def detailContent(self,ids):
        vid=str(ids[0]).split('/')[-1];h=self._get('/voddetail/'+vid+'.html')
        tm=re.search(r'<title>(.*?)</title>',h,re.S|re.I);title=re.sub(r'_.*','',tm.group(1)).strip() if tm else vid
        hm=re.search(r'<meta name="description" content="(.*?)"',h,re.S|re.I);desc=html.unescape(hm.group(1)) if hm else ''
        pm=re.search(r'(?:vod_pic|pic)["\']?\s*[:=]\s*["\']([^"\']+)',h,re.I)
        pic=pm.group(1) if pm else ''
        if pic in ('b','pic') or not pic.startswith('http'):
            # 少数条目没有官方封面；不要把模板中的字符 b 当作图片 URL。
            pic=''

        eps=self._eps(h)
        if not eps:
            eps=[('第1集','/vodplay/%s-1-1.html'%vid)]
        # 按来源分组：MacCMS 页面将线路/剧集混在同一组链接中。
        groups={}
        for name,u in eps:
            m=re.search(r'/vodplay/\d+-(\d+)-(\d+)\.html$',u)
            if not m:continue
            sid,ep=m.group(1),m.group(2)
            # 相同线路按集号保留，避免标题相同导致宿主去重。
            groups.setdefault(sid,[]).append((name,u))
        # 站点的某些电影详情页是“单集多线路”：同一集的不同 sid
        # 应作为同一个选集里的多个线路来源，而不是拆成多个 route 造成宿主自动切换。
        if len(groups)>1 and all(len(x)==1 for x in groups.values()):
            merged=[]
            for sid,items in groups.items():
                name,u=items[0]
                merged.append((name,u))
            play_from=['线路1']
            play_url=['#'.join((name or '线路%d'%idx)+'$'+u for idx,(name,u) in enumerate(merged,1))]
        else:
            play_from=[];play_url=[]
            for sid,items in groups.items():
                play_from.append('线路'+sid)
                play_url.append('#'.join((name or '第%s集'%idx)+'$'+u for idx,(name,u) in enumerate(items,1)))
        if not play_from:
            play_from=['奈飞工厂'];play_url=['播放$'+eps[0][1]]
        return {'list':[{'vod_id':vid,'vod_name':title,'vod_pic':pic,'vod_content':desc,'vod_play_from':'$$$'.join(play_from),'vod_play_url':'$$$'.join(play_url)}]}
    def _decode_page_url(self,u):
        """读取播放页中的 player_aaaa.url；只接受最终真实媒体 URL。"""
        h=self._get(u)
        m=re.search(r'var player_aaaa=(\{.*?\});',h,re.S)
        if not m:return''
        try:d=json.JSONDecoder().raw_decode(m.group(1))[0]
        except:return''
        raw=d.get('url','')
        for _ in range(3):
            x=urllib.parse.unquote(raw)
            if x==raw:break
            raw=x
        if not raw.startswith('http'):
            try:raw=base64.b64decode(raw).decode()
            except:return''
            raw=urllib.parse.unquote(raw)
        return raw if (raw.startswith('http') and ('.m3u8' in raw or '.mp4' in raw)) else''

    def playerContent(self,flag,id,vipFlags=None):
        u=id if id.startswith('http') else H+id
        url=self._decode_page_url(u)
        return {'parse':0,'url':url,'header':json.dumps({'User-Agent':U,'Referer':H+'/'})}
    def searchContent(self,key,quick=False,pg=1):
        # Search page is server-rendered and capped by the site at 40/100 results.
        h=self._get('/vodsearch/-------------.html?wd='+urllib.parse.quote(key))
        items=[]
        for m in re.finditer(r'href=["\'](/voddetail/(\d+)\.html)["\'][^>]*>(.*?)</a>',h,re.S|re.I):
            name=re.sub('<[^>]+>','',m.group(3)).strip();items.append({'vod_id':m.group(2),'vod_name':name,'vod_pic':''})
        # Fallback to inline play/detail pairs where theme markup differs.
        seen={x['vod_id'] for x in items}
        for m in re.finditer(r'/voddetail/(\d+)\.html',h):
            if m.group(1) not in seen:seen.add(m.group(1));items.append({'vod_id':m.group(1),'vod_name':m.group(1),'vod_pic':''})
        return {'list':items}
    def localProxy(self,param):pass

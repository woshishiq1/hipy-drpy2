# -*- coding: utf-8 -*-
import sys,re,json
from urllib.parse import quote,unquote
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):pass
class Spider(Spider):
    def init(self,extend=''):
        self.hdr={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36','Accept':'application/json','X-Requested-With':'XMLHttpRequest'}
    def _get(self,url,jsonmode=False,html=False):
        hdr={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'}
        if not html:hdr.update({'Accept':'application/json','X-Requested-With':'XMLHttpRequest'})
        try:
            import urllib.parse as up
            url=up.quote(url,safe=':/?=&%.-_')
        except:pass
        for _ in range(4):
            try:
                import requests
                r=requests.get(url,headers=hdr,timeout=20)
                txt=r.text
            except:
                try:
                    import urllib.request
                    req=urllib.request.Request(url,headers=hdr)
                    txt=urllib.request.urlopen(req,timeout=20).read().decode('utf-8',errors='ignore')
                except:return '' if not jsonmode else {}
            m=re.search(r'<meta\s+http-equiv="refresh"\s+content="0;url=\'([^\']+)\'"',txt)
            if m:
                url=m.group(1) if m.group(1).startswith('http') else 'https://javhd.com'+m.group(1)
                continue
            return json.loads(txt) if jsonmode else txt
        return {} if jsonmode else ''
    def _cards(self,t):
        out=[]
        for c in re.findall(r'<thumb-component\s+type-thumb="video"\s+(?:item-id="\d+"\s+)?video-id="(\d+)"\s+link-content="([^"]+)"\s+url-thumb="([^"]+)"\s+video-preview="([^"]*)"(?:\s+has-label="([^"]*)")?\s+title="([^"]+)"',t):
            out.append({'vid':c[0],'link':c[1],'pic':c[2],'preview':c[3],'label':c[4] or 'free','title':c[5]})
        return out
    def homeContent(self,filter=False):
        return {'class':[{'type_id':'justadded','type_name':'最新'},{'type_id':'popular','type_name':'热门'},{'type_id':'top','type_name':'最多播放'}],'list':self.homeVideoContent()}
    def _pic(self,th):
        if isinstance(th,dict):
            for k in ('1130x706','940x530','468x264','374x233'):
                if th.get(k):return th[k]
            return next(iter(th.values()),'')
        return ''
    def homeVideoContent(self):
        j=self._get('https://javhd.com/en/api/content_block?block=custom&pgid=1339887660&isCasting=1&count=24&offset=0&castingPosition=8',True)
        out=[]
        for i in j.get('template',[]):
            if isinstance(i,dict) and i.get('id'):
                out.append({'vod_id':'https://javhd.com'+i.get('studioUrl',''),'vod_name':i.get('title',''),'vod_pic':self._pic(i.get('thumbs')),'vod_remarks':''})
        return out
    def categoryContent(self,tid,pg='1',filter=False,extend={}):
        j=self._get(f'https://javhd.com/en/japanese-porn-videos/{tid}/all/{pg}',True)
        if not j:return {'list':[]}
        items=self._cards(j.get('template',''))
        import math
        pc=max(1,int(math.ceil(j.get('results_count',0)/max(1,j.get('per_page',24)))))
        return {'list':[{'vod_id':i['link'],'vod_name':i['title'],'vod_pic':i['pic'],'vod_remarks':'VIP' if i['label']!='free' else '','vod_content':i['label']} for i in items],'page':int(pg),'pagecount':pc,'limit':j.get('per_page',24),'total':j.get('results_count',0)}
    def detailContent(self,ids):
        if not isinstance(ids,list):ids=[ids]
        u=ids[0]
        if re.fullmatch(r'\d+',u):u=f'https://javhd.com/en/id/{u}/'
        h=self._get(u,html=True)
        if not h:return {'list':[]}
        m=re.search(r'content-path="/en/player_api\?videoId=(\d+)&amp;is_trailer=\d+"',h)
        if not m:m=re.search(r'content-id="(\d+)"',h)
        if not m:return {'list':[]}
        cid=m.group(1)
        t=re.search(r'<title>([^<]*)</title>',h)
        name=(t.group(1).split('|')[0].strip() if t else '')
        p=re.search(r'--playerPoster:\s*url\(([^)]+)\)',h)
        pic=p.group(1) if p else ''
        d=re.search(r'<meta\s+name="description"\s+content="([^"]*)"',h)
        desc=d.group(1) if d else ''
        return {'list':[{'vod_id':u,'vod_name':name,'vod_pic':pic,'vod_content':desc,'vod_play_from':'javhd','vod_play_url':f'完整版$https://javhd.com/en/player_api?videoId={cid}&is_trailer=0'}]}
    def searchContent(self,key,quick=False,pg='1'):
        j=self._get('https://javhd.com/en/search?q='+quote(key),True)
        if not j:return {'list':[]}
        items=self._cards(j.get('template',''))
        return {'list':[{'vod_id':i['link'],'vod_name':i['title'],'vod_pic':i['pic'],'vod_remarks':'VIP' if i['label']!='free' else '','vod_content':i['label']} for i in items]}
    def playerContent(self,flag,id,vipFlags):
        j=self._get(id,True)
        if not j or not j.get('sources'):return {}
        s=sorted(j['sources'],key=lambda x:x.get('res',0),reverse=True)[0]
        return {'parse':0,'url':s.get('src','')}
    def localProxy(self,param):
        return []

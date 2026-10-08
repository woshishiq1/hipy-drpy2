# -*- coding: utf-8 -*-
# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。

from base.spider import Spider
import re,sys,time,random,secrets,hashlib,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    host,device_id = 'https://bubutv.top/','com.sunshine.tv_3qys_B7k7Dt56Rn'

    def homeContent(self, filter):
        if not self.host: return None
        response = self.fetch(f'{self.host}/api.php/app/index/home', headers=self.headers(), verify=False).json()
        categories = response['data']['categories']
        videos,classes = [],[]
        for i in categories:
            classes.append({'type_id': i['type_name'],'type_name': i['type_name']})
            videos.extend(self.arr2vods(i['videos']))
        return {'class': classes, 'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        response = self.fetch(f'{self.host}/api.php/app/filter/vod?type_name={tid}&page={pg}&sort=hits', headers=self.headers(), verify=False).json()
        return {'list': self.arr2vods(response['data']), 'pagecount':response['pageCount'], 'page': pg}

    def searchContent(self, key, quick, pg='1'):
        response = self.fetch(f'{self.host}/api.php/app/search/index?wd={key}&page={pg}&limit=15', headers=self.headers(), verify=False).json()
        videos = self.arr2vods(response['data'])
        return {'list': videos, 'pagecount':response['pageCount'], 'page': pg}

    def detailContent(self, ids):
        response = self.fetch(f'{self.host}/api.php/app/vod/get_detail?vod_id={ids[0]}', headers=self.headers(), verify=False).json()
        data = response['data'][0]
        shows,play_urls = [],[]
        raw_shows = data['vod_play_from'].split('$$$')
        raw_urls_list = data['vod_play_url'].split('$$$')
        for show_code, urls_str in zip(raw_shows, raw_urls_list):
            need_parse,is_show,name,urls = 0,0,show_code,[]
            for i in response['vodplayer']:
                if i['from'] == show_code:
                    is_show = 1
                    need_parse = i['decode_status']
                    if show_code.casefold() != i['show'].casefold():
                        name = f"{i['show']}\u2005({show_code})"
                    break
            if is_show == 1:
                for url_item in urls_str.split('#'):
                    if '$' in url_item:
                        episode, url = url_item.split('$',1)
                        urls.append(f"{episode}${show_code}@{int(need_parse)}@{url}")
                if urls:
                    play_urls.append('#'.join(urls))
                    shows.append(name)
        video = {
            'vod_id': data['vod_id'],
            'vod_name': data['vod_name'],
            'vod_pic': data['vod_pic'],
            'vod_remarks': data['vod_remarks'],
            'vod_year': data['vod_year'],
            'vod_area': data['vod_area'],
            'vod_actor': data['vod_actor'],
            'vod_director': data['vod_director'],
            'vod_content': data['vod_content'],
            'vod_play_from': '$$$'.join(shows),
            'vod_play_url': '$$$'.join(play_urls),
            'type_name': data['vod_class']
        }
        return {'list': [video]}

    def playerContent(self, flag, vid, vip_flags):
        play_from, need_parse, raw_url = vid.split('@', 2)
        jx,url = 0,''
        if need_parse == '1':
            try:
                response = self.fetch(f'{self.host}/api.php/app/decode/url/?url={raw_url}&vodFrom={play_from}',headers=self.headers(),timeout=30,verify=False).json()
                play_url = response['data']
                if play_url.startswith('http'): url = play_url
            except Exception:
                pass
        if not url:
            url = raw_url
            if re.search(r'(?:www\.iqiyi|v\.qq|v\.youku|www\.mgtv|www\.bilibili)\.com', raw_url):
                jx = 1
        return { 'jx': jx, 'parse': 0, 'url': url, 'header': {'User-Agent': 'com.sunshine.tv/1.2.0 (Linux;Android 15) AndroidXMedia3/1.4.1'}}

    def arr2vods(self, arr):
        videos = []
        for i in arr:
            type_name = i.get('type_name')
            if i.get('vod_class'):
                type_name = f"{type_name},{i.get('vod_class','')}"
            videos.append({
                'vod_id': i['vod_id'],
                'vod_name': i['vod_name'],
                'vod_pic': i['vod_pic'],
                'vod_remarks': i['vod_remarks'],
                'type_name': type_name,
                'vod_year': i.get('vod_year')
            })
        return videos

    def headers(self):
        timestamp = str(int(time.time()))
        nonce = ''.join(random.choice('0123456789') for _ in range(3))
        ver,pkg = '3','com.sunshine.tv'
        sign_str = f"finger=SF-C3B2B41F6EFFFF9869176CF68F6790E8F07506FC88632C94B4F5F0430D5498CA&id={pkg}&nonce={nonce}&sk=SK-thanks&time={timestamp}&v={ver}"
        sign = hashlib.sha256(sign_str.encode('utf-8')).hexdigest().upper()
        if not self.device_id:
            device_id_cache_key = 'com.sunshine.tv_3qys_B7k7Dt56Rn'
            self.device_id = self.getCache(device_id_cache_key)
            if not(isinstance(self.device_id,str) and len(self.device_id) == 16):
                self.device_id = ''.join(secrets.choice('0123456789abcdef') for _ in range(16))
                self.setCache(device_id_cache_key, self.device_id)
        return {
            'User-Agent': 'okhttp/4.12.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'x-aid': pkg,
            'x-ave': ver,
            'x-time': timestamp,
            'x-nonc': nonce,
            'x-sign': sign,
            'x-device-id': self.device_id,
            'x-device-brand': 'vivo',
            'x-device-model': 'V2309A',
            'x-update-id': '0245861b-2ebf-5524-389d-f983830651ec'
        }

    def init(self, extend=''):
        pass

    def homeVideoContent(self):
        pass

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
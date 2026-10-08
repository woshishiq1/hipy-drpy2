# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/3/23 21:55
import base64
import sys
import time
import json
import requests
import re
from datetime import datetime
sys.path.append('..')
from base.spider import Spider
from bs4 import BeautifulSoup

class Spider(Spider):
    def getName(self):
        return "Litv"

    def init(self, extend):
        self.extend = extend
        try:
            self.extendDict = json.loads(extend)
        except:
            self.extendDict = {}

        proxy = self.extendDict.get('proxy', None)
        if proxy is None:
            self.is_proxy = False
        else:
            self.proxy = proxy
            self.is_proxy = True
        pass

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass


    def liveContent(self, url):
        cookies = {
            '_ga': 'GA1.1.782627561.1745936696',
            '_oredge_rl': 'u1ORyxILkguVwZ3LWQNJTpqceYPzrL/Cgugwu74xDwA=',
            'dailyMessageShown515': 'shown',
            '_ga_F2ET4TBC70': 'GS2.1.s1747232930$o3$g1$t1747233259$j0$l0$h0',
        }

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'max-age=0',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            # 'cookie': '_ga=GA1.1.782627561.1745936696; _oredge_rl=u1ORyxILkguVwZ3LWQNJTpqceYPzrL/Cgugwu74xDwA=; dailyMessageShown515=shown; _ga_F2ET4TBC70=GS2.1.s1747232930$o3$g1$t1747233259$j0$l0$h0',
        }

        response = requests.get('https://www.515001.tv/', cookies=cookies, headers=headers)

        #print(response.text)  #自己添加，表示输出响应的内容

        html = response.text

        soup = BeautifulSoup(html, 'html.parser')

        matches = []
        for a in soup.find_all('a', class_='clearfix'):
            # 提取链接
            link = a.get('href', '')
            link = f"video://{link}"
            
            # 提取赛事名称和时间
            event_time_p = a.find('p', class_='eventtime_wuy')
            if event_time_p:
                em = event_time_p.find('em')
                event_name = em.get_text(strip=True) if em else ''
                i_tag = event_time_p.find('i')
                time = i_tag.get_text(strip=True) if i_tag else ''
            else:
                event_name = ''
                time = ''
            
            # 提取主队名称
            home_div = a.find('div', class_=lambda c: c and 'zhudui' in c)
            home_team = home_div.find('p').get_text(strip=True) if home_div else ''
            
            # 提取客队名称
            away_div = a.find('div', class_='kedui')
            away_team = away_div.find('p').get_text(strip=True) if away_div else ''
            
            if event_name and home_team and away_team and time and link:
                match_str = f"[{event_name}]{home_team} VS {away_team}{time},{link}"
                matches.append(match_str)
        
        m3u_content = ['#EXTM3U']
        for match in matches:
            title = match.split(",")[0]
            ch_url = match.split(",")[1]
            extinf = f'#EXTINF:-1 tvg-name="{title}" group-title="515001",{title}'
            m3u_content.extend([extinf, ch_url])
 
        return '\n'.join(m3u_content)

    def homeContent(self, filter):
        return {}

    def homeVideoContent(self):
        return {}

    def categoryContent(self, cid, page, filter, ext):
        return {}

    def detailContent(self, did):
        return {}

    def searchContent(self, key, quick, page='1'):
        return {}

    def searchContentPage(self, keywords, quick, page):
        return {}

    def playerContent(self, flag, pid, vipFlags):
        return {}

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        if params['type'] == "ts":
            return self.get_ts(params)
        return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]
    def proxyM3u8(self, params):
        pid = params['pid']
        info = pid.split(',')
        a = info[0]
        b = info[1]
        c = info[2]
        timestamp = int(time.time() / 4 - 355017625)
        t = timestamp * 4
        m3u8_text = f'#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:{timestamp}\n'
        for i in range(10):
            url = f'https://ntd-tgc.cdn.hinet.net/live/pool/{a}/litv-pc/{a}-avc1_6000000={b}-mp4a_134000_zho={c}-begin={t}0000000-dur=40000000-seq={timestamp}.ts'
            if self.is_proxy:
                url = f'http://127.0.0.1:9978/proxy?do=py&type=ts&url={self.b64encode(url)}'

            m3u8_text += f'#EXTINF:4,\n{url}\n'
            timestamp += 1
            t += 4
        return [200, "application/vnd.apple.mpegurl", m3u8_text]

    def get_ts(self, params):
        url = self.b64decode(params['url'])
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, stream=True, proxies=self.proxy)
        return [206, "application/octet-stream", response.content]

    def destroy(self):
        return '正在Destroy'

    def b64encode(self, data):
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    def b64decode(self, data):
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')


if __name__ == '__main__':
    pass

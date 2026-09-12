"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '飞牛影视',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
# 飞牛影视爬虫 - 完整修复版
import re
import sys
from urllib.parse import quote, urljoin
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = 'https://www.ntmsxy.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '飞牛影视'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {
            'class': [
                {'type_name': '电影', 'type_id': '1'},
                {'type_name': '电视剧', 'type_id': '2'},
                {'type_name': '综艺', 'type_id': '3'},
                {'type_name': '动漫', 'type_id': '4'},
                {'type_name': '短剧', 'type_id': '5'},
            ],
            'filters': {},
            'list': []
        }
        try:
            html = self.fetch(self.host + '/', headers=self.headers).text
            result['list'] = self.get_vod_list(html)
        except:
            pass
        return result

    def homeVideoContent(self):
        try:
            html = self.fetch(self.host + '/', headers=self.headers).text
            return self.get_vod_list(html)
        except:
            return []

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        try:
            url = f'/ntmsxytp/{tid}.html' if pg == '1' else f'/ntmsxytp/{tid}-{pg}.html'
            html = self.fetch(self.host + url, headers=self.headers).text
            result['list'] = self.get_vod_list(html)
        except:
            pass
        return result

    def detailContent(self, ids):
        result = {'list': []}
        try:
            url = ids[0] if ids[0].startswith('http') else self.host + ids[0]
            html = self.fetch(url, headers=self.headers).text
            
            vod = {}
            
            # 标题
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if not m:
                m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).strip()
                title = re.sub(r'\s*-\s*飞牛影视.*$', '', title)
                vod['vod_name'] = title
            
            # 海报
            m = re.search(r'<div[^>]+class="[^"]*poster[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
            if m:
                vod['vod_pic'] = m.group(1)
            else:
                m = re.search(r'<img[^>]+class="[^"]*poster[^"]*"[^>]+src="([^"]+)"', html)
                if m:
                    vod['vod_pic'] = m.group(1)
            
            # 简介
            m = re.search(r'<div[^>]+id="info"[^>]*>.*?<p>([^<]+)</p>', html, re.DOTALL)
            if m:
                vod['vod_content'] = m.group(1).strip()
            
            # 提取ID
            m = re.search(r'/ntmsxydt/(\d+)', ids[0])
            vid = m.group(1) if m else ''
            
            # 播放源 - 从 ui-box 提取
            play_from = []
            play_url_list = []
            
            # 找到所有 playlist_X 的容器
            playlist_blocks = re.findall(r'<div[^>]+id="playlist_\d+"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
            
            if playlist_blocks:
                for block in playlist_blocks:
                    # 提取线路名称
                    name_m = re.search(r'<h2>([^<]+)</h2>', block)
                    if name_m:
                        play_from.append(name_m.group(1).strip())
                    
                    # 提取所有播放链接
                    episodes = re.findall(r'<a[^>]+href="(/ntmsxypy/[^"]+)"[^>]*>([^<]+)</a>', block)
                    if episodes:
                        eps = []
                        for href, text in episodes:
                            eps.append((text.strip(), href))
                        play_url_list.append('#'.join([f"{t}${self.host + h}" for t, h in eps]))
                    else:
                        play_url_list.append('')
            
            if not play_from:
                play_from = ['线路1']
            if not play_url_list:
                play_url_list = ['']
            
            vod['vod_play_from'] = '$$$'.join(play_from)
            vod['vod_play_url'] = '$$$'.join(play_url_list)
            result['list'].append(vod)
        except:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        try:
            url = f'{self.host}/ntmsxysc/{quote(key)}-------------.html'
            html = self.fetch(url, headers=self.headers).text
            result['list'] = self.get_vod_list(html)
        except:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {'parse': 1, 'url': '', 'header': {}}
        try:
            play_url = id if id.startswith('http') else self.host + id
            html = self.fetch(play_url, headers=self.headers).text
            
            # 查找iframe
            m = re.search(r'<iframe[^>]+src="([^"]+)"[^>]*>', html, re.I)
            if m:
                iframe_src = m.group(1)
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                result['parse'] = 1
                result['url'] = iframe_src
                result['header'] = {
                    'Referer': self.host,
                    'User-Agent': self.headers['User-Agent']
                }
                return result
            
            # 查找m3u8
            m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m:
                result['parse'] = 0
                result['url'] = m.group(1)
                return result
            
            result['parse'] = 1
            result['url'] = play_url
        except Exception as e:
            print(f'playerContent 错误: {e}')
        return result

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def get_vod_list(self, html):
        videos = []
        seen = set()
        
        # 匹配 /ntmsxydt/数字.html 链接及其附近的图片
        for m in re.finditer(r'<a[^>]+href="(/ntmsxydt/\d+\.html)"[^>]*>', html):
            href = m.group(1)
            m2 = re.search(r'/ntmsxydt/(\d+)', href)
            if not m2:
                continue
            
            vid = m2.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            
            start = max(0, m.start() - 1000)
            end = min(len(html), m.end() + 500)
            context = html[start:end]
            
            # 标题 - 从 alt 属性或上下文获取
            title = ''
            title_m = re.search(r'alt="([^"]+)"', context)
            if title_m:
                title = title_m.group(1).strip()
            if not title:
                title_m = re.search(r'<h3[^>]*>([^<]+)</h3>', context)
                if title_m:
                    title = title_m.group(1).strip()
            
            # 图片 - 在链接附近的 <img> 中查找
            pic = ''
            pic_m = re.search(r'<img[^>]+src="(/upload/[^"]+)"', context)
            if pic_m:
                pic = pic_m.group(1)
                if pic.startswith('/'):
                    pic = self.host + pic
            
            if title:
                full_url = self.host + href
                videos.append({
                    'vod_id': full_url,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': ''
                })
        
        return videos
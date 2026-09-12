"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '酷客影院',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
# 酷客影院爬虫
import re
import sys
from urllib.parse import quote, urlencode
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = 'https://www.199dy.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '酷客影院'

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
                {'type_name': '动漫', 'type_id': '3'},
                {'type_name': '综艺', 'type_id': '4'},
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
            url = f'{self.host}/list/{tid}.html'
            if int(pg) > 1:
                url = f'{self.host}/list/{tid}-{pg}.html'
            html = self.fetch(url, headers=self.headers).text
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
            if m:
                title = m.group(1).strip()
                title = re.sub(r'\s*-.*$', '', title)
                vod['vod_name'] = title
            
            # 海报 - 详情页中的 img
            m = re.search(r'<img[^>]+class="[^"]*lazyload[^"]*"[^>]+(?:data-original|src)="([^"]+)"', html)
            if not m:
                m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if m:
                vod['vod_pic'] = m.group(1)
            
            # 简介
            m = re.search(r'<span[^>]+class="detail-sketch"[^>]*>([^<]+)', html)
            if not m:
                m = re.search(r'简介：</span>\s*([^<]+)', html)
            if m:
                vod['vod_content'] = m.group(1).strip()[:500]
            
            # 播放源和集数
            play_from = []
            play_url_list = []
            
            # 方法1：提取 nav-tabs 中的源名称
            tabs = re.findall(r'<ul class="nav[^"]*tabs[^"]*"[^>]*>(.*?)</ul>', html, re.DOTALL)
            source_names = re.findall(r'<li[^>]*><a[^>]+href="#([^"]+)"[^>]*>([^<]+)</a></li>', tabs[0] if tabs else '')
            
            if source_names:
                for tab_id, source_name in source_names:
                    play_from.append(source_name.strip())
                    # 查找对应 tab-content 里的播放列表
                    playlist_match = re.search(r'<div[^>]+id="' + tab_id + '"[^>]*>(.*?)</div>', html, re.DOTALL)
                    if playlist_match:
                        episodes = re.findall(r'<li[^>]*><a href="(/gov-\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a></li>', playlist_match.group(1))
                        ep_list = []
                        for href, name in episodes:
                            full_url = self.host + href
                            ep_list.append(f"{name.strip()}${full_url}")
                        play_url_list.append('#'.join(ep_list))
                    else:
                        play_url_list.append('')
            
            # 方法2：备用 - 提取所有 stui-content__playlist
            if not play_from:
                source_blocks = re.findall(r'<ul class="stui-content__playlist clearfix">(.*?)</ul>', html, re.DOTALL)
                if source_blocks:
                    play_from = ['线路1']
                    all_eps = []
                    for block in source_blocks:
                        eps = re.findall(r'<li[^>]*><a href="(/gov-\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a></li>', block)
                        for href, name in eps:
                            full_url = self.host + href
                            all_eps.append(f"{name.strip()}${full_url}")
                    play_url_list.append('#'.join(all_eps))
            
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
            # 搜索是POST请求
            import requests
            url = f'{self.host}/search.php'
            post_data = f'searchword={quote(key)}&page={pg}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': self.host + '/',
            }
            resp = requests.post(url, data=post_data.encode('utf-8'), headers=headers, timeout=10)
            html = resp.text
            result['list'] = self.get_vod_list(html)
        except Exception as e:
            print(f'搜索错误: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {'parse': 0, 'url': '', 'header': {}}
        try:
            play_url = id if id.startswith('http') else self.host + id
            html = self.fetch(play_url, headers=self.headers).text
            
            # 提取 iframe src
            m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if m:
                iframe_url = m.group(1)
                result['parse'] = 1  # 使用解析模式，让系统处理这个 iframe
                result['url'] = iframe_url
                result['header'] = {
                    'Referer': self.host + '/'
                }
                return result
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
        
        # 匹配视频列表项 - 多种可能的顺序
        # 格式1: 首页/分类页 <a class="stui-vodlist__thumb lazyload" data-original="..." href="/edu-xxx.html" title="...">
        # 格式2: 搜索页 <a class="v-thumb stui-vodlist__thumb lazyload" data-original="..." href="/edu-xxx.html" title="...">
        # 需要同时匹配两种顺序
        patterns = [
            r'<a[^>]+data-original="([^"]+)"[^>]+href="(/edu-\d+\.html)"[^>]+title="([^"]+)"',
            r'<a[^>]+class="[^"]*stui-vodlist__thumb[^"]*"[^>]+href="(/edu-\d+\.html)"[^>]+data-original="([^"]+)"[^>]+title="([^"]+)"',
        ]
        
        for pattern in patterns:
            for m in re.finditer(pattern, html):
                if pattern.startswith(r'<a[^>]+data-original'):
                    pic = m.group(1)
                    href = m.group(2)
                    title = m.group(3)
                else:
                    href = m.group(1)
                    pic = m.group(2)
                    title = m.group(3)
                
                # 提取 ID
                m2 = re.search(r'/edu-(\d+)\.html', href)
                if not m2:
                    continue
                vid = m2.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                
                # 在附近查找备注
                remark = ''
                start = max(0, m.start() - 300)
                end = min(len(html), m.end() + 300)
                context = html[start:end]
                remark_m = re.search(r'<span class="pic-text text-right">([^<]+)</span>', context)
                if remark_m:
                    remark = remark_m.group(1).strip()
                
                full_url = self.host + href
                if title:
                    videos.append({
                        'vod_id': full_url,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': remark
                    })
        
        return videos
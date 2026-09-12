"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '539影视',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
# 539影视爬虫
import re
import sys
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = 'http://www.539539.xyz'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '539影视'

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
                {'type_name': '剧集', 'type_id': '2'},
                {'type_name': '综艺', 'type_id': '3'},
                {'type_name': '动漫', 'type_id': '4'},
                {'type_name': '短剧', 'type_id': '25'},
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
            # 分类URL格式: /index.php/vod/show/id/{type_id}.html
            url = f'{self.host}/index.php/vod/show/id/{tid}.html'
            if int(pg) > 1:
                url = f'{self.host}/index.php/vod/show/id/{tid}/page/{pg}.html'
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
            m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            if not m:
                m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).strip()
                title = re.sub(r'\s*-.*$', '', title)
                vod['vod_name'] = title
            
            # 海报
            m = re.search(r'<a[^>]+class="[^"]*stui-vodlist__thumb[^"]*"[^>]+data-original="([^"]+)"', html)
            if m:
                vod['vod_pic'] = m.group(1)
            
            # 简介/剧情
            m = re.search(r'<span class="detail-content"[^>]*>([^<]+)', html)
            if not m:
                m = re.search(r'<span class="detail-sketch"[^>]*>([^<]+)', html)
            if m:
                vod['vod_content'] = m.group(1).strip()[:500]
            
            # 播放源和集数
            play_from = []
            play_url_list = []
            
            # 先统计有多少条线路（查看 dropdown-menu 中的 li 数量）
            line_count = len(re.findall(r'<li><a href="javascript:;">线路\d+</a></li>', html))
            
            if line_count == 0:
                line_count = 1
            
            # 提取每个 tab-pane 中的集数
            # 格式: <div class="tab-pane fade in clearfix"><ul class="stui-content__playlist">
            tab_pattern = r'<div class="tab-pane[^"]*"[^>]*>.*?<ul class="stui-content__playlist[^"]*">(.*?)</ul>'
            tabs = re.findall(tab_pattern, html, re.DOTALL)
            
            if tabs:
                for i, tab_content in enumerate(tabs):
                    play_from.append(f'线路{i+1}')
                    # 提取该线路的所有集数
                    episodes = re.findall(r'<a[^>]+href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/(\d+)\.html)"[^>]*>([^<]+)</a>', tab_content)
                    if episodes:
                        # 按集数排序
                        episodes_sorted = sorted(episodes, key=lambda x: int(x[1]))
                        ep_list = []
                        for href, nid, name in episodes_sorted:
                            full_url = self.host + href
                            ep_list.append(f"{name}${full_url}")
                        play_url_list.append('#'.join(ep_list))
                    else:
                        play_url_list.append('')
            else:
                # 备用：只有一个播放链接的情况
                m = re.search(r'<a[^>]+href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>立即播放</a>', html)
                if m:
                    play_from = ['线路1']
                    play_url_list.append(f"立即播放${self.host + m.group(1)}")
            
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
            url = f'{self.host}/index.php/vod/search.html?wd={quote(key)}&page={pg}'
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
            
            # 提取 player_aaaa 配置
            m = re.search(r'var player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
            if m:
                player_data_str = m.group(1)
                
                # 提取关键字段
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', player_data_str)
                encrypt_match = re.search(r'"encrypt"\s*:\s*(\d+)', player_data_str)
                
                if url_match:
                    video_url = url_match.group(1)
                    encrypt = int(encrypt_match.group(1)) if encrypt_match else 0
                    
                    # 简单 URL 解码（处理转义的斜杠等）
                    video_url = video_url.replace('\\/', '/')
                    
                    if encrypt == 0:
                        # URL 未加密，直接返回
                        result['parse'] = 0
                        result['url'] = video_url
                        return result
                    elif encrypt == 1:
                        # URL 编码
                        from urllib.parse import unquote
                        result['parse'] = 0
                        result['url'] = unquote(video_url)
                        return result
                    elif encrypt == 2:
                        # Base64 编码
                        import base64
                        try:
                            decoded = base64.b64decode(video_url).decode('utf-8')
                            result['parse'] = 0
                            result['url'] = decoded
                            return result
                        except:
                            pass
            
            # 备用：查找 iframe
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
            
            # 备用：查找 m3u8 直接链接
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
        
        # 匹配视频列表项 - 多种可能的格式
        # 格式1: <a class="..." href="..." title="..." data-original="...">
        # 先查找所有包含 detail/id 的链接及其周围上下文
        pattern = r'<a[^>]+class="[^"]*stui-vodlist__thumb[^"]*"[^>]+>'
        
        for m in re.finditer(pattern, html):
            link_html = m.group(0)
            
            # 提取链接
            href_m = re.search(r'href="(/index\.php/vod/detail/id/\d+\.html)"', link_html)
            title_m = re.search(r'title="([^"]+)"', link_html)
            pic_m = re.search(r'data-original="([^"]+)"', link_html)
            
            if not href_m or not title_m:
                continue
            
            href = href_m.group(1)
            title = title_m.group(1)
            
            # 提取 ID
            m2 = re.search(r'/detail/id/(\d+)\.html', href)
            if not m2:
                continue
            vid = m2.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            
            pic = pic_m.group(1) if pic_m else ''
            remark = ''
            
            # 在链接附近查找备注
            start = max(0, m.start() - 200)
            end = min(len(html), m.end() + 200)
            context = html[start:end]
            
            # 备注（如：HD中字、已完结等）
            remark_m = re.search(r'<span class="[^"]*pic-text[^"]*"[^>]*>([^<]+)</span>', context)
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
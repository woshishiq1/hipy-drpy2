# -*- coding: utf-8 -*-
# 🌈 Love 
import json
import random
import re
import sys
import time
from base64 import b64decode, b64encode
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    """51吸瓜视频爬虫"""
    
    # 常量定义
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }
    
    DYNAMIC_HOSTS = [
        'https://artist.vgwtswi.xyz',
        'https://ability.vgwtswi.xyz', 
        'https://51chiguada.com', 
        'https://am.vgwtswi.xyz'
    ]
    
    CATEGORY_SELECTORS = [
        '.category-list ul li',
        '.nav-menu li',
        '.menu li',
        'nav ul li'
    ]
    
    AES_KEY = b'f5d965df75336270'
    AES_IV = b'97b60394abc2fbe1'
    
    def init(self, extend: str = "") -> None:
        """初始化爬虫"""
        self.proxies = json.loads(extend) if extend else {}
        self.headers = self.DEFAULT_HEADERS.copy()
        self.host = self._get_working_host()
        self.headers.update({
            'Origin': self.host, 
            'Referer': f"{self.host}/"
        })
        self.log(f"使用站点: {self.host}")
    
    def getName(self) -> str:
        return "🌈 51吸瓜"
    
    def isVideoFormat(self, url: str) -> bool:
        """检查是否为视频格式"""
        video_exts = ['.m3u8', '.mp4', '.ts']
        return any(ext in (url or '') for ext in video_exts)
    
    def manualVideoCheck(self) -> bool:
        return False
    
    def destroy(self) -> None:
        pass
    
    def homeContent(self, filter: Any) -> Dict:
        """获取首页内容"""
        try:
            response = self._safe_request(self.host)
            if not response:
                return {'class': [], 'list': []}
            
            data = self.getpq(response.text)
            
            return {
                'class': self._get_categories(data),
                'list': self._get_video_list(data('#index article a'))
            }
            
        except Exception as e:
            self.log(f"homeContent error: {e}")
            return {'class': [], 'list': []}
    
    def homeVideoContent(self) -> Dict:
        """获取首页视频内容"""
        try:
            response = self._safe_request(self.host)
            if not response:
                return {'list': []}
            
            data = self.getpq(response.text)
            selectors = '#index article a, #archive article a'
            return {'list': self._get_video_list(data(selectors))}
            
        except Exception as e:
            self.log(f"homeVideoContent error: {e}")
            return {'list': []}
    
    def categoryContent(self, tid: str, pg: str, filter: Any, extend: str) -> Dict:
        """获取分类内容"""
        try:
            if '@folder' in tid:
                videos = self._get_folder_content(tid.replace('@folder', ''))
                pagecount = 1
            else:
                url = self._build_category_url(tid, pg)
                response = self._safe_request(url)
                if not response:
                    return self._empty_category_result(pg)
                
                data = self.getpq(response.text)
                videos = self._get_video_list(data('#archive article a, #index article a'), tid)
                pagecount = 99999
            
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 90,
                'total': 999999
            }
            
        except Exception as e:
            self.log(f"categoryContent error: {e}")
            return self._empty_category_result(pg)
    
    def detailContent(self, ids: List[str]) -> Dict:
        """获取详情内容"""
        try:
            url = ids[0] if ids[0].startswith('http') else f"{self.host}{ids[0]}"
            response = self._safe_request(url)
            
            if not response:
                return {'list': [self._create_error_vod('页面加载失败', url)]}
            
            data = self.getpq(response.text)
            vod = self._parse_detail(data, url)
            return {'list': [vod]}
            
        except Exception as e:
            self.log(f"detailContent error: {e}")
            return {'list': [self._create_error_vod('详情页加载失败', ids[0] if ids else '')]}
    
    def searchContent(self, key: str, quick: bool, pg: str = "1") -> Dict:
        """搜索内容"""
        try:
            url = f"{self.host}/search/{key}/" if pg == "1" else f"{self.host}/search/{key}/{pg}"
            response = self._safe_request(url)
            
            if not response:
                return {'list': [], 'page': pg}
            
            data = self.getpq(response.text)
            videos = self._get_video_list(data('#archive article a, #index article a'))
            return {'list': videos, 'page': pg}
            
        except Exception as e:
            self.log(f"searchContent error: {e}")
            return {'list': [], 'page': pg}
    
    def playerContent(self, flag: str, id: str, vipFlags: Any) -> Dict:
        """获取播放内容"""
        url = id
        parse_type = 0 if self.isVideoFormat(url) else 1
        
        if '.m3u8' in url:
            url = self.proxy(url)
        
        self.log(f"播放请求: parse={parse_type}, url={url}")
        return {'parse': parse_type, 'url': url, 'header': self.headers}
    
    def localProxy(self, param: Dict) -> List:
        """本地代理"""
        proxy_type = param.get('type')
        
        if proxy_type == 'img':
            return self._proxy_image(param['url'])
        elif proxy_type == 'm3u8':
            return self.m3Proxy(param['url'])
        else:
            return self.tsProxy(param['url'])
    
    def proxy(self, data: str, type: str = 'm3u8') -> str:
        """生成代理URL"""
        if data and self.proxies:
            return f"{self.getProxyUrl()}&url={self.e64(data)}&type={type}"
        return data
    
    def m3Proxy(self, url: str) -> List:
        """M3U8代理"""
        url = self.d64(url)
        ydata = requests.get(url, headers=self.headers, proxies=self.proxies, allow_redirects=False)
        data = ydata.text
        
        if ydata.headers.get('Location'):
            url = ydata.headers['Location']
            data = requests.get(url, headers=self.headers, proxies=self.proxies).text
        
        lines = data.strip().split('\n')
        last_r = url[:url.rfind('/')]
        parsed_url = urlparse(url)
        durl = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        processed_lines = self._process_m3u8_lines(lines, last_r, durl)
        return [200, "application/vnd.apple.mpegur", '\n'.join(processed_lines)]
    
    def tsProxy(self, url: str) -> List:
        """TS代理"""
        url = self.d64(url)
        response = requests.get(url, headers=self.headers, proxies=self.proxies, stream=True)
        return [200, response.headers.get('Content-Type', 'video/MP2T'), response.content]
    
    def e64(self, text: str) -> str:
        """Base64编码"""
        try:
            return b64encode(text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            self.log(f"Base64编码错误: {e}")
            return ""
    
    def d64(self, encoded_text: str) -> str:
        """Base64解码"""
        try:
            return b64decode(encoded_text).decode('utf-8')
        except Exception as e:
            self.log(f"Base64解码错误: {e}")
            return ""
    
    def getpq(self, data: str) -> pq:
        """获取PyQuery对象"""
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))
    
    # ==================== 私有方法 ====================
    
    def _safe_request(self, url: str, timeout: int = 15) -> Optional[requests.Response]:
        """安全的请求方法"""
        try:
            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=timeout)
            if response.status_code == 200:
                return response
            return None
        except Exception as e:
            self.log(f"请求失败 {url}: {e}")
            return None
    
    def _get_working_host(self) -> str:
        """获取可用的站点"""
        for url in self.DYNAMIC_HOSTS:
            try:
                response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=10)
                if response.status_code == 200:
                    data = self.getpq(response.text)
                    if len(data('#index article a')) > 0:
                        self.log(f"选用可用站点: {url}")
                        return url
            except Exception:
                continue
        
        fallback = self.DYNAMIC_HOSTS[0]
        self.log(f"未检测到可用站点，回退: {fallback}")
        return fallback
    
    def _get_categories(self, data: pq) -> List[Dict]:
        """获取分类列表"""
        categories = []
        
        for selector in self.CATEGORY_SELECTORS:
            for item in data(selector).items():
                link = item('a')
                href = (link.attr('href') or '').strip()
                name = (link.text() or '').strip()
                
                if href and href != '#' and name:
                    categories.append({
                        'type_name': name,
                        'type_id': href
                    })
            
            if categories:
                break
        
        if not categories:
            categories = [
                {'type_name': '首页', 'type_id': '/'},
                {'type_name': '最新', 'type_id': '/latest/'},
                {'type_name': '热门', 'type_id': '/hot/'}
            ]
        
        return categories
    
    def _get_video_list(self, data: pq, tid: str = '') -> List[Dict]:
        """获取视频列表"""
        videos = []
        is_folder = '/mrdg' in tid
        
        for item in data.items():
            href = item.attr('href')
            title = item('h2').text()
            date = item('span[itemprop="datePublished"]').text() or \
                   item('.post-meta, .entry-meta, time').text()
            
            if href and title:
                videos.append({
                    'vod_id': f"{href}{'@folder' if is_folder else ''}",
                    'vod_name': title.replace('\n', ' '),
                    'vod_pic': self._get_image_url(item('script').text()),
                    'vod_remarks': date or '',
                    'vod_tag': 'folder' if is_folder else '',
                    'style': {"type": "rect", "ratio": 1.33}
                })
        
        return videos
    
    def _get_image_url(self, script_text: str) -> str:
        """获取图片URL"""
        match = re.search(r"loadBannerDirect\('([^']+)'", script_text)
        if match:
            return f"{self.getProxyUrl()}&url={match.group(1)}&type=img"
        return ''
    
    def _get_folder_content(self, folder_id: str) -> List[Dict]:
        """获取文件夹内容"""
        url = f"{self.host}{folder_id}"
        response = requests.get(url, headers=self.headers, proxies=self.proxies)
        data = self.getpq(response.text)
        
        vdata = data('.post-content[itemprop="articleBody"]')
        remove_selectors = ['.txt-apps', '.line', 'blockquote', '.tags', '.content-tabs']
        for selector in remove_selectors:
            vdata.remove(selector)
        
        paragraphs = vdata('p')
        videos = []
        
        for i, heading in enumerate(vdata('h2').items()):
            idx = i * 2
            videos.append({
                'vod_id': paragraphs.eq(idx)('a').attr('href'),
                'vod_name': paragraphs.eq(idx).text(),
                'vod_pic': f"{self.getProxyUrl()}&url={paragraphs.eq(idx+1)('img').attr('data-xkrkllgl')}&type=img",
                'vod_remarks': heading.text()
            })
        
        return videos
    
    def _parse_detail(self, data: pq, url: str) -> Dict:
        """解析详情页"""
        vod = {'vod_play_from': '51吸瓜'}
        
        # 解析内容
        vod['vod_content'] = self._parse_content(data) or '51吸瓜视频'
        
        # 解析播放列表
        play_url = self._parse_play_url(data, url)
        vod['vod_play_url'] = play_url or f"未找到视频源${url}"
        
        return vod
    
    def _parse_content(self, data: pq) -> str:
        """解析内容描述"""
        try:
            tags = data('.tags .keywords a')
            if tags:
                content_parts = []
                for tag in tags.items():
                    title = tag.text()
                    href = tag.attr('href')
                    if title and href:
                        tag_data = json.dumps({'id': href, 'name': title})
                        content_parts.append(f'[a=cr:{tag_data}/]{title}[/a]')
                return ' '.join(content_parts)
        except Exception:
            pass
        
        return data('.post-title').text()
    
    def _parse_play_url(self, data: pq, url: str) -> str:
        """解析播放URL"""
        try:
            players = data('.dplayer')
            if not players:
                return f"未找到视频源${url}"
            
            play_list = []
            used_names = set()
            
            for idx, player in enumerate(players.items(), start=1):
                config_attr = player.attr('data-config')
                if not config_attr:
                    continue
                
                try:
                    config = json.loads(config_attr)
                    video_url = config.get('video', {}).get('url', '')
                    if not video_url:
                        continue
                    
                    name = self._get_episode_name(player, idx, used_names)
                    used_names.add(name)
                    play_list.append(f"{name}${video_url}")
                    
                except Exception:
                    continue
            
            if play_list:
                self.log(f"拼装播放列表，共{len(play_list)}个")
                return '#'.join(play_list)
            
            return f"未找到视频源${url}"
            
        except Exception as e:
            self.log(f"解析播放URL失败: {e}")
            return f"视频解析失败${url}"
    
    def _get_episode_name(self, player: pq, idx: int, used_names: set) -> str:
        """获取剧集名称"""
        try:
            parent = player.parents().eq(0)
            for _ in range(3):
                if not parent:
                    break
                heading = parent.find('h2, h3, h4').eq(0).text().strip()
                if heading:
                    base_name = heading
                    break
                parent = parent.parents().eq(0)
            else:
                base_name = f"视频{idx}"
        except Exception:
            base_name = f"视频{idx}"
        
        # 确保名称唯一
        name = base_name
        count = 2
        while name in used_names:
            name = f"{base_name} {count}"
            count += 1
        
        return name
    
    def _process_m3u8_lines(self, lines: List[str], last_r: str, durl: str) -> List[str]:
        """处理M3U8行"""
        processed = []
        is_key = True
        
        for line in lines:
            # 处理密钥URI
            if is_key and 'URI' in line:
                pattern = r'URI="([^"]*)"'
                match = re.search(pattern, line)
                if match:
                    new_line = re.sub(pattern, f'URI="{self.proxy(match.group(1), "mkey")}"', line)
                    processed.append(new_line)
                    is_key = False
                    continue
            
            # 处理视频片段
            if '#EXT' not in line:
                if 'http' not in line:
                    domain = last_r if line.count('/') < 2 else durl
                    line = domain + ('' if line.startswith('/') else '/') + line
                line = self.proxy(line, line.split('.')[-1].split('?')[0])
            
            processed.append(line)
        
        return processed
    
    def _proxy_image(self, url: str) -> List:
        """代理图片"""
        response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=10)
        decrypted = self.aesimg(response.content)
        return [200, response.headers.get('Content-Type'), decrypted]
    
    def aesimg(self, data: bytes) -> bytes:
        """AES解密图片"""
        cipher = AES.new(self.AES_KEY, AES.MODE_CBC, self.AES_IV)
        return unpad(cipher.decrypt(data), AES.block_size)
    
    def _build_category_url(self, tid: str, pg: str) -> str:
        """构建分类URL"""
        if tid.startswith('/'):
            return f"{self.host}{tid}page/{pg}/" if pg != '1' else f"{self.host}{tid}"
        return f"{self.host}/{tid}"
    
    def _empty_category_result(self, pg: str) -> Dict:
        """返回空分类结果"""
        return {
            'list': [],
            'page': pg,
            'pagecount': 1,
            'limit': 90,
            'total': 0
        }
    
    def _create_error_vod(self, error_msg: str, url: str) -> Dict:
        """创建错误视频对象"""
        return {
            'vod_play_from': '51吸瓜',
            'vod_play_url': f"{error_msg}${url}"
        }
    
    def log(self, message: str) -> None:
        """日志输出"""
        print(f"[51吸瓜] {message}")

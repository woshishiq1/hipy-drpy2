# -*- coding: utf-8 -*-
import json
import re
import sys
from urllib.parse import urlparse, quote

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider

PAGE_SIZE = 90


class Spider(Spider):

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.proxies = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                self.proxies = json.loads(extend)
            except Exception:
                self.proxies = {}
        else:
            self.proxies = {}

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        # 取得可用站點（若動態站點不可用，則自動回退至 51cg1.com）
        self.host = self.get_working_host()
        self.headers.update({'Origin': self.host, 'Referer': f"{self.host}/"})

    def getName(self):
        return "🌈 51吸瓜"

    def isVideoFormat(self, url):
        path = urlparse(str(url or '')).path.lower()
        return any(path.endswith(ext) for ext in ['.m3u8', '.mp4', '.ts', '.flv', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self.proxies = {}

    def homeContent(self, filter):
        try:
            response = requests.get(self.host, headers=self.headers, proxies=self.proxies, timeout=10)
            if response.status_code != 200:
                return {'class': [], 'list': []}
                
            data = self.getpq(response.text)
            classes = []
            
            category_selectors = [
                '.category-list ul li',
                '.nav-menu li',
                '.menu li',
                'nav ul li'
            ]
            
            for selector in category_selectors:
                for k in data(selector).items():
                    link = k('a')
                    href = (link.attr('href') or '').strip()
                    name = (link.text() or '').strip()
                    if not href or href == '#' or not name:
                        continue
                    classes.append({
                        'type_name': name,
                        'type_id': href
                    })
                if classes:
                    break
            
            if not classes:
                classes = [
                    {'type_name': '最新', 'type_id': '/latest/'},
                    {'type_name': '热门', 'type_id': '/hot/'}
                ]
            
            return {
                'class': classes,
                'list': self.getlist(data('#index article a'))
            }
        except Exception:
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        try:
            response = requests.get(self.host, headers=self.headers, proxies=self.proxies, timeout=10)
            if response.status_code != 200:
                return {'list': []}
            data = self.getpq(response.text)
            return {'list': self.getlist(data('#index article a, #archive article a'))}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page_num = max(1, int(pg)) if str(pg).isdigit() else 1
            
            if '@folder' in tid:
                folder_id = tid.replace('@folder', '')
                videos = self.getfod(folder_id)
                return {
                    'list': videos,
                    'page': page_num,
                    'pagecount': 1,
                    'limit': len(videos) or PAGE_SIZE,
                    'total': len(videos)
                }
            
            base_url = f"{self.host}{tid}" if tid.startswith('/') else f"{self.host}/{tid}"
            base_url = base_url.rstrip('/')
            
            url = f"{base_url}/{page_num}/" if page_num > 1 else f"{base_url}/"

            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=12)
            if response.status_code != 200:
                return {'list': [], 'page': page_num, 'pagecount': 1, 'limit': PAGE_SIZE, 'total': 0}
                
            data = self.getpq(response.text)
            videos = self.getlist(data('#archive article a, #index article a'), tid)
            
            pagecount = 1
            try:
                pagination_selectors = ['.pagination', '.page-nav', '.pager', '.nav-links', '.pages']
                for selector in pagination_selectors:
                    pagination = data(selector)
                    if pagination:
                        page_numbers = [
                            int(link.text().strip()) 
                            for link in pagination.find('a').items() 
                            if link.text().strip().isdigit()
                        ]
                        if page_numbers:
                            pagecount = max(page_numbers)
                            break
                
                if pagecount == 1 and data('a:contains("下一页"), a:contains("Next")'):
                    pagecount = page_num + 1
            except Exception:
                pagecount = page_num
                
            return {
                'list': videos,
                'page': page_num,
                'pagecount': max(1, pagecount),
                'limit': PAGE_SIZE,
                'total': max(len(videos), page_num * PAGE_SIZE)
            }
        except Exception:
            return {'list': [], 'page': max(1, int(pg) if str(pg).isdigit() else 1), 'pagecount': 1, 'limit': PAGE_SIZE, 'total': 0}

    def detailContent(self, ids):
        try:
            if not ids or not ids[0]:
                return {'list': [], 'msg': '無效的影片 ID'}

            req_id = ids[0]
            url = req_id if req_id.startswith('http') else f"{self.host}{req_id}"
            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=12)
            
            if response.status_code != 200:
                return {'list': [], 'msg': '頁面加載失敗'}
                
            data = self.getpq(response.text)
            vod = {
                'vod_id': req_id,
                'vod_name': self._safe_label(data('.post-title').text() or '51吸瓜视频'),
                'vod_play_from': '51吸瓜'
            }
            
            try:
                clist = []
                if data('.tags .keywords a'):
                    for k in data('.tags .keywords a').items():
                        title = k.text().strip()
                        href = k.attr('href')
                        if title and href:
                            payload = json.dumps({'id': href, 'name': title, 'type_flag': '1'}, ensure_ascii=False)
                            clist.append(f"[a=cr:{payload}/]{title}[/a]")
                vod['vod_content'] = ' '.join(clist) if clist else (data('.post-title').text() or '')
            except Exception:
                vod['vod_content'] = data('.post-title').text() or ''
            
            plist = []
            used_names = set()
            if data('.dplayer'):
                for c, k in enumerate(data('.dplayer').items(), start=1):
                    config_attr = k.attr('data-config')
                    if not config_attr:
                        continue
                    try:
                        config = json.loads(config_attr)
                        video_url = config.get('video', {}).get('url', '')
                        if not video_url:
                            continue

                        ep_name = ''
                        try:
                            parent = k.parents().eq(0)
                            for _ in range(3):
                                if not parent: break
                                heading = parent.find('h2, h3, h4').eq(0).text() or ''
                                heading = heading.strip()
                                if heading:
                                    ep_name = heading
                                    break
                                parent = parent.parents().eq(0)
                        except Exception:
                            ep_name = ''

                        base_name = ep_name if ep_name else f"视频{c}"
                        name = base_name
                        count = 2
                        while name in used_names:
                            name = f"{base_name} {count}"
                            count += 1
                        used_names.add(name)
                        
                        safe_ep_name = self._safe_label(name)
                        plist.append(f"{safe_ep_name}${video_url}")
                    except Exception:
                        continue
            
            if plist:
                vod['vod_play_url'] = '#'.join(plist)
            else:
                return {'list': [], 'msg': '未找到有效視頻源'}
                    
            return {'list': [vod]}
        except Exception as e:
            return {'list': [], 'msg': f'詳情頁加載失敗: {type(e).__name__}'}

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(pg)) if str(pg).isdigit() else 1
            url = f"{self.host}/search/{quote(key)}/{page_num}/" if page_num > 1 else f"{self.host}/search/{quote(key)}/"
            
            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=12)
            if response.status_code != 200:
                return {'list': [], 'page': page_num, 'pagecount': 1, 'limit': PAGE_SIZE, 'total': 0}
                
            data = self.getpq(response.text)
            videos = self.getlist(data('#archive article a, #index article a'))
            
            pagecount = 1
            try:
                pagination_selectors = ['.pagination', '.page-nav', '.pager', '.nav-links', '.pages']
                for selector in pagination_selectors:
                    pagination = data(selector)
                    if pagination:
                        page_numbers = [
                            int(link.text().strip()) 
                            for link in pagination.find('a').items() 
                            if link.text().strip().isdigit()
                        ]
                        if page_numbers:
                            pagecount = max(page_numbers)
                            break
            except Exception:
                pagecount = page_num
                
            return {
                'list': videos,
                'page': page_num,
                'pagecount': max(1, pagecount),
                'limit': PAGE_SIZE,
                'total': max(len(videos), page_num * PAGE_SIZE)
            }
        except Exception:
            return {'list': [], 'page': max(1, int(pg) if str(pg).isdigit() else 1), 'pagecount': 1, 'limit': PAGE_SIZE, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '').strip()
        if not url:
            return {'parse': 0, 'msg': '無效的播放網址'}
            
        parse = 0 if self.isVideoFormat(url) else 1
        
        if parse == 0 and '.m3u8' in url and self.proxies:
            url = self.proxy(url)

        return {
            'parse': parse,
            'url': url,
            'header': self.headers
        }

    def localProxy(self, param):
        req_type = param.get('type')
        if req_type == 'img':
            res = requests.get(param['url'], headers=self.headers, proxies=self.proxies, timeout=10)
            return [200, res.headers.get('Content-Type', 'image/jpeg'), self.aesimg(res.content)]
        elif req_type == 'm3u8':
            return self.m3Proxy(param['url'])
        else:
            return self.tsProxy(param['url'])

    def proxy(self, data, type='m3u8'):
        if data and self.proxies:
            return f"{self.getProxyUrl()}&url={self.e64(data)}&type={type}"
        return data

    def m3Proxy(self, url):
        url = self.d64(url)
        ydata = requests.get(url, headers=self.headers, proxies=self.proxies, allow_redirects=False)
        data = ydata.content.decode('utf-8', errors='ignore')
        if ydata.headers.get('Location'):
            url = ydata.headers['Location']
            data = requests.get(url, headers=self.headers, proxies=self.proxies).content.decode('utf-8', errors='ignore')
        lines = data.strip().split('\n')
        last_r = url[:url.rfind('/')]
        parsed_url = urlparse(url)
        durl = f"{parsed_url.scheme}://{parsed_url.netloc}"
        iskey = True
        for index, string in enumerate(lines):
            if iskey and 'URI' in string:
                pattern = r'URI="([^"]*)"'
                match = re.search(pattern, string)
                if match:
                    lines[index] = re.sub(pattern, f'URI="{self.proxy(match.group(1), "mkey")}"', string)
                    iskey = False
                    continue
            if '#EXT' not in string:
                if 'http' not in string:
                    domain = last_r if string.count('/') < 2 else durl
                    string = domain + ('' if string.startswith('/') else '/') + string
                lines[index] = self.proxy(string, string.split('.')[-1].split('?')[0])
        data = '\n'.join(lines)
        return [200, "application/vnd.apple.mpegurl", data]

    def tsProxy(self, url):
        url = self.d64(url)
        data = requests.get(url, headers=self.headers, proxies=self.proxies, stream=True)
        return [200, data.headers.get('Content-Type', 'video/MP2T'), data.content]

    @staticmethod
    def _safe_label(value):
        """清理標籤文字，避免破壞 Fongmi 播放分隔符 $ 與 #"""
        return str(value or '').replace('$', '＄').replace('#', '＃').strip()

    def get_working_host(self):
        """動態站點測試：若均不可用，直接使用 51cg1.com"""
        dynamic_urls = [
            'https://artist.vgwtswi.xyz',
            'https://ability.vgwtswi.xyz', 
            'https://am.vgwtswi.xyz'
        ]
        
        # 設定較短的 timeout(3秒)，避免 TV 端因超時卡死
        for url in dynamic_urls:
            try:
                response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=3)
                if response.status_code == 200:
                    data = self.getpq(response.text)
                    if len(data('#index article a')) > 0:
                        return url
            except Exception:
                continue
        
        # 動態站點全部連不上時，回退使用固定主站
        return "https://51cg1.com"

    def getlist(self, data, tid=''):
        videos = []
        is_folder = '/mrdg' in tid
        for k in data.items():
            a = k.attr('href')
            b = k('h2').text()
            c = k('span[itemprop="datePublished"]').text() or k('.post-meta, .entry-meta, time').text()
            if a and b:
                item = {
                    'vod_id': f"{a}{'@folder' if is_folder else ''}",
                    'vod_name': self._safe_label(b.replace('\n', ' ')),
                    'vod_pic': self.getimg(k('script').text()),
                    'vod_remarks': self._safe_label(c),
                    'style': {"type": "rect", "ratio": 1.33}
                }
                if is_folder:
                    item['vod_tag'] = 'folder'
                videos.append(item)
        return videos

    def getfod(self, folder_id):
        url = f"{self.host}{folder_id}"
        response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=12)
        if response.status_code != 200:
            return []
            
        data = self.getpq(response.text)
        vdata = data('.post-content[itemprop="articleBody"]')
        for i in ['.txt-apps', '.line', 'blockquote', '.tags', '.content-tabs']:
            vdata.remove(i)
            
        p = vdata('p')
        videos = []
        for i, x in enumerate(vdata('h2').items()):
            c = i * 2
            pic_raw = p.eq(c + 1)('img').attr('data-xkrkllgl')
            pic_url = f"{self.getProxyUrl()}&url={pic_raw}&type=img" if pic_raw else ""
            videos.append({
                'vod_id': p.eq(c)('a').attr('href') or '',
                'vod_name': self._safe_label(p.eq(c).text()),
                'vod_pic': pic_url,
                'vod_remarks': self._safe_label(x.text())
            })
        return videos

    def getimg(self, text):
        match = re.search(r"loadBannerDirect\('([^']+)'", text)
        if match:
            url = match.group(1)
            return f"{self.getProxyUrl()}&url={url}&type=img"
        return ''

    def aesimg(self, word):
        try:
            key = b'f5d965df75336270'
            iv = b'97b60394abc2fbe1'
            cipher = AES.new(key, AES.MODE_CBC, iv)
            return unpad(cipher.decrypt(word), AES.block_size)
        except Exception:
            return word

    def getpq(self, data):
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))
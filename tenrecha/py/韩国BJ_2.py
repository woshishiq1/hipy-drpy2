# -*- coding: utf-8 -*-
import json
import sys
import re
import urllib3
from pyquery import PyQuery as pq
import requests
import concurrent.futures
from urllib.parse import urljoin, urlparse

sys.path.append('..')
from base.spider import Spider

# 禁用 SSL 警告，避免日志刷屏
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider(Spider):
    def getName(self):
        return "韩国BJ"

    def init(self, extend=""):
        print("============Korean BJ Spider============")
        pass

    def homeContent(self, filter):
        result = {}
        cateManual = {
            "最新视频": "latest"
        }
        classes = []
        for k in cateManual:
            classes.append({
                'type_name': k,
                'type_id': cateManual[k]
            })

        result['class'] = classes
        return result

    def homeVideoContent(self):
        result = self.videosContent(self.home + "/")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        if tid == "latest":
            url = self.home + "/" if pg == 1 else self.home + "/?page={0}".format(pg)
            result = self.videosContent(url)
        elif tid == "tags":
            url = self.home + "/"
            rsp = self._fetch(url)
            root = pq(rsp.text)
            videos = []
            tag_elems = root('a[href*="/tags/"]')
            for tag in tag_elems.items():
                href = tag.attr('href')
                if href and href.startswith('/tags/'):
                    tag_name = tag.text().strip()
                    if tag_name:
                        video = {
                            "vod_id": href.split('/')[-1],
                            "vod_name": tag_name,
                            "vod_pic": "",
                            "vod_remarks": ""
                        }
                        videos.append(video)
            result['list'] = videos[:90]
            result['page'] = pg
            result['pagecount'] = 1
            result['limit'] = len(videos)
            result['total'] = len(videos)
        return result

    def detailContent(self, array):
        tid = array[0]
        url = self.home + "/posts/" + tid
        rsp = self._fetch(url)
        root = pq(rsp.text)
        
        vod = {
            "vod_id": tid,
            "vod_name": "",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": ""
        }
        
        title_elem = root('h1')
        if title_elem:
            vod['vod_name'] = title_elem.text().strip()
        else:
            title_elem = root('h1.font-bold')
            if title_elem:
                vod['vod_name'] = title_elem.text().strip()
        
        img_elem = root('meta[property="og:image"]')
        if img_elem:
            vod['vod_pic'] = img_elem.attr('content')
        else:
            img_elem = root('script[type="application/ld+json"]')
            if img_elem:
                try:
                    json_data = json.loads(img_elem.text())
                    if 'thumbnailUrl' in json_data:
                        vod['vod_pic'] = json_data['thumbnailUrl']
                except:
                    pass
        
        date_elem = root('time')
        if date_elem:
            vod['vod_remarks'] = date_elem.attr('datetime')
        
        play_url = ""
        
        json_ld_elem = root('script[type="application/ld+json"]')
        if json_ld_elem:
            try:
                json_data = json.loads(json_ld_elem.text())
                if 'embedUrl' in json_data:
                    play_url = json_data['embedUrl']
            except:
                pass
        
        if not play_url:
            iframe_elem = root('#players iframe')
            if iframe_elem:
                play_url = iframe_elem.attr('src')
        
        if not play_url:
            script_content = rsp.text
            filemoon_match = re.search(r'filemoon\.to/e/([a-zA-Z0-9]+)', script_content)
            if filemoon_match:
                play_url = f"https://filemoon.to/e/{filemoon_match.group(1)}"
        
        tags = []
        tag_elems = root('a[href*="/tags/"]')
        for tag in tag_elems.items():
            if tag.attr('href').startswith('/tags/'):
                tags.append(tag.text().strip())
        
        if tags:
            vod['vod_actor'] = ','.join(tags)
        
        if play_url:
            vod['vod_play_from'] = 'KBJ视频'
            vod['vod_play_url'] = f"第1集${play_url}"
        
        return {'list': [vod]}

    def searchContent(self, key, quick, pg=1):
        result = {}
        url = self.home + f"/?kw={key}" if pg == 1 else self.home + f"/?kw={key}&page={pg}"
        result = self.videosContent(url)
        result['page'] = pg
        return result

    # ===================== 核心修复：重写 playerContent =====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "playUrl": "", "url": id}
        
        # 空值保护
        if not id:
            return result
        
        m3u8_urls = []
        
        # 1. 如果是 Filemoon 链接（支持变体域名），优先走官方 API 取直链
        if 'filemoon' in id.lower():
            m3u8_urls = self._filemoon_api(id)
        
        # 2. 如果 API 没拿到，且不是直链，尝试递归解析页面里的 iframe/filemoon
        if not m3u8_urls and not id.endswith('.m3u8'):
            m3u8_urls = self._resolve_playurl(id)
        
        # 3. 成功拿到 m3u8，改为直链模式(parse=0)，播放器直接播放
        if m3u8_urls:
            result["parse"] = 0
            result["playUrl"] = '$'.join(m3u8_urls)
            result["url"] = m3u8_urls[0]  # 直链模式下 url 通常放主链接
            result["header"] = {
                "User-Agent": self.UA,
                "Referer": "https://filemoon.to/"
            }
            return result
        
        # 4. 最终 Fallback：启用嗅探，但把快速嗅探到的链接带上
        sniff_urls = self._fast_sniff_m3u8(id)
        if sniff_urls:
            result["playUrl"] = '$'.join(sniff_urls)
            result["header"] = {
                "User-Agent": self.UA,
                "Referer": id
            }
        
        return result

    # ===================== 修复：Filemoon API 直链提取 =====================
    def _filemoon_api(self, filemoon_url):
        """
        Filemoon 官方 API：POST /api/source/{file_id}
        支持 filemoon.to / filemoon.sx 等变体域名
        """
        try:
            parsed = urlparse(filemoon_url)
            file_id = parsed.path.rstrip('/').split('/')[-1]
            if not file_id or not re.match(r'^[a-zA-Z0-9]+$', file_id):
                return []
            
            domain = f"{parsed.scheme}://{parsed.netloc}"
            api = f'{domain}/api/source/{file_id}'
            
            headers = {
                'User-Agent': self.UA,
                'Referer': filemoon_url,
                'Origin': domain,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            resp = requests.post(api, headers=headers, timeout=8, verify=False)
            j = resp.json()
            
            # 兼容多种可能的返回结构
            data = j.get('data') or j.get('result') or []
            if not isinstance(data, list):
                data = [data] if data else []
            
            m3u8_list = []
            for item in data:
                if isinstance(item, dict):
                    file_url = item.get('file', '')
                    if file_url and '.m3u8' in file_url:
                        m3u8_list.append(file_url)
            
            return m3u8_list
        except Exception as e:
            print('filemoon api err:', e)
            return []

    # ===================== 修复：递归解析 iframe / 嵌套页面 =====================
    def _resolve_playurl(self, page_url):
        """
        解析页面，寻找 Filemoon 直链或 iframe，递归解析
        同时支持 streamtape、 dood 等常见备用源（可选扩展）
        """
        seen = set()
        q = [page_url]
        m3u8 = []
        
        while q and not m3u8:
            url = q.pop(0)  # 用队列保证广度优先
            if url in seen:
                continue
            seen.add(url)
            
            try:
                html = requests.get(url, headers={'User-Agent': self.UA}, timeout=6, verify=False).text
            except Exception as e:
                print(f'resolve fetch err: {e}')
                continue
            
            # a) 直接找 filemoon 地址（放宽域名匹配）
            fm_pattern = r'https?://[^"\s<>]*filemoon[^"\s<>]*(?:\.[a-z]+)+/(?:e|embed)/[a-zA-Z0-9]+'
            fm_match = re.search(fm_pattern, html)
            if fm_match:
                m3u8 = self._filemoon_api(fm_match.group())
                if m3u8:
                    break
            
            # b) 找 iframe src 并递归
            iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
            for src in re.findall(iframe_pattern, html):
                full = urljoin(url, src)
                if urlparse(full).netloc and full not in seen:
                    q.append(full)
        
        return m3u8

    # ===================== 修复：_fast_sniff_m3u8 去掉错误端点 =====================
    def _fast_sniff_m3u8(self, url):
        """异步快速提取 m3u8 链接，超时 5s，多线程"""
        m3u8_set = set()
        
        def fetch_and_extract(target_url):
            try:
                resp = requests.get(target_url, timeout=5, verify=False, headers={'User-Agent': self.UA})
                content = resp.text
                matches = re.findall(r'(https?://[^\s\'"<>]+?\.m3u8(?:\?[^\'"<>]*)?)', content)
                for match in matches:
                    m3u8_set.add(match)
            except Exception as e:
                print(f'sniff err: {e}')
        
        urls_to_check = [url]
        # 如果已知是 filemoon /e/ 页面，也试试 embed 版本
        if '/e/' in url and 'filemoon' in url.lower():
            urls_to_check.append(url.replace('/e/', '/embed/'))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_and_extract, u) for u in urls_to_check]
            concurrent.futures.wait(futures, timeout=5)
        
        return list(m3u8_set) if m3u8_set else []

    # ===================== 修复：实现 isVideoFormat =====================
    def isVideoFormat(self, url):
        """
        TVBox 嗅探时会调用此方法判断 URL 是否为视频。
        必须实现，否则 parse=1 时播放器无法识别视频流。
        """
        if not url:
            return False
        url_lower = url.lower()
        video_exts = ['.m3u8', '.mp4', '.ts', '.flv', '.avi', '.mkv', '.mov', '.webm']
        for ext in video_exts:
            if ext in url_lower:
                return True
        # 也匹配常见的视频流路径特征
        if any(x in url_lower for x in ['/m3u8', '/video/', '/stream/', '/play/', '.m3u8']):
            return True
        return False

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        action = {}
        return action

    def videosContent(self, url):
        rsp = self._fetch(url)
        root = pq(rsp.text)
        d = pq(rsp.text)
        videos = []
        
        video_items = d('div.grid > div')
        
        for item in video_items.items():
            video = {
                "vod_id": "",
                "vod_name": "",
                "vod_pic": "",
                "vod_remarks": ""
            }
            
            link_elem = item('a[href*="/posts/"]').eq(0)
            if link_elem:
                href = link_elem.attr('href')
                if href and '/posts/' in href:
                    video['vod_id'] = href.split('/')[-1]
            
            title_elem = item('h2.font-semibold')
            if title_elem:
                video['vod_name'] = title_elem.text().strip()
            
            img_elem = item('img')
            if img_elem:
                video['vod_pic'] = img_elem.attr('src')
            
            date_elem = item('time')
            if date_elem:
                video['vod_remarks'] = date_elem.attr('datetime')
            
            if video['vod_id'] and video['vod_name']:
                videos.append(video)
        
        pagecount = 1
        current_page = 1
        
        pagination = d('nav[aria-label="Pagination Navigation"]')
        if pagination:
            page_links = pagination('a[href*="?page="]')
            if page_links:
                pages = []
                for link in page_links.items():
                    try:
                        page_num = int(link.text().strip())
                        pages.append(page_num)
                    except:
                        pass
                if pages:
                    pagecount = max(pages)
            
            current_page_elem = pagination('span[aria-current="page"]')
            if current_page_elem:
                try:
                    current_page = int(current_page_elem.text().strip())
                except:
                    pass
        
        result = {
            'list': videos,
            'page': current_page,
            'pagecount': pagecount,
            'limit': len(videos),
            'total': len(videos) * pagecount
        }
        
        return result

    @property
    def home(self):
        return "https://kbj.im"

    def _fetch(self, url, **kwargs):
        try:
            # 修复：带上 UA，避免被反爬
            headers = kwargs.pop('headers', {})
            headers.setdefault('User-Agent', self.UA)
            response = requests.get(url, timeout=10, verify=False, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"Fetch error for {url}: {e}")
            return self.fetch(url, **kwargs)

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
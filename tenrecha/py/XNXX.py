# coding: utf-8
import re
import sys
import urllib.parse
import time
import requests
import json
from pyquery import PyQuery as pq
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin, urlparse, quote

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "XNXX"

    def init(self, extend):
        self.host = extend.get('host', 'https://xnxx.health') if extend else 'https://xnxx.health'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        # 备用分类列表（XNXX 常见标签）
        self.fallback_categories = extend.get('categories', [
            {'type_id': 'teen', 'type_name': 'Teen'},
            {'type_id': 'milf', 'type_name': 'MILF'},
            {'type_id': 'big+ass', 'type_name': 'Big Ass'},
            {'type_id': 'big+tits', 'type_name': 'Big Tits'},
            {'type_id': 'amateur', 'type_name': 'Amateur'},
            {'type_id': 'anal', 'type_name': 'Anal'},
            {'type_id': 'asian', 'type_name': 'Asian'},
            {'type_id': 'bbw', 'type_name': 'BBW'},
            {'type_id': 'bdsm', 'type_name': 'BDSM'},
            {'type_id': 'blonde', 'type_name': 'Blonde'},
            {'type_id': 'blowjob', 'type_name': 'Blowjob'},
            {'type_id': 'brunette', 'type_name': 'Brunette'},
            {'type_id': 'casting', 'type_name': 'Casting'},
            {'type_id': 'creampie', 'type_name': 'Creampie'},
            {'type_id': 'cumshot', 'type_name': 'Cumshot'},
            {'type_id': 'deepthroat', 'type_name': 'Deepthroat'},
            {'type_id': 'ebony', 'type_name': 'Ebony'},
            {'type_id': 'fetish', 'type_name': 'Fetish'},
            {'type_id': 'gangbang', 'type_name': 'Gangbang'},
            {'type_id': 'hardcore', 'type_name': 'Hardcore'},
            {'type_id': 'interracial', 'type_name': 'Interracial'},
            {'type_id': 'latina', 'type_name': 'Latina'},
            {'type_id': 'lesbian', 'type_name': 'Lesbian'},
            {'type_id': 'masturbation', 'type_name': 'Masturbation'},
            {'type_id': 'mature', 'type_name': 'Mature'},
            {'type_id': 'pov', 'type_name': 'POV'},
            {'type_id': 'public', 'type_name': 'Public'},
            {'type_id': 'redhead', 'type_name': 'Redhead'},
            {'type_id': 'rough', 'type_name': 'Rough'},
            {'type_id': 'squirt', 'type_name': 'Squirt'},
            {'type_id': 'threesome', 'type_name': 'Threesome'},
        ]) if extend else [
            {'type_id': 'teen', 'type_name': 'Teen'},
            {'type_id': 'milf', 'type_name': 'MILF'},
            {'type_id': 'big+ass', 'type_name': 'Big Ass'},
            {'type_id': 'big+tits', 'type_name': 'Big Tits'},
            {'type_id': 'amateur', 'type_name': 'Amateur'},
            {'type_id': 'anal', 'type_name': 'Anal'},
            {'type_id': 'asian', 'type_name': 'Asian'},
            {'type_id': 'creampie', 'type_name': 'Creampie'},
            {'type_id': 'cumshot', 'type_name': 'Cumshot'},
            {'type_id': 'hardcore', 'type_name': 'Hardcore'},
            {'type_id': 'interracial', 'type_name': 'Interracial'},
            {'type_id': 'lesbian', 'type_name': 'Lesbian'},
            {'type_id': 'mature', 'type_name': 'Mature'},
            {'type_id': 'threesome', 'type_name': 'Threesome'},
        ]
        self.session = self._create_session()
        self._categories = None

    def _create_session(self):
        session = requests.Session()
        session.headers.update(self.headers)
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def fetch(self, url, retry=3):
        for i in range(retry):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 403:
                    pattern = r'document\.cookie\s*=\s*"([^"]+)"'
                    match = re.search(pattern, resp.text)
                    if match:
                        cookie_line = match.group(1)
                        parts = [p.strip() for p in cookie_line.split(';')]
                        name_value = parts[0]
                        if '=' in name_value:
                            name, value = name_value.split('=', 1)
                            path = '/'
                            for part in parts[1:]:
                                if part.lower().startswith('path='):
                                    path = part.split('=', 1)[1]
                                    break
                            parsed = urlparse(url)
                            self.session.cookies.set(name, value, path=path, domain=parsed.netloc)
                            resp2 = self.session.get(url, timeout=15)
                            if resp2.status_code == 200:
                                return resp2
                time.sleep(1)
            except Exception as e:
                print(f"fetch error ({i+1}/{retry}): {e}")
                time.sleep(2)
        return None

    def homeContent(self, filter):
        result = {'class': []}
        if self._categories is not None:
            result['class'] = self._categories
            return result

        try:
            rsp = self.fetch(self.host)
            if rsp and rsp.text:
                doc = pq(rsp.text)
                categories = []
                # XNXX 分类通常在导航栏或标签云中
                selectors = [
                    'a[href^="/tags/"]',
                    'a[href^="/search/"]',
                    'a[href*="/best/"]',
                    '.nav a[href*="/tags/"]',
                    '.menu a[href*="/tags/"]',
                    '.tag-list a',
                    '.categories a'
                ]
                for sel in selectors:
                    for a in doc(sel).items():
                        href = a.attr('href')
                        name = a.text().strip()
                        if not href or not name:
                            continue
                        match = re.search(r'/(?:tags|search|best)/([^/?&]+)', href)
                        if match:
                            tid = match.group(1)
                            categories.append({'type_id': tid, 'type_name': name})
                    if categories:
                        break
                if categories:
                    seen = set()
                    unique = []
                    for c in categories:
                        if c['type_id'] not in seen:
                            seen.add(c['type_id'])
                            unique.append(c)
                    self._categories = unique
                    result['class'] = unique
                    return result
        except Exception as e:
            print(f"自动获取分类失败: {e}")

        print("使用备用分类列表")
        self._categories = self.fallback_categories
        result['class'] = self.fallback_categories
        return result

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 24, 'total': 1}
        try:
            # XNXX 分页通常是 ?p=页码
            if pg == 1:
                url = f"{self.host}/search/{tid}"
            else:
                url = f"{self.host}/search/{tid}?p={pg}"
            
            rsp = self.fetch(url)
            if not rsp or not rsp.text:
                return result

            doc = pq(rsp.text)
            videos = []
            # XNXX 视频列表选择器
            item_selectors = [
                '.thumb-block',
                '.video-thumb',
                '.thumb',
                '.video-item',
                '.video'
            ]
            items = None
            for sel in item_selectors:
                items = doc(sel)
                if items and len(items) > 0:
                    break
            if not items:
                return result

            for item in items.items():
                a_tag = item('a') if item('a').attr('href') else item.find('a').eq(0)
                if not a_tag:
                    continue
                href = a_tag.attr('href')
                if not href:
                    continue
                # XNXX 视频链接格式: /video-xxxxx/title
                vod_id = href
                if not vod_id.startswith('/'):
                    vod_id = '/' + vod_id
                if vod_id.startswith('http'):
                    vod_id = vod_id.replace(self.host, '')
                
                img = a_tag('img').attr('data-src') or a_tag('img').attr('src') or ''
                name = item.find('.title, .thumb-under p, .video-title').text().strip() or a_tag.attr('title') or ''
                if not name:
                    name = item.text().strip()[:50]
                remark = item.find('.duration, .time, .video-duration').text().strip() or ''
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': name,
                    'vod_pic': img,
                    'vod_remarks': remark
                })
            result['list'] = videos

            # 分页信息
            max_page = 1
            pagination = doc('.pagination, .page, .pages, .pager')
            if pagination:
                page_links = pagination.find('a')
                page_numbers = []
                for link in page_links.items():
                    href = link.attr('href')
                    if href:
                        match = re.search(r'[?&]p=(\d+)', href)
                        if match:
                            page_numbers.append(int(match.group(1)))
                        else:
                            match2 = re.search(r'/(\d+)$', href)
                            if match2:
                                page_numbers.append(int(match2.group(1)))
                if page_numbers:
                    max_page = max(page_numbers)
            
            if max_page == 1 and len(videos) > 0:
                next_link = pagination.find('a:contains("Next"), a:contains("»"), a.next') if pagination else None
                if next_link and next_link.attr('href'):
                    max_page = pg + 1
            
            result['pagecount'] = max(max_page, int(pg))
            result['total'] = result['pagecount'] * len(videos) if len(videos) > 0 else 1

        except Exception as e:
            print(f"categoryContent error: {e}")
            import traceback
            traceback.print_exc()
        return result

    def detailContent(self, array):
        result = {}
        if not array or not array[0]:
            return result
        vod_id = array[0]
        if not vod_id.startswith('/'):
            vod_id = '/' + vod_id
        url = self.host + vod_id if not vod_id.startswith('http') else vod_id
        try:
            rsp = self.fetch(url)
            if not rsp or not rsp.text:
                return result
            doc = pq(rsp.text)

            vod_name = doc('h1, .video-title, .title').text().strip() or ''
            vod_pic = doc('.video-player img, .poster img, #video-player img').attr('src') or ''
            vod_content = doc('.video-description, .description').text().strip() or ''

            # XNXX 播放页通常直接包含视频地址
            video_url = None
            html = rsp.text
            
            # 多种 XNXX 视频地址提取模式
            patterns = [
                r'setVideoUrl\([\'"]([^\'"]+)[\'"]\)',
                r'setVideoUrlHigh\([\'"]([^\'"]+)[\'"]\)',
                r'setVideoUrlLow\([\'"]([^\'"]+)[\'"]\)',
                r'var\s+video_url\s*=\s*[\'"]([^\'"]+)[\'"]',
                r'var\s+html5player\s*=\s*({.*?});',
                r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"',
                r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                r'https?://[^\s"\']+\.mp4[^\s"\']*',
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'videoSrc\s*=\s*[\'"]([^\'"]+)[\'"]',
                r'sources\s*:\s*\[\s*\{\s*file\s*:\s*[\'"]([^\'"]+)[\'"]'
            ]
            for pat in patterns:
                match = re.search(pat, html, re.DOTALL)
                if match:
                    if 'html5player' in pat:
                        try:
                            data = json.loads(match.group(1))
                            video_url = data.get('videoUrl') or data.get('url')
                        except:
                            pass
                    else:
                        video_url = match.group(1).replace('\\/', '/')
                    if video_url and ('.mp4' in video_url or '.m3u8' in video_url):
                        break

            play_from = ['默认线路']
            if video_url:
                play_urls = [f"正片${video_url}"]
            else:
                play_urls = []

            vod = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'vod_content': vod_content,
                'vod_play_from': '$$$'.join(play_from) if play_from else '',
                'vod_play_url': '$$$'.join(play_urls) if play_urls else ''
            }
            result['list'] = [vod]
        except Exception as e:
            print(f"detailContent error: {e}")
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': []}
        try:
            encoded_key = quote(key, safe='')
            if pg == '1' or pg == 1:
                url = f"{self.host}/search/{encoded_key}"
            else:
                url = f"{self.host}/search/{encoded_key}?p={pg}"
            rsp = self.fetch(url)
            if not rsp or not rsp.text:
                return result
            doc = pq(rsp.text)
            videos = []
            item_selectors = ['.thumb-block', '.video-thumb', '.thumb', '.video-item', '.video']
            items = None
            for sel in item_selectors:
                items = doc(sel)
                if items and len(items) > 0:
                    break
            if not items:
                return result
            for item in items.items():
                a_tag = item('a') if item('a').attr('href') else item.find('a').eq(0)
                if not a_tag:
                    continue
                href = a_tag.attr('href')
                if not href:
                    continue
                vod_id = href
                if not vod_id.startswith('/'):
                    vod_id = '/' + vod_id
                if vod_id.startswith('http'):
                    vod_id = vod_id.replace(self.host, '')
                img = a_tag('img').attr('data-src') or a_tag('img').attr('src') or ''
                name = item.find('.title, .thumb-under p, .video-title').text().strip() or a_tag.attr('title') or ''
                remark = item.find('.duration, .time, .video-duration').text().strip() or ''
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': name,
                    'vod_pic': img,
                    'vod_remarks': remark
                })
            result['list'] = videos
        except Exception as e:
            print(f"searchContent error: {e}")
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            if id.startswith('http') and ('.m3u8' in id or '.mp4' in id):
                result["url"] = id
                result["header"] = {'User-Agent': self.headers['User-Agent'], 'Referer': self.host}
                return result

            if not id.startswith('http'):
                play_url = self.host + id if id.startswith('/') else self.host + '/' + id
            else:
                play_url = id

            rsp = self.fetch(play_url)
            if not rsp or not rsp.text:
                return result
            html = rsp.text

            patterns = [
                r'setVideoUrl\([\'"]([^\'"]+)[\'"]\)',
                r'setVideoUrlHigh\([\'"]([^\'"]+)[\'"]\)',
                r'setVideoUrlLow\([\'"]([^\'"]+)[\'"]\)',
                r'var\s+video_url\s*=\s*[\'"]([^\'"]+)[\'"]',
                r'var\s+html5player\s*=\s*({.*?});',
                r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"',
                r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                r'https?://[^\s"\']+\.mp4[^\s"\']*',
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'videoSrc\s*=\s*[\'"]([^\'"]+)[\'"]',
                r'sources\s*:\s*\[\s*\{\s*file\s*:\s*[\'"]([^\'"]+)[\'"]'
            ]
            video_url = None
            for pat in patterns:
                match = re.search(pat, html, re.DOTALL)
                if match:
                    if 'html5player' in pat:
                        try:
                            data = json.loads(match.group(1))
                            video_url = data.get('videoUrl') or data.get('url')
                        except:
                            pass
                    else:
                        video_url = match.group(1).replace('\\/', '/')
                    if video_url and ('.mp4' in video_url or '.m3u8' in video_url):
                        break

            if video_url:
                result["url"] = video_url
                result["header"] = {'User-Agent': self.headers['User-Agent'], 'Referer': play_url}
                return result

            result["parse"] = 1
            result["url"] = id
        except Exception as e:
            print(f"playerContent error: {e}")
        return result

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}
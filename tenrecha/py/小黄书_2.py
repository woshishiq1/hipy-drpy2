# -*- coding: utf-8 -*-
import base64
import html
import json
import re
import sys
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3
from lxml import etree
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):

    HOST = 'https://xchina.co'

    def __init__(self):
        self.host = self.HOST
        self.ext = ''
        self.session = requests.Session()
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/138.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.classes = [
            {'type_name': '成人影片', 'type_id': 'video@@/videos'},
            {'type_name': 'AI视频', 'type_id': 'video@@/videos/series-69f3977abc9f7'},
            {'type_name': '情色套图', 'type_id': 'photo@@/photos'},
            {'type_name': 'AI图区', 'type_id': 'photo@@/photos/series-6443d480eb757'},
            {'type_name': '成人小说', 'type_id': 'fiction@@/fictions'},
        ]

    def getName(self):
        return '小黄书'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        self.ext = getattr(self, 'ext', '') or extend or ''
        config = self._parse_config(self.ext)
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
        cookie = str(config.get('cookie') or config.get('Cookie') or '').strip()
        if cookie:
            self.headers['Cookie'] = cookie
        referer = str(config.get('referer') or '').strip()
        self.headers['Referer'] = referer if referer.startswith(('http://', 'https://')) else self.host + '/'
        self.headers.update({
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
        })
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        path = urlparse(str(url or '')).path.lower()
        return path.endswith(('.m3u8', '.mp4', '.ts', '.flv'))

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            response = self._request(self.host + '/videos.html')
            return {'list': self._parse_cards(response.text, 'video')[:36]}
        except Exception as error:
            self.log('XChina 首页加载失败: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        try:
            kind, route = self._split_tid(tid)
            url = self._paged_url(route, page)
            response = self._request(url)
            videos = self._parse_cards(response.text, kind)
            page_count = self._page_count(response.text, page)
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': len(videos) or 20,
                'total': page_count * (len(videos) or 20),
            }
        except Exception as error:
            self.log('XChina 分类加载失败: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        raw_id = str(ids[0] if ids else '').strip()
        if not raw_id:
            return {'list': []}
        try:
            url = urljoin(self.host + '/', raw_id)
            response = self._request(url)
            path = urlparse(response.url or url).path
            if '/photo/' in path:
                vod = self._photo_detail(response.text, response.url or url)
            elif '/fiction/' in path:
                vod = self._fiction_detail(response.text, response.url or url)
            else:
                vod = self._video_detail(response.text, response.url or url)
            return {'list': [vod]} if vod else {'list': []}
        except Exception as error:
            self.log('XChina 详情加载失败: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 20, 'total': 0}
        videos = []
        seen = set()
        max_page = page
        for kind, root in (('video', 'videos'), ('photo', 'photos'), ('fiction', 'fictions')):
            try:
                route = '/%s/keyword-%s' % (root, quote(keyword, safe=''))
                response = self._request(self._paged_url(route, page))
                max_page = max(max_page, self._page_count(response.text, page))
                for item in self._parse_cards(response.text, kind):
                    if item.get('vod_id') and item['vod_id'] not in seen:
                        seen.add(item['vod_id'])
                        videos.append(item)
            except Exception as error:
                self.log('XChina %s 搜索失败: %s' % (kind, error))
        return {
            'list': videos,
            'page': page,
            'pagecount': max_page,
            'limit': len(videos) or 20,
            'total': max_page * (len(videos) or 20),
        }

    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if value.startswith('pics@@'):
            detail_url = value[6:]
            try:
                response = self._request(detail_url)
                images = self._photo_images(response.text, response.url or detail_url)
                if images:
                    return {
                        'parse': 0,
                        'playUrl': '',
                        'url': 'pics://' + '&&'.join(images),
                        'header': self._media_headers(response.url or detail_url),
                    }
            except Exception as error:
                self.log('XChina 套图解析失败: %s' % error)
            return {'parse': 1, 'url': detail_url, 'header': self.headers}
        if value.startswith('article@@'):
            article_url = value[9:]
            try:
                response = self._request(article_url)
                payload = self._fiction_article(response.text, response.url or article_url)
                encoded = base64.urlsafe_b64encode(
                    json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                ).decode('ascii').rstrip('=')
                return {'parse': 0, 'playUrl': '', 'url': 'article://' + encoded, 'header': {}}
            except Exception as error:
                self.log('XChina 小说正文解析失败: %s' % error)
                return {'parse': 1, 'url': article_url, 'header': self.headers}
        return {
            'parse': 0 if value.startswith(('http://', 'https://')) else 1,
            'playUrl': '',
            'url': value,
            'header': self._media_headers(self.host + '/'),
        }

    def localProxy(self, param):
        if param.get('type') != 'img' or not param.get('url'):
            return [404, 'text/plain; charset=utf-8', b'not found']
        try:
            response = self.session.get(
                str(param['url']), headers=self._media_headers(self.host + '/'),
                timeout=20, verify=False
            )
            response.raise_for_status()
            return [200, self._mime(response.content, response.headers.get('Content-Type')), response.content]
        except Exception as error:
            self.log('XChina 图片代理失败: %s' % error)
            return [500, 'text/plain; charset=utf-8', b'image proxy failed']

    def _request(self, url, timeout=20):
        response = self.session.get(
            url, headers=self.headers, timeout=timeout, verify=False, allow_redirects=True
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response

    def _parse_cards(self, html_text, kind):
        data = self._doc(html_text)
        singular = {'video': 'video', 'photo': 'photo', 'fiction': 'fiction'}[kind]
        selector = 'a[href*="/%s/id-"]' % singular
        videos = []
        seen = set()
        for anchor in data(selector).items():
            href = str(anchor.attr('href') or '').strip()
            if not href or href in seen:
                continue
            image_node = anchor.find('.img')
            title = self._clean(anchor.attr('title') or anchor.text())
            if not title or not image_node:
                continue
            seen.add(href)
            parent = anchor.parents('.item').eq(0)
            style = str(image_node.attr('style') or '')
            pic = self._css_url(style)
            remark = ''
            tags = [self._clean(x.text()) for x in parent.find('.tags > div').items()]
            tags = [x for x in tags if x]
            if tags:
                remark = tags[-1] if re.search(r'\d{1,3}:\d{2}', tags[-1]) else tags[0]
            if kind == 'photo':
                remark = remark or '套图'
            elif kind == 'fiction':
                remark = remark or '小说'
            videos.append({
                'vod_id': urljoin(self.host + '/', href),
                'vod_name': title.replace('《', '').replace('》', ''),
                'vod_pic': urljoin(self.host + '/', pic) if pic else '',
                'vod_remarks': remark,
                'style': {'type': 'rect', 'ratio': 1.5} if kind == 'video' else {'type': 'rect', 'ratio': 0.72},
            })
        return videos

    def _video_detail(self, html_text, page_url):
        data = self._doc(html_text)
        title = self._clean(data('h1').eq(0).text() or data('meta[property="og:title"]').attr('content'))
        pic = str(data('meta[property="og:image"]').attr('content') or '').strip()
        sources = []
        for script in data('script').items():
            text = html.unescape(script.text() or '')
            if 'VideoPlayer' not in text:
                continue
            for match in re.findall(r"\bsrc\s*:\s*['\"]([^'\"]+)['\"]", text):
                url = urljoin(page_url, match.replace('\\/', '/'))
                if url not in sources and self.isVideoFormat(url):
                    sources.append(url)
        if not sources:
            return None
        plays = []
        for index, source in enumerate(sources, start=1):
            quality = re.search(r'/(\d{3,4})\.m3u8', source)
            name = (quality.group(1) + 'P') if quality else ('播放%d' % index)
            plays.append('%s$%s' % (name, source))
        content = self._clean(data('.info-card.video-detail').text() or data('meta[name="description"]').attr('content'))
        return {
            'vod_id': page_url,
            'vod_name': title or '小黄书视频',
            'vod_pic': pic,
            'vod_content': content or title,
            'vod_play_from': '小黄书直链',
            'vod_play_url': '#'.join(plays),
        }

    def _photo_detail(self, html_text, page_url):
        data = self._doc(html_text)
        title = self._clean(data('h1').eq(0).text()) or '情色套图'
        images = self._photo_images(html_text, page_url)
        if not images:
            return None
        cover = self._photo_thumbnails(data, page_url)[0] if self._photo_thumbnails(data, page_url) else images[0]
        return {
            'vod_id': page_url,
            'vod_name': title,
            'vod_pic': cover,
            'vod_remarks': '%dP' % len(images),
            'vod_content': '%s，共 %d 张原图' % (title, len(images)),
            'vod_play_from': '套图原图',
            'vod_play_url': '全套图片$pics@@' + page_url,
        }

    def _fiction_detail(self, html_text, page_url):
        data = self._doc(html_text)
        title = self._clean(data('h1').eq(0).text()).strip('《》') or '成人小说'
        cover = self._css_url(str(data('.fiction-cover-left').attr('style') or ''))
        chapters = []
        seen = set()
        for anchor in data('a[href*="/fiction/id-"]').items():
            href = str(anchor.attr('href') or '').strip()
            name = self._clean(anchor.text())
            if not href or href in seen or not name:
                continue
            if not re.search(r'(章|节|卷|序|阅读|尾声|后记)', name):
                continue
            if re.search(r'/fiction/id-[0-9a-f]{10,}\.html', href, re.I):
                continue
            seen.add(href)
            chapters.append('%s$article@@%s' % (self._safe_name(name), urljoin(page_url, href)))
        if not chapters and data('.fiction-body'):
            chapters.append('正文$article@@' + page_url)
        if not chapters:
            return None
        content = self._clean(data('.fiction-intro, .description, .info-card').eq(0).text())
        return {
            'vod_id': page_url,
            'vod_name': title,
            'vod_pic': urljoin(page_url, cover) if cover else '',
            'vod_remarks': '%d章' % len(chapters),
            'vod_content': content or title,
            'vod_play_from': '小说章节',
            'vod_play_url': '#'.join(chapters),
        }

    def _photo_images(self, html_text, page_url):
        data = self._doc(html_text)
        result = []
        for thumb in self._photo_thumbnails(data, page_url):
            full = re.sub(r'_\d+x\d+\.webp(?=\?|$)', '.jpg', thumb, flags=re.I)
            if full not in result:
                result.append(full)
        return result

    def _photo_thumbnails(self, data, page_url):
        result = []
        for node in data('.list.photo-items .photo-image .img').items():
            value = self._css_url(str(node.attr('style') or ''))
            value = urljoin(page_url, value) if value else ''
            if value and value not in result:
                result.append(value)
        return result

    def _fiction_article(self, html_text, page_url):
        data = self._doc(html_text)
        title = self._clean(data('h1').eq(0).text())
        body = data('.fiction-body').eq(0)
        blocks = []
        for node in body.find('h2, h3, p, img').items():
            tag = str(node[0].tag or '').lower()
            if tag == 'img':
                src = str(node.attr('src') or node.attr('data-src') or '').strip()
                if src:
                    blocks.append({'type': 'image', 'url': urljoin(page_url, src), 'alt': self._clean(node.attr('alt'))})
                continue
            text = self._clean(node.text())
            if not text:
                continue
            if tag in ('h2', 'h3'):
                blocks.append({'type': 'heading', 'level': int(tag[1]), 'text': text})
            else:
                blocks.append({'type': 'text', 'text': text})
        return {'version': 1, 'title': title, 'source': page_url, 'blocks': blocks}

    def _paged_url(self, route, page):
        route = str(route or '').rstrip('/')
        if route in ('/videos', '/photos', '/fictions'):
            return self.host + route + '/%d.html' % page
        if page <= 1:
            return self.host + route + '.html'
        return self.host + route + '/%d.html' % page

    def _split_tid(self, tid):
        parts = str(tid or '').split('@@', 1)
        if len(parts) != 2:
            return 'video', '/videos'
        return parts[0], parts[1]

    def _page_count(self, html_text, current):
        data = self._doc(html_text)
        values = [current]
        for anchor in data('a[href]').items():
            text = self._clean(anchor.text())
            if text.isdigit():
                values.append(self._int(text, current))
        return max(values)

    def _doc(self, value):
        text = value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else str(value or '')
        try:
            parser = etree.HTMLParser(encoding='utf-8', recover=True)
            root = etree.fromstring(text.encode('utf-8', errors='ignore'), parser=parser)
            return pq(root) if root is not None else pq('<html></html>')
        except Exception:
            return pq('<html></html>')

    def _parse_config(self, value):
        if isinstance(value, dict):
            return value
        text = str(value or '').strip()
        if text.startswith('{'):
            try:
                return json.loads(text)
            except Exception:
                pass
        if text.startswith(('http://', 'https://')):
            return {'host': text}
        return {}

    def _media_headers(self, referer):
        return {
            'User-Agent': self.headers['User-Agent'],
            'Referer': referer,
            'Accept': '*/*',
        }

    @staticmethod
    def _css_url(style):
        match = re.search(r"url\(\s*['\"]?([^'\")]+)", str(style or ''), re.I)
        return html.unescape(match.group(1).strip()) if match else ''

    @staticmethod
    def _clean(value):
        return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()

    @staticmethod
    def _safe_name(value):
        return re.sub(r'[$#]+', ' ', str(value or '')).strip() or '正文'

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _mime(data, content_type=''):
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        if data.startswith(b'GIF8'):
            return 'image/gif'
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            return 'image/webp'
        if data.startswith(b'\xff\xd8'):
            return 'image/jpeg'
        return str(content_type or 'application/octet-stream').split(';', 1)[0]

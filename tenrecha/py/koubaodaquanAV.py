# -*- coding: utf-8 -*-
"""KNM111 / 口爆大全AV - FongMi/WebHomeTV/PickTV compatible spider.
仅解析站点公开页面；列表条目保持干净，播放地址只在 detailContent 返回。
"""
import re
import json
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser


class _Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.links = []
        self.articles = []
        self._a = None
        self._article = None
        self._img = None
        self._text = []
        self._in_h2 = False
        self._in_title = False
        self.title = ''
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class', '')
        if tag == 'title':
            self._in_title = True
        if tag == 'meta' and a.get('name', '').lower() in ('description', 'keywords'):
            self.meta[a.get('name', '').lower()] = a.get('content', '')
        if tag == 'a' and a.get('href'):
            self._a = {'href': a['href'], 'title': a.get('title', ''), 'pic': '', 'name': ''}
        if tag == 'img' and self._a is not None:
            self._a['pic'] = a.get('src') or a.get('data-src') or ''
        if tag == 'h2' and self._a is not None:
            self._in_h2 = True
        if tag == 'article':
            self._article = self._a

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag == 'h2':
            self._in_h2 = False
        if tag == 'a' and self._a is not None:
            x = self._a
            if self._in_h2:
                x['name'] = ''.join(self._text).strip()
            if not x['name']:
                x['name'] = x['title']
            if '/video/' in x['href']:
                self.links.append(x.copy())
            self._a = None
            self._text = []
        if tag == 'article' and self._article is not None:
            x = self._article
            if x in self.links and x not in self.articles:
                self.articles.append(x)
            self._article = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h2:
            self._text.append(data)


class Spider:
    host = 'https://knm111.top'
    ua = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36'
    referer = host + '/'
    cats = {
        '57': '精品推荐', '58': '主播秀色', '59': 'AV解说', '60': '日本无码',
        '61': '中文字幕', '62': '童颜巨乳', '63': '性感人妻', '64': '强奸乱伦',
        '65': '欧美情色', '67': '群P换妻', '68': '成人动画', '69': '丝袜OL',
        '70': '自拍偷拍', '71': '网曝系列', '72': '同性恋', '90': '探花嫖娼',
        '91': '国产人妻', '92': '国产SM', '93': '国产丝袜', '94': '麻豆传媒',
        '95': '国产乱伦', '96': '自慰系列', '97': '教师学生', '98': '口交视频'
    }

    def __init__(self):
        self.s = None
        self.session = None
        self.sess = None
        self.extend = ''

    def getDependence(self):
        return []

    def init(self, extend=''):
        self.extend = extend or ''
        return None

    def _get(self, url):
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.host + '/', url)
        req = urllib.request.Request(url, headers={
            'User-Agent': self.ua, 'Referer': self.referer, 'Accept': 'text/html,application/xhtml+xml'
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode('utf-8', 'ignore'), r.geturl()
        except Exception:
            return '', url

    def _parse(self, text):
        p = _Parser()
        try:
            p.feed(text)
        except Exception:
            pass
        out = []
        seen = set()
        for x in p.links:
            href = urllib.parse.urljoin(self.host + '/', x['href'])
            m = re.search(r'/video/\?(\d+)-', href)
            if not m or href in seen:
                continue
            seen.add(href)
            out.append({'vod_id': m.group(1),
                        'vod_name': unescape(x['name'] or x['title']).strip(),
                        'vod_pic': self._pic(x['pic']) if x['pic'] else '',
                        'vod_remarks': ''})
        return out, p

    def _page(self, tid, pg):
        tid = str(tid or '57')
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        path = '/list/?%s.html' % tid if pg <= 1 else '/list/?%s-%s.html' % (tid, pg)
        return self._get(self.host + path)[0]

    def homeContent(self, filter=None):
        classes = [{'type_id': k, 'type_name': v} for k, v in self.cats.items()]
        text = self._get(self.host + '/index.php')[0]
        videos, _ = self._parse(text)
        return {'class': classes, 'list': videos}

    def homeVideoContent(self):
        text = self._get(self.host + '/index.php')[0]
        videos, _ = self._parse(text)
        return {'list': videos}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        videos, _ = self._parse(self._page(tid, pg))
        return {'list': videos, 'page': int(pg or 1), 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        q = urllib.parse.quote(str(key), safe='')
        url = self.host + '/search.php?searchword=' + q
        if page > 1:
            url += '&page=' + str(page)
        videos, _ = self._parse(self._get(url)[0])
        return {'list': videos, 'page': page, 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def _id(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ''
        if isinstance(ids, dict):
            ids = ids.get('id', '')
        s = str(ids)
        m = re.search(r'(\d+)', s)
        return m.group(1) if m else s

    def detailContent(self, ids):
        vid = self._id(ids)
        text, final = self._get(self.host + '/video/?%s-0-0.html' % vid)
        videos, p = self._parse(text)
        title = p.title.strip()
        title = re.sub(r'^(《|\[)', '', title)
        title = re.sub(r'(》)?(?:全集在线播放|全集在线观看).*$', '', title).strip()
        if not title:
            title = next((x['vod_name'] for x in videos if x['vod_id'] == vid), '视频 ' + vid)
        # 详情页的图片只有相关推荐，不能取第一张；真实封面与播放流同目录。
        mm = re.search(r'\bvar\s+now\s*=\s*["\']([^"\']+)', text, re.I)
        play = mm.group(1) if mm else ''
        pic = ''
        if play:
            pic = re.sub(r'/index\.m3u8(?:\?.*)?$', '/1.jpg', play)
        if not pic:
            # 首页/分类中的同 ID 卡片可作为降级封面来源
            home_videos, _ = self._parse(self._get(self.host + '/index.php')[0])
            pic = next((x.get('vod_pic', '') for x in home_videos if x.get('vod_id') == vid), '')
            if pic.startswith('proxy://?do=py&url='):
                pic = urllib.parse.unquote(pic.split('url=', 1)[1])
        if not pic:
            mm = re.search(r'<img[^>]+src=["\']([^"\']+)', text, re.I)
            pic = mm.group(1) if mm else ''
        vod = {'vod_id': vid, 'vod_name': title, 'vod_pic': self._pic(pic),
               'vod_content': p.meta.get('description', ''), 'vod_remarks': '高清',
               'vod_play_from': 'KNM111', 'vod_play_url': '正片$' + play if play else ''}
        return {'list': [vod]}

    def playerContent(self, flag, ids, vipFlags=None):
        url = str(ids or '')
        if not url.startswith('http'):
            url = self._id(url)
            d = self.detailContent([url]).get('list', [{}])[0]
            pu = d.get('vod_play_url', '')
            url = pu.split('$', 1)[-1] if '$' in pu else pu
        return {'parse': 0, 'jx': 0, 'url': url,
                'header': {'User-Agent': self.ua, 'Referer': self.referer},
                'format': 'application/x-mpegURL'}

    def _pic(self, url):
        if not url:
            return ''
        # 该 CDN 可直接访问；封面返回原始 .jpg 地址，避免部分壳不解析 proxy:// 图片。
        # localProxy 仍保留，作为需要代理时的兼容入口。
        return url

    def localProxy(self, param):
        if isinstance(param, str):
            try: param = json.loads(param)
            except Exception: param = {}
        url = (param or {}).get('url', '')
        if not url:
            return [404, 'text/plain', b'', {}]
        url = urllib.parse.unquote(url)
        req = urllib.request.Request(url, headers={'User-Agent': self.ua, 'Referer': self.referer})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
                ctype = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
                # CDN 常返回 application/octet-stream，影视壳可能因此不显示封面。
                if body.startswith(b'\xff\xd8\xff'):
                    ctype = 'image/jpeg'
                elif body.startswith(b'\x89PNG'):
                    ctype = 'image/png'
                elif body.startswith(b'GIF8'):
                    ctype = 'image/gif'
                elif body.startswith(b'RIFF') and body[8:12] == b'WEBP':
                    ctype = 'image/webp'
                return [200, ctype, body, {'Cache-Control': 'max-age=3600'}]
        except Exception:
            return [502, 'text/plain', b'', {}]

    def manualVideoCheck(self): return False
    def isVideoFormat(self, url): return '.m3u8' in str(url).lower() or '.mp4' in str(url).lower()
    def action(self, action): return {}
    def destroy(self): return None

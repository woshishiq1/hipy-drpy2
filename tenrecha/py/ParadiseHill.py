import sys
sys.path.append('..')

from base.spider import BaseSpider
import re
import requests
from urllib.parse import quote, urlparse, unquote

HOST = 'https://en.paradisehill.cc'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

TIMEOUT = 15


class Spider(BaseSpider):
    def getName(self):
        return "ParadiseHill"

    filterable = False
    searchable = True
    host = HOST

    def init(self, extend=""):
        pass

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _get(self, url):
        try:
            r = self.fetch(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if r.status_code != 200:
                return ''
            return r.text
        except Exception as e:
            print('[ph] 请求失败: {} {}'.format(url, e))
            return ''

    def _parse_films(self, html):
        items = []
        blocks = re.findall(r'<div class="item list-film-item".*?</div>\s*</div>', html, re.S)
        for block in blocks:
            a = re.search(r'<a href="([^"]+)"', block)
            if not a:
                continue
            href = a.group(1)
            if not re.match(r'^/[A-Za-z0-9_-]+/$', href):
                continue
            if href in ('/', '/porn/', '/all/', '/categories/', '/actors/', '/studios/', '/news/', '/orders/', '/popular/'):
                continue
            name = re.search(r'<span itemprop="name">([^<]+)</span>', block)
            if not name:
                continue
            img = re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = ''
            if img:
                pic = img.group(1)
                if pic.startswith('/'):
                    pic = HOST + pic
                pic = self._proxy_img(pic)
            items.append({
                'vod_id': href,
                'vod_name': name.group(1).strip(),
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return items

    def _parse_channel_cards(self, html, kind):
        items = []
        blocks = re.findall(r'<div class="item"[^>]*>\s*<a [^>]*href="([^"]+)"(.*?)</a>\s*</div>', html, re.S)
        for href, inner in blocks:
            if not re.search(r'/(actor|studio|category)/', href):
                continue
            t = re.search(r'itemprop="name"[^>]*>\s*<span>([^<]+)</span>', inner)
            if not t:
                t = re.search(r'<div><span>([^<]+)</span></div>', inner)
            title = t.group(1).strip() if t else href.strip('/').split('/')[-1]
            img = re.search(r'<img[^>]*src="([^"]+)"', inner)
            pic = ''
            if img:
                pic = img.group(1)
                if pic.startswith('/'):
                    pic = HOST + pic
                pic = self._proxy_img(pic)
            path = href.split('?')[0].strip('/')
            sub = path.split('/')[-1]
            items.append({
                'vod_id': kind + '|' + sub + '@',
                'vod_name': title,
                'vod_pic': pic,
                'vod_tag': 'folder',
            })
        return items

    def homeContent(self, filter):
        classes = [
            {'type_name': 'All films', 'type_id': 'all'},
            {'type_name': 'Popular', 'type_id': 'popular'},
            {'type_name': 'Actors', 'type_id': 'actor'},
            {'type_name': 'Studios', 'type_id': 'studio'},
            {'type_name': 'Categories', 'type_id': 'category'},
        ]
        filters = {
            'all': [{'key': 'sort', 'name': '排序', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '最新', 'v': 'release'},
                {'n': '最热', 'v': 'title_en'},
            ]}],
            'popular': [
                {'key': 'filter', 'name': '时间', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '今年', 'v': 'year'},
                    {'n': '本月', 'v': 'month'},
                    {'n': '本周', 'v': 'week'},
                    {'n': '今日', 'v': 'day'},
                ]},
                {'key': 'sort', 'name': '热度', 'value': [
                    {'n': '按喜欢', 'v': ''},
                    {'n': '按浏览', 'v': 'by_views'},
                    {'n': '按评论', 'v': 'by_comment'},
                ]},
            ],
            'actor': [{'key': 'sort', 'name': '排序', 'value': [
                {'n': '最热', 'v': ''},
                {'n': '名称', 'v': 'name'},
            ]}],
            'studio': [{'key': 'sort', 'name': '排序', 'value': [
                {'n': '最热', 'v': ''},
                {'n': '名称', 'v': 'title'},
                {'n': '作品数', 'v': 'by_films'},
            ]}],
            'category': [{'key': 'sort', 'name': '排序', 'value': [
                {'n': '名称', 'v': ''},
                {'n': '最热', 'v': 'by_likes'},
            ]}],
        }
        return {'class': classes, 'filters': filters, 'type': '视频'}

    def homeVideoContent(self):
        html = self._get(HOST + '/porn/')
        return {'list': self._parse_films(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        extend = extend if isinstance(extend, dict) else {}

        if tid == 'home':
            return self.homeVideoContent()

        if tid in ('all', 'orders'):
            sort = extend.get('sort', 'created_at')
            url = HOST + '/' + tid + '/?sort=' + sort + ('&page=' + str(pg) if pg > 1 else '')
            html = self._get(url)
            return {'list': self._parse_films(html), 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 99999}

        if tid == 'popular':
            pf = extend.get('filter', 'all')
            ps = extend.get('sort', 'by_likes')
            url = HOST + '/popular/?filter=' + pf + '&sort=' + ps + ('&page=' + str(pg) if pg > 1 else '')
            html = self._get(url)
            return {'list': self._parse_films(html), 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 99999}

        if '@' in str(tid):
            return self._folderContent(tid, pg)

        if tid in ('actor', 'studio', 'category'):
            default_sort = {'actor': 'by_likes', 'studio': 'by_likes', 'category': 'by_likes'}[tid]
            sort = extend.get('sort', default_sort)
            entry_url = {'actor': '/actors/', 'studio': '/studios/', 'category': '/categories/'}[tid]
            url = HOST + entry_url + '?sort=' + sort + ('&page=' + str(pg) if pg > 1 else '')
            html = self._get(url)
            items = self._parse_channel_cards(html, tid)
            return {'list': items, 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 99999}

        return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 18, 'total': 0}

    def _folderContent(self, tid, pg):
        kind, _, sub = str(tid).rstrip('@').partition('|')
        url = HOST + '/' + kind + '/' + sub + '/?sort=created_at' + ('&page=' + str(pg) if pg > 1 else '')
        html = self._get(url)
        items = self._parse_films(html)
        return {'list': items, 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 99999}

    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else HOST + vid
        html = self._get(url)
        name = re.search(r'<h1 class="title-inside" itemprop="name">([^<]+)</h1>', html)
        img = re.search(r'<meta itemprop="image"[^>]*content="([^"]+)"', html)
        if not img:
            img = re.search(r'<img[^>]*itemprop="image"[^>]*src="([^"]+)"', html)
        vod_play_url = ''
        vod_play_from = 'ParadiseHill'
        m = re.search(r'var videoList\s*=\s*(\[.*?\])\s*;', html, re.S)
        if m:
            arr_txt = m.group(1)
            srcs = re.findall(r'"src"\s*:\s*"([^"]+)"', arr_txt)
            if not srcs:
                srcs = re.findall(r'https?://[^\s"\\]+\.mp4', arr_txt)
            urls = []
            for i, s in enumerate(srcs, 1):
                s = s.replace('\\/', '/')
                urls.append('Part ' + str(i) + '$' + s)
            vod_play_url = '#'.join(urls)
        title = name.group(1).strip() if name else '未知'
        pic = ''
        if img:
            pic = img.group(1).replace('\\/', '/')
            if pic.startswith('/'):
                pic = HOST + pic
            pic = self._proxy_img(pic)
        return {'list': [{
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': '',
            'vod_play_from': vod_play_from,
            'vod_play_url': vod_play_url,
        }]}

    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        url = HOST + '/search/?pattern=' + quote(key) + '&what=1&page=' + str(pg)
        html = self._get(url)
        items = self._parse_films(html)
        return {'list': items, 'page': pg, 'pagecount': 9999, 'limit': 18, 'total': 99999}

    def playerContent(self, flag, id, vipFlags=None):
        return {
            'parse': 0,
            'playUrl': '',
            'url': id,
            'header': '',
        }

    PROXY_TYPE = 'img'

    def _ensure_proxy_prefix(self):
        if not hasattr(self, '_proxy_prefix') or not self._proxy_prefix:
            base = self.getProxyUrl() or 'http://127.0.0.1:9980/proxy?do=py'
            self._proxy_prefix = base + '&type=' + self.PROXY_TYPE + '&url='

    def _proxy_img(self, url):
        if not url:
            return ''
        self._ensure_proxy_prefix()
        return self._proxy_prefix + quote(url, safe='')

    def localProxy(self, params):
        try:
            if params.get('type') != self.PROXY_TYPE:
                return [404, 'text/plain', 'not found']
            img_url = params.get('url', '')
            if not img_url:
                return [400, 'text/plain', 'missing url']
            img_url = unquote(img_url)
            _u = urlparse(img_url)
            _img_headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': '{s}://{n}/'.format(s=_u.scheme, n=_u.netloc),
            }
            r = requests.get(img_url, headers=_img_headers, timeout=TIMEOUT, verify=False)
            if r.status_code != 200:
                return [404, 'text/plain', 'image not found']
            data = r.content
            mime = r.headers.get('Content-Type', 'image/jpeg')
            if data[:2] == b'\xff\xd8':
                return [200, 'image/jpeg', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'\x89PNG':
                return [200, 'image/png', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return [200, 'image/webp', data, {'Content-Length': str(len(data))}]
            elif mime.startswith('image/'):
                return [200, mime, data, {'Content-Length': str(len(data))}]
            return [404, 'text/plain', 'invalid image format']
        except Exception:
            return [500, 'text/plain', 'proxy error']

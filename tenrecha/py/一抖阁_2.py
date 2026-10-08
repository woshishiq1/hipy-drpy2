"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '一抖阁',
  lang: 'hipy',
})
"""

import re
import json
import html
from urllib.parse import urljoin, quote, unquote

try:
    import requests
except Exception:
    requests = None


class Spider:
    host = 'https://yidouge.com'
    ua = 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    def __init__(self, *args, **kwargs):
        self.t4_api = kwargs.get('t4_api', '')
        self.extend = ''
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update({
                'User-Agent': self.ua,
                'Referer': self.host + '/'
            })

    def init(self, extend=''):
        self.extend = extend
        return '{}'

    def getName(self):
        return '一抖阁'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.s:
            self.s.close()

    def _get(self, url):
        if self.s:
            r = self.s.get(url, timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        from urllib.request import Request, urlopen
        return urlopen(Request(url, headers={'User-Agent': self.ua, 'Referer': self.host + '/'}), timeout=20).read().decode('utf-8', 'ignore')

    def _clean(self, s):
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()

    def _href(self, h):
        return urljoin(self.host, html.unescape(h or '').replace('\\/', '/'))

    def _pic(self, block):
        m = re.search(r'(?:data-src|data-lazy-src|src)=["\']([^"\']+)', block, re.I)
        return self._href(m.group(1)) if m else ''

    def _items(self, text):
        out, seen = [], set()
        blocks = re.findall(r'<article[^>]+class=["\'][^"\']*video-card[^"\']*["\'].*?</article>', text, re.I | re.S)
        for b in blocks:
            hm = re.search(r'<a[^>]+href=["\']([^"\']*(?:/video/|/creator/)[^"\']*)["\'][^>]*(?:aria-label=["\']([^"\']+)["\'])?', b, re.I)
            if not hm:
                hm = re.search(r'<a[^>]+href=["\']([^"\']*(?:/video/|/creator/)[^"\']*)["\']', b, re.I)
            if not hm:
                continue
            u = self._href(hm.group(1))
            if u in seen:
                continue
            title = self._clean(hm.group(2) if len(hm.groups()) > 1 and hm.group(2) else '')
            if not title:
                z = re.search(r'class=["\'][^"\']*(?:video-card__title|ydg-author-collection-title)[^"\']*["\'][^>]*>(.*?)</', b, re.I | re.S)
                title = self._clean(z.group(1)) if z else ''
            if not title:
                z = re.search(r'<img[^>]+alt=["\']([^"\']+)', b, re.I)
                title = self._clean(z.group(1)) if z else unquote(u.rstrip('/').split('/')[-1])
            pic = self._pic(b)
            rm = re.search(r'class=["\'][^"\']*(?:video-card__duration)[^"\']*["\'][^>]*>(.*?)</', b, re.I | re.S)
            remark = self._clean(rm.group(1)) if rm else ''
            out.append({'vod_id': u, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remark})
            seen.add(u)
        return out

    def homeContent(self, filter=None):
        cats = [
            {'type_id': self.host + '/v2/ai%E7%9F%AD%E5%89%A7/', 'type_name': 'AI短剧'},
            {'type_id': self.host + '/v2/%E7%BB%BF%E5%B8%BDntr/', 'type_name': '伦理绿帽NTR'},
            {'type_id': self.host + '/v2/%E9%83%BD%E5%B8%82/', 'type_name': '现代'},
            {'type_id': self.host + '/v2/%E5%8F%A4%E8%A3%85/', 'type_name': '古装'},
            {'type_id': self.host + '/v2/pmv/', 'type_name': 'PMV'},
        ]
        return {'class': cats, 'filters': {}}

    def homeVideoContent(self):
        t = self._get(self.host)
        return {'list': self._items(t)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        u = tid if str(tid).startswith('http') else self._href(str(tid))
        u = u.rstrip('/') + ('/' if '/page/' not in u else '')
        if str(pg) != '1':
            u = u.rstrip('/') + '/page/' + str(pg) + '/'
        t = self._get(u)
        items = self._items(t)
        return {'page': int(pg), 'pagecount': 999, 'limit': len(items), 'total': 999999, 'list': items}

    def searchContent(self, key, quick=False, pg='1'):
        u = self.host + '/?s=' + quote(str(key))
        if str(pg) != '1':
            u += '&paged=' + str(pg)
        t = self._get(u)
        items = self._items(t)
        return {'page': int(pg), 'pagecount': 999, 'limit': len(items), 'total': 999999, 'list': items}

    def detailContent(self, ids):
        u = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        u = self._href(u)
        t = self._get(u)
        if '/creator/' in u:
            items = self._items(t)
            eps = []
            for i, x in enumerate(items, 1):
                if '/video/' not in x['vod_id']:
                    continue
                name = x['vod_name'] or ('第%d集' % i)
                eps.append(name + '$' + x['vod_id'])
            title = ''
            m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.I | re.S)
            if m:
                title = self._clean(m.group(1))
            if not title:
                title = unquote(u.rstrip('/').split('/')[-1])
            return {'list': [{'vod_id': u, 'vod_name': title, 'vod_pic': items[0].get('vod_pic', '') if items else '', 'vod_content': '', 'vod_play_from': '一抖阁', 'vod_play_url': '#'.join(eps)}]}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.I | re.S)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>(.*?)</title>', t, re.I | re.S)
            title = self._clean(m.group(1)).split(' - ')[0] if m else unquote(u.rstrip('/').split('/')[-1])
        
        pm = re.search(r'data-video-poster=["\']([^"\']+)', t, re.I)
        if not pm:
            pm = re.search(r'<video[^>]+poster=["\']([^"\']+)', t, re.I)
        pic = self._href(pm.group(1)) if pm else ''
        
        return {'list': [{'vod_id': u, 'vod_name': title, 'vod_pic': pic, 'vod_content': '', 'vod_play_from': '一抖阁', 'vod_play_url': '正片$' + u}]}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        # 如果传入的是网页链接，先请求页面提取真实的视频文件 (mp4 / m3u8)
        if str(url).startswith('http') and ('/video/' in url or not re.search(r'\.(?:mp4|m3u8|flv|m4v)', url, re.I)):
            try:
                t = self._get(url)
                vm = re.search(r'data-video-url=["\']([^"\']+)', t, re.I)
                if not vm:
                    vm = re.search(r'<video[^>]+src=["\']([^"\']+)', t, re.I)
                if not vm:
                    vm = re.search(r'<source[^>]+src=["\']([^"\']+)', t, re.I)
                if not vm:
                    vm = re.search(r'["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', t, re.I)
                if vm:
                    url = self._href(vm.group(1))
            except Exception:
                pass

        return {
            'parse': 0,
            'jx': 0,
            'playUrl': '',
            'url': url,
            'header': {
                'User-Agent': self.ua,
                'Referer': self.host + '/'
            }
        }

    def localProxy(self, param):
        return [404, 'text/plain', b'', {}]

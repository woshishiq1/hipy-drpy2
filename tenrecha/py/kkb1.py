# -*- coding: utf-8 -*-
import json
import re
from html import unescape
from urllib.parse import quote, urljoin

import requests
from base.spider import Spider


class Spider(Spider):
    host = 'https://kkb1.sixniceezsx.xyz'
    searchable = True
    filterable = False
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
        'Referer': 'https://kkb1.sixniceezsx.xyz/',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def getName(self):
        return 'kkb1'

    def init(self, extend=''):
        return None

    def _get(self, url, ref=None):
        headers = dict(self.headers)
        if ref:
            headers['Referer'] = ref
        try:
            r = self.session.get(urljoin(self.host + '/', url), headers=headers, timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except Exception:
            return ''

    def _clean(self, value):
        return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', value or ''))).strip()

    def _pic(self, value):
        value = (value or '').strip()
        if value.startswith('//'):
            return 'https:' + value
        return urljoin(self.host + '/', value)

    def _extend(self, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        return extend if isinstance(extend, dict) else {}

    def homeContent(self, filter):
        html = self._get('/')
        classes = []
        seen = set()
        pat = r'<a[^>]+href=["\']([^"\']*/index\.php/vod/type/id/\d+\.html)["\'][^>]*>(.*?)</a>'
        for href, name in re.findall(pat, html, re.I | re.S):
            tid = re.search(r'/id/(\d+)\.html', href)
            if not tid:
                continue
            tid = tid.group(1)
            name = self._clean(name)
            if name and tid not in seen and len(name) < 40:
                seen.add(tid)
                classes.append({'type_id': tid, 'type_name': name})
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        return self.categoryContent('6', 1, {}, {})

    def _list(self, html, pg):
        result = {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 0}
        seen = set()
        pat = r'<a[^>]+href=["\']([^"\']*/index\.php/vod/detail/id/(\d+)\.html)[^>]*>\s*<img[^>]+(?:data-original|src)=["\']([^"\']+)["\'][^>]*>.*?</a>.*?<h5>\s*<a[^>]+title=["\']([^"\']+)["\'][^>]*>.*?</a>\s*</h5>\s*<p>(.*?)</p>'
        for href, vid, pic, title, remark in re.findall(pat, html, re.I | re.S):
            if vid in seen:
                continue
            seen.add(vid)
            result['list'].append({
                'vod_id': vid,
                'vod_name': self._clean(title),
                'vod_pic': self._pic(pic),
                'vod_remarks': self._clean(remark),
            })
        if not result['list']:
            fallback = r'href=["\']([^"\']*/index\.php/vod/detail/id/(\d+)\.html)["\'][^>]*.*?title=["\']([^"\']+)["\']'
            for href, vid, title in re.findall(fallback, html, re.I | re.S):
                if vid not in seen:
                    seen.add(vid)
                    result['list'].append({'vod_id': vid, 'vod_name': self._clean(title), 'vod_pic': '', 'vod_remarks': ''})
        nums = re.findall(r'(?:page|id)/(\d+)\.html', html, re.I)
        if nums:
            result['pagecount'] = max(int(x) for x in nums)
        result['total'] = len(result['list'])
        return result

    def categoryContent(self, tid, pg, filter=None, extend=None):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        # 实测路径为 /index.php/vod/type/id/7.html；分页采用 page/N.html
        url = '/index.php/vod/type/id/%s.html' % tid
        if pg > 1:
            url = '/index.php/vod/type/id/%s/page/%s.html' % (tid, pg)
        return self._list(self._get(url), pg)

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid).strip()
        html = self._get('/index.php/vod/detail/id/%s.html' % vid)
        title = ''
        m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        if m:
            title = self._clean(m.group(1)).replace('-儿子上穴', '').strip()
        pic = ''
        m = re.search(r'<div class=["\']detail-poster["\'].*?<img[^>]+(?:data-original|src)=["\']([^"\']+)', html, re.I | re.S)
        if m:
            pic = self._pic(m.group(1))
        play = '/index.php/vod/play/id/%s/sid/1/nid/1.html' % vid
        play_html = self._get(play, self.host + '/index.php/vod/detail/id/%s.html' % vid)
        urls = []
        for raw in re.findall(r'var\s+player_data\s*=\s*(\{.*?\})\s*</script>', play_html, re.I | re.S):
            try:
                data = json.loads(raw)
                if data.get('url'):
                    urls.append((data.get('from') or '播放', data['url']))
            except Exception:
                pass
        if not urls:
            m = re.search(r'"url"\s*:\s*"(https?:\\?/\\?/[^"\\]+)', play_html, re.I)
            if m:
                urls.append(('播放', m.group(1).replace('\\/', '/')))
        if not title:
            title = vid
        return {'list': [{
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': '',
            'vod_play_from': '$$$'.join(x[0] for x in urls) if urls else '播放',
            'vod_play_url': '$$$'.join('播放$' + x[1] for x in urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        real = str(id).split('$', 1)[1] if '$' in str(id) else str(id)
        return {
            'parse': 0,
            'playUrl': '',
            'url': real,
            'header': json.dumps({
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            }),
        }

    def searchContent(self, key, quick, pg=1):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        url = '/index.php/vod/search.html?wd=' + quote(str(key))
        if pg > 1:
            url += '&page=%s' % pg
        return self._list(self._get(url), pg)

    def isVideoFormat(self, url):
        return any(x in str(url).lower() for x in ('.m3u8', '.mp4', '.mkv', '.flv'))

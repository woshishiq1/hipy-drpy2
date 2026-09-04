# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import urllib.parse
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            t = kw.pop('timeout', 20)
            r = requests.get(url, headers=headers, timeout=t, verify=False, **kw)
            r.encoding = 'utf-8'
            return r

_API = 'http://sekihfde.com/api'
_PLAY_UUID = '724b9c9fdd5e7b6f'
_CATS = {'t': 0, 'list': []}
_ITEM_PIC = {}
_FALLBACK = [
    ('58', '热播电影'), ('56', '小编推荐'), ('51', '国产AV'), ('10', '国产精品'), ('57', '黑料特爆'),
    ('53', '网红主播'), ('16', '欧美激情'), ('25', '三级电影'), ('14', 'H动漫'), ('41', '高清无码'),
    ('54', 'AV解说'), ('40', '美乳巨乳'), ('39', 'AV剧情'), ('36', '淫欲痴女'), ('35', '人妻熟女'),
    ('9', '绝色佳人'), ('46', '师生不伦'), ('38', '风俗按摩'), ('43', '家庭乱伦'), ('47', '绝顶痉挛'),
    ('42', '少女萝莉'), ('37', '制服丝袜'), ('44', '痴汉轮奸'), ('50', '女同性爱'), ('55', '恐怖系列'),
]


class Spider(Spider):
    host = 'http://sekihfde.com'
    ua = 'ok'
    classes = [{'type_name': n, 'type_id': i} for i, n in _FALLBACK]
    filters = {}

    def init(self, extend=''):
        pass

    def _get(self, u, timeout=10):
        for i in range(2):
            try:
                r = requests.get(u, headers={'User-Agent': self.ua}, timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                pass
            time.sleep(0.5)
        return ''

    def _cats(self):
        global _CATS
        if time.time() - _CATS['t'] > 3600 or not _CATS['list']:
            h = self._get(_API + '/videosort')
            try:
                j = json.loads(h or '')
                _CATS['list'] = [{'type_id': str(c['id']), 'type_name': c['name']} for c in j.get('rescont', [])]
                _CATS['t'] = time.time()
            except Exception:
                pass
        return _CATS['list'] or self.classes

    def _items(self, h):
        out = []
        try:
            j = json.loads(h or '')
            rc = j.get('rescont')
            data = rc.get('data') if isinstance(rc, dict) else rc
            if not isinstance(data, list):
                return out
            for it in data:
                _ITEM_PIC[str(it.get('id', ''))] = it.get('coverpath', '') or ''
                out.append({'vod_id': str(it.get('id', '')), 'vod_name': it.get('title', '') or '', 'vod_pic': it.get('coverpath', '') or '', 'vod_remarks': it.get('authername', '') or ''})
        except Exception:
            pass
        return out

    def _page(self, h):
        try:
            j = json.loads(h or '')
            rc = j.get('rescont')
            if isinstance(rc, dict):
                return int(rc.get('last_page') or 1), int(rc.get('total') or 0)
        except Exception:
            pass
        return 1, 0

    def getName(self):
        return '采花大盗'

    def isVideoFormat(self, u):
        return any(x in u for x in ('.m3u8', '.mp4', '.flv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter=False):
        return {'class': self._cats(), 'filters': self.filters, 'list': []}

    def homeVideoContent(self):
        h = self._get('%s/videosort/58?orderby=new&page=1' % _API)
        return {'list': self._items(h) if h else []}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        pg = int(pg or 1)
        h = self._get('%s/videosort/%s?orderby=new&page=%d' % (_API, tid, pg))
        if not h:
            return {'page': pg, 'pagecount': 1, 'limit': 15, 'total': 0, 'list': []}
        pc, total = self._page(h)
        return {'page': pg, 'pagecount': pc, 'limit': 15, 'total': total, 'list': self._items(h)}

    def detailContent(self, ids):
        vid = str(ids[0])
        h = self._get('%s/videoplay/%s?uuid=%s' % (_API, vid, _PLAY_UUID))
        name = ''
        try:
            j = json.loads(h or '')
            rc = j.get('rescont') or {}
            name = rc.get('title', '') or ''
        except Exception:
            pass
        vod = {'vod_id': vid, 'vod_name': name, 'vod_pic': _ITEM_PIC.get(vid, ''), 'vod_remarks': '', 'vod_play_from': '线路1', 'vod_play_url': '第1集$%s/videoplay/%s?uuid=%s' % (_API, vid, _PLAY_UUID)}
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        h = self._get('%s/videosort/0?page=%s&serach=%s' % (_API, str(pg), urllib.parse.quote(key, safe='')))
        if not h:
            return {'page': int(pg or 1), 'pagecount': 1, 'limit': 15, 'total': 0, 'list': []}
        pc, total = self._page(h)
        return {'page': int(pg or 1), 'pagecount': pc, 'limit': 15, 'total': total, 'list': self._items(h)}

    def playerContent(self, flag, id, vipFlags=None):
        h = self._get(str(id))
        vp = ''
        try:
            j = json.loads(h or '')
            vp = (j.get('rescont') or {}).get('videopath', '') or ''
        except Exception:
            pass
        url = vp if vp.startswith('http') else ('http://sekihfde.com/api/index.m3u8?m3u8=' + vp if vp else '')
        return {'parse': 0, 'url': url, 'header': {'User-Agent': self.ua}}

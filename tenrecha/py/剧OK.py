# -*- coding: utf-8 -*-
import base64
import json
import re
import sys
import time
from urllib.parse import quote

import requests

sys.path.append('/root/.openclaw/workspace')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    host = 'https://juok3.top'
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    cats = {'movie': 1, 'tv': 2, 'variety': 3, 'anime': 4}
    cat_names = {'movie': '电影', 'tv': '电视剧', 'variety': '综艺', 'anime': '动漫'}
    site_names = {'qq': '腾讯', 'qiyi': '爱奇艺', 'youku': '优酷', 'mgtv': '芒果', 'bilibili': '哔哩哔哩', 'sohu': '搜狐'}

    def init(self, extend=''):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'Referer': self.host + '/'
        })
        self.timeout = (5, 15)
        # 先获取 cookie
        try:
            self.session.get(self.host + '/api/filter?catId=1&page=1&size=1', timeout=self.timeout)
        except:
            pass

    def getName(self):
        return '剧OK'

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|mp3|flac|m4a)(?:\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=False):
        classes = [{'type_name': self.cat_names[k], 'type_id': k} for k in self.cats]
        result = {'class': classes}
        if filter:
            result['filters'] = {
                'movie': [
                    {'key': 'type', 'name': '类型', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'area', 'name': '地区', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'year', 'name': '年份', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'sort', 'name': '排序', 'value': [
                        {'n': '最近更新', 'v': 'ranklatest'},
                        {'n': '热播优先', 'v': 'rankhot'}
                    ]}
                ],
                'tv': [
                    {'key': 'type', 'name': '类型', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'area', 'name': '地区', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'year', 'name': '年份', 'value': [{'n': '全部', 'v': ''}]},
                    {'key': 'sort', 'name': '排序', 'value': [
                        {'n': '最近更新', 'v': 'ranklatest'},
                        {'n': '热播优先', 'v': 'rankhot'}
                    ]}
                ]
            }
        return result

    def homeVideoContent(self):
        videos = []
        for key in ('movie', 'tv'):
            data = self._filter(key, 1, {}, 8)
            videos.extend(self._movie_cards(data.get('movies') or []))
        return {'list': videos[:20]}

    def categoryContent(self, tid, pg='1', filt=False, ext={}):
        page = max(int(pg), 1)
        if tid in self.cats:
            data = self._filter(tid, page, ext, 20)
            total = int(data.get('total', 0)) or len(data.get('movies') or [])
            return {
                'list': self._movie_cards(data.get('movies') or [], tid),
                'page': page,
                'pagecount': max(1, (total + 19) // 20),
                'limit': 20,
                'total': total
            }
        return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        meta = self._decode(ids[0])
        cat = str(meta.get('c') or '')
        ent_id = str(meta.get('i') or '')
        if cat not in self.cats or not ent_id:
            return {'list': []}
        raw = self._get('/api/detail', {'cat': self.cats[cat], 'id': ent_id})
        data = raw.get('data') or {}
        if not data:
            return {'list': []}
        sources, playlists = [], []
        playlinksdetail = data.get('playlinksdetail') or {}
        for site in playlinksdetail:
            url = playlinksdetail[site].get('default_url') or ''
            if not url:
                continue
            play = self._encode({'k': 'video', 'u': url, 'c': cat, 'i': ent_id, 's': site, 't': data.get('title') or ''})
            sources.append(self.site_names.get(site, site))
            playlists.append(f'正片${play}')
        if not sources:
            playlinks = data.get('playlinks') or {}
            for site, url in playlinks.items():
                if not url:
                    continue
                play = self._encode({'k': 'video', 'u': url, 'c': cat, 'i': ent_id, 's': site, 't': data.get('title') or ''})
                sources.append(self.site_names.get(site, site))
                playlists.append(f'正片${play}')
        cover = data.get('cdncover') or meta.get('p') or ''
        if cover and not cover.startswith('http'):
            cover = 'https:' + cover if cover.startswith('//') else 'https://' + cover
        vod = {
            'vod_id': ids[0],
            'vod_name': data.get('title') or meta.get('n') or '',
            'vod_pic': cover,
            'type_name': ' / '.join(data.get('moviecategory') or []),
            'vod_year': str(data.get('pubdate') or '')[:4],
            'vod_area': ' / '.join(data.get('area') or []),
            'vod_actor': ' / '.join(data.get('actor') or []),
            'vod_director': ' / '.join(data.get('director') or []),
            'vod_content': data.get('description') or '',
            'vod_play_from': '$$$'.join(sources),
            'vod_play_url': '$$$'.join(playlists)
        }
        return {'list': [vod]}

    def playerContent(self, flag, pid, vipFlags):
        meta = self._decode(pid)
        url = str(meta.get('u') or pid or '')
        if not url:
            return {'parse': 0, 'url': ''}
        direct = self._resolve_video(url, meta)
        if direct:
            return {'parse': 0, 'jx': 0, 'url': direct, 'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': 'https://jx.xmflv.com/?url=' + quote(url, safe=''), 'header': {'User-Agent': self.ua, 'Referer': 'https://jx.xmflv.com/'}}

    def searchContent(self, key, quick=False, pg='1'):
        page = max(int(pg), 1)
        raw = self._get('/api/search', {'q': key, 'page': page})
        rows = raw.get('results') or []
        videos = []
        for row in rows:
            cat_num = int(row.get('cat_id') or 1)
            cat = next((k for k, v in self.cats.items() if v == cat_num), 'movie')
            ent_id = row.get('en_id') or row.get('id') or ''
            title = self._strip_html(row.get('titleTxt') or row.get('title') or '')
            cover = row.get('cover') or row.get('cdncover') or ''
            if cover and not cover.startswith('http'):
                cover = 'https:' + cover if cover.startswith('//') else 'https://' + cover
            videos.append({
                'vod_id': self._encode({'k': 'vod', 'c': cat, 'i': ent_id, 'n': title, 'p': cover}),
                'vod_name': title,
                'vod_pic': cover,
                'vod_remarks': str(row.get('year') or '')
            })
        return {'list': videos, 'page': page, 'pagecount': 1, 'limit': 20, 'total': len(videos)}

    def localProxy(self, params):
        return None

    # --------------------------- 内部方法 ---------------------------
    def _filter(self, cat, page, ext, size):
        params = {'catId': self.cats[cat], 'page': page, 'size': size}
        for key in ('type', 'area', 'year', 'sort'):
            val = str(ext.get(key) or '').strip()
            if val and val != '全部':
                params[key] = val
        return self._get('/api/filter', params)

    def _resolve_video(self, play_url, meta=None):
        meta = meta or {}
        referer = f'{self.host}/play/{meta.get("c", 1)}/{meta.get("i", "tvbox")}/1?s={meta.get("s", "")}'
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'Referer': referer,
            'Origin': self.host
        })
        try:
            r = session.get(self.host + '/api/player/token', timeout=(5, 15))
            token = r.json() if r.status_code == 200 else {}
            body = {
                'playUrl': play_url,
                'statVodId': str(meta.get('i') or ''),
                'statSource': str(meta.get('s') or ''),
                'statVodName': str(meta.get('t') or '')
            }
            if not token.get('disabled'):
                body.update({'nonce': token.get('nonce') or '', 'timestamp': token.get('timestamp') or 0, 'sig': token.get('sig') or ''})
            for _ in range(2):
                r = session.post(self.host + '/api/player/resolve', json=body,
                    headers={'X-Player-Request': '1', 'Content-Type': 'application/json'}, timeout=(6, 35))
                data = r.json() if r.status_code == 200 else {}
                if data.get('success') and data.get('mode') == 'direct':
                    direct = str(data.get('url') or '')
                    if direct.startswith(('http://', 'https://')):
                        return direct
                    encrypted = data.get('encrypted')
                    if encrypted:
                        r2 = session.post(self.host + '/api/player/decrypt', json={'encrypted': encrypted, 'nonce': token.get('nonce') or ''},
                            headers={'X-Player-Request': '1', 'Content-Type': 'application/json'}, timeout=(5, 20))
                        d2 = r2.json() if r2.status_code == 200 else {}
                        direct = str(d2.get('url') or '')
                        if direct.startswith(('http://', 'https://')):
                            return direct
        except:
            pass
        return ''

    def _get(self, path, params=None):
        for _ in range(2):
            try:
                r = self.session.get(self.host + path, params=params or {}, timeout=self.timeout)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        return data
            except:
                continue
        return {}

    def _movie_cards(self, rows, cat='movie'):
        result = []
        for row in rows:
            ent_id = row.get('ent_id') or row.get('en_id') or row.get('id')
            title = str(row.get('title') or row.get('titleTxt') or '')
            if not ent_id or not title:
                continue
            pic = row.get('cdncover') or row.get('cover') or ''
            if pic and not pic.startswith('http'):
                pic = 'https:' + pic if pic.startswith('//') else 'https://' + pic
            remarks = row.get('comment') or row.get('upinfo') or row.get('pubdate') or ''
            result.append({
                'vod_id': self._encode({'k': 'vod', 'c': cat, 'i': ent_id, 'n': title, 'p': pic}),
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': str(remarks)
            })
        return result

    @staticmethod
    def _encode(value):
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    @staticmethod
    def _decode(value):
        try:
            raw = base64.urlsafe_b64decode(str(value) + '=' * (-len(str(value)) % 4))
            data = json.loads(raw.decode('utf-8'))
            return data if isinstance(data, dict) else {}
        except:
            return {}

    @staticmethod
    def _strip_html(value):
        return re.sub(r'<[^>]+>', '', str(value or '')).replace('&nbsp;', ' ').strip()

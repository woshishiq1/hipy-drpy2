#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import re
import sys
import time
import urllib.parse
import uuid

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = None
    unpad = None

try:
    import requests
except ImportError:
    requests = None

sys.path.append('../../')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://mh.yichengwlkj.com'
        self.api = 'https://api.rrmj.plus'
        self.origin = 'https://rrsp.com.cn'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.sign_secret = 'ES513W0B1CsdUrR13Qk5EgDAKPeeKZY'
        self.aes_key = b'3b744389882a4067'
        self.play_iv = b'b1da7878016e4e2b'
        self.ct = 'web_pc'
        self.cv = '1.0.0'
        self.device_id = '4E292B5D-FE99-4860-8054-5B0A11CC27AF'
        self.vip_token = ''
        self.channels = {
            'MOVIE|': {'name': '电影', 'dramaType': 'MOVIE', 'area': ''},
            'TV|': {'name': '电视剧', 'dramaType': 'TV', 'area': ''},
            'TV|美国': {'name': '美剧', 'dramaType': 'TV', 'area': '美国'},
            'TV|韩国': {'name': '韩剧', 'dramaType': 'TV', 'area': '韩国'},
            'TV|日本': {'name': '日剧', 'dramaType': 'TV', 'area': '日本'},
            'TV|英国': {'name': '英剧', 'dramaType': 'TV', 'area': '英国'},
            'TV|泰国': {'name': '泰剧', 'dramaType': 'TV', 'area': '泰国'},
            'SHORT|': {'name': '短剧', 'dramaType': 'SHORT', 'area': ''},
            'VARIETY|': {'name': '综艺', 'dramaType': 'VARIETY', 'area': ''},
            'COMIC|': {'name': '动漫', 'dramaType': 'COMIC', 'area': ''},
            'DOCUMENTARY|': {'name': '纪录片', 'dramaType': 'DOCUMENTARY', 'area': ''},
        }
        self.filters = {
            'MOVIE|': [
                {'key': 'area', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '美国', 'v': '美国'}, {'n': '中国', 'v': '中国'},
                    {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'}, {'n': '英国', 'v': '英国'},
                    {'n': '法国', 'v': '法国'}, {'n': '其他', 'v': '其他'}
                ]},
                {'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最新', 'v': 'new'}, {'n': '热门', 'v': 'hot'}, {'n': '评分', 'v': 'score'}
                ]}
            ],
            'TV|': [
                {'key': 'area', 'name': '地区', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'},
                    {'n': '日本', 'v': '日本'}, {'n': '英国', 'v': '英国'}, {'n': '泰国', 'v': '泰国'},
                    {'n': '中国', 'v': '中国'}
                ]},
                {'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最新', 'v': 'new'}, {'n': '热门', 'v': 'hot'}, {'n': '评分', 'v': 'score'}
                ]}
            ]
        }

    def getName(self):
        return '人人视频'

    def init(self, extend=""):
        try:
            if isinstance(extend, str) and extend.strip().startswith('rrtv-'):
                self.vip_token = extend.strip()
            elif extend:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                self.vip_token = str(ext.get('token') or ext.get('vipToken') or '')
                if ext.get('deviceId'):
                    self.device_id = str(ext.get('deviceId'))
        except Exception:
            pass
        if not self.device_id:
            self.device_id = str(uuid.uuid4()).upper()

    def _pathname(self, url):
        p = urllib.parse.urlparse(url)
        return p.path or '/'

    def _sorted_qs(self, params):
        params = params or {}
        items = []
        for k in sorted(params.keys()):
            v = params[k]
            if isinstance(v, bool):
                v = 'true' if v else 'false'
            elif v is None:
                v = ''
            else:
                v = str(v)
            items.append('%s=%s' % (urllib.parse.quote(str(k), safe=''), urllib.parse.quote(v, safe='')))
        return '&'.join(items)

    def _sign(self, method, pathname, qs, ts):
        sign_str = '%s\naliId:%s\nct:%s\ncv:%s\nt:%s\n%s?%s' % (
            (method or 'GET').upper(), self.device_id, self.ct, self.cv, ts, pathname, qs or ''
        )
        digest = hmac.new(self.sign_secret.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha256).digest()
        return base64.b64encode(digest).decode('ascii')

    def _headers(self, method, url, params=None, token=''):
        ts = str(int(time.time() * 1000))
        qs = self._sorted_qs(params or {})
        return {
            'User-Agent': self.userAgent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': self.origin,
            'Referer': self.origin + '/',
            'clientType': self.ct,
            'clientVersion': self.cv,
            'aliId': self.device_id,
            'deviceId': self.device_id,
            'umid': self.device_id,
            'ct': self.ct,
            'cv': self.cv,
            't': ts,
            'uet': '9',
            'token': token or self.vip_token or '',
            'x-ca-sign': self._sign(method, self._pathname(url), qs, ts),
        }

    def _aes_ecb(self, raw):
        if not AES or not raw:
            return ''
        try:
            data = base64.b64decode(raw.strip())
            cipher = AES.new(self.aes_key, AES.MODE_ECB)
            pt = cipher.decrypt(data)
            if unpad:
                pt = unpad(pt, 16)
            else:
                pt = pt[:-pt[-1]]
            return pt.decode('utf-8', 'ignore')
        except Exception:
            return ''

    def _aes_cbc_play(self, enc_url, new_sign):
        if not AES or not enc_url:
            return ''
        try:
            sign = str(new_sign or '')
            key_str = sign[4:20] if len(sign) >= 20 else sign
            if len(key_str) < 16:
                return ''
            data = base64.b64decode(enc_url.strip())
            cipher = AES.new(key_str.encode('utf-8')[:16], AES.MODE_CBC, self.play_iv)
            pt = cipher.decrypt(data)
            if unpad:
                pt = unpad(pt, 16)
            else:
                pt = pt[:-pt[-1]]
            return pt.decode('utf-8', 'ignore')
        except Exception:
            return ''

    def fetch(self, url, headers=None, params=None, method='GET', body=None):
        if headers is None:
            headers = {'User-Agent': self.userAgent}
        try:
            if requests:
                if method == 'POST':
                    resp = requests.post(url, headers=headers, json=body or {}, timeout=15)
                else:
                    resp = requests.get(url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            if method == 'POST':
                data = json.dumps(body or {}).encode('utf-8')
                from urllib.request import Request, urlopen
                req = Request(url, data=data, headers=headers, method='POST')
            else:
                full = url
                if params:
                    full += ('&' if '?' in url else '?') + self._sorted_qs(params)
                from urllib.request import Request, urlopen
                req = Request(full, headers=headers)
            raw = urlopen(req, timeout=15).read()

            class R:
                def __init__(self, raw):
                    self.content = raw
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def _unwrap(self, raw):
        if raw is None:
            return {}
        if isinstance(raw, dict):
            data = raw.get('data')
            if isinstance(data, str) and len(data) > 20 and not data.startswith('http'):
                dec = self._aes_ecb(data)
                try:
                    j = json.loads(dec) if dec else None
                    if j:
                        return j if isinstance(j, dict) else {'data': j}
                except Exception:
                    pass
            return raw
        if isinstance(raw, str):
            try:
                return self._unwrap(json.loads(raw))
            except Exception:
                dec = self._aes_ecb(raw)
                if dec:
                    try:
                        return self._unwrap(json.loads(dec))
                    except Exception:
                        return {}
        return {}

    def api_get(self, path, params=None, token=''):
        url = self.api + path
        headers = self._headers('GET', url, params or {}, token)
        resp = self.fetch(url, headers=headers, params=params)
        if not resp:
            return {}
        try:
            return self._unwrap(resp.json())
        except Exception:
            return self._unwrap(getattr(resp, 'text', ''))

    def api_post(self, path, body=None, token=''):
        url = self.api + path
        headers = self._headers('POST', url, {}, token)
        headers['Content-Type'] = 'application/json'
        resp = self.fetch(url, headers=headers, method='POST', body=body or {})
        if not resp:
            return {}
        try:
            return self._unwrap(resp.json())
        except Exception:
            return self._unwrap(getattr(resp, 'text', ''))

    def _pick_list(self, payload):
        d = (payload or {}).get('data', payload) or {}
        if isinstance(d, list):
            return d
        for k in ('data', 'list', 'searchDramaList', 'results'):
            if isinstance(d.get(k), list):
                return d.get(k)
        return []

    def _map_vod(self, e):
        if not e:
            return None
        vid = e.get('dramaId') or e.get('id') or e.get('sid')
        if not vid:
            return None
        return {
            'vod_id': str(vid),
            'vod_name': e.get('title') or e.get('name') or e.get('dramaName') or '',
            'vod_pic': e.get('coverUrl') or e.get('cover') or e.get('poster') or e.get('pic') or '',
            'vod_remarks': e.get('subtitle') or e.get('cornerMark') or e.get('upInfo') or e.get('score') or '',
        }

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        filters = {}
        if filter:
            for k in self.channels:
                filters[k] = self.filters.get(k) or self.filters.get('TV|')
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        videos = []
        try:
            payload = self.api_post('/m-station/drama/drama_filter_search', {
                'area': '', 'sort': 'hot', 'year': '', 'dramaType': 'TV',
                'plotType': '', 'contentLabel': '', 'page': 1, 'rows': 24
            })
            for item in self._pick_list(payload):
                v = self._map_vod(item)
                if v:
                    videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        info = self.channels.get(str(tid), {'dramaType': 'TV', 'area': ''})
        ext = extend or {}
        if isinstance(ext, str):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        drama_type = ext.get('dramaType') or info.get('dramaType') or 'TV'
        area = ext.get('area') if ext.get('area') is not None else info.get('area', '')
        sort = ext.get('sort') or 'new'
        try:
            payload = self.api_post('/m-station/drama/drama_filter_search', {
                'area': area or '',
                'sort': sort,
                'year': ext.get('year') or '',
                'dramaType': drama_type,
                'plotType': ext.get('plotType') or '',
                'contentLabel': ext.get('contentLabel') or '',
                'page': pg,
                'rows': 30
            })
            for item in self._pick_list(payload):
                v = self._map_vod(item)
                if v:
                    videos.append(v)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 30 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            payload = self.api_get('/m-station/search/drama', {
                'keywords': key,
                'size': 20,
                'order': 'match',
                'search_after': '',
                'isExecuteVipActivity': True
            })
            for item in self._pick_list(payload):
                v = self._map_vod(item)
                if v:
                    videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': 1,
            'limit': 20,
            'total': len(videos),
        }

    def _ep_name(self, e, idx):
        title = str((e or {}).get('title') or '')
        if title and not re.match(r'^\d+$', title):
            return title
        no = (e or {}).get('episodeNo') or (e or {}).get('episode') or (e or {}).get('seq') or idx
        return '第%s集' % no

    def detailContent(self, ids):
        vid = str((ids or [''])[0]).split('|')[0]
        try:
            payload = self.api_get('/m-station/drama/page', {
                'hsdrOpen': 0, 'isAgeLimit': 0, 'dramaId': vid,
                'quality': 'AI4K', 'hevcOpen': 1, 'tria4k': 1
            })
            d = payload.get('data') or payload or {}
            drama = d.get('drama') or d.get('dramaInfo') or d
            episodes = d.get('episodeList') or d.get('episodes') or []
            items = ((d.get('watchInfo') or {}).get('sortedItems')) or d.get('sortedItems') or []
            froms, urls = [], []
            if items:
                for it in items:
                    q = it.get('qualityCode') or it.get('quality') or it.get('name') or '线路'
                    parts = []
                    for i, ep in enumerate(episodes, 1):
                        sid = ep.get('sid') or ep.get('episodeSid') or ep.get('id')
                        if not sid:
                            continue
                        parts.append('%s$%s|%s|%s' % (self._ep_name(ep, i), vid, sid, q))
                    if parts:
                        froms.append(str(q))
                        urls.append('#'.join(parts))
            if not froms:
                q = (items[0].get('qualityCode') or items[0].get('quality')) if items else 'HD'
                parts = []
                for i, ep in enumerate(episodes, 1):
                    sid = ep.get('sid') or ep.get('episodeSid') or ep.get('id')
                    if sid:
                        parts.append('%s$%s|%s|%s' % (self._ep_name(ep, i), vid, sid, q))
                froms.append('人人视频' if parts else '网页')
                urls.append('#'.join(parts) if parts else ('正片$%s' % vid))
            return {
                'list': [{
                    'vod_id': vid,
                    'vod_name': drama.get('title') or drama.get('name') or drama.get('dramaName') or vid,
                    'vod_pic': drama.get('coverUrl') or drama.get('cover') or drama.get('poster') or '',
                    'vod_remarks': drama.get('subtitle') or drama.get('upInfo') or '',
                    'vod_year': drama.get('year') or drama.get('releaseYear') or '',
                    'vod_area': drama.get('areaNameCn') or drama.get('area') or '',
                    'vod_actor': drama.get('actor') or drama.get('actors') or '',
                    'vod_director': drama.get('director') or '',
                    'vod_content': drama.get('brief') or drama.get('intro') or drama.get('summary') or '',
                    'vod_play_from': '$$$'.join(froms),
                    'vod_play_url': '$$$'.join(urls),
                }]
            }
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': [{'vod_id': vid, 'vod_name': vid, 'vod_play_from': '网页', 'vod_play_url': '正片$%s' % vid}]}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.mpd'))

    def playerContent(self, flag, id, vipFlags):
        header = {'User-Agent': self.userAgent, 'Referer': self.origin + '/', 'Origin': self.origin}
        parts = str(id or '').split('|')
        drama_id = parts[0] if parts else ''
        episode_sid = parts[1] if len(parts) > 1 else ''
        quality = parts[2] if len(parts) > 2 else (flag or 'HD')
        if not episode_sid:
            return {'parse': 1, 'jx': '1', 'url': self.siteUrl + '/drama/' + drama_id, 'header': header}
        try:
            payload = self.api_get('/m-station/drama/play', {
                'hsdrOpen': 0, 'dramaId': drama_id, 'episodeSid': episode_sid,
                'quality': quality, 'hevcOpen': 1, 'tria4k': 1
            }, self.vip_token)
            d = payload.get('data') or payload or {}
            play_url = ''
            m3 = d.get('m3u8') or {}
            if m3.get('url'):
                play_url = self._aes_cbc_play(m3.get('url'), d.get('newSign') or m3.get('newSign')) or m3.get('url')
            if not play_url and d.get('url'):
                u = d.get('url')
                play_url = u if self.isVideoFormat(u) else (self._aes_cbc_play(u, d.get('newSign')) or u)
            if not play_url:
                play_url = d.get('playUrl') or ''
            if play_url and play_url.startswith('http'):
                return {'parse': 0 if self.isVideoFormat(play_url) else 1, 'url': play_url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {'parse': 1, 'jx': '1', 'url': self.siteUrl + '/drama/' + drama_id, 'header': header}

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))

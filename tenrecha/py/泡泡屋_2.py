# -*- coding: utf-8 -*-
"""
泡泡屋 (ppw666.com -> tlobcnv.com) Python Spider
兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)

封面图：mvimg.kaibmy.com 的 .log 为 AES-128-CBC 加密 JPEG
  key(hex): 88ce35562a6f085b53a00145444c445f
  iv(hex):  d005d14d7ce6312ae54527a659be2c55
通过 localProxy 解密后返回 image/jpeg，TVBox 即可显示。
"""
import sys
import re
import json
import time
import base64

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        _session = rq.Session()
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = self._session.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r
        def post(self, url, headers=None, data=None, **kw):
            kw.pop('timeout', None)
            r = self._session.post(url, headers=headers, data=data, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r
        def getProxyUrl(self, local=True):
            return 'http://127.0.0.1:9978/proxy?do=py'


class Spider(Spider):
    HOST = 'https://tlobcnv.com'
    API = 'https://tlobcnv.com/api/app/v1'
    IMG_HOST = 'https://mvimg.kaibmy.com'
    M3U8_HOST = 'https://idx.jvnmtr.cn'

    # 封面 AES-128-CBC（hex 密钥，不是 ASCII 字符串）
    _IMG_KEY = bytes.fromhex('88ce35562a6f085b53a00145444c445f')
    _IMG_IV = bytes.fromhex('d005d14d7ce6312ae54527a659be2c55')

    def getName(self):
        return "泡泡屋"

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self.host = self.HOST
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self._token = ''
        self._token_time = 0
        self._play_cache = {}
        self._ep_cache = {}

    # ========== 认证 ==========

    def _ensure_token(self):
        if self._token and (time.time() - self._token_time < 7000):
            return self._token
        try:
            import requests as rq
            url = self.API + '/auth/register'
            body = json.dumps({'deviceFingerprint': 'web:Linux:zh-CN'})
            rsp = rq.post(url, headers={**self.header, 'Content-Type': 'application/json'},
                          data=body, timeout=15)
            data = rsp.json()
            if data.get('code') == 0:
                self._token = data['data']['token']
                self._token_time = time.time()
                return self._token
        except Exception:
            pass
        return self._token

    def _auth_header(self):
        token = self._ensure_token()
        h = dict(self.header)
        if token:
            h['Authorization'] = 'Bearer ' + token
        return h

    def _api_get(self, path, params=None):
        url = self.API + path
        headers = self._auth_header()
        for attempt in range(2):
            try:
                rsp = self.fetch(url, headers=headers, timeout=15)
                data = rsp.json()
                if data.get('code') == 1001 and attempt == 0:
                    self._token = ''
                    self._token_time = 0
                    headers = self._auth_header()
                    continue
                return data
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return {}
        return {}

    # ========== 封面图（代理解密） ==========

    def _cover_url(self, cover_path):
        """
        普通封面：加密 .log → 走 localProxy 解密
        合集等外链完整 http 且非 mvimg：直接返回
        """
        if not cover_path:
            return ''
        # 外站明文封面（如合集 ncp.xxx）
        if cover_path.startswith('http') and self.IMG_HOST not in cover_path:
            return cover_path

        path = cover_path
        if path.startswith('http'):
            # 完整 mvimg URL，抽出 path
            path = path.split(self.IMG_HOST, 1)[-1]
        if not path.startswith('/'):
            path = '/' + path
        if not path.endswith('.log'):
            path = path + '.log'

        from urllib.parse import quote
        try:
            proxy = self.getProxyUrl()
        except Exception:
            proxy = 'http://127.0.0.1:9978/proxy?do=py'
        # 标记 do=ppwimg，localProxy 识别
        sep = '&' if '?' in proxy else '?'
        # 用 ppwimg=1，避免覆盖框架自带的 do=py
        return f'{proxy}{sep}ppwimg=1&path={quote(path)}'

    def _decrypt_cover(self, enc_bytes):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            cipher = AES.new(self._IMG_KEY, AES.MODE_CBC, self._IMG_IV)
            return unpad(cipher.decrypt(enc_bytes), 16)
        except Exception:
            try:
                from Crypto.Cipher import AES
                cipher = AES.new(self._IMG_KEY, AES.MODE_CBC, self._IMG_IV)
                pt = cipher.decrypt(enc_bytes)
                # 去掉可能的 PKCS 填充（容错）
                pad_len = pt[-1]
                if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                    return pt[:-pad_len]
                return pt
            except Exception:
                return b''

    def localProxy(self, param):
        """TVBox 本地代理：解密封面 JPEG"""
        try:
            path = param.get('path') or param.get('url') or ''
            # 仅处理封面代理（ppwimg=1 或带 path 的加密图请求）
            if not path:
                return [404, 'text/plain', b'']
            if not (param.get('ppwimg') or param.get('do') in ('ppwimg', 'img', 'py') or path.endswith('.log')):
                return [404, 'text/plain', b'']

            if path.startswith('http'):
                img_url = path if path.endswith('.log') else path
            else:
                if not path.startswith('/'):
                    path = '/' + path
                if not path.endswith('.log'):
                    path = path + '.log'
                img_url = self.IMG_HOST + path

            import requests as rq
            r = rq.get(img_url, headers={'User-Agent': self.header['User-Agent']}, timeout=15)
            if r.status_code != 200 or not r.content:
                return [404, 'text/plain', b'']

            raw = r.content
            # 已是 JPEG
            if raw[:2] == b'\xff\xd8':
                return [200, 'image/jpeg', raw]
            # PNG
            if raw[:8] == b'\x89PNG\r\n\x1a\n':
                return [200, 'image/png', raw]

            dec = self._decrypt_cover(raw)
            if not dec:
                return [404, 'text/plain', b'']
            ctype = 'image/jpeg'
            if dec[:8] == b'\x89PNG\r\n\x1a\n':
                ctype = 'image/png'
            elif dec[:2] == b'\xff\xd8':
                ctype = 'image/jpeg'
            return [200, ctype, dec]
        except Exception:
            return [404, 'text/plain', b'']

    # ========== m3u8 ==========

    def _build_m3u8_url(self, play_path):
        if not play_path:
            return ''
        m3u8_dir = play_path.rsplit('/', 1)[0] if play_path.count('/') >= 3 else play_path
        return self.M3U8_HOST + m3u8_dir + '/index.m3u8'

    # ========== 视频对象 ==========

    def _to_vod(self, item):
        return {
            'vod_id': str(item.get('id', '')),
            'vod_name': item.get('title', ''),
            'vod_pic': self._cover_url(item.get('coverPath', '')),
            'vod_remarks': item.get('duration', ''),
        }

    def _to_collection_vod(self, item):
        episodes = item.get('episodes', 0)
        free_eps = item.get('freeEpisodes', 0)
        unlock_coins = item.get('unlockCoins', 0)
        remark = f'{episodes}集'
        if free_eps > 0:
            remark += f'(免费{free_eps}集)'
        if unlock_coins == 0:
            remark = f'{episodes}集(免费)'
        return {
            'vod_id': 'col_' + str(item.get('id', '')),
            'vod_name': item.get('title', ''),
            'vod_pic': self._cover_url(item.get('coverPath', '')),
            'vod_remarks': remark,
        }

    # ========== 首页 ==========

    def homeContent(self, filter):
        from urllib.parse import quote
        classes = []
        filters = {}

        classes.append({'type_id': 'all', 'type_name': '最新'})
        classes.append({'type_id': 'hot', 'type_name': '热门'})
        classes.append({'type_id': 'collections', 'type_name': '合集'})

        sort_filter = {
            'key': 'sort',
            'name': '排序',
            'value': [
                {'n': '最新', 'v': 'time'},
                {'n': '热门', 'v': 'hot'},
            ]
        }
        filters['all'] = [sort_filter]
        filters['hot'] = [sort_filter]
        filters['collections'] = []

        data = self._api_get('/videos/categories')
        cats = (data.get('data') or {}).get('list', [])

        for cat in cats:
            type_id = cat.get('name', '')
            type_name = cat.get('name', '')
            classes.append({'type_id': type_id, 'type_name': type_name})
            filters[type_id] = [sort_filter]

        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        result = {'list': []}
        try:
            data = self._api_get('/home/today')
            items = (data.get('data') or {}).get('list', [])
            if not items:
                data = self._api_get('/videos?sort=time&page=1&pageSize=20')
                items = (data.get('data') or {}).get('list', [])
            result['list'] = [self._to_vod(v) for v in items]
        except Exception:
            pass
        return result

    # ========== 分类 ==========

    def categoryContent(self, tid, pg, filter, ext):
        from urllib.parse import quote
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        sort = 'time'
        if ext:
            if isinstance(ext, dict):
                sort = ext.get('sort', 'time') or 'time'
            elif isinstance(ext, str):
                try:
                    params = json.loads(ext)
                    sort = params.get('sort', 'time') or 'time'
                except Exception:
                    pass
        if sort not in ('time', 'hot'):
            sort = 'time'

        if tid == 'collections':
            data = self._api_get(f'/collections?page={page}&pageSize=30')
            d = data.get('data') or {}
            videos = [self._to_collection_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 30
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }

        if tid == 'hot':
            data = self._api_get(f'/home/hot?sort=plays&page={page}&pageSize=30')
            d = data.get('data') or {}
            videos = [self._to_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 30
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }

        params_list = [f'sort={sort}', f'page={page}', 'pageSize=30']
        if tid and tid != 'all':
            params_list.insert(0, f'category={quote(tid)}')

        url_path = '/videos?' + '&'.join(params_list)
        data = self._api_get(url_path)

        d = data.get('data') or {}
        videos = [self._to_vod(v) for v in d.get('list', [])]

        total = d.get('total', 0)
        page_size = d.get('pageSize', 30)
        page_count = max(1, (total + page_size - 1) // page_size) if total else 1

        return {
            'list': videos,
            'page': page,
            'pagecount': page_count,
            'limit': page_size,
            'total': total,
        }

    # ========== 详情 ==========

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ''
        if not vid:
            return {}

        if vid.startswith('col_'):
            return self._collection_detail(vid[4:])

        data = self._api_get(f'/videos/{vid}')
        d = data.get('data') or {}
        if not d:
            return {}

        play_path = d.get('playPath', '')
        if play_path:
            self._play_cache[vid] = play_path

        vod = {
            'vod_id': vid,
            'vod_name': d.get('title', ''),
            'vod_pic': self._cover_url(d.get('coverPath', '')),
            'vod_year': '',
            'vod_area': d.get('category', ''),
            'vod_remarks': d.get('duration', ''),
            'vod_tags': d.get('tag', ''),
            'vod_play_from': '泡泡屋',
            'vod_play_url': '播放$' + vid,
        }

        try:
            rec_data = self._api_get(f'/videos/{vid}/recommend?limit=6')
            rec_items = (rec_data.get('data') or {}).get('list', [])
            if rec_items:
                vod['vod_content'] = '相关推荐：' + '、'.join(
                    v.get('title', '')[:20] for v in rec_items[:3]
                )
        except Exception:
            pass

        return {'list': [vod]}

    def _collection_detail(self, cid):
        data = self._api_get(f'/collections/{cid}')
        d = data.get('data') or {}
        if not d:
            return {}

        ep_data = self._api_get(f'/collections/{cid}/episodes')
        episodes = (ep_data.get('data') or {}).get('list', [])
        self._ep_cache[cid] = episodes

        free_eps = [ep for ep in episodes if ep.get('free')]
        if not free_eps:
            free_eps = episodes[:10]

        play_names = []
        for ep in free_eps:
            idx = ep.get('index', 0)
            title = ep.get('title', f'第{idx}集')
            ep_id = f'col_{cid}_{idx}'
            play_names.append(f'{title}${ep_id}')

        vod = {
            'vod_id': 'col_' + cid,
            'vod_name': d.get('title', ''),
            'vod_pic': self._cover_url(d.get('coverPath', '')),
            'vod_year': d.get('releaseDate', ''),
            'vod_area': '',
            'vod_remarks': f'{d.get("episodes", 0)}集(免费{len(free_eps)}集)',
            'vod_content': d.get('intro', ''),
            'vod_play_from': '免费剧集',
            'vod_play_url': '#'.join(play_names),
        }

        return {'list': [vod]}

    # ========== 播放 ==========

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        if '$' in id:
            parts = id.split('$')
            if len(parts) == 2:
                id = parts[1]

        vid = str(id)

        if vid.startswith('col_'):
            return self._collection_play(vid)

        play_path = self._play_cache.get(vid)
        if not play_path:
            try:
                data = self._api_get(f'/videos/{vid}')
                d = data.get('data') or {}
                play_path = d.get('playPath', '')
                if play_path:
                    self._play_cache[vid] = play_path
            except Exception:
                pass

        if not play_path:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        m3u8_url = self._build_m3u8_url(play_path)

        return {
            'parse': 0,
            'playUrl': '',
            'url': m3u8_url,
            'header': {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
            },
            'format': 'application/x-mpegURL',
            'contentType': 'application/x-mpegURL',
        }

    def _collection_play(self, vid):
        parts = vid.split('_')
        if len(parts) < 3:
            return {'parse': 1, 'playUrl': '', 'url': ''}
        cid = parts[1]
        ep_idx = int(parts[2]) if parts[2].isdigit() else 0

        episodes = self._ep_cache.get(cid)
        if not episodes:
            ep_data = self._api_get(f'/collections/{cid}/episodes')
            episodes = (ep_data.get('data') or {}).get('list', [])
            self._ep_cache[cid] = episodes

        play_path = ''
        for ep in episodes:
            if ep.get('index') == ep_idx:
                play_path = ep.get('playPath', '')
                break

        if not play_path:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        m3u8_url = self._build_m3u8_url(play_path)

        return {
            'parse': 0,
            'playUrl': '',
            'url': m3u8_url,
            'header': {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
            },
            'format': 'application/x-mpegURL',
            'contentType': 'application/x-mpegURL',
        }

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg):
        from urllib.parse import quote
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        try:
            url_path = f'/search?keyword={quote(key)}&type=video&page={page}&pageSize=20'
            data = self._api_get(url_path)
            d = data.get('data') or {}
            videos = [self._to_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 20
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }
        except Exception:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}

    def isLive(self):
        return False

    def manualContent(self, lv):
        return {}

"""
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 1,
  title: '笔盒',
  lang: 'hipy',
})
"""

import re
import json
import html
import base64
from urllib.parse import quote, unquote_plus

try:
    import requests
except Exception:
    requests = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except Exception:
    AES = None
    unpad = None

from base.spider import Spider


class Spider(Spider):
    host = 'https://bh3009.top'
    ua = 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    key_hex = 'f6322fa1c064370ea40c8cdc20649f8e'

    def __init__(self, *args, **kwargs):
        self.t4_api = kwargs.get('t4_api', '')
        self.extend = ''
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update({
                'User-Agent': self.ua,
                'Referer': self.host + '/home',
                'Accept': 'application/json,text/plain,*/*',
            })

    def init(self, extend=''):
        self.extend = extend
        return '{}'

    def getName(self):
        return '笔盒'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.s:
            self.s.close()

    def _log(self, msg):
        try:
            self.log('[BiHe] ' + str(msg))
        except Exception:
            pass

    def _clean(self, s):
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', str(s or '')))).strip()

    def _request(self, path):
        url = path if str(path).startswith('http') else self.host + path
        headers = {'User-Agent': self.ua, 'Referer': self.host + '/home', 'Accept': 'application/json'}
        if self.s:
            r = self.s.get(url, headers=headers, timeout=20)
        else:
            import requests as _rq
            r = _rq.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r

    def _decrypt_hex(self, data):
        if not data:
            return None
        if AES is None:
            raise Exception('missing Crypto AES')
        raw = bytes.fromhex(str(data))
        if len(raw) < 17:
            raise Exception('encrypted payload too short')
        key = bytes.fromhex(self.key_hex)[:16]
        iv, ct = raw[:16], raw[16:]
        text = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16).decode('utf-8')
        try:
            return json.loads(text)
        except Exception:
            return text

    def _api(self, path):
        r = self._request('/api' + path if not str(path).startswith('/api/') else path)
        obj = r.json()
        if obj.get('code') != 200:
            raise Exception(obj.get('msg') or 'api error')
        data = obj.get('data')
        enc = str(r.headers.get('x-encrypted') or r.headers.get('X-Encrypted') or '')
        if enc.upper().startswith('AES-128-CBC') and isinstance(data, str):
            return self._decrypt_hex(data)
        return data

    def _pic_proxy(self, url):
        if not url:
            return ''
        # 该站图片 .txt 是前 4096 字节 XOR 18 后得到 data:image/*;base64,...
        if not str(url).lower().split('?')[0].endswith('.txt'):
            return url
        try:
            proxy = self.getProxyUrl()
            if not proxy:
                return url
            sep = '&' if '?' in proxy else '?'
            enc = base64.urlsafe_b64encode(url.encode('utf-8')).decode('ascii')
            site_key = quote(str(getattr(self, 'siteKey', '') or ''), safe='')
            target = proxy + sep + 'do=py' if 'do=py' not in proxy else proxy
            if site_key:
                target += '&siteKey=' + site_key
            return target + '&type=img&url=' + quote(enc, safe='')
        except Exception:
            return url

    def _vod_item(self, v):
        vid = str(v.get('vodId') or v.get('id') or '')
        name = self._clean(v.get('vodName') or v.get('name') or vid)
        pic = self._pic_proxy(v.get('vodPic') or v.get('vodThumb') or '')
        classes = v.get('vodClass') or []
        if isinstance(classes, list):
            remark = ' / '.join([self._clean(x) for x in classes if x])
        else:
            remark = self._clean(classes)
        rating = self._clean(v.get('rating') or '')
        if rating:
            remark = (remark + ' ' + rating).strip()
        return {'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remark}

    def _page_result(self, obj, pg):
        data = obj.get('data') if isinstance(obj, dict) else obj
        if data is None:
            data = []
        items = [self._vod_item(x) for x in data if isinstance(x, dict)] if isinstance(data, list) else []
        page = int(obj.get('page') or pg or 1) if isinstance(obj, dict) else int(pg or 1)
        total = int(obj.get('total') or len(items)) if isinstance(obj, dict) else len(items)
        pagecount = int(obj.get('totalPages') or (page + 1 if items else page)) if isinstance(obj, dict) else 1
        return {'page': page, 'pagecount': max(pagecount, page), 'limit': len(items), 'total': total, 'list': items}

    def _config(self):
        try:
            obj = self._api('/configs?platformType=h5')
            return obj if isinstance(obj, dict) else {}
        except Exception as e:
            self._log('config error %r' % e)
            return {}

    def _tag_cats(self):
        cfg = self._config()
        text = cfg.get('home_tags') or cfg.get('hot_search_words') or ''
        names, seen = [], set()
        for x in re.split(r'[,，\s]+', str(text)):
            name = self._clean(x)
            if not name or name in seen:
                continue
            names.append(name)
            seen.add(name)
        return [{'type_id': 'tag:' + x, 'type_name': x} for x in names[:36]]

    def _tag_folder_cats(self, pg=1, size=20):
        tags = self._tag_cats()
        start = max(0, (int(pg) - 1) * int(size))
        end = start + int(size)
        items = []
        for x in tags[start:end]:
            items.append({'vod_id': 'folder_' + x['type_id'], 'vod_name': x['type_name'], 'vod_pic': '', 'vod_remarks': '标签', 'vod_tag': 'folder'})
        return items, len(tags)

    def _topic_cats(self):
        try:
            obj = self._api('/topic/list?page=1&limit=20&sortBy=topicSort&sortOrder=ASC&vodLimit=1')
            topics = obj.get('data') if isinstance(obj, dict) else obj
            out = []
            if isinstance(topics, list):
                for t in topics:
                    tid = str(t.get('topicId') or '')
                    name = self._clean(t.get('topicName') or '')
                    if tid and name:
                        out.append({'type_id': 'topic:' + tid, 'type_name': name})
            return out
        except Exception as e:
            self._log('topic cats error %r' % e)
            return []

    def _topic_folder_cats(self, pg=1):
        try:
            obj = self._api('/topic/list?page=%s&limit=20&sortBy=topicSort&sortOrder=ASC&vodLimit=1' % pg)
            topics = obj.get('data') if isinstance(obj, dict) else obj
            out = []
            if isinstance(topics, list):
                for t in topics:
                    tid = str(t.get('topicId') or '')
                    name = self._clean(t.get('topicName') or '')
                    if tid and name:
                        out.append({'vod_id': 'folder_topic:' + tid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': '专题', 'vod_tag': 'folder'})
            total = int(obj.get('total') or len(out)) if isinstance(obj, dict) else len(out)
            pagecount = int(obj.get('totalPages') or (pg + 1 if out else pg)) if isinstance(obj, dict) else pg
            return out, total, pagecount
        except Exception as e:
            self._log('topic folder error %r' % e)
            return [], 0, pg


    def homeContent(self, filter=None):
        cats = [
            {'type_id': 'latest', 'type_name': '最新视频'},
            {'type_id': 'folder_topic_root', 'type_name': '专题合集', 'vod_tag': 'folder'},
            {'type_id': 'folder_tag_root', 'type_name': '热搜标签', 'vod_tag': 'folder'},
        ]
        return {'class': cats, 'filters': {}}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = int(pg or 1)
        tid = str(tid)
        try:
            if tid == 'recommend':
                obj = self._api('/vod/recommend')
                arr = obj.get('data') if isinstance(obj, dict) else obj
                if not isinstance(arr, list):
                    arr = []
                items = [self._vod_item(x) for x in arr if isinstance(x, dict)]
                return {'page': pg, 'pagecount': 1, 'limit': len(items), 'total': len(items), 'list': items if pg == 1 else []}

            if tid == 'topic':
                obj = self._api('/topic/list?page=%s&limit=20&sortBy=topicSort&sortOrder=ASC&vodLimit=10' % pg)
                topics = obj.get('data') if isinstance(obj, dict) else obj
                items = []
                if isinstance(topics, list):
                    for t in topics:
                        for v in (t.get('relatedVods') or t.get('vods') or t.get('vodList') or []):
                            if isinstance(v, dict):
                                items.append(self._vod_item(v))
                total = int(obj.get('total') or len(items)) if isinstance(obj, dict) else len(items)
                pc = int(obj.get('totalPages') or (pg + 1 if items else pg)) if isinstance(obj, dict) else 1
                return {'page': pg, 'pagecount': pc, 'limit': len(items), 'total': total, 'list': items}

            if tid.startswith('topic:') or tid.startswith('folder_topic:'):
                topic_id = tid.split(':', 1)[1]
                obj = self._api('/topic/detail/%s?vodPage=%s&vodLimit=10' % (quote(topic_id), pg))
                arr = obj.get('relatedVods') if isinstance(obj, dict) else []
                items = [self._vod_item(x) for x in arr if isinstance(x, dict)] if isinstance(arr, list) else []
                total = int(obj.get('relatedVodTotal') or len(items)) if isinstance(obj, dict) else len(items)
                page = int(obj.get('relatedVodPage') or pg) if isinstance(obj, dict) else pg
                pagecount = int(obj.get('relatedVodTotalPages') or (pg + 1 if len(items) >= 10 else pg)) if isinstance(obj, dict) else pg
                return {'page': page, 'pagecount': pagecount, 'limit': len(items), 'total': total, 'list': items}

            if tid.startswith('tag:') or tid.startswith('folder_tag:'):
                key = tid.split(':', 1)[1]
                obj = self._api('/vod/search?keyword=%s&page=%s&limit=20' % (quote(key), pg))
                return self._page_result(obj, pg)

            if tid == 'folder_topic_root':
                items, total, pc = self._topic_folder_cats(pg)
                return {'page': pg, 'pagecount': pc, 'limit': len(items), 'total': total, 'list': items}

            if tid == 'folder_tag_root':
                items, total = self._tag_folder_cats(pg)
                pc = int((total + 19) / 20) if total else pg
                return {'page': pg, 'pagecount': pc, 'limit': len(items), 'total': total, 'list': items}

            obj = self._api('/vod/latest?page=%s&limit=20' % pg)
            return self._page_result(obj, pg)
        except Exception as e:
            self._log('category error %s %r' % (tid, e))
            return {'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0, 'list': []}

    def searchContent(self, key, quick=False, pg='1'):
        pg = int(pg or 1)
        try:
            obj = self._api('/vod/search?keyword=%s&page=%s&limit=20' % (quote(str(key)), pg))
            return self._page_result(obj, pg)
        except Exception as e:
            self._log('search error %r' % e)
            return {'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0, 'list': []}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        try:
            v = self._api('/vod/detail/' + quote(str(vid)))
            title = self._clean(v.get('vodName') or vid)
            pic = self._pic_proxy(v.get('vodPic') or v.get('vodThumb') or '')
            classes = v.get('vodClass') or []
            content = ' / '.join(classes) if isinstance(classes, list) else self._clean(classes)
            sources = v.get('vodPlaySource') or {}
            froms, urls = [], []
            if isinstance(sources, dict):
                for key, arr in sources.items():
                    if not isinstance(arr, list):
                        continue
                    eps = []
                    line_name = ''
                    for idx, p in enumerate(arr, 1):
                        if not isinstance(p, dict):
                            continue
                        play = p.get('playUrl') or p.get('url') or ''
                        if not play:
                            continue
                        line_name = self._clean(p.get('flag') or key or '播放源')
                        eps.append(('第%d集' % idx) + '$' + play)
                    if eps:
                        froms.append(line_name or key)
                        urls.append('#'.join(eps))
            if not urls:
                preview = v.get('vodPreview') or ''
                urls = ['正片$' + preview] if preview else ['正片$' + str(vid)]
                froms = ['笔盒']
            vod = {'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_content': content,
                   'vod_play_from': '$$$'.join(froms), 'vod_play_url': '$$$'.join(urls)}
            return {'list': [vod]}
        except Exception as e:
            self._log('detail error %r' % e)
            return {'list': [{'vod_id': vid, 'vod_name': str(vid), 'vod_play_from': '笔盒', 'vod_play_url': '正片$' + str(vid)}]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        if not re.search(r'\.(?:m3u8|mp4|flv|m4v)(?:$|[?#])', url, re.I) and url:
            try:
                v = self._api('/vod/detail/' + quote(url))
                sources = v.get('vodPlaySource') or {}
                for arr in sources.values():
                    if isinstance(arr, list) and arr:
                        url = arr[0].get('playUrl') or arr[0].get('url') or url
                        break
            except Exception:
                pass
        return {'parse': 0 if re.search(r'\.(?:m3u8|mp4|flv|m4v)(?:$|[?#])', url, re.I) else 1,
                'jx': 0, 'playUrl': '', 'url': url,
                'header': 'User-Agent: %s\r\nReferer: %s/home' % (self.ua, self.host)}

    def _decode_txt_image(self, content):
        buf = bytearray(content or b'')
        n = min(4096, len(buf))
        for i in range(n):
            buf[i] ^= 18
        text = bytes(buf).decode('utf-8', 'ignore')
        m = re.match(r'^data:([^;]+);base64,(.+)$', text, re.S)
        if m:
            return base64.b64decode(m.group(2)), m.group(1)
        return bytes(buf), 'image/jpeg'

    def localProxy(self, param):
        try:
            p = param or {}
            ptype = str(p.get('type') or p.get('ptype') or '').lower()
            if ptype not in ('img', 'image'):
                return [404, 'text/plain', b'']
            encoded = unquote_plus(str(p.get('url') or p.get('u') or ''))
            try:
                pad = '=' * ((4 - len(encoded) % 4) % 4)
                url = base64.urlsafe_b64decode((encoded + pad).encode('ascii')).decode('utf-8')
            except Exception:
                url = encoded
            if not url.startswith('http'):
                return [400, 'text/plain', b'']
            headers = {'User-Agent': self.ua, 'Referer': self.host + '/home'}
            if self.s:
                r = self.s.get(url, headers=headers, timeout=20)
            else:
                import requests as _rq
                r = _rq.get(url, headers=headers, timeout=20)
            if r.status_code != 200 or not r.content:
                return [r.status_code or 404, 'text/plain', b'']
            data, mime = self._decode_txt_image(r.content) if url.lower().split('?')[0].endswith('.txt') else (r.content, (r.headers.get('Content-Type') or 'image/jpeg').split(';')[0])
            if data.startswith(b'\xff\xd8'):
                mime = 'image/jpeg'
            elif data.startswith(b'\x89PNG'):
                mime = 'image/png'
            elif data.startswith(b'GIF8'):
                mime = 'image/gif'
            elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
                mime = 'image/webp'
            return [200, mime, data]
        except Exception:
            return [404, 'text/plain', b'']

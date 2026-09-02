# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import math
import re
import sys
import time
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad

sys.path.append('..')
from base.spider import Spider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):
    WEB_HOST = 'https://aqx1.8uyp35j.com:51888'
    DEFAULT_CHANNEL = 'zavdh'
    DEFAULT_CDN = '1'
    PAGE_SIZE = 24
    IMAGE_KEY = b'H0Z%7n#k$H8*M7xSE^N@8xXZPG*RZ&wY'
    MAX_IMAGE_BYTES = 8 * 1024 * 1024
    MAX_MANIFEST_BYTES = 2 * 1024 * 1024
    FALLBACK_APIS = [
        'https://h05j.883rm9.com:51111',
        'https://64gb.ng4fwv.com:52000',
        'https://50hd.gkrle7.com:51777',
        'https://g70j.bbkjtp.com:51888',
        'https://yg81.bpy0rd.com:51888',
    ]

    def __init__(self):
        self.ext = ''
        self.web_host = self.WEB_HOST
        self.channel = self.DEFAULT_CHANNEL
        self.preferred_cdn = self.DEFAULT_CDN
        self.session = requests.Session()
        self.session.trust_env = False
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/138.0.0.0 Safari/537.36'),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.api_candidates = []
        self._api_updated = 0

    def getName(self):
        return 'AQX'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        self.ext = getattr(self, 'ext', '') or extend or ''
        config = self._config(self.ext)
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.web_host = host
        channel = str(config.get('channel') or '').strip()
        if channel:
            self.channel = channel
        preferred_cdn = str(config.get('preferredCdn') or config.get('cdnId') or '').strip()
        if preferred_cdn:
            self.preferred_cdn = preferred_cdn
        ua = str(config.get('ua') or config.get('userAgent') or '').strip()
        if ua:
            self.headers['User-Agent'] = ua
        cookie = str(config.get('cookie') or '').strip()
        if cookie:
            self.session.headers.update({'Cookie': cookie})
        proxy = config.get('proxy')
        if isinstance(proxy, str) and proxy.strip():
            value = proxy.strip()
            if not value.startswith(('http://', 'https://')):
                value = 'http://' + value
            self.session.proxies.update({'http': value, 'https': value})
        apis = config.get('api') or config.get('apis')
        if isinstance(apis, str):
            apis = [x.strip() for x in apis.split(',')]
        if isinstance(apis, list):
            self.api_candidates = self._unique_hosts(apis)
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        value = str(url or '')
        return self._is_hls_url(value) or value.lower().split('?', 1)[0].endswith(('.mp4', '.flv', '.ts'))

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def homeContent(self, filter=False):
        try:
            nav = self._api('/api/old_v3/video/nav')
            classes = []
            for item in self._list(nav):
                item_type = self._text(item.get('type')).lower()
                item_id = item.get('id', item.get('tid'))
                name = self._text(item.get('title') or item.get('name'))
                if name and item_id is not None and item_type != 'home':
                    classes.append({'type_name': name, 'type_id': self._category_id(item_id, item_type)})
            return {'class': classes, 'filters': {}}
        except Exception as error:
            self.log('AQX homeContent: %s' % error)
            return {'class': [], 'filters': {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            data = self._api('/api/old_v3/video/home')
            videos, seen = [], set()
            for section in self._list(data):
                title = self._text(section.get('title') or section.get('name'))
                for item in self._list(section.get('list')):
                    video = self._video(item, title)
                    if video['vod_id'] and video['vod_id'] not in seen:
                        seen.add(video['vod_id'])
                        videos.append(video)
            return {'list': videos}
        except Exception as error:
            self.log('AQX homeVideoContent: %s' % error)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, self._int(pg, 1))
        item_id, item_type = self._parse_category_id(tid)
        try:
            data = self._api('/api/old_v3/video/getList', {
                'id': item_id, 'type': item_type, 'page': page, 'size': self.PAGE_SIZE,
            })
            items = self._list(data.get('list') if isinstance(data, dict) else data)
            total = self._int(data.get('total'), len(items)) if isinstance(data, dict) else len(items)
            return {'list': [self._video(x) for x in items], 'page': page,
                    'pagecount': max(page, int(math.ceil(float(total) / self.PAGE_SIZE))) if total else page,
                    'limit': self.PAGE_SIZE, 'total': total}
        except Exception as error:
            self.log('AQX categoryContent: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}

    def detailContent(self, ids):
        video_id = str(ids[0] if ids else '').strip()
        if not video_id:
            return {'list': []}
        try:
            item = self._api('/api/v3/home/public/video/long/detail', {'id': video_id})
            if not isinstance(item, dict):
                return {'list': []}
            sources = self._sources(item)
            if not sources:
                return {'list': []}
            names, urls, used = [], [], set()
            for index, source in enumerate(sources, 1):
                name = self._safe_name(source.get('name')) or ('Line%d' % index)
                original, suffix = name, 2
                while name in used:
                    name = '%s%d' % (original, suffix)
                    suffix += 1
                used.add(name)
                names.append(name)
                # Each source is one playback group; this item has one episode.
                urls.append('正片$' + source['url'])
            return {'list': [{'vod_id': video_id,
                'vod_name': self._text(item.get('title') or item.get('name')),
                'vod_pic': self._image(item.get('upload_thumb') or item.get('thumb') or item.get('backstage_thumb')),
                'vod_remarks': self._text(item.get('label') or item.get('duration')),
                'vod_year': self._text(item.get('year')), 'vod_area': self._text(item.get('region')),
                'vod_actor': self._text(item.get('author')),
                'vod_content': self._clean_html(item.get('desc') or item.get('description')),
                'vod_play_from': '$$$'.join(names), 'vod_play_url': '$$$'.join(urls)}]}
        except Exception as error:
            self.log('AQX detailContent: %s' % error)
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg='1'):
        page = max(1, self._int(pg, 1))
        try:
            data = self._api('/api/old_v3/video/search', {
                'keyword': str(key or '').strip(), 'page': page, 'size': self.PAGE_SIZE,
            })
            items = self._list(data.get('list') if isinstance(data, dict) else data)
            total = self._int(data.get('total'), len(items)) if isinstance(data, dict) else len(items)
            per_page = self._int(data.get('per_page'), self.PAGE_SIZE) if isinstance(data, dict) else self.PAGE_SIZE
            last_page = self._int(data.get('last_page'), 0) if isinstance(data, dict) else 0
            return {'list': [self._video(x) for x in items], 'page': page,
                    'pagecount': max(page, last_page or int(math.ceil(float(total) / max(1, per_page)))) if total else page,
                    'limit': per_page, 'total': total}
        except Exception as error:
            self.log('AQX searchContent: %s' % error)
            return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '').strip()
        if url.startswith(('http://', 'https://')):
            result = {
                'parse': 0, 'playUrl': '', 'url': url,
                'header': self._play_headers(url),
            }
            if self._is_hls_url(url):
                result.update({
                    'url': self._manifest_proxy_url(url) or url,
                    'type': 'm3u8',
                    'format': 'application/x-mpegURL',
                    'contentType': 'application/x-mpegURL',
                })
            return result
        return {'parse': 1, 'playUrl': '', 'url': url, 'header': {}}

    def localProxy(self, param):
        try:
            proxy_type = str(param.get('type') or '')
            remote_url = str(param.get('url') or '').strip()
            signature = str(param.get('sig') or '').strip()
        except Exception:
            proxy_type = remote_url = signature = ''
        if proxy_type == 'aqx_m3u8':
            return self._proxy_manifest(remote_url, signature)
        image_url = remote_url
        if proxy_type != 'aqx_img' or not image_url:
            return [404, 'text/plain; charset=utf-8', b'not found']
        if not image_url.startswith(('http://', 'https://')):
            image_url = unquote(image_url)
        if (not image_url.startswith(('http://', 'https://'))
                or not urlparse(image_url).path.lower().endswith('.enc')):
            return [400, 'text/plain; charset=utf-8', b'invalid image url']
        if not hmac.compare_digest(signature, self._image_signature(image_url)):
            return [403, 'text/plain; charset=utf-8', b'forbidden']

        try:
            response = self.session.get(
                image_url,
                headers={
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                    'Referer': self.web_host + '/home',
                    'Connection': 'close',
                },
                timeout=(8, 25),
                verify=False,
                allow_redirects=False,
                stream=True,
            )
            response.raise_for_status()
            declared_size = self._int(response.headers.get('Content-Length'), 0)
            if declared_size > self.MAX_IMAGE_BYTES:
                raise ValueError('AQX encrypted cover is too large')
            chunks, size = [], 0
            try:
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.MAX_IMAGE_BYTES:
                        raise ValueError('AQX encrypted cover is too large')
                    chunks.append(chunk)
            finally:
                response.close()
            image = self._decrypt_image(b''.join(chunks))
            return [200, self._image_mime(image), image]
        except Exception as error:
            self.log('AQX image proxy: %s' % error)
            return [502, 'text/plain; charset=utf-8', b'image proxy failed']

    def _proxy_manifest(self, remote_url, signature):
        if not remote_url.startswith(('http://', 'https://')):
            remote_url = unquote(remote_url)
        if (not remote_url.startswith(('http://', 'https://'))
                or not self._is_hls_url(remote_url)):
            return [400, 'text/plain; charset=utf-8', b'invalid manifest url']
        if not hmac.compare_digest(signature, self._manifest_signature(remote_url)):
            return [403, 'text/plain; charset=utf-8', b'forbidden']

        response = None
        try:
            headers = self._play_headers(remote_url)
            headers.update({
                'Accept': ('application/vnd.apple.mpegurl,application/x-mpegURL,'
                           'text/plain;q=0.9,*/*;q=0.8'),
                'Connection': 'close',
            })
            response = self.session.get(
                remote_url, headers=headers, timeout=(8, 20), verify=False,
                allow_redirects=False, stream=True,
            )
            response.raise_for_status()
            declared_size = self._int(response.headers.get('Content-Length'), 0)
            if declared_size > self.MAX_MANIFEST_BYTES:
                raise ValueError('AQX HLS manifest is too large')

            chunks, size = [], 0
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > self.MAX_MANIFEST_BYTES:
                    raise ValueError('AQX HLS manifest is too large')
                chunks.append(chunk)
            text = b''.join(chunks).decode('utf-8-sig', errors='replace')
            text = text.lstrip('\ufeff \t\r\n')
            if not text.startswith('#EXTM3U'):
                raise ValueError('AQX HLS response does not start with #EXTM3U')
            body = self._absolute_manifest(text, response.url).encode('utf-8')
            return [200, 'application/vnd.apple.mpegurl', body, {
                'Content-Type': 'application/vnd.apple.mpegurl',
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*',
            }]
        except Exception as error:
            self.log('AQX manifest proxy: %s' % error)
            return [502, 'text/plain; charset=utf-8', b'manifest proxy failed']
        finally:
            if response is not None:
                response.close()

    def _api(self, path, params=None):
        last = None
        for host in self._get_apis():
            try:
                query = dict(params or {})
                query['channel'] = self.channel
                response = self.session.get(host + path, params=query, headers=self.headers,
                                            timeout=15, verify=False)
                response.raise_for_status()
                payload = self._unwrap(response.json())
                if isinstance(payload, dict):
                    code = self._int(payload.get('code'), 200)
                    if code not in (0, 200):
                        raise RuntimeError(self._text(payload.get('message')) or ('API error %s' % code))
                    value = payload.get('data', payload)
                else:
                    value = payload
                if host in self.api_candidates:
                    self.api_candidates.remove(host)
                    self.api_candidates.insert(0, host)
                return value
            except Exception as error:
                last = error
        raise RuntimeError(last or 'No AQX API available')

    def _get_apis(self):
        if self.api_candidates and time.time() - self._api_updated < 1800:
            return list(self.api_candidates)
        discovered = []
        try:
            html = self._verified_home()
            for decoded in self._decode_scripts(html):
                try:
                    value = json.loads(decoded)
                    if isinstance(value, list):
                        discovered.extend(value)
                except Exception:
                    pass
            match = re.search(r'window\.__rv\s*=\s*[\'\"]([^\'\"]+)', html)
            if match:
                self.channel = match.group(1).strip() or self.channel
        except Exception as error:
            self.log('AQX API discovery: %s' % error)
        # The site publishes these dynamically after its JS challenge.  Keep
        # known public endpoints as a resilient fallback when that challenge
        # page is temporarily rotated or unavailable.
        self.api_candidates = self._unique_hosts(discovered + self.api_candidates + self.FALLBACK_APIS)
        self._api_updated = time.time()
        return list(self.api_candidates)

    def _verified_home(self):
        response = self.session.get(self.web_host + '/home', headers={**self.headers, 'Accept': 'text/html,*/*'},
                                    timeout=18, verify=False)
        response.raise_for_status()
        text = response.text
        if '/__js_challenge/html' not in text:
            return text
        scripts = self._decode_scripts(text)
        script = next((x for x in scripts if 'postUrl' in x and 'difficulty' in x), '')
        match = re.search(r'const q=\"[^\"]*\",p=(\{.*?\}),d=document', script, re.S)
        if not match:
            raise ValueError('AQX challenge parameters not found')
        task = json.loads(match.group(1))
        proof = self._proof(task.get('task') or {})
        meta = {'ua': self.headers['User-Agent'], 'lang': 'zh-CN', 'tz': 'Asia/Shanghai',
                'screen': '1920x1080', 'webdriver': False, 'framed': False}
        key_text = '|'.join([str(task.get('nonce')), str(task.get('issuedAt')), meta['ua'], meta['lang'],
                             meta['tz'], meta['screen'], str(proof)])
        body = {'nonce': task.get('nonce'), 'issuedAt': task.get('issuedAt'),
                'key': self._fnv1a(key_text), 'meta': meta, 'proof': proof, 'path': '/home'}
        verified = self.session.post(urljoin(self.web_host + '/', str(task.get('postUrl')).lstrip('/')),
            headers={**self.headers, 'Content-Type': 'application/json'}, json=body, timeout=18, verify=False)
        verified.raise_for_status()
        if '/__js_challenge/html' in verified.text:
            raise ValueError('AQX challenge failed')
        return verified.text

    @staticmethod
    def _decode_scripts(text):
        result = []
        for encoded, key, _ in re.findall(r'const _0=\"([^\"]+)\",_1=\"([^\"]+)\",_2=\"([^\"]*)\"', text or ''):
            try:
                raw = base64.b64decode(encoded)
                key_bytes = key.encode('utf-8')
                result.append(bytes(v ^ key_bytes[i % len(key_bytes)] for i, v in enumerate(raw)).decode('utf-8'))
            except Exception:
                pass
        return result

    @classmethod
    def _proof(cls, task):
        seed = str(task.get('seed') or '')
        difficulty = max(1, cls._int(task.get('difficulty'), 1))
        maximum = max(1, cls._int(task.get('maxIterations'), 150000))
        for value in range(maximum):
            if cls._fnv1a(seed + '|' + str(value)).startswith('0' * difficulty):
                return value
        raise ValueError('AQX proof not found')

    @staticmethod
    def _fnv1a(value):
        number = 2166136261
        for char in str(value):
            number = ((number ^ ord(char)) * 16777619) & 0xFFFFFFFF
        return '%08x' % number

    def _unwrap(self, payload):
        value = payload
        for _ in range(5):
            value, changed = self._unwrap_once(value)
            if not changed:
                break
        return value

    def _unwrap_once(self, value):
        if isinstance(value, dict):
            if isinstance(value.get('key'), str) and isinstance(value.get('data'), str):
                result = dict(value)
                result['data'] = self._decrypt(value['data'], value['key'])
                result.pop('key', None)
                return result, True
            result, changed = {}, False
            for key, child in value.items():
                result[key], child_changed = self._unwrap_once(child)
                changed = changed or child_changed
            return result, changed
        if isinstance(value, list):
            result, changed = [], False
            for child in value:
                child, child_changed = self._unwrap_once(child)
                result.append(child)
                changed = changed or child_changed
            return result, changed
        return value, False

    def _decrypt(self, encrypted, password):
        try:
            raw = self._b64(''.join(chr(ord(char) - 3) for char in encrypted))
            if len(raw) < 44:
                raise ValueError('short AES payload')
            salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
            key = PBKDF2(password.encode('utf-8'), salt, dkLen=32, count=1000, hmac_hash_module=SHA256)
            plain = AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(ciphertext[:-16], ciphertext[-16:])
        except Exception:
            raw = self._b64(encrypted)
            key = password.encode('utf-8')
            plain = bytes(value ^ key[index % len(key)] for index, value in enumerate(raw))
        text = plain.decode('utf-8')
        try:
            return json.loads(text)
        except Exception:
            return text

    @staticmethod
    def _b64(value):
        text = re.sub(r'\s+', '', str(value or '')).replace('-', '+').replace('_', '/')
        return base64.b64decode(text + '=' * ((4 - len(text) % 4) % 4))

    def _sources(self, item):
        sources = []
        direct = self._text(item.get('play_hls_url') or item.get('href'))
        if direct.startswith('/'):
            direct = urljoin(self.web_host + '/', direct.lstrip('/'))
        cdn_items = self._list(item.get('cdn_list'))
        cdn_items = sorted(
            cdn_items,
            key=lambda cdn: (
                0 if str(cdn.get('id', cdn.get('cdnId', cdn.get('cdn_id', '')))) == self.preferred_cdn else 1,
                0 if cdn.get('isDefault') else 1,
            ) if isinstance(cdn, dict) else (2, 2),
        )
        if cdn_items and direct.startswith(('http://', 'https://')):
            # The API puts only the CDN origin in videoUrl.  Reuse the manifest
            # endpoint and switch its cdnId query parameter for each line.
            for index, cdn in enumerate(cdn_items, 1):
                if not isinstance(cdn, dict):
                    continue
                cdn_id = cdn.get('id', cdn.get('cdnId', cdn.get('cdn_id')))
                url = ''
                for key in ('play_hls_url', 'hls_url', 'm3u8', 'm3u8_url', 'href', 'url'):
                    candidate = self._text(cdn.get(key))
                    if candidate.startswith('/'):
                        candidate = urljoin(self.web_host + '/', candidate.lstrip('/'))
                    if candidate.startswith(('http://', 'https://')):
                        url = candidate
                        break
                if not url:
                    url = self._with_cdn_id(direct, cdn_id)
                if url:
                    name = self._text(cdn.get('title') or cdn.get('name'))
                    if not name:
                        name = '默认线路' if cdn.get('isDefault') else ('线路%d' % index)
                    sources.append({'name': name, 'url': url})
        elif direct.startswith(('http://', 'https://')):
            sources.append({'name': '默认线路', 'url': direct})
        for index, key in enumerate(('href_1', 'href_2', 'href_3', 'href_4', 'href_5'), 1):
            url = self._text(item.get(key))
            if url.startswith('/'):
                url = urljoin(self.web_host + '/', url.lstrip('/'))
            if url.startswith(('http://', 'https://')):
                sources.append({'name': 'Line%d' % index, 'url': url})
        result, seen = [], set()
        for source in sources:
            if source['url'] not in seen:
                seen.add(source['url'])
                result.append(source)
        return result

    @staticmethod
    def _with_cdn_id(url, cdn_id):
        if cdn_id is None or str(cdn_id).strip() == '':
            return url
        parsed = urlparse(url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        replaced = False
        for index, (key, value) in enumerate(query):
            if key.lower() == 'cdnid':
                query[index] = (key, str(cdn_id))
                replaced = True
        if not replaced:
            query.append(('cdnId', str(cdn_id)))
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _video(self, item, remark=''):
        item = item if isinstance(item, dict) else {}
        return {'vod_id': str(item.get('id') or item.get('video_id') or ''),
                'vod_name': self._text(item.get('title') or item.get('name')),
                'vod_pic': self._image(item.get('upload_thumb') or item.get('thumb') or item.get('backstage_thumb')),
                'vod_remarks': self._text(item.get('label') or item.get('duration') or remark),
                'style': {'type': 'rect', 'ratio': 1.78}}

    def _image(self, value):
        url = self._text(value)
        if not url:
            return ''
        if not url.startswith(('http://', 'https://')):
            url = urljoin(self.web_host + '/', url.lstrip('/'))
        if not urlparse(url).path.lower().endswith('.enc'):
            return url
        signature = self._image_signature(url)
        return '%s&type=aqx_img&url=%s&sig=%s' % (
            self.getProxyUrl(), quote(url, safe=''), signature
        )

    def _image_signature(self, url):
        return hmac.new(self.IMAGE_KEY, str(url).encode('utf-8'), hashlib.sha256).hexdigest()

    def _manifest_proxy_url(self, remote_url):
        remote_url = str(remote_url or '').strip()
        if not self._is_hls_url(remote_url):
            return ''
        try:
            proxy = str(self.getProxyUrl() or '')
        except Exception:
            return ''
        if not proxy:
            return ''
        separator = '&' if '?' in proxy else '?'
        return '%s%stype=aqx_m3u8&url=%s&sig=%s' % (
            proxy, separator, quote(remote_url, safe=''),
            self._manifest_signature(remote_url),
        )

    def _manifest_signature(self, remote_url):
        message = ('aqx_m3u8\n' + str(remote_url)).encode('utf-8')
        return hmac.new(self.IMAGE_KEY, message, hashlib.sha256).hexdigest()

    @staticmethod
    def _is_hls_url(value):
        url = str(value or '').strip()
        if not url.startswith(('http://', 'https://')):
            return False
        parsed = urlparse(url)
        path = parsed.path.lower()
        return (
            path.endswith('.m3u8')
            or '/hls/m3u8/' in path
            or path.endswith('_play') and '/hls/' in path
            or 'type=aqx_m3u8' in url.lower()
        )

    @staticmethod
    def _absolute_manifest(manifest, base_url):
        output = []
        for raw_line in str(manifest or '').replace('\r', '').split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('#'):
                def replace_uri(match):
                    target = urljoin(base_url, match.group(2))
                    return 'URI=%s%s%s' % (match.group(1), target, match.group(1))

                output.append(re.sub(
                    r"URI=([\"'])(.*?)(\1)", replace_uri, line, flags=re.I
                ))
            else:
                output.append(urljoin(base_url, line))
        return '\n'.join(output) + '\n'

    def _decrypt_image(self, encrypted):
        if len(encrypted) <= AES.block_size:
            raise ValueError('AQX encrypted cover is too short')
        iv, payload = encrypted[:AES.block_size], encrypted[AES.block_size:]
        if not payload or len(payload) % AES.block_size:
            raise ValueError('AQX encrypted cover has invalid block length')
        plain = AES.new(self.IMAGE_KEY, AES.MODE_CBC, iv).decrypt(payload)
        image = unpad(plain, AES.block_size)
        if self._image_mime(image) == 'application/octet-stream':
            raise ValueError('AQX decrypted cover has unknown format')
        return image

    @staticmethod
    def _image_mime(data):
        if data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        if data.startswith(b'\x89PNG'):
            return 'image/png'
        if data.startswith(b'GIF8'):
            return 'image/gif'
        if len(data) > 11 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'image/webp'
        return 'application/octet-stream'

    def _play_headers(self, url):
        parsed = urlparse(url)
        return {
            'User-Agent': self.headers['User-Agent'],
            'Referer': parsed.scheme + '://' + parsed.netloc + '/',
            # The bundled IJK/FFmpeg build cannot decode Brotli responses.
            'Accept-Encoding': 'identity',
        }

    @staticmethod
    def _config(extend):
        if isinstance(extend, dict):
            return extend
        text = str(extend or '').strip()
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {'host': text} if text.startswith(('http://', 'https://')) else {}

    @staticmethod
    def _unique_hosts(values):
        result = []
        for value in values or []:
            host = str(value or '').strip().rstrip('/')
            if host.startswith(('http://', 'https://')) and host not in result:
                result.append(host)
        return result

    @staticmethod
    def _list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ('list', 'items', 'data'):
                if isinstance(value.get(key), list):
                    return value[key]
        return []

    @staticmethod
    def _text(value):
        return str(value or '').strip()

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _clean_html(value):
        return re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', '\n', str(value or ''), flags=re.I)).strip()

    @staticmethod
    def _safe_name(value):
        return re.sub(r'[#$]+', ' ', str(value or '')).strip()

    @staticmethod
    def _category_id(item_id, item_type):
        return str(item_type or 'cate') + '|' + str(item_id)

    @staticmethod
    def _parse_category_id(tid):
        value = str(tid or '')
        if '|' in value:
            item_type, item_id = value.split('|', 1)
            return item_id, item_type
        return value, 'cate'

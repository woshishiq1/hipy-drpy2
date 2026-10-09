# -*- coding: utf-8 -*-
"""
kaiduan.fun CMS 采集 Spider

接口：
  分类 /user/movie/cms/v1/category?count=20&names={tid}&page={pg}
  搜索 /user/movie/cms/v1/search?name={key}&page=1&count=10
  详情 /user/movie/cms/v1/play?id={id}

数据格式：
  响应头前缀 AkEdSJx，剩余部分 Base64( key(16) + iv(16) + AES_CBC密文 )
  部分接口返回再套一层 Base64，需要二次解码

详情返回结构：
  {
    "code": 1,
    "data": { ... 视频信息 ... },
    "datas": [
      {"id": xxx, "name": "kdjx", "urls": "正片$https://.../redirect/xxx.m3u8"}
    ]
  }
"""

import base64
import json
import sys
import urllib3
from urllib.parse import urljoin

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from base.spider import Spider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')


class Spider(Spider):

    host = ''
    site = ''
    timeout = 10

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2; rv:107) '
            'Gecko/20100101 Firefox/98'
        ),
        'Accept-Encoding': 'gzip',
        'referer': '',
    }

    DEFAULT_HOST = 'https://api.kaiduan.fun'

    # ---------- 初始化 ----------
    def init(self, extend=''):
        try:
            ext = json.loads(extend) if extend else {}
            self.host = (ext.get('host') or self.DEFAULT_HOST).rstrip('/')
            self.headers['referer'] = f'{self.host}/'

            cookie = ext.get('cookie') or ext.get('Cookie')
            if cookie:
                self.headers['Cookie'] = cookie

            self.site = ext.get('site')
            if ext.get('timeout'):
                self.timeout = ext['timeout']
        except Exception as e:
            print(f'[init] {e}', file=sys.stderr)
            self.host = self.DEFAULT_HOST

    # ---------- 首页 ----------
    def homeContent(self, filter):
        if not self.host:
            return None
        return {
            'class': [
                {'type_id': '电影',   'type_name': '电影'},
                {'type_id': '连续剧', 'type_name': '连续剧'},
                {'type_id': '动漫',   'type_name': '动漫'},
                {'type_id': '短剧',   'type_name': '短剧'},
                {'type_id': '综艺',   'type_name': '综艺'},
                {'type_id': '纪录片', 'type_name': '纪录片'},
            ]
        }

    def homeVideoContent(self):
        return self.categoryContent('电影', 1, False, {})

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        if not self.host:
            return None
        try:
            url = (
                f'{self.host}/user/movie/cms/v1/category'
                f'?count=20&names={tid}&page={pg}'
            )
            raw = self.fetch(url, headers=self.headers,
                             verify=False, timeout=self.timeout).text
            data = json.loads(self.decrypt(raw)).get('datas') or []
            return {'list': self.arr2vods(data)}
        except Exception as e:
            print(f'[categoryContent] {e}', file=sys.stderr)
            return {'list': []}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        if not self.host or str(pg) != '1':
            return None
        try:
            url = (
                f'{self.host}/user/movie/cms/v1/search'
                f'?name={key}&page=1&count=10'
            )
            raw = self.fetch(url, headers=self.headers,
                             verify=False, timeout=self.timeout).text
            root = json.loads(self.decrypt(raw))
            data = root.get('datas') or root.get('data') or []
            if isinstance(data, dict):
                data = [data]
            return {'list': self.arr2vods(data), 'page': pg}
        except Exception as e:
            print(f'[searchContent] {e}', file=sys.stderr)
            return {'list': [], 'page': pg}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not self.host:
            return None

        try:
            vid = str(ids[0])
            url = f'{self.host}/user/movie/cms/v1/play?id={vid}'

            raw = self.fetch(url, headers=self.headers,
                             verify=False, timeout=self.timeout).text
            root = json.loads(self.decrypt(raw))

            data = root.get('data') or {}
            datas = root.get('datas') or []

            # 播放线路：每条 {"id":x, "name":"kdjx", "urls":"正片$https://...m3u8"}
            show, play_urls = [], []
            for idx, line in enumerate(datas):
                line_name = line.get('name') or f'线路{idx + 1}'
                urls = line.get('urls') or ''
                if urls:
                    show.append(line_name)
                    play_urls.append(urls)

            video = {
                'vod_id': vid,
                'vod_name': data.get('name') or '',
                'vod_pic': data.get('pic') or '',
                'vod_remarks': data.get('remarks') or '',
                'vod_year': data.get('year') or '',
                'vod_area': data.get('area') or '',
                'vod_actor': data.get('actor') or '',
                'vod_director': data.get('director') or '',
                'vod_content': data.get('content') or '',
                'vod_play_from': '$$$'.join(show),
                'vod_play_url': '$$$'.join(play_urls),
                'type_name': data.get('classify') or data.get('category') or '',
            }
            return {'list': [video]}
        except Exception as e:
            print(f'[detailContent] {e}', file=sys.stderr)
            return None

    # ---------- 播放 ----------
    def playerContent(self, flag, url, vip_flags):
        # url 格式："正片$https://..."，取出 $ 后面的部分
        if '$' in url:
            url = url.split('$', 1)[1]

        # 如果不以 http 开头，尝试 base64 解码
        try:
            if url and not url.startswith('http'):
                decoded = base64.b64decode(url + '=' * (-len(url) % 4))
                decoded = decoded.decode('utf-8', errors='ignore')
                if decoded.startswith('http'):
                    url = decoded
        except Exception:
            pass

        # 跟踪 redirect 拿真实地址（若是 302）
        try:
            real = self.raw_url(url)
            if real:
                url = real
        except Exception:
            pass

        return {
            'jx': 0,
            'parse': '0',
            'url': url,
            'header': {
                'User-Agent': (
                    'ijkplayer/1.0.0 (Linux;Android 11) '
                    'ExoPlayerLib/2.14.1'
                ),
                'Accept-Encoding': 'gzip',
            },
        }

    # ---------- 解密 ----------
    def decrypt(self, data: str) -> str:
        prefix = "AkEdSJx"
        if not data.startswith(prefix):
            return data

        raw = base64.b64decode(data[len(prefix):])
        if len(raw) < 32:
            raise ValueError("加密数据太短")

        key, iv, ct = raw[:16], raw[16:32], raw[32:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ct), AES.block_size).decode('utf-8')

        # 部分接口是双层：先 AES 再 Base64
        p = plaintext.strip()
        try:
            decoded = base64.b64decode(
                p + "=" * ((4 - len(p) % 4) % 4)
            ).decode('utf-8')
            if decoded.lstrip()[:1] in ('{', '['):
                return decoded
        except Exception:
            pass

        return plaintext

    # ---------- 列表转 vod ----------
    def arr2vods(self, arr):
        videos = []
        if not arr:
            return videos

        for item in arr:
            vid = item.get('id') or item.get('url') or item.get('vodId')
            if vid is None:
                continue

            videos.append({
                'vod_id': vid,
                'vod_name': item.get('name') or item.get('vodName') or '',
                'vod_pic': item.get('pic') or item.get('vodPic') or '',
                'vod_remarks': item.get('remarks') or item.get('vodRemarks') or '',
                'vod_year': item.get('year') or item.get('vodYear') or '',
                'type_name': (
                    item.get('classify')
                    or item.get('category')
                    or item.get('vodClass')
                    or ''
                ),
            })
        return videos

    # ---------- 获取真实地址（跟踪 302） ----------
    def raw_url(self, original_url):
        try:
            response = self.fetch(
                original_url, allow_redirects=False,
                stream=True, timeout=20,
            )
            if 300 <= response.status_code < 400:
                loc = response.headers.get('Location')
                if loc:
                    return urljoin(original_url, loc)
            return original_url
        except Exception:
            return original_url

    # ---------- 框架接口 ----------
    def getName(self):
        return self.site or 'kaiduan'

    def isVideoFormat(self, url):
        if not url:
            return False
        exts = ('.m3u8', '.mp4', '.flv', '.avi',
                '.mkv', '.ts', '.mov', '.webm')
        return any(url.lower().split('?')[0].endswith(e) for e in exts)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                url = param.get('url') or param.get('src') or ''
            else:
                url = str(param)
            if not url:
                return [404, 'text/plain', b'']
            real_url = self.raw_url(url)
            return [302, 'text/plain', b'', {'Location': real_url}]
        except Exception as e:
            print(f'[localProxy] {e}', file=sys.stderr)
            return [500, 'text/plain', str(e).encode('utf-8')]

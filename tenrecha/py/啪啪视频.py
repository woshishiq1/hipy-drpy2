# coding=utf-8
# !/usr/bin/python
"""
啪啪视频 T3 爬虫源
站点: 4.pp795pp.cc:88
"""

import sys
sys.path.append('..')

from base.spider import BaseSpider
from base.htmlParser import jsoup
import requests
import re
import html as _html
import base64
from urllib.parse import quote, unquote

# ============================================================
# 全局配置
# ============================================================
TIMEOUT = 15
HOST = 'https://4.pp795pp.cc:88'
PROXY_TYPE = 'pp795_img'


class Spider(BaseSpider):

    # ---- 基础信息 ----
    def getName(self):
        return "啪啪视频"

    def isVideoFormat(self, url):
        return bool(url) and '.m3u8' in url

    def manualVideoCheck(self):
        return False

    def init(self, extend=""):
        self._proxy_prefix = ''

    # ---- 类变量 ----
    filterable = True
    searchable = True
    host = HOST
    _proxy_prefix = ''
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": HOST + '/',
    }

    # ============================================================
    # HTML 解码 (页面被 decodeURIComponent 包裹)
    # ============================================================
    def _decode_html(self, raw):
        if not raw:
            return ''
        try:
            decoded = unquote(raw)
        except Exception:
            decoded = raw
        if '<html' in decoded.lower() or '<body' in decoded.lower():
            # 二次解码：HTML 属性值可能仍有 URL 编码 (如 %3D → =, %22 → ")
            try:
                return unquote(decoded)
            except Exception:
                return decoded
        return raw

    # ============================================================
    # 网络请求
    # ============================================================
    def _fetch(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=TIMEOUT, verify=False)
            return self._decode_html(r.text)
        except Exception:
            return ''

    # ============================================================
    # 图片代理
    # ============================================================
    def _ensure_proxy_prefix(self):
        if self._proxy_prefix:
            return
        base = self.getProxyUrl() or 'http://127.0.0.1:9980/proxy?do=py'
        self._proxy_prefix = base + '&type=' + PROXY_TYPE + '&url='

    def _proxy_img(self, url):
        if not url:
            return ''
        self._ensure_proxy_prefix()
        return self._proxy_prefix + quote(url, safe='')

    # ============================================================
    # 视频列表解析
    # ============================================================
    def _parse_video_list(self, html):
        if not html:
            return []
        jsp = jsoup(self.host)
        items = jsp.pdfa(html, '.vod-item')
        results = []
        for item in items:
            href = jsp.pdfh(item, 'div&&to') or jsp.pdfh(item, 'a&&to')
            if not href:
                to_match = re.search(r'to=["\'](/play/[^"\']+)', item)
                href = to_match.group(1) if to_match else ''
            if not href or '/play/' not in href:
                continue
            vid = href.replace('/play/', '')
            title = _html.unescape(jsp.pdfh(item, '.rank-title&&Text') or '')
            pic = jsp.pdfh(item, 'img&&data-original') or jsp.pdfh(item, 'img&&src')

            # 时长
            dur = ''
            dur_match = re.search(r'secondsToHMS\((\d+)\)', item)
            if dur_match:
                s = int(dur_match.group(1))
                dur = f'{s // 60:02d}:{s % 60:02d}'

            # 热度
            hits = jsp.pdfh(item, '.pre-hits span&&Text') or ''

            results.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_img(pic),
                'vod_remarks': dur or hits,
            })
        return results

    def _get_pagecount(self, html):
        m = re.search(r'var\s+total\s*=\s*parseInt\((\d+)\)', html)
        if m:
            return int(m.group(1))
        m = re.search(r'/ (\d+)</span>', html)
        if m:
            return int(m.group(1))
        return 1

    # ============================================================
    # 首页
    # ============================================================
    def homeContent(self, filter):
        html = self._fetch(self.host)
        if not html:
            return {'class': [], 'type': '影视'}

        jsp = jsoup(self.host)
        classes = []
        seen_names = set()
        skip_tids = {'28', '29'}  # 其他综艺、成人游戏
        for span in jsp.pdfa(html, '.v-s-li-nav-link-vs.a-link'):
            href = jsp.pdfh(span, 'span&&to')
            name = _html.unescape(jsp.pdfh(span, 'span&&Text') or '')
            if href and name and '/type/' in href and name not in seen_names:
                seen_names.add(name)
                tid = href.split('/type/')[1].strip('/')
                if tid in skip_tids:
                    continue
                classes.append({'type_name': name, 'type_id': tid})

        # 首页推荐列表
        home_list = self._parse_video_list(html)
        return {'class': classes, 'list': home_list, 'type': '影视'}

    def homeVideoContent(self, tid, pg, filter, extend):
        pg = int(pg)
        url = self.host if pg <= 1 else f'{self.host}/page/{pg}'
        html = self._fetch(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        data = self._parse_video_list(html)
        pagecount = self._get_pagecount(html)
        return {'list': data, 'page': pg, 'pagecount': pagecount,
                'limit': len(data), 'total': pagecount * len(data)}

    # ============================================================
    # 分类列表
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        url = f'{self.host}/type/{tid}' if pg <= 1 else f'{self.host}/type/{tid}/{pg}'
        html = self._fetch(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        data = self._parse_video_list(html)
        pagecount = self._get_pagecount(html)
        return {'list': data, 'page': pg, 'pagecount': pagecount,
                'limit': len(data), 'total': pagecount * len(data)}

    # ============================================================
    # 详情页
    # ============================================================
    def detailContent(self, ids):
        did = ids[0] if isinstance(ids, list) else ids
        url = f'{self.host}/play/{did}'
        html = self._fetch(url)
        if not html:
            return {'list': []}

        jsp = jsoup(self.host)

        # 标题
        title = _html.unescape(jsp.pdfh(html, '.video-title&&Text') or '')

        # M3U8 地址 (页面内嵌 JS 变量)
        m3u8 = ''
        m = re.search(r'var\s+url\s*=\s*["\']([^"\']+\.m3u8[^"\']*)', html)
        if m:
            m3u8 = m.group(1)

        play_url = f'播放${m3u8}' if m3u8 else ''

        return {'list': [{
            'vod_id': did,
            'vod_name': title or did,
            'vod_pic': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_play_from': '啪啪视频',
            'vod_play_url': play_url,
            'type': 'video',
        }]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg=1):
        pg = int(pg)
        encoded = quote(key, safe='')
        url = f'{self.host}/search/{encoded}' if pg <= 1 else f'{self.host}/search/{encoded}/{pg}'
        html = self._fetch(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        data = self._parse_video_list(html)
        pagecount = self._get_pagecount(html)
        return {'list': data, 'page': pg, 'pagecount': pagecount,
                'limit': len(data), 'total': pagecount * len(data)}

    # ============================================================
    # 播放解析
    # ============================================================
    def playerContent(self, flag, id, vipFlags=None):
        url = id
        # 如果 id 不含 m3u8，可能是 vod_id，从详情页重新取
        if not url or '.m3u8' not in url:
            detail_url = f'{self.host}/play/{id}'
            html = self._fetch(detail_url)
            m = re.search(r'var\s+url\s*=\s*["\']([^"\']+\.m3u8[^"\']*)', html) if html else None
            url = m.group(1) if m else ''

        if not url:
            return {'parse': 1, 'url': '', 'jx': 0}

        try:
            r = requests.head(url, headers=self.headers, timeout=TIMEOUT,
                            verify=False, allow_redirects=True)
            final_url = r.url
        except Exception:
            final_url = url

        return {'parse': 0, 'url': final_url, 'jx': 0,
                'header': {'Referer': self.host + '/'}}

    # ============================================================
    # 图片代理
    # ============================================================
    def _detect_mime(self, data):
        """根据 magic bytes 检测图片 MIME 类型"""
        if data[:2] == b'\xff\xd8':
            return 'image/jpeg'
        elif data[:4] == b'\x89PNG':
            return 'image/png'
        elif data[:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
            return 'image/webp'
        return 'image/jpeg'  # 默认

    def localProxy(self, params):
        try:
            if params.get('type') != PROXY_TYPE:
                return [404, 'text/plain', 'not found']

            img_url = params.get('url', '')
            if not img_url:
                return [400, 'text/plain', 'missing url']

            img_url = unquote(img_url)
            headers = dict(self.headers)
            headers['Referer'] = self.host + '/'

            is_dat = img_url.lower().endswith('.dat')

            if is_dat:
                # .dat 文件的响应体是 base64 字符串，解码后得到实际图片二进制
                r = requests.get(img_url, headers=headers, timeout=TIMEOUT, verify=False)
                if r.status_code != 200:
                    return [404, 'text/plain', 'image not found']
                try:
                    b64_text = "".join(r.text.split())
                    data = base64.b64decode(b64_text)
                    mime = self._detect_mime(data)
                    return [200, mime, data, {'Content-Length': str(len(data))}]
                except Exception:
                    return [404, 'text/plain', 'decode error']
            else:
                r = requests.get(img_url, headers=headers, timeout=TIMEOUT, verify=False)
                if r.status_code != 200:
                    return [404, 'text/plain', 'image not found']
                data = r.content
                mime = r.headers.get('Content-Type', 'image/jpeg')
                if not mime.startswith('image/'):
                    mime = self._detect_mime(data)
                return [200, mime, data, {'Content-Length': str(len(data))}]
        except Exception:
            return [500, 'text/plain', 'proxy error']

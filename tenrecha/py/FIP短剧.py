# -*- coding: utf-8 -*-@猪猪
"""
fip.539582.xyz Python Spider (基于 ump 模板修改)
"""
import sys
import re
import base64
import json
from urllib.parse import quote

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    HOST = 'https://fip.539582.xyz'   # 修改为新站域名

    def getName(self):
        return "FIP短剧"               # 修改为合适的名称

    def init(self, extend=''):
        self.host = self.HOST
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/',
        }
        self._classes = None

    # ========== 基础工具 ==========

    def _fetch_html(self, url, timeout=15):
        try:
            rsp = self.fetch(url, headers=self.header, timeout=timeout)
            return rsp.text
        except Exception:
            return ''

    def _decode_page(self, html):
        """页面层解码: 动态找 window.atob 函数 → 提取参数 → 反转 → b64decode → utf-8"""
        if not html:
            return None

        func_match = re.search(
            r'function\s+(\w+)\s*\(\s*\w+\s*\)\s*\{\s*var\s+\w+\s*=\s*window\.atob',
            html
        )
        if not func_match:
            return None

        fname = func_match.group(1)

        # 跳过函数定义, 找调用 = fname('...')
        func_end = html.find('}', html.find('return', html.find(fname)))
        if func_end == -1:
            return None
        call_area = html[func_end + 1:]

        call_match = re.search(r'=\s*' + re.escape(fname) + r'\s*\(', call_area)
        if not call_match:
            return None

        # 手动配对引号, 处理超长字符串
        rest = call_area[call_match.end():].lstrip()
        if not rest:
            return None
        quote_char = rest[0]
        end_quote = rest.find(quote_char, 1)
        if end_quote <= 0:
            return None
        arg = rest[1:end_quote]

        # 反转 → b64decode → utf-8
        try:
            rev = arg[::-1]
            pad = 4 - len(rev) % 4
            if pad != 4:
                rev += '=' * pad
            raw = base64.b64decode(rev)
            return raw.decode('utf-8', errors='replace')
        except Exception:
            return None

    def _extract_json(self, decoded):
        """从解码后的页面内容中提取 j_b64, 解码为 JSON"""
        if not decoded:
            return None

        m = re.search(r"j_b64\s*=\s*'([^']+)'", decoded)
        if not m:
            return None

        try:
            j_raw = base64.b64decode(m.group(1))
            j_str = j_raw.decode('utf-8', errors='replace')
            return json.loads(j_str)
        except Exception:
            return None

    def _parse_videos_from_json(self, j_data):
        """从 JSON 中解析视频列表"""
        videos = []
        if not j_data or 'l' not in j_data:
            return videos

        l_data = j_data.get('l', {})
        if isinstance(l_data, dict):
            items = []
            for k in l_data:
                items.extend(l_data[k])
        elif isinstance(l_data, list):
            items = l_data
        else:
            return videos

        seen = set()
        for item in items:
            vid_url = item.get('url', '')
            m = re.search(r'/(\d+)\.html', vid_url)
            vid = m.group(1) if m else vid_url

            if vid in seen:
                continue
            seen.add(vid)

            videos.append({
                'vod_id': vid,
                'vod_name': item.get('title', '') or vid,
                'vod_pic': item.get('pic', ''),
                'vod_remarks': ''
            })

        return videos

    def _load_classes(self):
        """从 JS 模板文件提取分类列表"""
        if self._classes is not None:
            return self._classes

        try:
            # 1. 获取首页, 解码出 JS 文件路径
            html = self._fetch_html(self.host + '/')
            decoded = self._decode_page(html)
            if not decoded:
                raise Exception("首页解码失败")

            js_match = re.search(r"loadScript\(['\"]([^'\"]+\.js)['\"]", decoded)
            if not js_match:
                raise Exception("未找到JS文件路径")

            # 2. 获取 JS 文件, 解码 var h
            js_html = self._fetch_html(self.host + js_match.group(1))
            h_match = re.search(r"var\s+h\s*=\s*'([^']+)'", js_html)
            if not h_match:
                raise Exception("JS文件中未找到 var h")

            h_decoded = base64.b64decode(h_match.group(1)).decode('utf-8', errors='replace')

            # 3. 用单条正则同时匹配 href 和 d('base64_name')
            cat_pattern = re.findall(
                r'href=["\']?(/list/(\d+)-\d+\.html)["\']?[^>]*>.*?d\([\'"]([^\'"]+)[\'"]\)',
                h_decoded, re.S
            )

            classes = []
            seen = set()
            for full_link, tid, b64_name in cat_pattern:
                if tid in seen:
                    continue
                seen.add(tid)

                name = ''
                try:
                    s = b64_name
                    pad = 4 - len(s) % 4
                    if pad != 4:
                        s += '=' * pad
                    name = base64.b64decode(s).decode('utf-8', errors='replace')
                    if '\ufffd' in name:
                        name = ''
                except Exception:
                    name = ''

                classes.append({'type_id': tid, 'type_name': name or tid})

            self._classes = classes if classes else self._fallback_classes()
        except Exception:
            self._classes = self._fallback_classes()

        return self._classes

    def _fallback_classes(self):
        # 此列表可能需要根据 fip.539582.xyz 的实际分类调整
        return [
            {'type_id': '27324551', 'type_name': '传媒作品'},
            {'type_id': '27334551', 'type_name': '网黄女神'},
            {'type_id': '27344551', 'type_name': '外围探花'},
            {'type_id': '27354551', 'type_name': '直播大秀'},
            {'type_id': '27364551', 'type_name': '绿帽淫妻'},
            {'type_id': '27374551', 'type_name': '夫妻交换'},
            {'type_id': '27384551', 'type_name': '亚洲媚黑'},
            {'type_id': '27394551', 'type_name': '良家人妻'},
            {'type_id': '27314582', 'type_name': '国产磁力'},
            {'type_id': '27324582', 'type_name': '日本磁力'},
            {'type_id': '27504581', 'type_name': '国产精品'},
        ]

    def _url(self, path):
        if not path:
            return self.host
        if path.startswith('http'):
            return path
        return self.host + path if path.startswith('/') else self.host + '/' + path

    # ========== 首页 ==========

    def homeContent(self, filter):
        return {
            'class': self._load_classes(),
            'filters': {},
        }

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.host + '/')
            decoded = self._decode_page(html)
            j_data = self._extract_json(decoded)
            videos = self._parse_videos_from_json(j_data)
            return {'list': videos[:72]}
        except Exception:
            return {'list': []}

    # ========== 分类 ==========

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            url = f"{self.host}/list/{tid}-{pg}.html"
            html = self._fetch_html(url)

            if not html or len(html) < 100:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 16, 'total': 0}

            decoded = self._decode_page(html)
            j_data = self._extract_json(decoded)

            if not j_data:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 16, 'total': 0}

            videos = self._parse_videos_from_json(j_data)

            page_info = j_data.get('p', {})
            pagecount = int(page_info.get('t', 1)) if isinstance(page_info, dict) else 1
            total = int(page_info.get('s', len(videos))) if isinstance(page_info, dict) else len(videos)

            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 16,
                'total': total
            }
        except Exception:
            return {'list': [], 'page': int(pg or 1), 'pagecount': 1, 'limit': 16, 'total': 0}

    # ========== 详情 ==========

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            url = f"{self.host}/video/{vid}.html"
            html = self._fetch_html(url)

            if not html or len(html) < 100:
                return {'list': [{'vod_id': vid, 'vod_name': str(vid)}]}

            decoded = self._decode_page(html)
            j_data = self._extract_json(decoded)

            vod = {
                'vod_id': vid,
                'vod_name': vid,
                'vod_pic': '',
                'vod_content': '',
                'vod_play_from': 'FIP短剧',
                'vod_play_url': ''
            }

            if j_data:
                vod['vod_name'] = j_data.get('name', '') or vid
                vod['vod_pic'] = j_data.get('co', '')

                related = j_data.get('l', {}).get('a', [])
                if related:
                    titles = [v.get('title', '') for v in related[:5]]
                    vod['vod_content'] = '相关推荐: ' + ' | '.join(titles)

                m3u8_url = j_data.get('m3', '')
                if m3u8_url:
                    vod['vod_play_url'] = '播放$' + m3u8_url
                else:
                    cdn_list = j_data.get('cdn', [])
                    if cdn_list and isinstance(cdn_list, list):
                        cdn_url = cdn_list[0].get('url', '')
                        if cdn_url:
                            vod['vod_play_url'] = '播放$' + cdn_url

            return {'list': [vod]}
        except Exception:
            return {'list': []}

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg or 1)
            search_url = f"{self.host}/index.php?m=vod-search-wd-{quote(key)}"
            if pg > 1:
                search_url += f"-{pg}"
            search_url += ".html"

            html = self._fetch_html(search_url)

            if not html or len(html) < 100:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 16, 'total': 0}

            decoded = self._decode_page(html)
            j_data = self._extract_json(decoded)

            if not j_data:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 16, 'total': 0}

            videos = self._parse_videos_from_json(j_data)

            page_info = j_data.get('p', {})
            pagecount = int(page_info.get('t', 1)) if isinstance(page_info, dict) else 1
            total = int(page_info.get('s', len(videos))) if isinstance(page_info, dict) else len(videos)

            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 16,
                'total': total
            }
        except Exception:
            return {'list': [], 'page': int(pg or 1), 'pagecount': 1, 'limit': 16, 'total': 0}

    # ========== 播放 ==========

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        url = id if id.startswith('http') else self._url(id)

        if '.m3u8' in url:
            return {
                'parse': 0,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                }
            }

        if 'api.php' in url:
            return {
                'parse': 1,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                }
            }

        return {'parse': 1, 'playUrl': '', 'url': url}

    def localProxy(self, param):
        return [200, 'video/MP2T', b'', '']

    def destroy(self):
        pass

    def close(self):
        self.destroy()
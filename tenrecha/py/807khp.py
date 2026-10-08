# -*- coding: utf-8 -*-
# 适配站点: https://807.khp22.cc
# 分类：动态解析导航栏一级分类（无二级）
# 列表：标准卡片解析（<article class="excerpt excerpt-c5">），支持列表页加密解码
# 播放：直链 + iframe 二次解析 + m3u8 清洗（可选）

import sys
import re
import json
import base64
import requests
import urllib3
import time
import random
from urllib.parse import unquote, quote, urljoin, urlparse

urllib3.disable_warnings()

class Spider:
    session = requests.Session()
    host = 'https://807.khp22.cc'
    _debug = True
    _category_cache = None

    def _log(self, msg):
        if self._debug:
            print(f'[807khp] {msg}')

    def getName(self):
        return '807khp'

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- 本地代理：清洗 m3u8（可选） ----------
    def localProxy(self, param):
        try:
            if not isinstance(param, dict):
                param = {}
            ptype = param.get('type') or param.get('action') or param.get('do')
            url = param.get('url', '')
            if ptype != 'm3u8' or not url:
                return [404, "text/plain", "not found"]
            referer = param.get('referer', '') or self.host
            if isinstance(url, list):
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            url = unquote(url)
            referer = unquote(referer)
            raw_m3u8 = self._get_m3u8_content(url, referer)
            if not raw_m3u8:
                return [404, "text/plain", "m3u8 download failed"]
            cleaned = self._clean_m3u8(raw_m3u8, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            self._log(f'localProxy error: {e}')
            return [404, "text/plain", "proxy error"]

    # ---------- 初始化 ----------
    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        try:
            self.session.get(self.host, timeout=10)
        except:
            pass

    def _get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': referer or self.host + '/',
        }
        return headers

    def _fetch(self, url, referer=None, retries=3):
        for i in range(retries):
            try:
                if referer is None:
                    referer = self.host + '/'
                headers = self._get_headers(referer)
                if i > 0:
                    time.sleep(random.uniform(1.5, 3.0))
                else:
                    time.sleep(random.uniform(0.5, 1.5))
                self._log(f'请求: {url}')
                r = self.session.get(url, headers=headers, timeout=30, verify=False, allow_redirects=True)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    self._log(f'成功获取，内容长度: {len(r.text)}')
                    return r.text
                else:
                    self._log(f'状态码 {r.status_code}，重试 {i+1}/{retries}')
            except Exception as e:
                self._log(f'请求异常 [{e}]，重试 {i+1}/{retries}')
        self._log(f'所有重试失败: {url}')
        return ''

    @staticmethod
    def _try_decode_b64(text):
        """尝试 Base64 解码，失败则返回原字符串"""
        if not text:
            return ''
        try:
            missing_padding = 4 - len(text) % 4
            if missing_padding != 4:
                text += "=" * missing_padding
            decoded_bytes = base64.b64decode(text)
            return decoded_bytes.decode('utf-8')
        except Exception:
            return text

    # ==================== 分类相关（动态解析，无二级） ====================
    def _fetch_category_data(self):
        if self._category_cache is not None:
            return self._category_cache

        html = self._fetch(self.host)
        if not html:
            self._log('首页获取失败，使用硬编码备用')
            return self._get_fallback_categories()

        real_html = self._extract_real_html(html)
        if not real_html:
            self._log('解码首页失败，使用备用')
            return self._get_fallback_categories()

        categories = []
        pattern = r'<a\s+href="(/type/(\d+)/hot/1\.html)"[^>]*>([^<]+)</a>'
        for href, tid, name in re.findall(pattern, real_html):
            name = name.strip()
            if not name or name in ['首页', '我的收藏', '收藏', '']:
                continue
            if any(c['type_name'] == name for c in categories):
                continue
            categories.append({'type_id': tid, 'type_name': name})

        if not categories:
            self._log('解析分类为空，使用备用')
            return self._get_fallback_categories()

        self._category_cache = categories
        self._log(f'动态解析到 {len(categories)} 个分类: {[c["type_name"] for c in categories]}')
        return categories

    def _get_fallback_categories(self):
        return [
            {'type_id': '1', 'type_name': '热门'},
            {'type_id': '7', 'type_name': '日本'},
            {'type_id': '6', 'type_name': '偷拍'},
            {'type_id': '2', 'type_name': '国产精选'},
            {'type_id': '4', 'type_name': '家庭'},
            {'type_id': '3', 'type_name': '华语'},
            {'type_id': '5', 'type_name': '动漫'},
            {'type_id': '9', 'type_name': '欧美'},
            {'type_id': '8', 'type_name': '黄网'},
        ]

    def _extract_real_html(self, html):
        """解码首页/详情页的 html_b 加密"""
        match = re.search(r'html_b\s*=\s*"([^"]+)"', html)
        if match:
            b64 = match.group(1)
            try:
                decoded = base64.b64decode(b64).decode('utf-8')
                return decoded
            except Exception as e:
                self._log(f'解码 html_b 失败: {e}')
                return ''
        self._log('未找到 html_b，可能未加密')
        return html

    # ==================== 首页 ====================
    def homeContent(self, filter=False):
        try:
            categories = self._fetch_category_data()
            classes = []
            for cat in categories:
                classes.append({'type_id': cat['type_id'], 'type_name': cat['type_name']})

            home_list = []
            if categories:
                first_cat = categories[0]
                home_list = self._get_video_list(first_cat['type_id'], 1)

            return {
                'class': classes,
                'filters': {},
                'type': '影视',
                'list': home_list,
                'page': 1,
                'pagecount': 1,
                'limit': len(home_list),
                'total': len(home_list)
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'filters': {}, 'type': '影视', 'list': [], 'page': 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg) if pg else 1
            items = self._get_video_list(tid, page)

            total_page = page + 1
            url = f'{self.host}/type/{tid}/hot/1.html'
            html = self._fetch(url)
            if html:
                pages = re.findall(r'/type/\d+/hot/(\d+)\.html', html)
                if pages:
                    total_page = max(int(p) for p in pages)

            return {
                'list': items,
                'page': page,
                'pagecount': total_page,
                'limit': len(items),
                'total': total_page * len(items) if items else 0,
                'type_name': self._get_category_name(tid)
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _get_category_name(self, tid):
        for cat in self._fetch_category_data():
            if cat['type_id'] == tid:
                return cat['type_name']
        return tid

    # ==================== 列表解析（封面 bbb 解码） ====================
    def _parse_list(self, html):
        items = []
        articles = re.findall(r'<article[^>]*class="[^"]*excerpt[^"]*"[^>]*>(.*?)</article>', html, re.S)
        self._log(f'解析到 {len(articles)} 个卡片')
        if not articles:
            self._log(f'HTML预览: {html[:500]}')
            return items
        for art in articles:
            a_match = re.search(r'<a\s+href="([^"]+)"', art)
            if not a_match:
                continue
            href = a_match.group(1)
            m = re.search(r'/(\d+)\.html', href)
            if not m:
                continue
            vid = m.group(1)

            # 标题
            title = ''
            title_match = re.search(r'<h2[^>]*>(.*?)</h2>', art, re.S)
            if title_match:
                inner = title_match.group(1)
                a_title = re.search(r'<a[^>]*>(.*?)</a>', inner, re.S)
                if a_title:
                    title = re.sub(r'<[^>]+>', '', a_title.group(1)).strip()
                else:
                    title = re.sub(r'<[^>]+>', '', inner).strip()

            # 封面提取（优先 data-src / bbb，并对 bbb 解码）
            pic = ''
            img_tag = re.search(r'<img[^>]+>', art, re.S)
            if img_tag:
                tag_str = img_tag.group(0)
                for attr in ['data-src', 'data-original', 'bbb', 'src']:
                    attr_match = re.search(r'{}=["\']([^"\']+)["\']'.format(attr), tag_str)
                    if attr_match:
                        raw = attr_match.group(1)
                        if attr == 'bbb':
                            raw = self._try_decode_b64(raw)
                        if 'loading.gif' not in raw:
                            pic = raw
                            break
                        else:
                            pic = raw  # 占位图暂时保留
            if not pic or 'loading.gif' in pic:
                bbb_match = re.search(r'bbb="([^"]+)"', art)
                if bbb_match:
                    pic = self._try_decode_b64(bbb_match.group(1))

            if pic and not pic.startswith('http'):
                pic = urljoin(self.host, pic)

            items.append({
                'vod_id': vid,
                'vod_name': title or '未知标题',
                'vod_pic': pic,
                'vod_remarks': ''
            })
        self._log(f'解析到 {len(items)} 个视频项，首项封面: {items[0]["vod_pic"] if items else "无"}')
        return items

    def _get_video_list(self, tid, page):
        url = f'{self.host}/type/{tid}/hot/{page}.html'
        self._log(f'请求列表页: {url}')
        raw_html = self._fetch(url, referer=f'{self.host}/type/{tid}/hot/1.html')
        if not raw_html:
            return []
        real_html = self._extract_real_html(raw_html)
        if real_html and real_html != raw_html:
            html = real_html
        else:
            html = raw_html
        return self._parse_list(html)

    # ==================== 详情解析（解码HTML + 只保留媒体链接 + 外链解析） ====================
    def _fetch_detail(self, vid):
        url = f'{self.host}/{vid}.html'
        self._log(f'尝试详情页: {url}')
        raw_html = self._fetch(url, referer=self.host + '/')
        if not raw_html:
            alt_url = f'{self.host}/play/{vid}.html'
            self._log(f'尝试备用路径: {alt_url}')
            raw_html = self._fetch(alt_url, referer=self.host + '/')
            if not raw_html:
                return {'vod_id': vid, 'vod_name': vid, 'vod_pic': '', 'vod_play_from': '', 'vod_play_url': ''}

        # 解码 html_b
        html = self._extract_real_html(raw_html)
        if not html:
            html = raw_html
        self._log('详情页HTML解码完成' if html != raw_html else '详情页未加密或解码失败')

        detail = self._parse_detail(html, vid, url)
        if not detail.get('vod_play_url'):
            detail['vod_play_from'] = ''
            detail['vod_play_url'] = ''
        return detail

    def _parse_detail(self, html, vid, base_url):
        # 标题
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).strip()

        # 封面（bbb 解码）
        cover = ''
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m: cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]*class="[^"]*(?:thumb|poster)[^"]*"[^>]*src="([^"]+)"', html)
            if m: cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]*data-(?:src|original)=["\']([^"\']+)["\']', html)
            if m: cover = self._try_decode_b64(m.group(1))
        if not cover:
            m = re.search(r'<img[^>]+bbb=["\']([^"\']+)["\']', html)
            if m: cover = self._try_decode_b64(m.group(1))
        if not cover:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
            if m: cover = m.group(1)
        if cover and not cover.startswith('http'):
            cover = urljoin(base_url, cover)

        # 收集所有可能的播放地址：直链 + iframe 外链
        media_urls = []   # 直接播放的媒体链接
        iframe_urls = []  # 需要二次解析的网页链接

        seen_media = set()
        seen_iframe = set()

        def clean_url(u):
            """去除 URL 末尾等号和多余字符"""
            if u:
                u = u.strip().rstrip('=')
            return u

        # --- 策略1：页面内直接出现的媒体链接 ---
        all_links = set(re.findall(r'(https?://[^\s"\'<>]+)', html))
        for link in all_links:
            link = clean_url(link)
            if any(ext in link for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                if link not in seen_media:
                    seen_media.add(link)
                    media_urls.append(link)

        # --- 策略2：iframe 深度解析 ---
        iframe_srcs = set(re.findall(r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html))
        for src in iframe_srcs:
            full = src if src.startswith('http') else urljoin(base_url, src)
            self._log(f'发现 iframe: {full}')
            # 尝试加载 iframe 内容
            iframe_html = self._fetch(full, referer=base_url)
            if iframe_html:
                # 提取所有绝对链接并筛选媒体
                iframe_links = set(re.findall(r'(https?://[^\s"\'<>]+)', iframe_html))
                for link in iframe_links:
                    link = clean_url(link)
                    if any(ext in link for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                        if link not in seen_media:
                            seen_media.add(link)
                            media_urls.append(link)
                # 提取脚本中的媒体链接
                scripts = re.findall(r'<script[^>]*>(.*?)</script>', iframe_html, re.S)
                all_script = '\n'.join(scripts)
                script_links = set(re.findall(r'''['"](https?://[^'" ]+\.(?:m3u8|mp4)[^'" ]*)['"]''', all_script))
                for link in script_links:
                    link = clean_url(link)
                    if any(ext in link for ext in ['.m3u8', '.mp4']) and link not in seen_media:
                        seen_media.add(link)
                        media_urls.append(link)
                # 尝试 Base64 解码
                b64_links = re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', iframe_html)
                for b64_str in b64_links:
                    decoded = self._try_decode_b64(b64_str)
                    if decoded.startswith('http') and any(ext in decoded for ext in ['.m3u8', '.mp4']):
                        link = clean_url(decoded)
                        if link not in seen_media:
                            seen_media.add(link)
                            media_urls.append(link)
            else:
                # iframe 加载失败，保存外链用于二次解析
                if full not in seen_iframe:
                    seen_iframe.add(full)
                    iframe_urls.append(full)

        # --- 策略3：JS 变量/JSON 中的链接 ---
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
        all_js = '\n'.join(scripts)
        js_patterns = [
            r'''url\s*:\s*['"]([^'"]+)['"]''',
            r'''file\s*:\s*['"]([^'"]+)['"]''',
            r'''src\s*:\s*['"]([^'"]+)['"]''',
            r'''video\s*:\s*['"]([^'"]+)['"]''',
            r'''player_aaaa\s*=\s*['"]([^'"]+)['"]''',
            r'''playurl\s*=\s*['"]([^'"]+)['"]''',
            r'''["\'](https?://[^"\']+?\.(?:m3u8|mp4)[^"\']*?)["\']''',
        ]
        for pat in js_patterns:
            for match in re.finditer(pat, all_js, re.IGNORECASE):
                val = match.group(1)
                # 先尝试 Base64 解码
                decoded = self._try_decode_b64(val)
                if decoded.startswith('http') and any(ext in decoded for ext in ['.m3u8', '.mp4']):
                    link = clean_url(decoded)
                    if link not in seen_media:
                        seen_media.add(link)
                        media_urls.append(link)
                elif val.startswith('http') and any(ext in val for ext in ['.m3u8', '.mp4']):
                    link = clean_url(val)
                    if link not in seen_media:
                        seen_media.add(link)
                        media_urls.append(link)

        # --- 策略4：HTML5 标签 ---
        for media in set(re.findall(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', html)):
            link = clean_url(media)
            if any(ext in link for ext in ['.m3u8', '.mp4', '.flv', '.ts']) and link not in seen_media:
                seen_media.add(link)
                media_urls.append(link)

        # --- 策略5：自定义 data 属性解码 ---
        for attr_val in re.findall(r'data-(?:url|video|src)=["\']([^"\']+)["\']', html):
            decoded = self._try_decode_b64(attr_val)
            if decoded.startswith('http') and any(ext in decoded for ext in ['.m3u8', '.mp4']):
                link = clean_url(decoded)
                if link not in seen_media:
                    seen_media.add(link)
                    media_urls.append(link)

        # 构建最终播放列表
        play_list = []
        sources = []

        if media_urls:
            # 有直接媒体链接，全部标记为直链
            for u in media_urls:
                play_list.append(f'直链${u}')
            sources.append('直链')
        else:
            # 没有媒体链接，使用 iframe 外链作为解析源
            if iframe_urls:
                for u in iframe_urls:
                    play_list.append(f'网页解析${u}')
                sources.append('网页解析')
            else:
                # 完全没找到任何链接
                self._log('未提取到任何播放地址')
                return {
                    'vod_id': vid,
                    'vod_name': title or vid,
                    'vod_pic': cover or '',
                    'vod_play_from': '',
                    'vod_play_url': '',
                    'vod_content': title or '',
                }

        self._log(f'提取到 {len(play_list)} 个播放地址：')
        for idx, p in enumerate(play_list):
            self._log(f'  [{idx}] {p[:120]}')

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': cover or '',
            'vod_play_from': '$$$'.join(sources),
            'vod_play_url': '#'.join(play_list),
            'vod_content': title or '',
        }

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            detail = self._fetch_detail(vid)
            return {'list': [detail]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ==================== 播放器（区分直链和解析链接） ====================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            # 如果是网页解析链接（flag 包含“网页解析”），让 TVBox 用 WebView 解析
            if flag and '网页解析' in flag:
                full_url = id if id.startswith('http') else urljoin(self.host, id)
                return {'parse': 1, 'url': full_url, 'header': ''}

            # 处理直链媒体
            if id.startswith('http'):
                headers = {
                    'Referer': self.host + '/',
                    'Origin': self.host,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                if '.m3u8' in id:
                    # 可选：使用本地代理清洗广告
                    proxy_url = self._proxy_m3u8_url(id, self.host)
                    return {'parse': 0, 'url': proxy_url, 'header': json.dumps(headers)}
                else:
                    return {'parse': 0, 'url': id, 'header': json.dumps(headers)}
            elif id.startswith('/'):
                full = urljoin(self.host, id)
                return self.playerContent(flag, full, vipFlags)
            else:
                return {'parse': 0, 'url': '', 'header': {}}
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return {'parse': 0, 'url': '', 'header': {}}

    # ==================== m3u8 清洗（保持不变） ====================
    def _proxy_m3u8_url(self, url, referer=''):
        try:
            if hasattr(self, 'getProxyUrl'):
                base = self.getProxyUrl()
                if '?' not in base:
                    base += '?do=py'
                return base + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except:
            pass
        return url

    def _get_m3u8_content(self, url, referer):
        try:
            headers = self.session.headers.copy()
            headers['Referer'] = referer
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
        except Exception as e:
            self._log(f'下载 m3u8 失败: {e}')
        return None

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        """清洗 m3u8：去除广告分片"""
        text = (m3u8_text or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in text:
            out = []
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer))
                    else:
                        out.append(abs_url)
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return text

        marker = self._main_path_marker(m3u8_url)
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        cleaned = []
        removed = 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            if marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        if removed == 0 and len(segments) > 4:
            acc = 0.0
            cut = 0
            for idx, seg in enumerate(segments[:12]):
                key = self._segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self._segment_host_key(segments[0]['uri'], m3u8_url)
                if first_key != main_key:
                    cleaned = segments[cut:]
                    removed = cut

        if not cleaned:
            cleaned = segments
            removed = 0

        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'):
                has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append(f'#EXT-X-MEDIA-SEQUENCE:{media_sequence + first_idx}')
        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        self._log(f'm3u8清洗: 原{len(segments)}片 → 删除{removed}片广告，保留{len(cleaned)}片')
        return '\n'.join(new_lines) + '\n'

    def _parse_m3u8_segments(self, text):
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try: media_sequence = int(line.split(':', 1)[1])
                except: pass
                if not started: header.append(line)
                else: pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try: target_duration = float(line.split(':', 1)[1])
                except: pass
                if not started: header.append(line)
                else: pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try: dur = float(m.group(1))
                    except: pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j])
                        j += 1
                        continue
                    uri = lines[j]
                    break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur})
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started: pending_tags.append(line)
                else: header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        u = (uri or '').strip().lower()
        if not u: return False
        ad_words = ['ad', 'ads', 'advert', 'sponsor', 'pre', 'preroll', '片头', '广告', '/gg/', '_gg', 'gg_', '/adv/']
        if any(w in u for w in ad_words): return True
        try:
            if 0 < float(dur) <= 1.2: return True
        except: pass
        return False

    def _segment_host_key(self, uri, base_url):
        try:
            full = urljoin(base_url, uri)
            p = urlparse(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlparse(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m: return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m: return m.group(1).lower()
        except: pass
        return ''

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = int(pg) if pg else 1
            urls = [
                f'{self.host}/search?keyword={quote(key)}&page={page}',
                f'{self.host}/search.php?content={quote(key)}&page={page}',
            ]
            items = []
            for url in urls:
                html = self._fetch(url, referer=self.host)
                if html:
                    items = self._parse_list(html)
                    if items:
                        break
            return {
                'list': items,
                'page': page,
                'pagecount': page + 1,
                'limit': len(items),
                'total': page * len(items)
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}
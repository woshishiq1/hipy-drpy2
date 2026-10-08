# -*- coding: utf-8 -*-
"""
2048核基地 爬虫 - 修复版 + 去广告
修复：发布页Cookie验证、域名自动获取、多域名备用、art列表/详情、分隔符编码
新增：m3u8 广告清洗（无AES），屏蔽图片/小说分类
"""
import sys
import re
import json
import requests
import urllib3
import time
import random
from urllib.parse import quote, urljoin, unquote, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # ========== 多域名配置 ==========
    # hosts[0] 是主域名，失效时自动从发布页获取更新
    hosts = ['https://s7t8u9v0.luanlunba15.cc']
    host = hosts[0]
    
    # 发布页配置（用于自动获取最新域名）
    PUBLISH_PAGES = [
        'https://www.luanlunba.cc',
        'https://s7t8u9v0.luanlunba13.cc',
        'https://s7t8u9v0.luanlunba14.cc',
    ]
    
    session = requests.Session()
    _debug = True
    _categories = []

    def _log(self, msg):
        if self._debug:
            print(f'[luanlunba] {msg}')

    def getName(self):
        return '2048核基地'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
            self.session = None

    # ---------- 本地代理：支持图片代理和 m3u8 清洗 ----------
    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        # 如果请求包含 do=m3u8 则进行 m3u8 广告清洗
        if 'do=m3u8' in param:
            try:
                # 解析参数
                params = dict(p.split('=', 1) for p in param.split('&') if '=' in p)
                url = unquote(params.get('url', ''))
                referer = unquote(params.get('referer', self.host))
                if not url:
                    return [404, "text/plain", "missing url"]
                # 下载原始 m3u8
                raw = self._get_m3u8_content(url, referer)
                if not raw:
                    return [404, "text/plain", "m3u8 download failed"]
                # 清洗广告
                cleaned = self._clean_m3u8(raw, url, referer)
                return [200, "application/vnd.apple.mpegurl", cleaned]
            except Exception as e:
                self._log(f'm3u8 清洗异常: {e}')
                return [404, "text/plain", "proxy error"]
        # 否则走原有的图片代理逻辑
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF]
        try:
            r = self.session.get(param, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': self.host + '/'
            }, timeout=(10, 15))
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', 'application/octet-stream')
            return [200, content_type, r.content]
        except:
            return [200, 'image/gif', EMPTY_GIF]

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/'
        }

    def _fetch(self, url, referer=None, retries=3):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=self._get_headers(referer), timeout=(10, 20), verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                else:
                    self._log(f'请求失败 [{r.status_code}] {url}')
                    return ''
            except Exception as e:
                self._log(f'请求异常 {e}，重试 {attempt+1}')
                continue
        return ''

    # ========== 【核心】域名自动更新（支持Cookie验证+AJAX接口） ==========
    def _update_host(self):
        """从发布页获取最新可用域名，支持多发布页、Cookie验证、AJAX接口"""
        for pub in self.PUBLISH_PAGES:
            try:
                # Step 1: 获取Cookie验证页
                r1 = self.session.get(pub + '/', headers=self._get_headers(), timeout=10, verify=False)
                cookie_match = re.search(r'document\.cookie\s*=\s*"([^"]+)"', r1.text)
                
                if cookie_match:
                    # 解析并设置Cookie
                    cookie_str = cookie_match.group(1)
                    parts = cookie_str.split(';')
                    for part in parts:
                        part = part.strip()
                        if '=' in part and 'path' not in part and 'max-age' not in part:
                            key, val = part.split('=', 1)
                            self.session.cookies.set(key.strip(), val.strip())
                    self._log(f'发布页 {pub} Cookie已设置')
                
                # Step 2: 请求AJAX接口获取域名列表
                ajax_url = pub + '/xuexi/data.php'
                ajax_headers = self._get_headers(pub + '/')
                ajax_headers['X-Requested-With'] = 'XMLHttpRequest'
                
                r2 = self.session.get(ajax_url, headers=ajax_headers, timeout=10, verify=False)
                r2.encoding = 'utf-8'
                
                try:
                    data = r2.json()
                    urls = data.get('urls', [])
                    self._log(f'发布页 {pub} 返回 {len(urls)} 个域名')
                except:
                    # 如果JSON解析失败，尝试从HTML提取
                    urls = re.findall(r'(https?://[a-z0-9]+\.luanlunba\d*\.\w+)', r2.text)
                    self._log(f'发布页 {pub} JSON失败，从HTML提取到 {len(urls)} 个域名')
                
                # Step 3: 验证每个域名可用性
                for url in urls:
                    url = url.strip('/')
                    if not url.startswith('http'):
                        continue
                    try:
                        test = self.session.get(url + '/', headers=self._get_headers(), timeout=8, verify=False)
                        if test.status_code == 200 and len(test.text) > 1000:
                            # 进一步验证：检查是否有分类结构
                            if 'vodtype' in test.text or 'arttype' in test.text or 'voddetail' in test.text:
                                self._log(f'验证可用域名: {url}')
                                self.host = url
                                self.hosts = [url] + [h for h in self.hosts if h != url]
                                return True
                    except:
                        continue
                        
            except Exception as e:
                self._log(f'发布页 {pub} 获取失败: {e}')
                continue
        
        # 所有发布页失败，尝试备用hosts列表
        for h in self.hosts:
            try:
                test = self.session.get(h + '/', headers=self._get_headers(), timeout=8, verify=False)
                if test.status_code == 200 and len(test.text) > 1000:
                    self.host = h
                    self._log(f'使用备用域名: {h}')
                    return True
            except:
                continue
        
        self._log('所有域名获取方式均失败')
        return False

    def _parse_categories(self, html):
        cats = []
        menu_match = re.search(r'<div[^>]+class="menu\s+clearfix"[^>]*>(.*?)</div>\s*</div>', html, re.S)
        menu_text = menu_match.group(1) if menu_match else html
        links = re.findall(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', menu_text, re.S)
        for href, text in links:
            m = re.search(r'/(vodtype|arttype)/(\d+)\.html', href)
            if not m:
                continue
            type_prefix, tid = m.groups()
            name = re.sub(r'<[^>]+>', '', text).strip()
            if not name or len(name) > 15:
                continue
            if name in ('首页', '搜索', '全部', '更多', '排行', '留言', '帮助', '返回首页', '发布页', '传送门'):
                continue
            # 【新增】屏蔽图片/小说分类（arttype）
            if type_prefix == 'arttype':
                continue
            cats.append({
                'type_id': tid,
                'type_name': name,
                'type': 'vod' if type_prefix == 'vodtype' else 'art'
            })
        return self._dedup(cats)

    def _dedup(self, cats):
        seen = set()
        unique = []
        for c in cats:
            tid = c['type_id']
            if tid not in seen:
                seen.add(tid)
                unique.append(c)
        return unique

    def init(self, extend=''):
        self._log('正在初始化...')
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
        self.session = requests.Session()
        
        # 尝试更新域名
        if not self._update_host():
            self._log('域名更新失败，使用默认域名')
        
        # 获取分类
        html = self._fetch(self.host + '/')
        if html:
            cats = self._parse_categories(html)
            if cats:
                self._categories = cats
                self._log(f'分类获取成功: {len(cats)} 个')
                return
        
        # 备用
        html = self._fetch(self.host + '/vodtype/1.html')
        if html:
            cats = self._parse_categories(html)
            if cats:
                self._categories = cats
                self._log(f'备用页分类获取成功: {len(cats)} 个')
                return
        
        # 硬编码兜底（仅保留视频分类）
        self._categories = [
            {'type_id': '1', 'type_name': '国产传媒', 'type': 'vod'},
            {'type_id': '2', 'type_name': '国产剧情', 'type': 'vod'},
            {'type_id': '58', 'type_name': '网曝黑料', 'type': 'vod'},
            {'type_id': '3', 'type_name': '特色仓库', 'type': 'vod'},
            {'type_id': '69', 'type_name': '精品资源', 'type': 'vod'},
            {'type_id': '78', 'type_name': '热播片库', 'type': 'vod'},
            # 已删除 '5': '激情图区' 和 '38': '情色小说'
        ]
        self._log('使用硬编码分类（仅视频）')

    # ========== 视频列表解析 ==========
    def _parse_video_list(self, html):
        items = []
        dl_pattern = r'<dl>\s*<dt[^>]*>.*?<a[^>]*href="/voddetail/(\d+)\.html"[^>]*>.*?<img[^>]*data-original="([^"]*)"[^>]*>.*?</a>.*?</dt>\s*<dd>\s*<a[^>]*href="/voddetail/\d+\.html"[^>]*>(.*?)</a>\s*</dd>\s*</dl>'
        for m in re.finditer(dl_pattern, html, re.S):
            vid, img, title_block = m.groups()
            if not img.startswith('http'):
                img = urljoin(self.host, img)
            title = re.sub(r'<[^>]+>', '', title_block).strip()
            items.append({
                'vod_id': vid,
                'vod_name': title if title else '未知标题',
                'vod_pic': img,
                'vod_remarks': '',
            })
        return items

    # ========== 【修复】图片/小说列表解析（保留方法，不会被调用） ==========
    def _parse_art_list(self, html):
        """解析图片/小说(arttype)列表页，兼容多种 HTML 结构"""
        items = []
        if not html:
            return items

        # 模式1: <dl> 传统结构
        pattern1 = r'<dl>\s*<dt[^>]*>.*?<a[^>]*href="/artdetail/(\d+)\.html"[^>]*>.*?<img[^>]*(?:data-original|src|data-src)="([^"]*)"[^>]*>.*?</a>.*?</dt>\s*<dd>\s*<a[^>]*href="/artdetail/\d+\.html"[^>]*>(.*?)</a>\s*</dd>\s*</dl>'
        for m in re.finditer(pattern1, html, re.S):
            vid, img, title_block = m.groups()
            if not img.startswith('http'):
                img = urljoin(self.host, img)
            title = re.sub(r'<[^>]+>', '', title_block).strip()
            items.append({
                'vod_id': vid,
                'vod_name': title if title else '未知标题',
                'vod_pic': img,
                'vod_remarks': '',
            })

        # 模式2: <a href="/artdetail/123.html"> 内部有 <img> 和文字标题
        if not items:
            pattern2 = r'<a[^>]*href="/artdetail/(\d+)\.html"[^>]*>(.*?)</a>'
            for m in re.finditer(pattern2, html, re.S):
                vid, block = m.groups()
                img_match = re.search(r'<img[^>]*(?:data-original|src|data-src|original)="([^"]+)"', block)
                img = img_match.group(1) if img_match else ''
                if img and not img.startswith('http'):
                    img = urljoin(self.host, img)
                title = ''
                alt_match = re.search(r'<img[^>]*alt="([^"]*)"', block)
                if alt_match:
                    title = alt_match.group(1).strip()
                if not title:
                    title = re.sub(r'<[^>]+>', '', block).strip()
                items.append({
                    'vod_id': vid,
                    'vod_name': title if title else '未知标题',
                    'vod_pic': img,
                    'vod_remarks': '',
                })

        # 模式3: 更宽松的 div/li 结构
        if not items:
            pattern3 = r'<(?:div|li)[^>]*>\s*<a[^>]*href="/artdetail/(\d+)\.html"[^>]*>.*?<img[^>]*(?:data-original|src|data-src|original)="([^"]*)"[^>]*>.*?</a>\s*<(?:h3|h4|p|div|span)[^>]*>(.*?)</(?:h3|h4|p|div|span)>\s*</(?:div|li)>'
            for m in re.finditer(pattern3, html, re.S):
                vid, img, title_block = m.groups()
                if not img.startswith('http'):
                    img = urljoin(self.host, img)
                title = re.sub(r'<[^>]+>', '', title_block).strip()
                items.append({
                    'vod_id': vid,
                    'vod_name': title if title else '未知标题',
                    'vod_pic': img,
                    'vod_remarks': '',
                })

        self._log(f'art列表解析到 {len(items)} 条')
        return items

    def homeContent(self, filter=False):
        try:
            if not self._categories:
                self.init()
            # 仅保留视频分类（type == 'vod'）
            video_cats = [c for c in self._categories if c.get('type') == 'vod']
            html = self._fetch(self.host + '/')
            items = self._parse_video_list(html) if html else []
            return {'class': video_cats, 'list': items[:20]}
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        html = self._fetch(self.host + '/')
        items = self._parse_video_list(html) if html else []
        return {'list': items[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=''):
        try:
            page = int(pg) if pg else 1
            # 检查是否为图片/小说分类（通过 _categories 判断）
            for c in self._categories:
                if str(c['type_id']) == str(tid):
                    if c.get('type') != 'vod':
                        # 图片/小说分类不再提供内容，返回空
                        return {'list': [], 'page': page, 'pagecount': 1}
                    break
            # 视频分类正常加载
            url = f'{self.host}/vodtype/{tid}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid}.html'
            html = self._fetch(url)
            items = self._parse_video_list(html) if html else []
            total_pages = page
            if html:
                page_links = re.findall(r'/vodtype/{}[-_](\d+)\.html'.format(tid), html)
                if page_links:
                    total_pages = max(int(p) for p in page_links)
                else:
                    total_pages = page + 1
            return {'list': items, 'page': page, 'pagecount': max(total_pages, page)}
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    # ========== 播放地址提取 ==========
    def _extract_m3u8(self, html):
        urls = []
        if not html:
            return urls
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.S)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                raw = data.get('url', '')
                if raw:
                    decoded = unquote(raw)
                    if decoded.startswith('http'):
                        urls.append(decoded)
            except:
                pass
        direct = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        urls.extend(direct)
        if not urls:
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
            for scr in scripts:
                json_urls = re.findall(r'''["\']url["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']''', scr)
                urls.extend(json_urls)
        seen = set()
        clean = []
        for u in urls:
            if u.startswith('http') and u not in seen:
                seen.add(u)
                clean.append(u)
        return clean

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            html = self._fetch(f'{self.host}/voddetail/{vid}.html')
            if html:
                return self._video_detail(vid, html)
            # 如果视频详情页无内容，不再尝试图片/小说详情（因分类已屏蔽）
            return {'list': [{'vod_id': vid, 'vod_name': '未知影片', 'vod_play_from': '错误', 'vod_play_url': ''}]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': [{'vod_id': vid, 'vod_name': '错误', 'vod_play_from': '错误', 'vod_play_url': ''}]}

    # ========== 【修复】视频详情 - 分隔符不编码 ==========
    def _video_detail(self, vid, html):
        title = ''
        cover = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>(.*?)</title>', html)
            if m:
                title = m.group(1).strip()
        m = re.search(r'<img[^>]*data-original="([^"]*)"[^>]*>', html)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if m:
                cover = m.group(1)
        if cover and not cover.startswith('http'):
            cover = urljoin(self.host, cover)

        # 更灵活的播放按钮匹配
        buttons = re.findall(
            r'<div[^>]+class="item"[^>]*>\s*<a[^>]+href="(/vodplay/' + vid + r'[-_]\d+[-_]\d+\.html)"[^>]*>(.*?)</a>',
            html, re.S
        )
        if not buttons:
            buttons = re.findall(
                r'href="(/vodplay/' + vid + r'[^"]*)"[^>]*>(.*?)</a>',
                html, re.S
            )
        if not buttons:
            buttons = [(f'/vodplay/{vid}-1-1.html', '立即播放')]
            self._log(f'未匹配到播放按钮，使用默认: {buttons[0][0]}')

        line_map = {}
        cache = {}

        for href, btn_name in buttons:
            btn_name = re.sub(r'<[^>]+>', '', btn_name).strip() or '播放'
            play_url = urljoin(self.host, href)

            if href not in cache:
                play_html = self._fetch(play_url)
                m3u8_list = self._extract_m3u8(play_html) if play_html else []
                cache[href] = m3u8_list
                self._log(f'播放页 {href} 提取到 {len(m3u8_list)} 个地址')
            else:
                m3u8_list = cache[href]

            if m3u8_list:
                for i, m3u8 in enumerate(m3u8_list):
                    name = btn_name if i == 0 else f'{btn_name}_{i+1}'
                    if btn_name not in line_map:
                        line_map[btn_name] = []
                    # 使用代理清洗链接（后续 playerContent 会处理）
                    line_map[btn_name].append((name, m3u8))
            else:
                if btn_name not in line_map:
                    line_map[btn_name] = []
                line_map[btn_name].append((btn_name, play_url))
                self._log(f'播放页 {href} 未提取到 m3u8，回退到播放页 URL')

        if not line_map:
            return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': cover,
                              'vod_play_from': '错误', 'vod_play_url': '未找到播放地址'}]}

        # TVBox 格式：$ # $$$ 绝对不能编码
        from_lines = []
        url_lines = []
        for line_name, episodes in line_map.items():
            from_lines.append(line_name)
            ep_str = '#'.join([f'{ep_name}${ep_url}' for ep_name, ep_url in episodes])
            url_lines.append(ep_str)

        vod_play_from = '#'.join(from_lines)
        vod_play_url = '$$$'.join(url_lines)

        self._log(f'vod_play_from: {vod_play_from}')
        self._log(f'vod_play_url: {vod_play_url[:200]}...')

        return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': cover,
                          'vod_play_from': vod_play_from, 'vod_play_url': vod_play_url}]}

    # ========== 播放器：集成 m3u8 广告清洗代理 ==========
    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id or '.ts' in id):
            # 如果是 m3u8，替换为本地代理清洗链接
            if '.m3u8' in id:
                proxy_url = self._proxy_m3u8_url(id, self.host)
                return {'parse': 0, 'url': proxy_url, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
            else:
                return {'parse': 0, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
        # 非直链，交由解析接口处理
        return {'parse': 1, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}

    # ===================== m3u8 广告清洗相关方法（移植自 qinav） =====================
    def _proxy_m3u8_url(self, url, referer=''):
        """生成走本地代理的清洗链接"""
        try:
            # 尝试使用基类提供的代理基础路径
            base = self.getProxyUrl()
            if '?' not in base:
                base += '?do=py'
            return base + '&do=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except:
            pass
        # 降级：直接返回原始 URL（不做清洗）
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
        """清洗 m3u8：去除广告分片，保留 KEY/MAP/DISCONTINUITY，URI 绝对化"""
        text = (m3u8_text or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in text:
            # master m3u8，将子 m3u8 的 URL 也替换为代理链接
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

        # 若未检测到广告，尝试按累积秒数跳过前置广告段
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
            if line.startswith('#EXTM3U'): has_m3u = True
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
                try:
                    media_sequence = int(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try:
                    target_duration = float(line.split(':', 1)[1])
                except:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try:
                        dur = float(m.group(1))
                    except:
                        pass
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
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        u = (uri or '').strip().lower()
        if not u:
            return False
        ad_words = [
            'ad', 'ads', 'advert', 'advertise', 'advertisement', 'sponsor',
            'pre', 'preroll', '片头', '广告', '/gg/', '_gg', 'gg_', '/adv/',
            '/ad/', '/ads/', 'banner', 'promo', 'commercial'
        ]
        if any(w in u for w in ad_words):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except:
            pass
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
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except:
            pass
        return ''

    # ========== 图片/小说详情（保留，但不再主动调用） ==========
    def _art_detail(self, vid, html):
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>(.*?)</title>', html)
            if m:
                title = m.group(1).strip()

        # 图片提取（增强）
        imgs = []
        for attr in ['data-original', 'src', 'data-src', 'original', 'data-url']:
            found = re.findall(rf'<img[^>]*{attr}="([^"]+)"', html)
            imgs.extend(found)

        real_imgs = []
        for img in imgs:
            lower = img.lower()
            if any(k in lower for k in ['logo', 'loading', 'ad.', 'icon', 'avatar', 'thumb', 'blank', 'default']):
                continue
            if img.startswith('//'):
                img = 'https:' + img
            if not img.startswith('http'):
                img = urljoin(self.host, img)
            if img not in real_imgs:
                real_imgs.append(img)

        if real_imgs:
            pics = '&&'.join(real_imgs)
            play_url = f'查看$pics://{pics}'
            vod_play_from = '图片'
            self._log(f'图片详情提取到 {len(real_imgs)} 张图片')
            return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': real_imgs[0] if real_imgs else '',
                              'vod_play_from': vod_play_from, 'vod_play_url': play_url}]}

        # 小说提取（增强）
        content = ''
        content_patterns = [
            r'<div[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+class="[^"]*text[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+class="[^"]*novel[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+id="content"[^>]*>(.*?)</div>',
            r'<div[^>]+id="article"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]+class="[^"]*main[^"]*"[^>]*>(.*?)</div>',
        ]

        for pattern in content_patterns:
            m = re.search(pattern, html, re.S)
            if m:
                raw = m.group(1)
                raw = re.sub(r'<br\s*/?>', '\n', raw)
                raw = re.sub(r'</p>', '\n', raw)
                raw = re.sub(r'<p>', '', raw)
                content = re.sub(r'<[^>]+>', '', raw)
                content = re.sub(r'&nbsp;', ' ', content)
                content = re.sub(r'&amp;', '&', content)
                content = re.sub(r'&lt;', '<', content)
                content = re.sub(r'&gt;', '>', content)
                content = re.sub(r'&quot;', '"', content)
                content = re.sub(r'&#\d+;', '', content)
                content = re.sub(r'[ \t]*\n[ \t]*', '\n', content)
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = content.strip()
                if len(content) > 50:
                    break

        if len(content) < 50:
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)
            texts = []
            for p in paragraphs:
                txt = re.sub(r'<[^>]+>', '', p).strip()
                if len(txt) > 10:
                    texts.append(txt)
            if texts:
                content = '\n\n'.join(texts)

        if content and len(content) > 20:
            novel_json = json.dumps({'title': title, 'content': content[:8000]}, ensure_ascii=False)
            play_url = f'阅读$novel://{novel_json}'
            vod_play_from = '小说'
            self._log(f'小说详情提取到 {len(content)} 字内容')
            return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': '',
                              'vod_play_from': vod_play_from, 'vod_play_url': play_url}]}

        return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_play_from': '错误', 'vod_play_url': '内容无法解析'}]}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}'
            html = self._fetch(url)
            items = self._parse_video_list(html) if html else []
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}
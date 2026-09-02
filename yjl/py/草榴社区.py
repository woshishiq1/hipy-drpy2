# -*- coding: utf-8 -*-

import sys
import re
import json
import requests
import urllib3
import base64
import html
from urllib.parse import quote, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://g3h4i5j6.caoliu28.cc'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://g3h4i5j6.caoliu28.cc/',
    }

    def getName(self): return "caoliu28"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False
        self._pass_ge_validator()

    def _pass_ge_validator(self):
        """处理 ge_js_validator Cookie 验证"""
        try:
            r = self.session.get(self.host + '/', headers=self.headers, timeout=20, verify=False, allow_redirects=True)
            text = r.text
            if 'ge_js_validator' in text and 'window.location.reload' in text:
                m = re.search(r'ge_js_validator_(\d+)=([^;]+)', text)
                if m:
                    key, val = m.group(1), m.group(2).strip().strip('"')
                    self.session.cookies.set(f'ge_js_validator_{key}', val, domain='.caoliu28.cc', path='/')
                    self.session.get(self.host + '/', headers=self.headers, timeout=20, verify=False, allow_redirects=True)
        except Exception:
            pass

    def _fetch(self, url, retries=2):
        """带验证自动重试的请求"""
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False, allow_redirects=True)
            r.encoding = 'utf-8'
            text = r.text if r.status_code == 200 else ''

            while 'ge_js_validator' in text and 'window.location.reload' in text and retries > 0:
                m = re.search(r'ge_js_validator_(\d+)=([^;]+)', text)
                if m:
                    key, val = m.group(1), m.group(2).strip().strip('"')
                    self.session.cookies.set(f'ge_js_validator_{key}', val, domain='.caoliu28.cc', path='/')
                r = self.session.get(url, headers=self.headers, timeout=20, verify=False, allow_redirects=True)
                r.encoding = 'utf-8'
                text = r.text if r.status_code == 200 else ''
                retries -= 1
            return text
        except Exception:
            return ''

    def homeContent(self, filter):
        classes = [
            {'type_id': '1',   'type_name': '国产传媒'},
            {'type_id': '2',   'type_name': '国产剧情'},
            {'type_id': '58',  'type_name': '网曝黑料'},
            {'type_id': '3',   'type_name': '特色仓库'},
            {'type_id': '69',  'type_name': '精品资源'},
            {'type_id': '78',  'type_name': '热播片库'},
            {'type_id': '92',  'type_name': '原创资源'},
            {'type_id': '6',   'type_name': '偷拍自拍'},
            {'type_id': '7',   'type_name': '国产大制作'},
            {'type_id': '8',   'type_name': '乱伦毁三观'},
            {'type_id': '9',   'type_name': '主播女网红'},
            {'type_id': '10',  'type_name': '黑料网曝'},
            {'type_id': '11',  'type_name': '会所技师'},
            {'type_id': '12',  'type_name': '制服诱惑'},
            {'type_id': '20',  'type_name': '淫乱学生妹'},
            {'type_id': '5',   'type_name': '激情图区'},
            {'type_id': '38',  'type_name': '情色小说'},
        ]
        return {'class': classes, 'filters': self._build_filters(), 'type': '影视'}

    def _build_filters(self):
        filters = {}
        filters['1'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '探花约炮', 'v': '13'}, {'n': '传媒视频', 'v': '14'},
            {'n': '主播福利', 'v': '15'}, {'n': 'SWAG', 'v': '16'}, {'n': '91系列', 'v': '17'},
        ]}]
        filters['2'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '玩偶姐姐', 'v': '18'}, {'n': 'mini传媒', 'v': '19'},
        ]}]
        filters['58'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '网曝门事件', 'v': '59'}, {'n': '黑料吃瓜', 'v': '60'},
        ]}]
        filters['8'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '母子乱伦', 'v': '21'}, {'n': '父女乱伦', 'v': '22'},
            {'n': '姐弟乱伦', 'v': '23'}, {'n': '家庭群交', 'v': '24'},
        ]}]
        filters['5'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '露出偷窥', 'v': '25'}, {'n': '网友自拍', 'v': '26'},
            {'n': '唯美清纯', 'v': '27'}, {'n': '欧美激情', 'v': '28'}, {'n': 'Gif动图', 'v': '29'},
            {'n': '亚洲性爱', 'v': '30'}, {'n': '卡通漫画', 'v': '31'}, {'n': '高跟丝袜', 'v': '32'},
        ]}]
        filters['38'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '暴力虐待', 'v': '33'}, {'n': '学生校园', 'v': '34'},
            {'n': '玄幻仙侠', 'v': '35'}, {'n': '明星偶像', 'v': '36'}, {'n': '生活都市', 'v': '37'},
            {'n': '不伦恋情', 'v': '39'}, {'n': '经验故事', 'v': '40'}, {'n': '科学幻想', 'v': '41'},
        ]}]
        return filters

    def homeVideoContent(self):
        text = self._fetch(self.host + '/')
        items = self._parse_list(text, page=1, is_article=False).get('list', [])
        return {
            'list': items[:30],
            'page': 1,
            'pagecount': 2 if items else 1,
            'limit': len(items),
            'total': len(items)
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        sub = extend.get('sub', '')
        if sub:
            tid = sub
        tid_str = str(tid)

        # 文章类ID：图区(5及子类25-32) / 小说(38及子类33-41)
        article_ids = {
            '5', '38', '25', '26', '27', '28', '29', '30', '31', '32',
            '33', '34', '35', '36', '37', '39', '40', '41'
        }
        is_article = tid_str in article_ids

        if is_article:
            url = f'{self.host}/arttype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/arttype/{tid_str}.html'
        else:
            url = f'{self.host}/vodtype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid_str}.html'
        text = self._fetch(url)
        return self._parse_list(text, page, is_article)

    def _parse_list(self, text, page=1, is_article=False):
        items = []
        if not text:
            return self._empty_list(page)

        detail_prefix = 'artdetail' if is_article else 'voddetail'

        # ========== 模式0：caoliu28 视频列表 <dl><dt class="preview-item"> 结构 ==========
        if not is_article:
            pattern_caoliu = re.compile(
                r'<dt class="preview-item">\s*'
                r'<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>.*?'
                r'data-original="([^"]*)"[^>]*>.*?'
                r'</dt>\s*<dd>.*?<h3>(.*?)</h3>',
                re.S
            )
            seen = set()
            for m in pattern_caoliu.finditer(text):
                vid, pic, title = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                title = html.unescape(title).strip()
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式1：caoliu28 文章列表 <li><a href="/artdetail-{vid}.html"><h3>标题</h3></a></li> ==========
        if is_article and not items:
            pattern_art = re.compile(
                r'<li><a[^>]+href="/artdetail-(\d+)\.html"[^>]*>.*?<h3>(.*?)</h3>.*?</a></li>',
                re.S
            )
            seen = set()
            for m in pattern_art.finditer(text):
                vid, title = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                title = html.unescape(title).strip()
                items.append({
                    'vod_id': f'art_{vid}',
                    'vod_name': title,
                    'vod_pic': '',
                    'vod_remarks': '',
                })

        # ========== 模式2：文章列表备用（含 title 属性） ==========
        if is_article and not items:
            pattern_art2 = re.compile(
                r'<li[^>]*>\s*<a[^>]+href="/artdetail-(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*</li>',
                re.S
            )
            for m in pattern_art2.finditer(text):
                vid, title = m.groups()
                items.append({
                    'vod_id': f'art_{vid}',
                    'vod_name': html.unescape(title).strip(),
                    'vod_pic': '',
                    'vod_remarks': '',
                })

        # ========== 模式3：content-item 结构（苹果CMS常见） ==========
        if not items:
            pattern = re.compile(
                r'<li[^>]*class="content-item[^"]*"[^>]*>'
                r'.*?<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>'
                r'.*?<img[^>]*?(?:data-original|src)="([^"]*)"[^>]*>'
                r'.*?</li>',
                re.S
            )
            for m in pattern.finditer(text):
                vid, title, pic = m.groups()
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': html.unescape(title).strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式4：苹果CMS标准 vod 结构 ==========
        if not items:
            pattern2 = re.compile(
                r'<div class="vod">\s*<div class="vod-img">\s*'
                r'<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*>.*?'
                r'<img[^>]*?(?:data-original|src)="([^"]*)"[^>]*>.*?</a>\s*</div>\s*'
                r'<div class="vod-txt">\s*<a[^>]*>([^<]+)</a>',
                re.S
            )
            for m in pattern2.finditer(text):
                vid, pic, title = m.groups()
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': html.unescape(title).strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式5：通用宽松匹配（兜底） ==========
        if not items:
            pattern3 = re.compile(
                r'<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*(?:title="([^"]*)")?[^>]*>'
                r'.*?<img[^>]*?(?:data-original|src|data-src)="([^"]*)"[^>]*>.*?</a>',
                re.S
            )
            seen = set()
            for m in pattern3.finditer(text):
                vid, title, pic = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                if not title:
                    t = re.search(r'<h[1-6][^>]*>\s*<a[^>]+href="/' + detail_prefix + r'/' + vid + r'\.html"[^>]*>([^<]+)</a>', text, re.S)
                    title = t.group(1).strip() if t else f'未知标题{vid}'
                title = html.unescape(title).strip()
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式6：纯文字链接（小说列表无图时） ==========
        if not items and is_article:
            pattern4 = re.compile(
                r'<a[^>]+href="/artdetail-(\d+)\.html"[^>]*>([^<]+)</a>',
                re.S
            )
            seen = set()
            for m in pattern4.finditer(text):
                vid, title = m.groups()
                if vid not in seen and len(title.strip()) > 1:
                    seen.add(vid)
                    items.append({
                        'vod_id': f'art_{vid}',
                        'vod_name': html.unescape(title).strip(),
                        'vod_pic': '',
                        'vod_remarks': '',
                    })

        # ========== 文章类列表补充封面图 ==========
        if is_article and items:
            for item in items:
                if not item.get('vod_pic'):
                    vid = item['vod_id'].replace('art_', '')
                    detail_text = self._fetch(f'{self.host}/artdetail-{vid}.html')
                    if detail_text:
                        imgs = re.findall(r'<img[^>]+src="(https?://[^"]+)"', detail_text)
                        for img in imgs:
                            low = img.lower()
                            if any(x in low for x in ['loading', 'blank', 'logo', 'icon', 'avatar', 'smiley', 'ad.', 'gif', 'banner', 'play.png']):
                                continue
                            item['vod_pic'] = img
                            break

        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def _empty_list(self, page):
        return {'list': [], 'page': page, 'pagecount': page, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        if vid.startswith('art_'):
            return self._art_detail(vid.replace('art_', ''))
        return self._vod_detail(vid)

    def _vod_detail(self, vid):
        url = f'{self.host}/voddetail/{vid}.html'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m:
            title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = html.unescape(m.group(1).replace('- 草榴社区', '').replace('- caoliu28', '')).strip()

        cover = ''
        for pat in [
            r'<div class="vod-img">.*?data-original="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*content-img',
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*content-img',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*nature',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and 'loading' not in cover and 'load.png' not in cover:
                    break

        play_from_list = []
        play_url_list = []
        source_blocks = re.findall(
            r'<div[^>]*class="[^"]*(?:play-list|playlist|stui-play__list)[^"]*"[^>]*>(.*?)</div>',
            text, re.S
        )
        if not source_blocks:
            source_blocks = re.findall(
                r'<ul[^>]*class="[^"]*(?:play-list|playlist)[^"]*"[^>]*>(.*?)</ul>',
                text, re.S
            )
        if source_blocks:
            for block in source_blocks:
                eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', block)
                if eps:
                    urls = '#'.join([f'{name.strip()}${href}' for href, name in eps])
                    play_url_list.append(urls)
                    play_from_list.append('线路' + str(len(play_from_list) + 1))

        if not play_url_list:
            play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')
            play_from_list.append('caoliu28')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def _art_detail(self, vid):
        urls_to_try = [
            f'{self.host}/artdetail/{vid}.html',
            f'{self.host}/artdetail-{vid}.html',
            f'{self.host}/art/{vid}.html',
            f'{self.host}/article/{vid}.html',
        ]
        text = ''
        for url in urls_to_try:
            text = self._fetch(url)
            if text:
                break

        if not text:
            return {'list': []}

        title = ''
        for pat in [r'<h1[^>]*>(.*?)</h1>', r'<h2[^>]*>(.*?)</h2>', r'<title>([^<]+)</title>']:
            m = re.search(pat, text, re.S)
            if m:
                title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                if title:
                    break
        if not title:
            title = f'文章{vid}'

        # ========== 提取内容区（caoliu28 用 class="m1938ing"） ==========
        content_html = ''
        selectors = [
            r'<div[^>]*class="m1938ing"[^>]*>(.*?)</div>',
            r'<div[^>]*class="content"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*text-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*main-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*show-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*art-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="(?:content|post_content|article_content|txt|text)"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<section[^>]*class="[^"]*(?:content|detail)[^"]*"[^>]*>(.*?)</section>',
            r'<div[^>]*class="[^"]*maomi-content[^"]*"[^>]*>.*?<div[^>]*>(.*?)</div>\s*</div>',
        ]
        for selector in selectors:
            m = re.search(selector, text, re.S)
            if m:
                content_html = m.group(1)
                if len(content_html) > 50:
                    break

        if not content_html or len(content_html) < 50:
            body = re.search(r'<body[^>]*>(.*?)</body>', text, re.S)
            if body:
                content_html = body.group(1)
                content_html = re.sub(r'<(header|nav|footer|aside)[^>]*>.*?</\1>', '', content_html, flags=re.S)
                content_html = re.sub(r'<div[^>]*class="[^"]*(?:header|nav|footer|sidebar|ad|ads|links|tags|menu)[^"]*"[^>]*>.*?</div>', '', content_html, flags=re.S)

        # ========== 提取图片（caoliu28 用 <img src="...">） ==========
        imgs = re.findall(r'<img[^>]+(?:src|data-original|data-src|original)="([^"]+)"', content_html)
        big_imgs = []
        for img in imgs:
            low = img.lower()
            if any(x in low for x in ['loading', 'blank', 'logo', 'icon', 'avatar', 'smiley', 'ad.', 'gif', 'banner']):
                continue
            if img.startswith('//'):
                img = 'https:' + img
            elif img.startswith('/'):
                img = self.host + img
            if img.startswith('http') and img not in big_imgs:
                big_imgs.append(img)

        if big_imgs:
            pics = '&&'.join(big_imgs)
            play_url = f'查看$pics://{pics}'
            vod = {
                'vod_id': f'art_{vid}',
                'vod_name': title,
                'vod_pic': big_imgs[0],
                'vod_content': f'共 {len(big_imgs)} 张',
                'vod_remarks': f'{len(big_imgs)}P',
                'vod_play_from': '图片',
                'vod_play_url': play_url,
                'vod_tag': 'image',
            }
            return {'list': [vod]}

        # ========== 小说文本处理 ==========
        txt = content_html
        txt = re.sub(r'<br\s*/?>', '\n', txt)
        txt = re.sub(r'<p>', '\n', txt)
        txt = re.sub(r'</p>', '\n', txt)
        txt = re.sub(r'<li>', '\n• ', txt)
        txt = re.sub(r'</li>', '\n', txt)
        txt = re.sub(r'<div>', '\n', txt)
        txt = re.sub(r'</div>', '\n', txt)
        txt = re.sub(r'<[^>]+>', '', txt)
        txt = re.sub(r'&nbsp;', ' ', txt)
        txt = re.sub(r'&[a-zA-Z]+;', '', txt)
        txt = re.sub(r'\n+', '\n', txt).strip()
        txt = re.sub(r'var\s+\w+\s*=\s*\{.*?\};', '', txt, flags=re.S)
        txt = re.sub(r'function\s+\w+\s*\(.*?\)\s*\{.*?\}', '', txt, flags=re.S)
        txt = re.sub(r'\{[^\}]{0,30}\}', '', txt)

        if len(txt) > 12000:
            txt = txt[:12000] + '...'
        if not txt:
            txt = '暂无内容，请检查文章详情页结构或联系维护者。'

        novel_json = json.dumps({'title': title, 'content': txt}, ensure_ascii=False)
        play_url = f'阅读$novel://{novel_json}'
        vod = {
            'vod_id': f'art_{vid}',
            'vod_name': title,
            'vod_pic': '',
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': '小说',
            'vod_play_url': play_url,
            'vod_tag': 'text',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page == 1:
            url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}'
        else:
            url = f'{self.host}/vodsearch/{quote(key)}----------{page}---.html'
        text = self._fetch(url)
        items = self._parse_list(text, page, is_article=False).get('list', [])
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith(('novel://', 'pics://')):
            return {'parse': 0, 'url': id, 'header': ''}
        if id.startswith('http'):
            return {
                'parse': 0,
                'url': id,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        url = self.host + ('' if id.startswith('/') else '/') + id
        text = self._fetch(url)
        m3u8 = ''

        if text:
            for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data', 'cms_player']:
                m = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})\s*</script>', text, re.S)
                if m:
                    try:
                        player = json.loads(m.group(1))
                        raw_url = player.get('url', '')
                        if raw_url and isinstance(raw_url, str):
                            decoded = raw_url.strip()
                            if re.match(r'^[A-Za-z0-9+/=]{20,}$', decoded):
                                try:
                                    decoded = base64.b64decode(decoded).decode('utf-8')
                                except Exception:
                                    pass
                            if '%' in decoded:
                                try:
                                    decoded = unquote(decoded)
                                except Exception:
                                    pass
                            if decoded.startswith('http'):
                                m3u8 = decoded
                                break
                    except Exception:
                        continue

            if not m3u8:
                m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
                if m:
                    iframe_src = m.group(1)
                    if iframe_src.startswith('http'):
                        m3u8 = iframe_src
                    else:
                        m3u8 = self.host + ('' if iframe_src.startswith('/') else '/') + iframe_src

            if not m3u8:
                m = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
                if m:
                    m3u8 = m.group(1)

            if not m3u8:
                m = re.search(r'unescape\(["\']([^"\']+)["\']\)', text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass

        return {
            'parse': 0,
            'url': m3u8,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }

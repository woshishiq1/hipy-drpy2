# -*- coding: utf-8 -*-
"""
qisegu Spider —— 七色谷修复版（图区/小说/视频全兼容）
"""

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
    host = 'https://u3v4w5x6.qisegu52.cc'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://u3v4w5x6.qisegu52.cc/',
    }

    def getName(self): return "qisegu"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
            # 自动检测编码，避免强制 utf-8 导致某些页面乱码
            if r.encoding == 'ISO-8859-1':
                r.encoding = r.apparent_encoding
            if not r.encoding:
                r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def homeContent(self, filter):
        classes = [
            {'type_id': '20',  'type_name': '网曝黑料'},
            {'type_id': '181', 'type_name': '黄色仓库'},
            {'type_id': '1',   'type_name': '国产传媒'},
            {'type_id': '2',   'type_name': '国产剧情'},
            {'type_id': '3',   'type_name': '必射精选'},
            {'type_id': '4',   'type_name': '精品资源'},
            {'type_id': '5',   'type_name': '特色仓库'},
            {'type_id': '16',  'type_name': '激情图区'},
            {'type_id': '19',  'type_name': '情色小说'},
        ]
        return {'class': classes, 'filters': self._build_filters(), 'type': '影视'}

    def _build_filters(self):
        filters = {}
        filters['20'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '探花约炮', 'v': '176'}, {'n': '禁漫天堂', 'v': '173'},
            {'n': '国产精品', 'v': '169'}, {'n': '黑料吃瓜', 'v': '171'}, {'n': '华语AV', 'v': '170'},
            {'n': '学生合集', 'v': '174'}, {'n': '金发欧美', 'v': '172'}, {'n': '乱伦专区', 'v': '175'},
        ]}]
        filters['181'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产视频', 'v': '182'}, {'n': '乌鸦传媒', 'v': '29'},
            {'n': '动漫剧情', 'v': '188'}, {'n': '无码中文', 'v': '183'}, {'n': '日本有码', 'v': '186'},
            {'n': '日本无码', 'v': '185'}, {'n': '欧美高清', 'v': '187'}, {'n': '有码中文', 'v': '184'},
        ]}]
        filters['1'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '精东影业', 'v': '27'}, {'n': '天美传媒', 'v': '23'},
            {'n': '91制片厂', 'v': '22'}, {'n': '麻豆视频', 'v': '21'}, {'n': '星空传媒', 'v': '26'},
            {'n': '蜜桃传媒', 'v': '24'}, {'n': '皇家华人', 'v': '25'}, {'n': '兔子先生', 'v': '30'},
        ]}]
        filters['2'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '杏吧原创', 'v': '31'}, {'n': 'mini传媒', 'v': '33'},
            {'n': '大象传媒', 'v': '34'}, {'n': '开心鬼传媒', 'v': '35'}, {'n': '性视界', 'v': '39'},
            {'n': '糖心Vlog', 'v': '37'}, {'n': '萝莉社', 'v': '38'}, {'n': '玩偶姐姐', 'v': '32'},
        ]}]
        filters['3'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '中文字幕', 'v': '41'}, {'n': '制服诱惑', 'v': '47'},
            {'n': '日本无码', 'v': '44'}, {'n': '强奸乱伦', 'v': '46'}, {'n': '国产传媒', 'v': '42'},
            {'n': '国产视频', 'v': '40'}, {'n': '欧美无码', 'v': '45'}, {'n': '日本有码', 'v': '43'},
        ]}]
        filters['4'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': 'AV解说', 'v': '55'}, {'n': '明星换脸', 'v': '50'},
            {'n': '抖阴视频', 'v': '51'}, {'n': '伦理三级', 'v': '54'}, {'n': '网曝黑料', 'v': '53'},
            {'n': '国产主播', 'v': '48'}, {'n': '女优明星', 'v': '52'}, {'n': '激情动漫', 'v': '49'},
        ]}]
        filters['5'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': 'VR视角', 'v': '63'}, {'n': 'SM调教', 'v': '56'},
            {'n': '网红头条', 'v': '60'}, {'n': '人妖系列', 'v': '61'}, {'n': '韩国主播', 'v': '62'},
            {'n': '极品媚黑', 'v': '58'}, {'n': '女同性恋', 'v': '59'}, {'n': '萝莉少女', 'v': '57'},
        ]}]
        filters['16'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '露出偷窥', 'v': '156'}, {'n': '网友自拍', 'v': '153'},
            {'n': '唯美清纯', 'v': '152'}, {'n': '欧美激情', 'v': '155'}, {'n': 'Gif动图', 'v': '159'},
            {'n': '亚洲性爱', 'v': '154'}, {'n': '卡通漫画', 'v': '158'}, {'n': '高跟丝袜', 'v': '157'},
        ]}]
        filters['19'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '暴力虐待', 'v': '160'}, {'n': '学生校园', 'v': '161'},
            {'n': '玄幻仙侠', 'v': '162'}, {'n': '明星偶像', 'v': '163'}, {'n': '生活都市', 'v': '164'},
            {'n': '不伦恋情', 'v': '165'}, {'n': '经验故事', 'v': '166'}, {'n': '科学幻想', 'v': '167'},
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

        article_ids = {
            '16', '19', '152', '153', '154', '155', '156', '157', '158', '159',
            '160', '161', '162', '163', '164', '165', '166', '167'
        }
        is_article = tid_str in article_ids

        if is_article:
            url = f'{self.host}/arttype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/arttype/{tid_str}.html'
        else:
            url = f'{self.host}/vodtype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid_str}.html'
        text = self._fetch(url)
        return self._parse_list(text, page, is_article)

    def _fix_pic(self, pic):
        """统一修复图片地址"""
        if not pic:
            return ''
        pic = pic.strip()
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif pic.startswith('/'):
            pic = self.host + pic
        return pic

    def _is_bad_pic(self, pic):
        """判断是否为占位图/广告图"""
        if not pic:
            return True
        low = pic.lower()
        bad = ['loading', 'blank', 'logo', 'icon', 'avatar', 'smiley', 'ad.', 'banner', 'play.png']
        return any(x in low for x in bad)

    def _parse_list(self, text, page=1, is_article=False):
        items = []
        if not text:
            return self._empty_list(page)

        detail_prefix = 'artdetail' if is_article else 'voddetail'

        # ========== 文章列表（横线格式 artdetail-xxx.html） ==========
        if is_article:
            pattern_art = re.compile(
                r'<li[^>]*>\s*<a[^>]+href="/artdetail-(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*</li>',
                re.S
            )
            for m in pattern_art.finditer(text):
                vid, title = m.groups()
                items.append({
                    'vod_id': f'art_{vid}',
                    'vod_name': html.unescape(title.strip()),
                    'vod_pic': '',
                    'vod_remarks': '',
                })

        # ========== 视频/图区列表：按 <li class="content-item"> 分块提取 ==========
        if not items:
            item_pattern = re.compile(r'<li[^>]*class="content-item[^"]*"[^>]*>(.*?)</li>', re.S)
            for m in item_pattern.finditer(text):
                block = m.group(1)

                # 提取ID和标题
                id_match = re.search(
                    r'href="/' + detail_prefix + r'/(\d+)\.html"[^>]*title="([^"]*)"',
                    block, re.S
                )
                if not id_match:
                    continue
                vid, title = id_match.groups()

                # 提取图片：优先 data-original，其次 src
                pic = ''
                img_m = re.search(r'<img[^>]*?data-original="([^"]*)"', block, re.S)
                if img_m and img_m.group(1).strip():
                    pic = img_m.group(1).strip()
                else:
                    img_m = re.search(r'<img[^>]*?src="([^"]*)"', block, re.S)
                    if img_m:
                        pic = img_m.group(1).strip()

                pic = self._fix_pic(pic)
                if self._is_bad_pic(pic):
                    pic = ''

                # 提取备注（日期/标签）
                note = ''
                note_m = re.search(r'<span[^>]*class="[^"]*note[^"]*"[^>]*>([^<]*)</span>', block, re.S)
                if note_m:
                    note = note_m.group(1).strip()

                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': html.unescape(title.strip()),
                    'vod_pic': pic,
                    'vod_remarks': note,
                })

        # ========== 兜底：苹果CMS标准 vod 结构 ==========
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
                pic = self._fix_pic(pic.strip())
                if self._is_bad_pic(pic):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': html.unescape(title.strip()),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 最终兜底：通用宽松匹配 ==========
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
                    t = re.search(
                        r'<h[1-6][^>]*>\s*<a[^>]+href="/' + detail_prefix + r'/' + vid + r'\.html"[^>]*>([^<]+)</a>',
                        text, re.S
                    )
                    title = html.unescape(t.group(1).strip()) if t else f'未知标题{vid}'
                pic = self._fix_pic(pic.strip() if pic else '')
                if self._is_bad_pic(pic):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': html.unescape(title.strip()),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 纯文字链接（小说列表无图时） ==========
        if not items and is_article:
            pattern4 = re.compile(
                r'<a[^>]+href="/artdetail-(\d+)\.html"[^>]*>([^<]+)</a>', re.S
            )
            seen = set()
            for m in pattern4.finditer(text):
                vid, title = m.groups()
                if vid not in seen and len(title.strip()) > 1:
                    seen.add(vid)
                    items.append({
                        'vod_id': f'art_{vid}',
                        'vod_name': html.unescape(title.strip()),
                        'vod_pic': '',
                        'vod_remarks': '',
                    })

        # ========== 文章类补充封面图 ==========
        if is_article and items:
            for item in items:
                if not item.get('vod_pic'):
                    vid = item['vod_id'].replace('art_', '')
                    detail_text = self._fetch(f'{self.host}/artdetail-{vid}.html')
                    if detail_text:
                        imgs = re.findall(r'<img[^>]+src="(https?://[^"]+)"', detail_text)
                        for img in imgs:
                            if not self._is_bad_pic(img):
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
            title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = html.unescape(m.group(1).replace('- 七色谷', '').replace('- qisegu', '').strip())

        cover = ''
        for pat in [
            r'<div class="vod-img">.*?data-original="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*content-img',
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*content-img',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = self._fix_pic(m.group(1))
                if cover and not self._is_bad_pic(cover):
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
            play_from_list.append('qisegu')

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
                title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
                if title:
                    break
        if not title:
            title = f'文章{vid}'

        content_html = ''
        selectors = [
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

        imgs = re.findall(r'<img[^>]+(?:src|data-original|data-src|original)="([^"]+)"', content_html)
        big_imgs = []
        for img in imgs:
            img = self._fix_pic(img)
            if self._is_bad_pic(img):
                continue
            if img not in big_imgs:
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
                m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', text)
                if m:
                    decoded = m.group(1)
                    if '%' in decoded:
                        try:
                            decoded = unquote(decoded)
                        except Exception:
                            pass
                    if decoded.startswith('http'):
                        m3u8 = decoded

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

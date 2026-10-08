# -*- coding: utf-8 -*-
"""
DJYZ51 Spider —— 东京淫朕修复版（图区/小说/视频全兼容）
适配域名: https://k7l8m9n0.djyz51.cc
"""

import sys
import re
import json
import requests
import urllib3
import base64
from urllib.parse import quote, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://k7l8m9n0.djyz51.cc'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://k7l8m9n0.djyz51.cc/',
    }

    def getName(self): return "djyz51"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
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
            {'n': '全部', 'v': ''}, {'n': '探花约炮', 'v': '176'}, {'n': '黑料吃瓜', 'v': '171'},
            {'n': '乱伦专区', 'v': '175'}, {'n': '金发欧美', 'v': '172'}, {'n': '学生合集', 'v': '174'},
            {'n': '国产精品', 'v': '169'}, {'n': '华语AV', 'v': '170'}, {'n': '禁漫天堂', 'v': '173'},
        ]}]
        filters['181'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产视频', 'v': '182'}, {'n': '无码中文', 'v': '183'},
            {'n': '欧美高清', 'v': '187'}, {'n': '动漫剧情', 'v': '188'}, {'n': '乌鸦传媒', 'v': '29'},
            {'n': '日本无码', 'v': '185'}, {'n': '有码中文', 'v': '184'}, {'n': '日本有码', 'v': '186'},
        ]}]
        filters['1'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '兔子先生', 'v': '30'}, {'n': '麻豆视频', 'v': '21'},
            {'n': '91制片厂', 'v': '22'}, {'n': '皇家华人', 'v': '25'}, {'n': '精东影业', 'v': '27'},
            {'n': '蜜桃传媒', 'v': '24'}, {'n': '天美传媒', 'v': '23'}, {'n': '星空传媒', 'v': '26'},
        ]}]
        filters['2'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '大象传媒', 'v': '34'}, {'n': '萝莉社', 'v': '38'},
            {'n': '玩偶姐姐', 'v': '32'}, {'n': '开心鬼传媒', 'v': '35'}, {'n': '杏吧原创', 'v': '31'},
            {'n': 'mini传媒', 'v': '33'}, {'n': '性视界', 'v': '39'}, {'n': '糖心Vlog', 'v': '37'},
        ]}]
        filters['3'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产视频', 'v': '40'}, {'n': '中文字幕', 'v': '41'},
            {'n': '日本无码', 'v': '44'}, {'n': '制服诱惑', 'v': '47'}, {'n': '强奸乱伦', 'v': '46'},
            {'n': '国产传媒', 'v': '42'}, {'n': '欧美无码', 'v': '45'}, {'n': '日本有码', 'v': '43'},
        ]}]
        filters['4'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产主播', 'v': '48'}, {'n': '明星换脸', 'v': '50'},
            {'n': '抖阴视频', 'v': '51'}, {'n': '伦理三级', 'v': '54'}, {'n': '女优明星', 'v': '52'},
            {'n': 'AV解说', 'v': '55'}, {'n': '激情动漫', 'v': '49'}, {'n': '网曝黑料', 'v': '53'},
        ]}]
        filters['5'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '网红头条', 'v': '60'}, {'n': '萝莉少女', 'v': '57'},
            {'n': 'VR视角', 'v': '63'}, {'n': '极品媚黑', 'v': '58'}, {'n': 'SM调教', 'v': '56'},
            {'n': '韩国主播', 'v': '62'}, {'n': '女同性恋', 'v': '59'}, {'n': '人妖系列', 'v': '61'},
        ]}]
        filters['16'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '高跟丝袜', 'v': '157'}, {'n': '露出偷窥', 'v': '156'},
            {'n': '卡通漫画', 'v': '158'}, {'n': 'Gif动图', 'v': '159'}, {'n': '欧美激情', 'v': '155'},
            {'n': '亚洲性爱', 'v': '154'}, {'n': '唯美清纯', 'v': '152'}, {'n': '网友自拍', 'v': '153'},
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

        # 文章类ID：图区(16及子类152-159) / 小说(19及子类160-167)
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

    def _parse_list(self, text, page=1, is_article=False):
        items = []
        if not text:
            return self._empty_list(page)

        detail_prefix = 'artdetail' if is_article else 'voddetail'

        # ========== 模式A：djyz51当前模板 portfolio-item 结构（精确解析） ==========
        if not is_article:
            block_pattern = re.compile(
                r'<div[^>]*class="[^"]*portfolio-item[^"]*"[^>]*>'
                r'(.*?)'
                r'<div[^>]*class="v-title"[^>]*>(.*?)</div>\s*</div>',
                re.S
            )
            seen = set()
            for block_match in block_pattern.finditer(text):
                group1 = block_match.group(1)  # portfolio-item 内部 v-title 之前的 HTML
                group2 = block_match.group(2)  # v-title 标签内部的 HTML

                # 提取 vid（从 group1 中的图片链接）
                vid = ''
                m = re.search(r'href="/voddetail/(\d+)\.html"', group1)
                if m:
                    vid = m.group(1)
                else:
                    m = re.search(r'href="/voddetail/(\d+)\.html"', group2)
                    if m:
                        vid = m.group(1)
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                # 提取图片：优先 data-original，其次 src（从 group1）
                pic = ''
                m = re.search(r'data-original="([^"]+)"', group1)
                if m:
                    pic = m.group(1)
                else:
                    m = re.search(r'src="([^"]+)"', group1)
                    if m:
                        pic = m.group(1)
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''

                # 提取 uptime（简介/描述）
                uptime_text = ''
                m = re.search(r'<div[^>]*class="uptime"[^>]*>(.*?)</div>', group2, re.S)
                if m:
                    uptime_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()

                # 提取上架时间
                add_time = ''
                m = re.search(r'上架时间：(\d{4}-\d{2}-\d{2})', group2)
                if m:
                    add_time = m.group(1)

                # 提取标题（从 group2 中的 <a> 标签文本）
                title = ''
                m = re.search(r'<a[^>]+href="[^"]*"[^>]*>([^<]+)</a>', group2, re.S)
                if m:
                    title = m.group(1).strip()
                if not title:
                    title = uptime_text

                # vod_remarks：用 uptime 内容作为简介
                # 如果 uptime 为空，用上架时间兜底
                remarks = uptime_text if uptime_text else add_time

                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        # ========== 模式B：ybhz51/content-item 结构（兼容） ==========
        if not items:
            pattern = re.compile(
                r'<li[^>]*class="content-item[^"]*"[^>]*>'
                r'.*?<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>'
                r'.*?<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)")[^>]*>'
                r'.*?</li>',
                re.S
            )
            for m in pattern.finditer(text):
                vid, title, pic1, pic2 = m.groups()
                pic = pic1 if pic1 else pic2
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式C：苹果CMS标准 vod 结构（乐园模板兼容） ==========
        if not items:
            pattern2 = re.compile(
                r'<div class="vod">\s*<div class="vod-img">\s*'
                r'<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*>.*?'
                r'<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)")[^>]*>.*?</a>\s*</div>\s*'
                r'<div class="vod-txt">\s*<a[^>]*>([^<]+)</a>',
                re.S
            )
            for m in pattern2.finditer(text):
                vid, pic1, pic2, title = m.groups()
                pic = pic1 if pic1 else pic2
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式D：通用宽松匹配（兜底） ==========
        if not items:
            pattern3 = re.compile(
                r'<a[^>]+href="/' + detail_prefix + r'/(\d+)\.html"[^>]*(?:title="([^"]*)")?[^>]*>'
                r'.*?<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)"|data-src="([^"]*)")[^>]*>.*?</a>',
                re.S
            )
            seen = set()
            for m in pattern3.finditer(text):
                vid, title, pic1, pic2, pic3 = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                if not title:
                    t = re.search(r'<h[1-6][^>]*>\s*<a[^>]+href="/' + detail_prefix + r'/' + vid + r'\.html"[^>]*>([^<]+)</a>', text, re.S)
                    title = t.group(1).strip() if t else f'未知标题{vid}'
                pic = pic1 or pic2 or pic3
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'load.png']):
                    pic = ''
                items.append({
                    'vod_id': f'art_{vid}' if is_article else vid,
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # ========== 模式E：文章列表纯文字（小说/图区无图时） ==========
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
                        'vod_name': title.strip(),
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

        # 提取标题
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<h2[^>]*>(.*?)</h2>', text, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).replace('- 东京淫朕', '').replace('- djyz51', '').strip()

        # 提取封面
        cover = ''
        cover_patterns = [
            r'<div class="vod-img">.*?<img[^>]+data-original="([^"]+)"',
            r'<div class="vod-img">.*?<img[^>]+src="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*content-img',
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*content-img',
            r'<img[^>]+class="[^"]*img-responsive[^"]*"[^>]+data-original="([^"]+)"',
            r'<img[^>]+class="[^"]*img-responsive[^"]*"[^>]+src="([^"]+)"',
            r'<div[^>]*class="[^"]*vod-pic[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
            r'<div[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
            r'<div[^>]*class="[^"]*lazyload[^"]*"[^>]+data-original="([^"]+)"',
        ]
        for pat in cover_patterns:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and 'loading' not in cover and 'blank' not in cover:
                    break

        # 提取剧情简介 vod_content
        content = ''
        content_patterns = [
            r'<div[^>]*class="[^"]*vod-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*data[^"]*"[^>]*>(.*?)</p>',
            r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>(.*?)</span>',
        ]
        for pat in content_patterns:
            m = re.search(pat, text, re.S)
            if m:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if len(content) > 10:
                    break

        # 提取演员/导演等 remarks 信息
        remarks = ''
        info_patterns = [
            r'<p[^>]*class="[^"]*data[^"]*"[^>]*>.*?主演[：:]\s*([^<]+)',
            r'<div[^>]*class="[^"]*vod-info[^"]*"[^>]*>.*?主演[：:]\s*([^<]+)',
            r'<span[^>]*>.*?主演[：:]\s*([^<]+)',
            r'<p[^>]*>.*?演员[：:]\s*([^<]+)',
        ]
        for pat in info_patterns:
            m = re.search(pat, text, re.S)
            if m:
                remarks = m.group(1).strip()
                if remarks:
                    break

        # 尝试解析多播放源/多集
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
            play_from_list.append('djyz51')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': content,
            'vod_remarks': remarks,
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
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if title:
                    break
        if not title:
            title = f'文章{vid}'

        # 提取内容区
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

        # 提取图片
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

        # 小说文本处理
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

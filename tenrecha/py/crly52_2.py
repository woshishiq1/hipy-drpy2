# -*- coding: utf-8 -*-
"""
crly52 Spider —— 分类判断修正版
"""

import sys
import re
import json
import requests
import urllib3
from urllib.parse import quote, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://c9d0e1f2.crly52.buzz'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://c9d0e1f2.crly52.buzz/',
    }

    def getName(self): return "crly52"
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
            {'type_id': '1',   'type_name': '国产传媒'},
            {'type_id': '2',   'type_name': '国产剧情'},
            {'type_id': '221', 'type_name': '热门爆料'},
            {'type_id': '233', 'type_name': '经典AV'},
            {'type_id': '208', 'type_name': '热播片库'},
            {'type_id': '3',   'type_name': '必射精选'},
            {'type_id': '5',   'type_name': '特色仓库'},
            {'type_id': '4',   'type_name': '精品资源'},
            {'type_id': '16',  'type_name': '激情图区'},
            {'type_id': '20',  'type_name': '情色小说'},
        ]
        return {'class': classes, 'filters': self._build_filters(), 'type': '影视'}

    def _build_filters(self):
        filters = {}
        filters['1'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '乌鸦传媒', 'v': '29'}, {'n': '精东影业', 'v': '27'},
            {'n': '蜜桃传媒', 'v': '24'}, {'n': '大象传媒', 'v': '34'}, {'n': '开心鬼传媒', 'v': '35'},
            {'n': '麻豆视频', 'v': '21'}, {'n': 'mini传媒', 'v': '33'}, {'n': '星空传媒', 'v': '26'},
        ]}]
        filters['2'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '91制片厂', 'v': '22'}, {'n': '天美传媒', 'v': '23'},
            {'n': '杏吧原创', 'v': '31'}, {'n': '萝莉社', 'v': '38'}, {'n': '皇家华人', 'v': '25'},
            {'n': '兔子先生', 'v': '30'}, {'n': '糖心Vlog', 'v': '37'}, {'n': '性视界', 'v': '39'},
        ]}]
        filters['221'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产大制作', 'v': '222'}, {'n': '乱伦毁三观', 'v': '223'},
            {'n': '主播女网红', 'v': '224'}, {'n': '黑料网曝', 'v': '225'}, {'n': '高清无码', 'v': '226'},
            {'n': '中文字幕', 'v': '227'}, {'n': '淫乱学生妹', 'v': '229'}, {'n': '偷拍自拍', 'v': '232'},
        ]}]
        filters['233'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '国产视频', 'v': '234'}, {'n': '无码中文', 'v': '235'},
            {'n': '有码中文', 'v': '236'}, {'n': '日本有码', 'v': '237'}, {'n': '日本无码', 'v': '238'},
            {'n': '欧美高清', 'v': '239'}, {'n': '动漫剧情', 'v': '240'}, {'n': '成人头条', 'v': '199'},
        ]}]
        filters['208'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '黑料吃瓜', 'v': '209'}, {'n': '乱伦精品', 'v': '210'},
            {'n': '欧美巨屌', 'v': '211'}, {'n': '约炮探花', 'v': '212'}, {'n': '网红主播', 'v': '213'},
            {'n': '成人头条', 'v': '214'}, {'n': '极品学妹', 'v': '215'}, {'n': '国产视频', 'v': '216'},
        ]}]
        filters['3'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '强奸乱伦', 'v': '46'}, {'n': '制服诱惑', 'v': '47'},
            {'n': '中文字幕', 'v': '41'}, {'n': '国产视频', 'v': '40'}, {'n': '欧美无码', 'v': '45'},
            {'n': '国产传媒', 'v': '42'}, {'n': '日本无码', 'v': '44'}, {'n': '日本有码', 'v': '43'},
        ]}]
        filters['5'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': 'SM调教', 'v': '56'}, {'n': '网红头条', 'v': '60'},
            {'n': '极品媚黑', 'v': '58'}, {'n': '萝莉少女', 'v': '57'}, {'n': 'VR视角', 'v': '63'},
            {'n': '人妖系列', 'v': '61'}, {'n': '韩国主播', 'v': '62'}, {'n': '女同性恋', 'v': '198'},
        ]}]
        filters['4'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '激情动漫', 'v': '49'}, {'n': 'AV解说', 'v': '55'},
            {'n': '国产主播', 'v': '48'}, {'n': '明星换脸', 'v': '50'}, {'n': '抖阴视频', 'v': '51'},
            {'n': '网曝黑料', 'v': '53'}, {'n': '伦理三级', 'v': '54'}, {'n': '女优明星', 'v': '52'},
        ]}]
        filters['16'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '露出偷窥', 'v': '156'}, {'n': 'Gif动图', 'v': '159'},
            {'n': '亚洲性爱', 'v': '154'}, {'n': '卡通漫画', 'v': '158'}, {'n': '高跟丝袜', 'v': '157'},
            {'n': '唯美清纯', 'v': '152'}, {'n': '网友自拍', 'v': '153'}, {'n': '欧美激情', 'v': '155'},
        ]}]
        filters['20'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '暴力虐待', 'v': '200'}, {'n': '学生校园', 'v': '201'},
            {'n': '玄幻仙侠', 'v': '202'}, {'n': '明星偶像', 'v': '203'}, {'n': '生活都市', 'v': '204'},
            {'n': '不伦恋情', 'v': '205'}, {'n': '经验故事', 'v': '206'}, {'n': '科学幻想', 'v': '207'},
        ]}]
        return filters

    def homeVideoContent(self):
        text = self._fetch(self.host + '/gbook/')
        items = self._parse_vod_list(text, page=1)
        return {'list': items, 'page': 1, 'pagecount': 2 if items else 1, 'limit': len(items), 'total': len(items)}

    # ==================== 修正：is_article 判断 ====================
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
        
        # 修正：只有真正的文章类 ID 才走文章接口
        # 图区：16 及子分类 152-159；小说：20 及子分类 200-207
        article_ids = {'16', '20', '152', '153', '154', '155', '156', '157', '158', '159',
                       '200', '201', '202', '203', '204', '205', '206', '207'}
        is_article = tid_str in article_ids

        if is_article:
            url = f'{self.host}/arttype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/arttype/{tid_str}.html'
        else:
            url = f'{self.host}/vodtype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid_str}.html'
        text = self._fetch(url)
        if is_article:
            return self._parse_art_list(text, page)
        return self._parse_vod_list(text, page)

    def _parse_vod_list(self, text, page=1):
        items = []
        if not text:
            return self._empty_list(page)
        pattern = re.compile(
            r'<div class="vod">\s*<div class="vod-img">\s*<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>.*?<img[^>]+data-original="([^"]*)"[^>]*>.*?</a>\s*</div>\s*<div class="vod-txt">\s*<a[^>]*>([^<]+)</a>',
            re.S
        )
        for m in pattern.finditer(text):
            vid, pic, title = m.groups()
            if pic and ('loading.svg' in pic or 'blank.gif' in pic):
                pic = ''
            if vid and title:
                items.append({
                    'vod_id': vid,
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def _parse_art_list(self, text, page=1):
        items = []
        if not text:
            return self._empty_list(page)
        pattern = re.compile(
            r'<div class="vod">\s*<div class="vod-img">\s*<a[^>]+href="/artdetail-(\d+)\.html"[^>]*>.*?<img[^>]+data-original="([^"]*)"[^>]*>.*?</a>\s*</div>\s*<div class="vod-txt">\s*<a[^>]*>([^<]+)</a>',
            re.S
        )
        for m in pattern.finditer(text):
            vid, pic, title = m.groups()
            if pic and ('loading.svg' in pic or 'blank.gif' in pic or pic == '/'):
                pic = ''
            if vid and title:
                items.append({
                    'vod_id': f'art_{vid}',
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })
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
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).replace('- 成人乐园', '').strip()
        cover = ''
        m = re.search(r'<div class="vod-img">.*?data-original="([^"]+)"', text, re.S)
        if m:
            cover = m.group(1)
        if not cover or 'loading.svg' in cover:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', text)
            if m:
                cover = m.group(1)
        play_url = f'/vodplay/{vid}-1-1.html'
        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': 'crly52',
            'vod_play_url': f'正片${play_url}',
        }
        return {'list': [vod]}

    def _art_detail(self, vid):
        url = f'{self.host}/artdetail-{vid}.html'
        text = self._fetch(url)
        if not text:
            return {'list': []}
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<h2[^>]*>(.*?)</h2>', text, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        content_html = ''
        m = re.search(r'<div class="content"[^>]*>(.*?)</div>', text, re.S)
        if m:
            content_html = m.group(1)
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', content_html)
        big_imgs = [img for img in imgs if not any(x in img for x in ['loading.svg', 'blank.gif', 'l.webp', 'logo', 'icon'])]
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
        else:
            txt = re.sub(r'<br\s*/?>', '\n', content_html)
            txt = re.sub(r'<p>', '\n', txt)
            txt = re.sub(r'</p>', '', txt)
            txt = re.sub(r'<[^>]+>', '', txt)
            txt = re.sub(r'&nbsp;', ' ', txt)
            txt = re.sub(r'\n+', '\n', txt).strip()
            if len(txt) > 8000:
                txt = txt[:8000] + '...'
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
        items = self._parse_vod_list(text, page)
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
            m = re.search(r'var player_aaaa\s*=\s*(\{.*?\})\s*</script>', text, re.S)
            if m:
                try:
                    player = json.loads(m.group(1))
                    raw_url = player.get('url', '')
                    if raw_url and isinstance(raw_url, str):
                        m3u8 = unquote(raw_url)
                except Exception:
                    pass
            if not m3u8:
                m = re.search(r"(https?://[^\s\"<>']+?\.m3u8)", text)
                if m:
                    m3u8 = m.group(1)
        return {
            'parse': 0,
            'url': m3u8,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }

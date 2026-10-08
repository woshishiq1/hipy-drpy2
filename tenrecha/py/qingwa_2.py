# -*- coding: utf-8 -*-
"""
青蛙视频 / tev969 / qw9977 爬虫
适配苹果CMS加密模板：SHA256(key) + AES-256-ECB + PKCS7 + URL-Safe Base64
"""

import sys
import re
import json
import requests
import urllib3
import base64
import hashlib
import html as htmlmod
from urllib.parse import quote, unquote, urljoin
from Crypto.Cipher import AES

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = "https://www.tev969.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.tev969.com/",
    }
    crypt_key = "nz52h7tsz68edd85"
    _aes_key = None
    _class_cache = None

    def getName(self): return "qingwa"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url or '.flv' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def _get_aes_key(self):
        if self._aes_key is None:
            self._aes_key = hashlib.sha256(self.crypt_key.encode('utf-8')).digest()
        return self._aes_key

    def _aes_decrypt(self, ciphertext_b64):
        """URL-safe base64 -> AES-256-ECB -> UTF-8 text"""
        if not ciphertext_b64:
            return ""
        try:
            s = ciphertext_b64.replace('-', '+').replace('_', '/')
            while len(s) % 4 != 0:
                s += '='
            data = base64.b64decode(s)
            if not data:
                return ""
            cipher = AES.new(self._get_aes_key(), AES.MODE_ECB)
            decrypted = cipher.decrypt(data)
            pad_len = decrypted[-1]
            if 1 <= pad_len <= 16:
                decrypted = decrypted[:-pad_len]
            return decrypted.decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def init(self, extend=""):
        self.session.verify = False
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            self.session.headers.update(self.headers)

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def _fix(self, url):
        if not url:
            return ""
        # 先解码HTML实体，防止 &amp; 导致URL错误
        url = htmlmod.unescape(url)
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        if url.startswith("http"):
            return url
        return urljoin(self.host, "/" + url)

    def _clean(self, text):
        if not text:
            return ""
        return htmlmod.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

    def homeContent(self, filter):
        if self._class_cache is not None:
            return self._class_cache

        text = self._fetch(self.host + '/')
        classes = []
        filters = {}

        # 提取分类导航块（大分类 + 子分类）
        # 结构：<div class="type-name">大分类</div> <div class="grid-link">子分类们</div>
        nav_blocks = re.findall(
            r'<div class="[^"]*type-name[^"]*">(.*?)<div class="[^"]*grid-link[^"]*">(.*?)</div>',
            text, re.S
        )
        
        seen = set()
        parent_map = {}  # tid -> 父分类ID，用于构建filters

        for type_block, link_block in nav_blocks:
            # 提取大分类ID和名称
            parent_m = re.search(r'href="/(?:vod|art)type/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)', type_block, re.S)
            if not parent_m:
                continue
            parent_tid, parent_enc = parent_m.groups()
            parent_name = self._aes_decrypt(parent_enc)
            if not parent_name:
                parent_name = f"分类{parent_tid}"
            
            # 去重后加入
            if parent_tid not in seen:
                seen.add(parent_tid)
                classes.append({"type_name": parent_name, "type_id": parent_tid})
            
            # 提取该块下的子分类
            sub_items = []
            sub_links = re.findall(
                r'href="/(vod|art)type/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)',
                link_block, re.S
            )
            for kind, sub_tid, sub_enc in sub_links:
                if sub_tid in seen:
                    continue
                seen.add(sub_tid)
                sub_name = self._aes_decrypt(sub_enc)
                if not sub_name:
                    sub_name = f"子类{sub_tid}"
                # 子分类ID前缀处理
                real_tid = f"art_{sub_tid}" if kind == "art" else sub_tid
                classes.append({"type_name": sub_name, "type_id": real_tid})
                sub_items.append({"n": sub_name, "v": real_tid})
            
            # 构建filters（为该父分类添加子分类筛选项）
            if sub_items:
                filters[parent_tid] = [
                    {"key": "sub", "name": "子分类", "value": sub_items}
                ]

        # 兜底：如果块提取失败，回退到原来的全局正则提取
        if not classes:
            vod_blocks = re.findall(
                r'href="/vodtype/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)',
                text, re.S
            )
            for tid, enc in vod_blocks:
                if tid in seen:
                    continue
                seen.add(tid)
                name = self._aes_decrypt(enc)
                if not name:
                    name = f"视频{tid}"
                classes.append({"type_name": name, "type_id": tid})

            art_blocks = re.findall(
                r'href="/arttype/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)',
                text, re.S
            )
            for tid, enc in art_blocks:
                tid = f"art_{tid}"
                if tid in seen:
                    continue
                seen.add(tid)
                name = self._aes_decrypt(enc)
                if not name:
                    name = f"文章{tid}"
                classes.append({"type_name": name, "type_id": tid})

        # 最终兜底
        if not classes:
            classes = [
                {"type_name": "视频", "type_id": "2"},
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "图区", "type_id": "art_4"},
                {"type_name": "小说", "type_id": "art_5"},
            ]

        self._class_cache = {'class': classes, 'filters': filters, 'type': '影视'}
        return self._class_cache

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
        tid_str = str(tid)
        is_article = tid_str.startswith('art_')

        # 支持子分类筛选（通过filter传入子分类ID）
        sub_tid = extend.get('sub', '') if extend else ''
        if sub_tid and not is_article:
            tid_str = str(sub_tid).replace('art_', '')

        if is_article:
            real_tid = tid_str.replace('art_', '')
            url = f'{self.host}/arttype/{real_tid}-{page}.html' if page > 1 else f'{self.host}/arttype/{real_tid}.html'
        else:
            url = f'{self.host}/vodtype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid_str}.html'

        text = self._fetch(url)
        return self._parse_list(text, page, is_article)

    def _parse_list(self, text, page=1, is_article=False):
        items = []
        if not text:
            return self._empty_list(page)

        if is_article:
            # 文章列表：先尝试带标题的 li 结构
            pattern = re.compile(
                r'<li[^>]*>.*?<a[^>]+href="/artdetail-?(\d+)\.html"[^>]*>(?:<span[^>]*>.*?</span>)?\s*([^<]+)</a>.*?</li>',
                re.S
            )
            for m in pattern.finditer(text):
                vid, title = m.groups()
                title = self._clean(title)
                if title:
                    items.append({
                        'vod_id': f'art_{vid}',
                        'vod_name': title,
                        'vod_pic': '',
                        'vod_remarks': '',
                    })
            # 兜底宽松匹配
            if not items:
                pattern2 = re.compile(
                    r'href="/artdetail-?(\d+)\.html"[^>]*>(?:<[^>]+>)*\s*([^<]{2,})',
                    re.S
                )
                seen = set()
                for m in pattern2.finditer(text):
                    vid, title = m.groups()
                    title = self._clean(title)
                    if vid not in seen and len(title) > 1:
                        seen.add(vid)
                        items.append({
                            'vod_id': f'art_{vid}',
                            'vod_name': title,
                            'vod_pic': '',
                            'vod_remarks': '',
                        })
        else:
            # 视频列表：匹配 video-card 块（支持 image 和 image-full 变体）
            # 先尝试包含3层闭合div的结构（标准卡片）
            cards = re.findall(
                r'<div class="video-card[^"]*">(.*?)</div>\s*</div>\s*</div>',
                text, re.S
            )
            # 再尝试2层闭合div的结构（无内嵌meta的简单卡片）
            if not cards:
                cards = re.findall(
                    r'<div class="video-card[^"]*">(.*?)</div>\s*</div>',
                    text, re.S
                )
            # 兜底：直接按video-card拆分
            if not cards:
                raw_cards = re.split(r'<div class="video-card[^"]*">', text)
                cards = []
                for raw in raw_cards[1:]:
                    end = raw.find('</div><div class="video-card')  # 找下一个卡片开始
                    if end == -1:
                        end = raw.rfind('</div>')
                    if end > 0:
                        cards.append(raw[:end])

            seen = set()
            for card in cards:
                # 跳过广告位
                if 'list-ad' in card or ('target="_blank"' in card and 'data-decrypt' not in card):
                    continue

                # 提取视频ID（支持 vodplay 和 voddetail 两种链接）
                vid = ''
                for vid_pat in [r'href="/vodplay/(\d+)-\d+-\d+\.html"', r'href="/voddetail/(\d+)\.html"']:
                    vid_m = re.search(vid_pat, card)
                    if vid_m:
                        vid = vid_m.group(1)
                        break
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                # 标题（优先解密 data-decrypt，支持多个密文尝试）
                title = ''
                title_encs = re.findall(r'data-decrypt="([^"]+)"', card)
                for enc in title_encs:
                    dec = self._aes_decrypt(enc)
                    if dec and len(dec) > 1:
                        title = dec
                        break
                if not title:
                    alt_m = re.search(r'alt="([^"]*)"', card)
                    title = alt_m.group(1) if alt_m else ''
                if not title:
                    txt_m = re.search(r'<a[^>]+href="/vodplay/[^"]+"[^>]*>([^<]+)</a>', card)
                    if txt_m:
                        title = self._clean(txt_m.group(1))
                if not title:
                    title = f'未知{vid}'

                # 封面图（支持 data-original / data-src / src，并解码HTML实体）
                pic = ''
                for pic_pat in [r'data-original="([^"]+)"', r'data-src="([^"]+)"', r'src="(https?://[^"]+)"']:
                    pic_m = re.search(pic_pat, card)
                    if pic_m:
                        pic = pic_m.group(1)
                        if pic and 'loading' not in pic and 'blank' not in pic:
                            break
                pic = self._fix(pic)

                # 备注（时长、集数等）
                remark = ''
                remark_m = re.search(r'<span[^>]*>(\d{2}:\d{2}:\d{2})</span>', card)
                if remark_m:
                    remark = remark_m.group(1)
                if not remark:
                    remark_m = re.search(r'<span[^>]*>([^<]{2,10})</span>', card)
                    if remark_m:
                        remark = remark_m.group(1).strip()

                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark,
                })

        # 分页处理
        pagecount = page + 1 if items else page
        maxpg = 1
        pg_links = re.findall(r'href="/(?:vod|art)type/\d+-(\d+)\.html"', text)
        for p in pg_links:
            try:
                if int(p) > maxpg:
                    maxpg = int(p)
            except:
                pass
        if maxpg > 1:
            pagecount = maxpg
        elif len(items) >= 24:
            pagecount = page + 1

        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
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
        # 先请求详情页
        url = f'{self.host}/voddetail/{vid}.html'
        text = self._fetch(url)
        if not text:
            url = f'{self.host}/vodplay/{vid}-1-1.html'
            text = self._fetch(url)

        if not text:
            return {'list': []}

        # 标题（播放页核心修复：从 data-decrypt 提取加密标题）
        title = ''
        # 方法1: 从 single-video-title 区域提取最后一个 data-decrypt（通常是视频名）
        title_block = re.search(r'<div class="single-video-title[^"]*">(.*?)</div>\s*</div>', text, re.S)
        if title_block:
            dec_list = re.findall(r'data-decrypt="([^"]+)"', title_block.group(1))
            for enc in reversed(dec_list):
                dec = self._aes_decrypt(enc)
                if dec and len(dec) > 1:
                    title = dec
                    break
        
        # 方法2: 从页面所有 data-decrypt 中找最长的作为标题兜底
        if not title:
            dec_list = re.findall(r'data-decrypt="([^"]+)"', text)
            best = ''
            for enc in dec_list:
                dec = self._aes_decrypt(enc)
                if dec and len(dec) > len(best):
                    best = dec
            if len(best) > 1:
                title = best

        # 方法3: 原有兜底逻辑
        if not title:
            m = re.search(r'"vod_name":"([^"]+)"', text)
            if m:
                title = m.group(1)
        if not title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<h2[^>]*>(.*?)</h2>', text, re.S)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).replace('- 青蛙视频', '').replace('- qw9977', '').strip()

        # 封面
        cover = ''
        for pat in [
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'data-original="(https?://[^"]+)"',
            r'<img[^>]+src="(https?://[^"]+)"[^>]*class="[^"]*img-fluid',
            r'data-src="(https?://[^"]+)"',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and 'loading' not in cover:
                    break
        cover = self._fix(cover)

        # 简介
        content = ''
        m = re.search(r'"vod_content":"([^"]*)"', text)
        if m:
            content = m.group(1).replace('\\n', '\n').replace('\\r', '').replace('\\t', '')
        if not content:
            m = re.search(r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>', text, re.S)
            if m:
                content = self._clean(m.group(1))

        # 播放源与选集
        play_from_list = []
        play_url_list = []

        # 尝试从 player_aaaa / player_data 提取
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', text, re.S)
        if not m:
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\})\s*</script>', text, re.S)
        if m:
            try:
                player = json.loads(m.group(1))
                from_src = player.get('from', '') or '线路1'
                url_now = player.get('url', '')
                if url_now and isinstance(url_now, str):
                    decoded = url_now.strip()
                    # 尝试 base64 解码
                    if re.match(r'^[A-Za-z0-9+/=]{20,}$', decoded):
                        try:
                            decoded = base64.b64decode(decoded).decode('utf-8')
                        except Exception:
                            pass
                    # 尝试 URL 解码
                    if '%' in decoded:
                        try:
                            decoded = unquote(decoded)
                        except Exception:
                            pass
                    if decoded.startswith('http'):
                        play_url_list.append(f'正片${decoded}')
                        play_from_list.append(from_src)
                    else:
                        play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')
                        play_from_list.append(from_src)
                else:
                    play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')
                    play_from_list.append(from_src)
            except:
                play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')
                play_from_list.append('线路1')
        else:
            # 从页面播放列表提取多集
            eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', text)
            if eps:
                urls = '#'.join([f'{name.strip()}${href}' for href, name in eps])
                play_url_list.append(urls)
                play_from_list.append('线路1')
            else:
                play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')
                play_from_list.append('线路1')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': content,
            'vod_remarks': '',
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def _art_detail(self, vid):
        urls_to_try = [
            f'{self.host}/artdetail/{vid}.html',
            f'{self.host}/artdetail-{vid}.html',
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
                title = self._clean(m.group(1))
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
            r'<article[^>]*>(.*?)</article>',
        ]
        for selector in selectors:
            m = re.search(selector, text, re.S)
            if m:
                content_html = m.group(1)
                if len(content_html) > 50:
                    break

        if not content_html:
            body = re.search(r'<body[^>]*>(.*?)</body>', text, re.S)
            if body:
                content_html = body.group(1)
                content_html = re.sub(r'<(header|nav|footer|aside)[^>]*>.*?</\1>', '', content_html, flags=re.S)

        # 提取图片
        imgs = re.findall(r'<img[^>]+(?:src|data-original|data-src)="([^"]+)"', content_html)
        big_imgs = []
        for img in imgs:
            low = img.lower()
            if any(x in low for x in ['loading', 'blank', 'logo', 'icon', 'avatar', 'smiley', 'ad.', 'gif', 'banner']):
                continue
            img = self._fix(img)
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

        # 小说模式
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

        if len(txt) > 12000:
            txt = txt[:12000] + '...'
        if not txt:
            txt = '暂无内容'

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
        url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}'
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

        if id.startswith('/vodplay/'):
            url = self.host + id
        else:
            url = f'{self.host}/vodplay/{id}'

        text = self._fetch(url)
        m3u8 = ''

        if text:
            # ① player_aaaa / player_data JSON
            for var_name in ['player_aaaa', 'player_data', 'player', 'mac_player']:
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

            # ② iframe 嵌套
            if not m3u8:
                m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
                if m:
                    iframe_src = m.group(1)
                    m3u8 = iframe_src if iframe_src.startswith('http') else self._fix(iframe_src)

            # ③ 直链正则
            if not m3u8:
                m = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
                if m:
                    m3u8 = m.group(1)

            # ④ unescape
            if not m3u8:
                m = re.search(r'unescape\(["\']([^"\']+)["\']\)', text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass

        if m3u8:
            return {
                'parse': 0,
                'url': m3u8,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        # 兜底：交给 APP 二次解析
        return {
            'parse': 1,
            'url': url,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }

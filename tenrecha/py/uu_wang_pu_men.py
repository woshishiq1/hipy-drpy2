# -*- coding: utf-8 -*-
"""
UU网曝门++ Spider —— 苹果CMS v10 海螺模板适配
修复汇总：
  1. 列表/详情页封面从 <a class="vodlist_thumb"> 提取
  2. 播放源名称清理 iconfont 私用区字符（含 &#xe62f; 等 HTML 实体形式）
  3. 播放列表直接从 ul.content_playlist 提取
  4. 列表页 + 详情页统一清洗番号前缀（Pacopacomama 032526_100 等）
  5. 【修复】playerContent 完整支持 MacPlayerConfig 解析器检测（ps!=0 时返回 parse:1）
  6. 【修复】playerContent 增强多层解析：var url/src/video、<source>、路径特征匹配
  7. 【修复】encrypt=0 时仍做 URL 解码
  8. 【修复】播放页 Referer 指向对应详情页
  9. 【修复】_fetch 支持传入临时 headers
 10. 【致命修复】localProxy 返回 500 导致 NanoHTTPD Status null 崩溃，改为 500
"""

import sys
import re
import json
import requests
import base64
import html as html_module
import random
import urllib3
from urllib.parse import quote, unquote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://g--othiesh.wangpumen-9eee999.click'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://g--othiesh.wangpumen-9eee999.click/',
    }

    def getName(self): return "uu_wang_pu_men"
    def isVideoFormat(self, url):
        if not url:
            return False
        url = url.lower()
        return any(ext in url for ext in ['.m3u8', '.mp4', '.ts', '.flv', '.mkv', '.avi'])
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def init(self, extend=""):
        self.session.verify = False
        if extend and isinstance(extend, str) and extend.startswith('http'):
            self.host = extend.rstrip('/')
            self.headers['Referer'] = self.host + '/'

    def _fetch(self, url, headers=None):
        try:
            h = headers if headers is not None else self.headers
            r = self.session.get(url, headers=h, timeout=20, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def _abs_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return self.host + '/' + url

    def _clean_text(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[\ue000-\uf8ff]', '', text)
        text = re.sub(r'&#[xX][0-9a-fA-F]+;?', '', text)
        text = text.replace('&nbsp;', ' ')
        text = ' '.join(text.split())
        return text.strip()

    def _clean_title(self, title):
        if not title:
            return ''
        title = title.strip()
        title = re.sub(r'^[A-Za-z0-9]+[\s\-][0-9]+[_\-][0-9]+\s*', '', title).strip()
        return title

    def homeContent(self, filter):
        classes = [
            {'type_id': '28', 'type_name': '中文字幕'},
            {'type_id': '21', 'type_name': '日本有码'},
            {'type_id': '22', 'type_name': '日本无码'},
            {'type_id': '105', 'type_name': '国产传媒'},
            {'type_id': '120', 'type_name': '麻豆合集'},
            {'type_id': '116', 'type_name': 'VR'},
            {'type_id': '23', 'type_name': '欧美无码'},
            {'type_id': '626', 'type_name': '门事件'},
            {'type_id': '625', 'type_name': '网红主播'},
            {'type_id': '624', 'type_name': '抖阴短片'},
            {'type_id': '623', 'type_name': '网曝吃瓜'},
            {'type_id': '622', 'type_name': '探花约炮'},
            {'type_id': '621', 'type_name': '国产传媒2'},
            {'type_id': '620', 'type_name': 'AV解说'},
            {'type_id': '617', 'type_name': '国产'},
            {'type_id': '400', 'type_name': '女优'},
            {'type_id': '300', 'type_name': '日本番號'},
            {'type_id': '200', 'type_name': '片源集散地'},
            {'type_id': '121', 'type_name': '葫芦影业'},
            {'type_id': '123', 'type_name': '天美传媒'},
            {'type_id': '124', 'type_name': '果冻传媒'},
            {'type_id': '125', 'type_name': '91制片厂'},
            {'type_id': '126', 'type_name': '蜜桃传媒'},
            {'type_id': '127', 'type_name': '精东影业'},
            {'type_id': '129', 'type_name': 'SWAG'},
            {'type_id': '101', 'type_name': '有码精品'},
            {'type_id': '111', 'type_name': 'AV新人'},
            {'type_id': '55', 'type_name': '教师'},
            {'type_id': '109', 'type_name': '制服诱惑'},
            {'type_id': '107', 'type_name': '熟女人妻'},
            {'type_id': '113', 'type_name': '激情口交'},
            {'type_id': '402', 'type_name': '波多野结衣'},
            {'type_id': '403', 'type_name': '三上悠亚'},
            {'type_id': '404', 'type_name': '河北彩花'},
            {'type_id': '401', 'type_name': '夢乃愛華'},
            {'type_id': '405', 'type_name': '高桥圣子'},
            {'type_id': '406', 'type_name': '葵司'},
            {'type_id': '418', 'type_name': '松本一香'},
            {'type_id': '441', 'type_name': '川上奈奈美'},
            {'type_id': '301', 'type_name': '200GANA'},
            {'type_id': '305', 'type_name': '259LUXU'},
            {'type_id': '306', 'type_name': '261ARA'},
            {'type_id': '302', 'type_name': '300MIUM'},
            {'type_id': '308', 'type_name': '300MAAN'},
            {'type_id': '311', 'type_name': '328HMDN'},
            {'type_id': '329', 'type_name': 'AARM'},
            {'type_id': '320', 'type_name': 'IPX'},
        ]
        return {'class': classes, 'filters': {}, 'type': '影视'}

    def homeVideoContent(self):
        text = self._fetch(self.host + '/')
        items = self._parse_list(text).get('list', [])
        return {
            'list': items[:30],
            'page': 1,
            'pagecount': 2 if items else 1,
            'limit': len(items),
            'total': len(items)
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1:
            url = f'{self.host}/t/{tid}/'
        else:
            url = f'{self.host}/t/{tid}-{page}/'
        text = self._fetch(url)
        result = self._parse_list(text)
        result['page'] = page
        result['pagecount'] = page + 1 if result.get('list') else page
        return result

    def _parse_list(self, text):
        items = []
        if not text:
            return {'list': items, 'limit': 0, 'total': 0}

        seen_vids = set()
        blocks = re.findall(
            r'<li[^>]*class="[^"]*vodlist_item[^"]*"[^>]*>(.*?)</li>',
            text, re.S
        )
        for block in blocks:
            m_link = re.search(r'<a[^>]+href="/d/(\d+)/"', block)
            if not m_link:
                continue
            vid = m_link.group(1)
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            title = ''
            m_title = re.search(r'<a[^>]+href="/d/\d+/"[^>]*title="([^"]+)"', block)
            if m_title:
                title = m_title.group(1).strip()
            if not title:
                m_title = re.search(r'<p[^>]*class="[^"]*vodlist_title[^"]*"[^>]*>.*?<a[^>]*title="([^"]+)"', block, re.S)
                if m_title:
                    title = m_title.group(1).strip()
            if not title:
                m_title = re.search(r'alt="([^"]+)"', block)
                if m_title:
                    title = m_title.group(1).strip()

            pic = ''
            m_pic = re.search(r'<a[^>]+class="[^"]*vodlist_thumb[^"]*"[^>]*(?:data-original|src)="([^"]+)"', block, re.S)
            if m_pic:
                pic = self._abs_url(m_pic.group(1))
            if not pic:
                m_pic = re.search(r'<img[^>]*(?:data-original|src)="([^"]+)"', block, re.S)
                if m_pic:
                    pic = self._abs_url(m_pic.group(1))

            note = ''
            m_note = re.search(r'<span[^>]*class="[^"]*pic_text[^"]*"[^>]*>(.*?)</span>', block, re.S)
            if m_note:
                note = self._clean_text(m_note.group(1))

            items.append({
                'vod_id': vid,
                'vod_name': self._clean_title(title),
                'vod_pic': pic,
                'vod_remarks': note,
            })

        if not items:
            pattern = re.compile(
                r'<a[^>]+class="[^"]*vodlist_thumb[^"]*"[^>]*href="/d/(\d+)/"[^>]*(?:data-original|src)="([^"]+)"(?:[^>]*title="([^"]+)")?',
                re.S
            )
            seen = set()
            for m in pattern.finditer(text):
                vid, pic, title = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                items.append({
                    'vod_id': vid,
                    'vod_name': self._clean_title((title or '').strip()),
                    'vod_pic': self._abs_url(pic),
                    'vod_remarks': '',
                })

        return {'list': items, 'limit': len(items), 'total': len(items)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        url = f'{self.host}/d/{vid}/'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', text, re.S)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(
                r'<div[^>]*class="[^"]*content_detail[^"]*content_top[^"]*"[^>]*>.*?<h2[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h2>',
                text, re.S
            )
            if m:
                title = self._clean_text(m.group(1))
        if not title:
            m = re.search(r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h2>', text, re.S)
            if m:
                title = self._clean_text(m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).split('-')[0].strip()

        title = self._clean_title(title)

        cover = ''
        m = re.search(
            r'<div[^>]*class="[^"]*content_thumb[^"]*"[^>]*>.*?<a[^>]+class="[^"]*vodlist_thumb[^"]*"[^>]*(?:data-original|src)="([^"]+)"',
            text, re.S
        )
        if m:
            cover = self._abs_url(m.group(1))
        if not cover:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', text, re.S)
            if m:
                cover = self._abs_url(m.group(1))

        year = ''
        m = re.search(r'<a[^>]+href="/s/-------------\d{4}/"[^>]*>(\d{4})</a>', text)
        if m:
            year = m.group(1)

        type_name = ''
        m = re.search(r'<a[^>]+href="/s/----([^"]+)---------/"[^>]*>([^<]+)</a>', text)
        if m:
            type_name = m.group(2).strip()

        actor = ''
        m = re.search(r'<li[^>]*class="[^"]*data[^"]*"[^>]*><span>主演：</span>(.*?)</li>', text, re.S)
        if m:
            actor = self._clean_text(m.group(1))

        director = ''
        m = re.search(r'<li[^>]*class="[^"]*data[^"]*"[^>]*><span>导演：</span>(.*?)</li>', text, re.S)
        if m:
            director = self._clean_text(m.group(1))

        content = ''
        m = re.search(
            r'<li[^>]*class="[^"]*desc[^"]*"[^>]*>.*?<span[^>]*>简介：</span>(.*?)(?:<a[^>]*href="#desc"[^>]*>.*?</a>)?\s*</li>',
            text, re.S
        )
        if m:
            content = self._clean_text(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]+name=(?:"|\x27)description(?:"|\x27)[^>]+content=(?:"|\x27)([^\x27"]*)', text, re.S | re.I)
            if m:
                content = self._clean_text(m.group(1))
        if content:
            content = html_module.unescape(content)
            content = ' '.join(content.split())
            ad_keywords = [
                '免费观看', '在线播放', '国产精品', '人妻无码', '91吃瓜', '黑料爆料',
                '在线观看', '中文字幕', '日韩无码', '国产综合', '自拍', '一区', '二区', '三区',
                '为您提供', '本站只适合18岁', '剧情:', '剧情：', '迅雷下载',
                '详情介绍', '在线收看', 'Powered by', 'Copyright', 'UU网曝门'
            ]
            cut_pos = len(content)
            for kw in ad_keywords:
                idx = content.lower().find(kw.lower())
                if idx != -1 and idx < cut_pos and idx > 3:
                    cut_pos = idx
            if cut_pos < len(content):
                content = content[:cut_pos].strip()
            if len(content) < 5 or content == title:
                content = ''
        if not content:
            content = self._generate_desc(title)

        sources = []
        m = re.search(r'<div[^>]*class="[^"]*play_source_tab[^"]*"[^>]*>(.*?)</div>', text, re.S)
        if m:
            tab = m.group(1)
            for mm in re.finditer(r'<a[^>]*alt="([^"]+)"[^>]*>(.*?)</a>', tab, re.S):
                alt = self._clean_text(mm.group(1).strip())
                name = self._clean_text(mm.group(2))
                sources.append(name or alt)
        if not sources:
            sources = ['jkm3u8']

        eps_by_source = []
        playlists = re.findall(r'<ul[^>]*class="[^"]*content_playlist[^"]*"[^>]*>(.*?)</ul>', text, re.S)
        for pl in playlists:
            eps = []
            seen_eps = set()
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', pl, re.S):
                href = m.group(1).strip()
                name = self._clean_text(m.group(2))
                if not name:
                    name = '高清'
                if href in seen_eps:
                    continue
                seen_eps.add(href)
                if href.startswith('/d/'):
                    m_vid = re.search(r'/d/(\d+)', href)
                    if m_vid:
                        href = f'/v/{m_vid.group(1)}-1-1/'
                eps.append(f'{name}${href}')
            if eps:
                eps_by_source.append('#'.join(eps))

        if not eps_by_source:
            m = re.search(r'<a[^>]+href="(/v/\d+-\d+-\d+/)"[^>]*>.*?(?:立即播放|在线播放)', text, re.S)
            if m:
                eps_by_source.append(f'高清${m.group(1)}')
            else:
                eps_by_source.append(f'高清$/v/{vid}-1-1/')

        while len(eps_by_source) < len(sources):
            eps_by_source.append(eps_by_source[-1] if eps_by_source else f'高清$/v/{vid}-1-1/')
        while len(sources) < len(eps_by_source):
            sources.append(f'线路{len(sources)+1}')

        play_from_list = sources[:len(eps_by_source)]
        play_url_list = eps_by_source[:len(sources)]

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_year': year,
            'vod_type': type_name,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content,
            'vod_remarks': '',
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def _generate_desc(self, title):
        if not title:
            return '暂无简介'
        templates = [
            '《{title}》高清完整版在线观看，画质清晰，播放流畅。',
            '热门资源推荐：《{title}》，精彩内容不容错过。',
            '本期带来《{title}》，真实场景，高清呈现。',
            '《{title}》已收录，欢迎在线观看。',
        ]
        return random.choice(templates).format(title=title)

    def _decode_mac_url(self, encoded, encrypt):
        if not encoded:
            return ''
        try:
            encrypt = int(encrypt)
        except (ValueError, TypeError):
            encrypt = 0
        if '%' in encoded:
            try:
                encoded = unquote(encoded)
            except Exception:
                pass
        if encrypt == 0:
            return encoded
        if encrypt == 1:
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                return encoded
        if encrypt == 2:
            try:
                return base64.b64decode(encoded[::-1]).decode('utf-8')
            except Exception:
                pass
            try:
                return base64.b64decode(encoded).decode('utf-8')[::-1]
            except Exception:
                pass
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                pass
            return encoded
        for method in [
            lambda e: base64.b64decode(e).decode('utf-8'),
            lambda e: base64.b64decode(e[::-1]).decode('utf-8'),
        ]:
            try:
                decoded = method(encoded)
                if decoded.startswith('http'):
                    return decoded
            except Exception:
                pass
        return encoded

    def _extract_player_config(self, text):
        cfg = {}
        m = re.search(r'MacPlayerConfig\.player_list\s*=\s*({.*?})', text, re.S)
        if m:
            try:
                cfg = json.loads(m.group(1))
            except Exception:
                pass
        return cfg

    def _is_likely_media(self, url):
        if not url:
            return False
        if self.isVideoFormat(url):
            return True
        url_lower = url.lower()
        media_patterns = ['/hls/', '/m3u8', '/mp4', '/video/', '/play/', '/stream/', '.m3u8?', '.mp4?', '/vod/', '/api/']
        return any(p in url_lower for p in media_patterns)

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('http'):
            return {
                'parse': 0,
                'url': id,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        if not id.startswith('/'):
            id = '/' + id
        url = self.host + id

        vid_match = re.search(r'/v/(\d+)', id)
        play_referer = f'{self.host}/d/{vid_match.group(1)}/' if vid_match else self.host + '/'
        play_headers = dict(self.headers)
        play_headers['Referer'] = play_referer

        text = self._fetch(url, headers=play_headers)
        if not text:
            return {
                'parse': 1,
                'url': url,
                'header': {'Referer': play_referer, 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        m3u8 = ''
        player_obj = None

        # ① player_aaaa / player / mac_player / player_data
        for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data']:
            m = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})', text, re.S)
            if m:
                try:
                    player_obj = json.loads(m.group(1))
                    break
                except Exception:
                    continue

        player_config = self._extract_player_config(text)

        if player_obj:
            raw_url = player_obj.get('url', '')
            encrypt = player_obj.get('encrypt', 0)
            from_src = player_obj.get('from', '')

            need_webview = False
            if from_src and from_src in player_config:
                ps = str(player_config[from_src].get('ps', '0'))
                if ps not in ('0', '', 'no'):
                    need_webview = True

            if not need_webview:
                if raw_url and isinstance(raw_url, str):
                    decoded = self._decode_mac_url(raw_url, encrypt)
                    decoded = self._abs_url(decoded)
                    if decoded and decoded.startswith('http'):
                        if self.isVideoFormat(decoded) or self._is_likely_media(decoded):
                            m3u8 = decoded

            if need_webview or (not m3u8 and from_src):
                return {
                    'parse': 1,
                    'url': url,
                    'header': {'Referer': play_referer, 'User-Agent': self.headers['User-Agent']},
                    'position': '0'
                }

        # ② var now
        if not m3u8:
            m = re.search(r"var\s+now\s*=\s*['\"]([^'\"]+)['\"]", text)
            if m:
                decoded = self._abs_url(m.group(1))
                if decoded.startswith('http') and self.isVideoFormat(decoded):
                    m3u8 = decoded

        # ②-1 var main / var url / var src / var video
        if not m3u8:
            for var_name in ['main', 'url', 'src', 'video']:
                m = re.search(rf"var\s+{var_name}\s*=\s*['\"]([^'\"]+)['\"]", text)
                if m:
                    decoded = self._abs_url(m.group(1))
                    if decoded.startswith('http') and self.isVideoFormat(decoded):
                        m3u8 = decoded
                        break

        # ③ <video src> / <source src>
        if not m3u8:
            m = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', text, re.S)
            if m:
                decoded = self._abs_url(m.group(1))
                if decoded.startswith('http') and self.isVideoFormat(decoded):
                    m3u8 = decoded

        # ④ iframe
        if not m3u8:
            m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text, re.S)
            if m:
                iframe_src = self._abs_url(m.group(1))
                if self.isVideoFormat(iframe_src):
                    m3u8 = iframe_src
                else:
                    iframe_text = self._fetch(iframe_src, headers=play_headers)
                    if iframe_text:
                        for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data']:
                            mm = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})', iframe_text, re.S)
                            if mm:
                                try:
                                    player = json.loads(mm.group(1))
                                    raw_url = player.get('url', '')
                                    encrypt = player.get('encrypt', 0)
                                    if raw_url and isinstance(raw_url, str):
                                        decoded = self._decode_mac_url(raw_url, encrypt)
                                        decoded = self._abs_url(decoded)
                                        if decoded.startswith('http') and self.isVideoFormat(decoded):
                                            m3u8 = decoded
                                            break
                                except Exception:
                                    continue
                        if not m3u8:
                            for var_name in ['now', 'main', 'url', 'src']:
                                mm = re.search(rf"var\s+{var_name}\s*=\s*['\"]([^'\"]+)['\"]", iframe_text)
                                if mm:
                                    decoded = self._abs_url(mm.group(1))
                                    if decoded.startswith('http') and self.isVideoFormat(decoded):
                                        m3u8 = decoded
                                        break
                        if not m3u8:
                            mm = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', iframe_text, re.S)
                            if mm:
                                decoded = self._abs_url(mm.group(1))
                                if decoded.startswith('http') and self.isVideoFormat(decoded):
                                    m3u8 = decoded
                        if not m3u8:
                            mm = re.search(r"['\"](https?://[^\s'\"<>]+?\.(?:m3u8|mp4|ts|flv))['\"]", iframe_text)
                            if mm:
                                m3u8 = mm.group(1)

                    if not m3u8 and iframe_src.startswith('http'):
                        return {
                            'parse': 1,
                            'url': iframe_src,
                            'header': {'Referer': url, 'User-Agent': self.headers['User-Agent']},
                            'position': '0'
                        }

        # ⑤ 页面直链
        if not m3u8:
            m = re.search(r"['\"](https?://[^\s'\"<>]+?\.(?:m3u8|mp4|ts|flv))['\"]", text)
            if m:
                m3u8 = m.group(1)

        # ⑥ unescape
        if not m3u8:
            m = re.search(r"unescape\(['\"]([^'\"]+)['\"]\)", text)
            if m:
                try:
                    decoded = unquote(m.group(1))
                    decoded = self._abs_url(decoded)
                    if decoded.startswith('http') and self.isVideoFormat(decoded):
                        m3u8 = decoded
                except Exception:
                    pass

        # 返回直链
        if m3u8 and m3u8 != url and self.isVideoFormat(m3u8):
            m3u8 = self._sanitize_m3u8_url(m3u8)
            proxy_url = self._proxy_m3u8_url(m3u8, url)
            return {
                'parse': 0,
                'playUrl': '',
                'url': proxy_url,
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': url, 'Origin': self.host},
                'position': '0'
            }

        # 兜底：WebView 嗅探
        return {
            'parse': 1,
            'url': url,
            'header': {'Referer': play_referer, 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }

    def _sanitize_m3u8_url(self, url):
        if not url:
            return url
        url = unquote(url)
        url = re.sub(r'&[Cc]over=.*', '', url)
        url = re.sub(r'&[Pp]oster=.*', '', url)
        url = re.sub(r'&[Tt]humb=.*', '', url)
        url = re.sub(r'&[Pp]ic=.*', '', url)
        url = url.rstrip('&?')
        return url

    def _proxy_m3u8_url(self, url, referer=''):
        try:
            if hasattr(self, 'getProxyUrl'):
                return self.getProxyUrl() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except Exception:
            pass
        return url

    def _get_m3u8_content(self, url, referer):
        try:
            headers = {
                'User-Agent': self.headers.get('User-Agent', ''),
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': self.host,
                'Connection': 'keep-alive',
            }
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

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
            m = re.search(r'(\/\d{8}\/[^/]+\/\d+kb\/hls\/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(\/\d{8}\/[^/]+\/)', p)
            if m:
                return m.group(1).lower()
        except:
            pass
        return ''

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        text = (m3u8_text or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in text:
            out = []
            last_stream = False
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                    last_stream = line.startswith('#EXT-X-STREAM-INF')
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if last_stream or '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer or self.host))
                    else:
                        out.append(abs_url)
                    last_stream = False
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
        return '\n'.join(new_lines) + '\n'

    def localProxy(self, param):
        try:
            if not isinstance(param, dict):
                param = {}
            do = param.get('type') or param.get('action') or param.get('do')
            url = param.get('url', '')
            if do not in ['m3u8', 'py'] and not url:
                return [404, "text/plain", "not found"]
            referer = param.get('referer', '') or self.host
            if isinstance(url, list):
                url = url[0] if url else ''
            if isinstance(referer, list):
                referer = referer[0] if referer else self.host
            url = unquote(url) if url else ''
            referer = unquote(referer) if referer else self.host
            if not url:
                return [404, "text/plain", "url is empty"]
            text = self._get_m3u8_content(url, referer)
            if not text:
                return [500, "text/plain", f"media download failed\nurl: {url}\nreferer: {referer}"]
            cleaned = self._clean_m3u8(text, url, referer)
            if not cleaned:
                return [500, "text/plain", "m3u8 clean returned empty"]
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            return [500, "text/plain", f"proxy error: {e}"]

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f'{self.host}/s/-------------.html?wd={quote(key)}'
        if page > 1:
            url += f'&page={page}'
        text = self._fetch(url)
        items = self._parse_list(text).get('list', [])
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

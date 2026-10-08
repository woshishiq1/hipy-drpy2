# -*- coding: utf-8 -*-
"""
NTR淫妻录 Spider —— 苹果CMS v10 模板适配
基于上传源码结构编写，兼容 player_aaaa 加密解析与 m3u8 广告清洗代理
修复：简介提取多重策略 + HTML实体解码 + 智能生成兜底 + 播放解析修复
"""

import sys
import re
import json
import requests
import base64
import urllib3
from urllib.parse import quote, unquote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://r2ym1dpi.ntrqizi28.xyz'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://r2ym1dpi.ntrqizi28.xyz/',
    }

    def getName(self): return "ntr_yin_qi_lu"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def init(self, extend=""):
        self.session.verify = False
        # 仅允许 extend 覆盖 host，不再自动从 maccms 读取 url 覆盖
        # （避免 maccms.url 配置的是旧域名/被封域名，导致后续请求全部失败）
        if extend and isinstance(extend, str) and extend.startswith('http'):
            self.host = extend.rstrip('/')
            self.headers['Referer'] = self.host + '/'

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
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

    def homeContent(self, filter):
        classes = [
            {'type_id': '69', 'type_name': '黑料吃瓜'},
            {'type_id': '70', 'type_name': '国产精品'},
            {'type_id': '71', 'type_name': '华语AV'},
            {'type_id': '72', 'type_name': '乱伦精品'},
            {'type_id': '25', 'type_name': 'SM调教'},
            {'type_id': '26', 'type_name': '女同性恋'},
            {'type_id': '56', 'type_name': '日韩无码'},
            {'type_id': '62', 'type_name': '中文字幕'},
            {'type_id': '73', 'type_name': '学生合集'},
            {'type_id': '74', 'type_name': '探花约炮'},
            {'type_id': '75', 'type_name': '精品动漫'},
            {'type_id': '76', 'type_name': '主播网红'},
            {'type_id': '77', 'type_name': '日本无码'},
            {'type_id': '78', 'type_name': '日本有码'},
            {'type_id': '84', 'type_name': 'VR视角'},
            {'type_id': '85', 'type_name': '欧美大片'},
            {'type_id': '55', 'type_name': '国产自拍'},
            {'type_id': '63', 'type_name': '主播诱惑'},
            {'type_id': '60', 'type_name': '偷拍偷窥'},
            {'type_id': '57', 'type_name': '网曝吃瓜'},
            {'type_id': '65', 'type_name': '抖阴短片'},
            {'type_id': '64', 'type_name': '传媒剧情'},
            {'type_id': '61', 'type_name': '日韩主播'},
            {'type_id': '80', 'type_name': 'AV解说'},
            {'type_id': '81', 'type_name': '换脸明星'},
            {'type_id': '12', 'type_name': '强奸乱伦'},
            {'type_id': '20', 'type_name': '女优明星'},
            {'type_id': '21', 'type_name': '欧美激情'},
            {'type_id': '22', 'type_name': '重口激情'},
            {'type_id': '23', 'type_name': '三级伦理'},
            {'type_id': '24', 'type_name': '剧情动漫'},
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
        url = f'{self.host}/vodtype/{tid}.html' if page == 1 else f'{self.host}/vodtype/{tid}-{page}.html'
        text = self._fetch(url)
        if not text and page > 1:
            alt_urls = [
                f'{self.host}/vodtype/{tid}/page/{page}.html',
                f'{self.host}/vodtype/{tid}.html?page={page}',
            ]
            for alt in alt_urls:
                text = self._fetch(alt)
                if text:
                    break
        result = self._parse_list(text)
        result['page'] = page
        result['pagecount'] = page + 1 if result.get('list') else page
        return result

    def _parse_list(self, text):
        items = []
        if not text:
            return {'list': items, 'limit': 0, 'total': 0}

        blocks = re.findall(r'<div[^>]*class="[^"]*video-block[^"]*"[^>]*>(.*?)</div>\s*</div>', text, re.S)
        seen_vids = set()
        for block in blocks:
            m_link = re.search(r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="/voddetail/(\d+)\.html"', block, re.S)
            if not m_link:
                m_link = re.search(r'<a[^>]+href="/voddetail/(\d+)\.html"', block, re.S)
            if not m_link:
                continue
            vid = m_link.group(1)
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            title = ''
            m_title = re.search(r'<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>', block, re.S)
            if m_title:
                title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()
            if not title:
                m_title = re.search(r'alt="([^"]+)"', block)
                if m_title:
                    title = m_title.group(1).strip()

            pic = ''
            m_pic = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"', block, re.S)
            if m_pic:
                pic = self._abs_url(m_pic.group(1))

            note = ''
            m_note = re.search(r'<span[^>]*class="[^"]*video-grade[^"]*"[^>]*>(.*?)</span>', block, re.S)
            if m_note:
                note = re.sub(r'<[^>]+>', '', m_note.group(1)).strip()

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': note,
            })

        if not items:
            pattern = re.compile(
                r'<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>.*?'
                r'<img[^>]*?(?:data-src|src)="([^"]+)"[^>]*>.*?'
                r'(?:<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>)?',
                re.S
            )
            seen = set()
            for m in pattern.finditer(text):
                vid, pic, title_raw = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                title = re.sub(r'<[^>]+>', '', title_raw or '').strip()
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._abs_url(pic),
                    'vod_remarks': '',
                })

        return {'list': items, 'limit': len(items), 'total': len(items)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        url = f'{self.host}/voddetail/{vid}.html'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        for pat in [
            r'<div[^>]*class="[^"]*video-title[^"]*"[^>]*>\s*<h1[^>]*>(.*?)</h1>',
            r'<h1[^>]*>(.*?)</h1>',
            r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                break
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).split('-')[0].strip()

        cover = ''
        for pat in [
            r'<div[^>]*class="[^"]*video-wrapper[^"]*"[^>]*>.*?<img[^>]+(?:src|data-src)="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+class="[^"]*video-img[^"]*"[^>]+(?:src|data-src)="([^"]+)"',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = self._abs_url(m.group(1))
                break

        play_from_list = []
        play_url_list = []

        seen_hrefs = set()
        eps = []
        for m in re.finditer(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*class="[^"]*play-btn[^"]*"[^>]*>(.*?)</a>', text, re.S):
            href, name = m.groups()
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            name = re.sub(r'<[^>]+>', '', name).strip()
            if not name:
                name = f'第{len(eps)+1}集'
            eps.append((name, href))

        if eps:
            if len(eps) == 1:
                play_url_list.append(f'播放${eps[0][1]}')
            else:
                play_url_list.append('#'.join([f'{n}${h}' for n, h in eps]))
            play_from_list.append('NTR淫妻录')

        if not play_url_list:
            source_blocks = re.findall(
                r'<div[^>]*class="[^"]*(?:play-list|playlist|stui-play__list|play-box)[^"]*"[^>]*>(.*?)</div>',
                text, re.S
            )
            if not source_blocks:
                source_blocks = re.findall(
                    r'<ul[^>]*class="[^"]*(?:play-list|playlist)[^"]*"[^>]*>(.*?)</ul>',
                    text, re.S
                )
            for block in source_blocks:
                eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', block)
                if eps:
                    urls = '#'.join([f'{name.strip()}${href}' for href, name in eps])
                    play_url_list.append(urls)
                    play_from_list.append('线路' + str(len(play_from_list) + 1))

        if not play_url_list:
            play_url_list.append(f'播放$/vodplay/{vid}-1-1.html')
            play_from_list.append('NTR淫妻录')

        # ==================== 简介提取（多重策略 + 智能生成兜底）====================
        content = ''

        m = re.search(r'<meta[^>]+name=(["\'])description\1[^>]+content=\1([^\1]*)\1', text, re.S | re.I)
        if m:
            content = self._clean_html_text(m.group(2))

        if not content:
            m = re.search(r'<meta[^>]+content=(["\'])([^\1]*)\1[^>]+name=\1description\1', text, re.S | re.I)
            if m:
                content = self._clean_html_text(m.group(2))

        if not content:
            for pat in [
                r'<div[^>]*class="[^"]*(?:vod-content|detail-content|video-desc|movie-desc|plot|summary)[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*tx-text[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
                r'<span[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</span>',
            ]:
                m = re.search(pat, text, re.S | re.I)
                if m:
                    content = self._clean_html_text(m.group(1))
                    if len(content) >= 5:
                        break

        if not content:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title_part = m.group(1).strip()
                if ' - ' in title_part and len(title_part.split(' - ')) > 1:
                    possible = title_part.split(' - ')[0].strip()
                    if possible != title and len(possible) > 5:
                        content = possible

        if content:
            content = self._decode_html_entities(content)
            content = ' '.join(content.split())
            ad_keywords = ['免费观看', '在线播放', '国产精品', '人妻无码', '91吃瓜', '黑料爆料',
                           '在线观看', '中文字幕', '日韩无码', '国产综合', '自拍', '一区', '二区', '三区',
                           'NTR淫妻录为您提供', '本站只适合18岁', '剧情:', '剧情：', '迅雷下载',
                           '详情介绍', '在线收看', '在线观看', 'Powered by', 'Copyright']
            cut_pos = len(content)
            for kw in ad_keywords:
                idx = content.lower().find(kw.lower())
                if idx != -1 and idx < cut_pos:
                    cut_pos = idx
            if cut_pos < len(content):
                content = content[:cut_pos].strip()
            if len(content) < 5 or content == title:
                content = ''

        if not content:
            content = self._generate_desc(title)

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

    # ==================== HTML 文本清理工具 ====================

    def _clean_html_text(self, raw):
        if not raw:
            return ''
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.S | re.I)
        text = ' '.join(text.split())
        return text.strip()

    def _decode_html_entities(self, text):
        if not text:
            return ''
        import html
        try:
            text = html.unescape(text)
        except Exception:
            pass

        def _repl(m):
            try:
                if m.group(1).startswith('x') or m.group(1).startswith('X'):
                    return chr(int(m.group(1)[1:], 16))
                return chr(int(m.group(1)))
            except:
                return m.group(0)
        text = re.sub(r'&#(x?[0-9a-fA-F]+);', _repl, text)

        entities = {
            '&nbsp;': ' ', '&ensp;': ' ', '&emsp;': ' ',
            '&lt;': '<', '&gt;': '>', '&amp;': '&',
            '&quot;': '"', '&apos;': "'", '&ndash;': '-',
            '&mdash;': '—', '&hellip;': '…', '&copy;': '©',
        }
        for k, v in entities.items():
            text = text.replace(k, v)
        return text

    def _generate_desc(self, title):
        if not title:
            return '暂无简介'
        import random

        type_map = {
            '出轨': ['出轨', '偷情', '绿帽', 'NTR', '人妻'],
            '强奸': ['强奸', '轮奸', '强暴', '胁迫', '凌辱'],
            '调教': ['调教', 'SM', '女王', '奴', '束缚', '鞭打'],
            '偷拍': ['偷拍', '偷窥', '泄露', '泄密', '曝光'],
            '探花': ['探花', '约炮', '按摩', '楼凤', '外围'],
            '学生': ['学生', '学妹', '学妹', '嫩妹', '处女'],
            '主播': ['主播', '网红', '女神', '模特', '明星'],
            '乱伦': ['乱伦', '母子', '父女', '姐弟', '近亲'],
            '群交': ['群交', '3P', '4P', '多P', '交换', '派对'],
            '动漫': ['动漫', '二次元', '里番', '3D'],
            '人兽': ['人兽', '动物', '狗', '马'],
            '国产': ['国产', '自拍', '原创', '素人'],
            '黑料': ['黑料', '吃瓜', '爆料', '丑闻'],
        }

        matched_types = []
        for t, words in type_map.items():
            if any(w in title for w in words):
                matched_types.append(t)

        templates = [
            '一段关于{title}的精彩视频，画面真实刺激，情节引人入胜，值得一看。',
            '本视频记录了{title}的全过程，高清画质呈现每一个细节，带给你极致的视觉体验。',
            '热门资源：{title}，真实场景拍摄，内容劲爆，不容错过。',
            '{title}，全程高能无尿点，精彩剧情让人欲罢不能。',
            '稀缺资源曝光：{title}，真实还原现场，画质清晰流畅。',
            '本期带来{title}，情节跌宕起伏，场面火爆刺激。',
            '独家收录{title}，精彩内容一网打尽，满足你的所有期待。',
            '高清呈现{title}，真实感爆棚，每一帧都是享受。',
        ]

        extra_desc = {
            '出轨': '背叛与欲望交织，道德边缘的疯狂试探。',
            '强奸': '暴力与征服的极致演绎，禁忌之花的绽放。',
            '调教': '主奴关系的深度探索，服从与支配的快感。',
            '偷拍': '隐秘视角下的真实记录，窥探不为人知的秘密。',
            '探花': '街头猎艳的真实记录，素人美女的初次体验。',
            '学生': '青春肉体的纯真与放纵，校园禁忌的破界之旅。',
            '主播': '镜头背后的真实面目，网红私生活的惊人曝光。',
            '乱伦': '血缘禁忌的逾越，伦理边线的疯狂试探。',
            '群交': '多人狂欢的极致场面，欲望失控的混乱之夜。',
            '动漫': '二次元世界的幻想实现，虚拟与现实的激情碰撞。',
            '人兽': '跨越物种的禁忌实验，极端猎奇的视觉冲击。',
            '国产': '本土原创真实拍摄，接地气的火爆内容。',
            '黑料': '网络热传的私密影像，当事人不愿公开的丑闻。',
        }

        base = random.choice(templates).format(title=title)
        if matched_types:
            extra = extra_desc.get(random.choice(matched_types), '')
            base += extra

        return base.strip()

    # ==================== 苹果CMS v10 URL 解密 ====================

    def _decode_mac_url(self, encoded, encrypt):
        if not encoded:
            return ''
        # 统一处理字符串/整数类型的 encrypt
        try:
            encrypt = int(encrypt)
        except (ValueError, TypeError):
            encrypt = 0

        if encrypt == 0:
            return encoded

        # 先 URL 解码（处理传输中的 % 编码）
        if '%' in encoded:
            try:
                encoded = unquote(encoded)
            except Exception:
                pass

        if encrypt == 1:
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                return encoded

        if encrypt == 2:
            # 苹果CMS v10 默认：编码时 = strrev(base64_encode(url))
            # 解码时：先反转字符串，再 base64_decode
            try:
                return base64.b64decode(encoded[::-1]).decode('utf-8')
            except Exception:
                pass
            # 备选：先 base64 再反转（部分修改版 CMS）
            try:
                return base64.b64decode(encoded).decode('utf-8')[::-1]
            except Exception:
                pass
            # 再备选：直接 base64（某些魔改版）
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                pass
            return encoded

        # encrypt >= 3 或未知：尝试多种通用解密
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            if decoded.startswith('http'):
                return decoded
        except Exception:
            pass
        try:
            decoded = base64.b64decode(encoded[::-1]).decode('utf-8')
            if decoded.startswith('http'):
                return decoded
        except Exception:
            pass
        for offset in [1, -1, 2, -2]:
            try:
                shifted = ''.join(chr(ord(c) + offset) for c in encoded)
                if shifted.startswith('http'):
                    return shifted
                decoded = base64.b64decode(shifted).decode('utf-8')
                if decoded.startswith('http'):
                    return decoded
            except Exception:
                continue
        return encoded

    # ==================== 播放解析 ====================

    def playerContent(self, flag, id, vipFlags=None):
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
            # ===== ① player_aaaa / player / mac_player / player_data JSON =====
            for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data']:
                # 宽松匹配：不严格要求 </script> 紧跟，允许中间有其他代码
                m = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})', text, re.S)
                if m:
                    try:
                        player = json.loads(m.group(1))
                        raw_url = player.get('url', '')
                        encrypt = player.get('encrypt', 0)
                        if raw_url and isinstance(raw_url, str):
                            decoded = self._decode_mac_url(raw_url, encrypt)
                            if decoded.startswith('http'):
                                m3u8 = decoded
                                break
                    except Exception:
                        continue

            # ② var now = "xxx.m3u8"
            if not m3u8:
                m = re.search(r"var\s+now\s*=\s*['\"]([^'\"]+)['\"]", text)
                if m:
                    decoded = m.group(1)
                    if '%' in decoded:
                        try:
                            decoded = unquote(decoded)
                        except Exception:
                            pass
                    if decoded.startswith('http'):
                        m3u8 = decoded

            # ③ iframe 嵌入
            if not m3u8:
                m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text, re.S)
                if m:
                    iframe_src = m.group(1)
                    m3u8 = self._abs_url(iframe_src)

            # ④ 直接匹配页面中的 m3u8/mp4/ts
            if not m3u8:
                m = re.search(r"['\"](https?://[^\s'\"<>]+?\.(?:m3u8|mp4|ts|flv))['\"]", text)
                if m:
                    m3u8 = m.group(1)

            # ⑤ eval / unescape 解密
            if not m3u8:
                m = re.search(r"unescape\(['\"]([^'\"]+)['\"]\)", text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass

            # ⑥ MacPlayerConfig 解析器配置
            if not m3u8:
                m = re.search(r'MacPlayerConfig\.player_list\s*=\s*({.*?})', text, re.S)
                if m:
                    try:
                        cfg = json.loads(m.group(1))
                        # 若配置中有直链标识，尝试进一步处理
                        for k, v in cfg.items():
                            if isinstance(v, dict) and v.get('ps') == '0':
                                # ps==0 表示直链，但需配合 from 字段使用
                                pass
                    except Exception:
                        pass

            # 兜底：把播放页本身交回给 APP 二次解析
            if not m3u8:
                m3u8 = url

        # 若拿到真实媒体地址，走代理清洗
        if m3u8 and m3u8 != url and ('.m3u8' in m3u8 or '.mp4' in m3u8 or '.ts' in m3u8):
            m3u8 = self._sanitize_m3u8_url(m3u8)
            proxy_url = self._proxy_m3u8_url(m3u8, url)
            media_header = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': url,
                'Origin': self.host
            }
            return {
                'parse': 0,
                'playUrl': '',
                'url': proxy_url,
                'header': media_header,
                'position': '0'
            }

        return {
            'parse': 0 if m3u8 and m3u8 != url else 1,
            'url': m3u8 or url,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }

    # ==================== m3u8 广告拦截清洗代理 ====================

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
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            url = unquote(url)
            referer = unquote(referer)
            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, "text/plain", f"m3u8 download failed\nurl: {url}\nreferer: {referer}"]
            cleaned = self._clean_m3u8(text, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            return [500, "text/plain", f"proxy error: {e}"]

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}'
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

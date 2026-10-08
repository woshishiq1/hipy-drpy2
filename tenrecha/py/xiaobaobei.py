# -*- coding: utf-8 -*-
"""
小宝贝 Spider —— 基于苹果CMS模板
修复点：
1. _parse_list：取消 <li> class 的严格限制，改为先按 <li> 分块再内部匹配，避免跨标签污染
2. detailContent：增加对 /v/{id}/ 格式播放按钮的提取（适配当前站点详情页结构）
3. playerContent：保持六重解析链不变，确保拿到正确的播放页后能正常出地址
4. 新增 m3u8 广告拦截清洗代理功能（从千媚宫移植）
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
    host = 'https://lay-aim-mix.mixbbaotutum1.top'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://lay-aim-mix.mixbbaotutum1.top/baby/',
    }

    def getName(self): return "xiaobaobei"
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

    def _abs_url(self, url):
        """链接标准化：处理相对路径"""
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
            {'type_id': '280', 'type_name': '辣椒资源'},
            {'type_id': '250', 'type_name': '大地资源'},
            {'type_id': '249', 'type_name': '奥斯卡'},
            {'type_id': '248', 'type_name': 'jkun资源'},
            {'type_id': '247', 'type_name': '奶香香'},
            {'type_id': '246', 'type_name': '玉兔资源'},
            {'type_id': '245', 'type_name': '热搜资源'},
            {'type_id': '281', 'type_name': '中文'},
            {'type_id': '311', 'type_name': '女优'},
            {'type_id': '313', 'type_name': '动漫'},
            {'type_id': '316', 'type_name': '强奸'},
            {'type_id': '309', 'type_name': '欧美'},
        ]
        return {'class': classes, 'filters': self._build_filters(), 'type': '影视'}

    def _build_filters(self):
        filters = {}
        filters['280'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '欧美极品', 'v': '309'}, {'n': '日韩无码', 'v': '310'},
            {'n': 'AV明星', 'v': '311'}, {'n': '中文字幕', 'v': '312'}, {'n': '动漫精品', 'v': '313'},
            {'n': '极骚萝莉', 'v': '314'}, {'n': '重咸口味', 'v': '315'}, {'n': '强奸乱伦', 'v': '316'},
        ]}]
        filters['250'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '日韩无码', 'v': '293'}, {'n': '日韩精品', 'v': '294'},
            {'n': '欧美精品', 'v': '295'}, {'n': '人妻系列', 'v': '297'}, {'n': '制服诱惑', 'v': '298'},
            {'n': '强奸乱伦', 'v': '299'}, {'n': '动漫精品', 'v': '300'}, {'n': '教师学生', 'v': '308'},
        ]}]
        filters['249'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '日本有码', 'v': '282'}, {'n': '日本无码', 'v': '283'},
            {'n': '强奸乱伦', 'v': '285'}, {'n': '制服诱惑', 'v': '286'}, {'n': '女优明星', 'v': '288'},
            {'n': 'SM调教', 'v': '289'}, {'n': '萝莉少女', 'v': '291'}, {'n': 'VR有碼', 'v': '292'},
        ]}]
        filters['248'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '中文字幕', 'v': '274'}, {'n': '日本有码', 'v': '275'},
            {'n': '日本无码', 'v': '276'}, {'n': '黑丝诱惑', 'v': '277'}, {'n': '素人搭讪', 'v': '278'},
            {'n': 'AV解说', 'v': '279'},
        ]}]
        filters['247'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '日韩无码', 'v': '265'}, {'n': '中文字幕', 'v': '266'},
            {'n': '强奸乱伦', 'v': '267'}, {'n': 'SM调教', 'v': '268'}, {'n': '女优明星', 'v': '269'},
            {'n': '重口激情', 'v': '271'}, {'n': '水果派', 'v': '272'}, {'n': 'VR视角', 'v': '273'},
        ]}]
        filters['246'] = [{'key': 'sub', 'name': '子分类', 'value': [
            {'n': '全部', 'v': ''}, {'n': '日本片商', 'v': '256'}, {'n': '日本有码', 'v': '257'},
            {'n': '日本无码', 'v': '258'}, {'n': '中文字幕', 'v': '259'}, {'n': '童颜巨乳', 'v': '260'},
            {'n': '性感人妻', 'v': '261'}, {'n': '强奸乱伦', 'v': '262'}, {'n': '欧美情色', 'v': '263'},
        ]}]
        return filters

    def homeVideoContent(self):
        text = self._fetch(self.host + '/baby/')
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

        base = f'{self.host}/t/{tid}/'
        url = base if page == 1 else f'{base}?page={page}'
        text = self._fetch(url)

        if not text and page > 1:
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

        # 策略1：先按 <li> 分块，再在块内精确匹配（避免跨标签、避免class限制过死）
        li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', text, re.S)
        seen_vids = set()
        for li in li_blocks:
            m = re.search(
                r'<a[^>]+href="/voddetail/(\d+)/"[^>]*title="([^"]*)"[^>]*>.*?'
                r'<img[^>]*?(?:src|data-original)="([^"]*)"[^>]*>.*?'
                r'(?:<span[^>]*class="item-auxiliary"[^>]*>.*?<small>([^<]*)</small>.*?</span>)?',
                li, re.S
            )
            if m:
                vid, title, pic, note = m.groups()
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)
                items.append({
                    'vod_id': vid,
                    'vod_name': title.strip(),
                    'vod_pic': self._abs_url(pic),
                    'vod_remarks': note.strip() if note else '',
                })

        # 策略2：全局兜底（若按li分块完全没解析到，再用宽松正则扫一遍）
        if not items:
            pattern2 = re.compile(
                r'<a[^>]+href="/voddetail/(\d+)/"[^>]*title="([^"]*)"[^>]*>.*?'
                r'<img[^>]*?(?:src|data-original)="([^"]*)"[^>]*>',
                re.S
            )
            seen = set()
            for m in pattern2.finditer(text):
                vid, title, pic = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                remark = ''
                rmk = re.search(r'<small>([^<]+)</small>', text[m.end():m.end()+300], re.S)
                if rmk:
                    remark = rmk.group(1).strip()
                items.append({
                    'vod_id': vid,
                    'vod_name': title.strip(),
                    'vod_pic': self._abs_url(pic),
                    'vod_remarks': remark,
                })

        return {
            'list': items,
            'limit': len(items),
            'total': len(items)
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        url = f'{self.host}/voddetail/{vid}/'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        # 标题提取
        title = ''
        for pat in [r'<h1[^>]*>(.*?)</h1>', r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"']:
            m = re.search(pat, text, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                break
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).replace('- 小宝贝', '').strip()

        # 封面提取（增加对 detail-image-wrapper 的适配）
        cover = ''
        for pat in [
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<div[^>]*class="[^"]*vod-img[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*content-img',
            r'<div[^>]*class="[^"]*detail-image-wrapper[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = self._abs_url(m.group(1))
                break

        play_from_list = []
        play_url_list = []

        # 模式A：标准苹果CMS播放列表 /vodplay/...
        source_blocks = re.findall(
            r'<div[^>]*class="[^"]*(?:play-list|playlist|stui-play__list|play-box)[^"]*"[^>]*>(.*?)</div>',
            text, re.S
        )
        if not source_blocks:
            source_blocks = re.findall(
                r'<ul[^>]*class="[^"]*(?:play-list|playlist)[^"]*"[^>]*>(.*?)</ul>',
                text, re.S
            )

        if source_blocks:
            for block in source_blocks:
                eps = re.findall(
                    r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>',
                    block
                )
                if eps:
                    urls = '#'.join([f'{name.strip()}${href}' for href, name in eps])
                    play_url_list.append(urls)
                    play_from_list.append('线路' + str(len(play_from_list) + 1))

        # 模式B：适配当前站点 /v/{id}/ 格式的播放按钮（如 <a href="/v/972186/">播放影片</a>）
        if not play_url_list:
            # 先精确匹配包含"播放"字样的 /v/ 链接
            v_links = re.findall(
                r'<a[^>]+href="(/v/\d+/?)"[^>]*>(?:[^<]*播放[^<]*|[^<]*立即观看[^<]*|[^<]*在线播放[^<]*)</a>',
                text, re.S | re.I
            )
            # 若精确匹配失败，再兜底提取所有 /v/数字/ 的去重链接
            if not v_links:
                all_v = re.findall(r'<a[^>]+href="(/v/\d+/?)"', text)
                seen = set()
                v_links = [x for x in all_v if not (x in seen or seen.add(x))]
            if v_links:
                if len(v_links) == 1:
                    play_url_list.append(f'播放${v_links[0]}')
                else:
                    play_url_list.append(
                        '#'.join([f'第{i+1}集${href}' for i, href in enumerate(v_links)])
                    )
                play_from_list.append('小宝贝')

        # 模式C：兜底（兼容传统苹果CMS）
        if not play_url_list:
            play_url_list.append(f'播放$/vodplay/{vid}-1-1.html')
            play_from_list.append('小宝贝')

        # 简介提取（适配 tx-text mb20r 结构）
        content = ''
        m = re.search(r'<div[^>]*class="[^"]*tx-text[^"]*"[^>]*>(.*?)</div>', text, re.S)
        if m:
            ps = re.findall(r'<p>(.*?)</p>', m.group(1), re.S)
            if ps:
                content = '\n'.join(re.sub(r'<[^>]+>', '', p).strip() for p in ps)
            else:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 内容净化：规范化空白 + 广告关键词截断
        if content:
            content = ' '.join(content.split())
            ad_keywords = ['免费观看', '在线播放', '国产精品', '人妻无码', '91吃瓜', '黑料爆料', '在线观看', '中文字幕', '日韩无码', '国产综合', '自拍', '一区', '二区', '三区']
            cut_pos = len(content)
            for kw in ad_keywords:
                idx = content.find(kw)
                if idx != -1 and idx < cut_pos:
                    cut_pos = idx
            if cut_pos < len(content):
                content = content[:cut_pos].strip()
            if len(content) < 5:
                content = ''

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
            # ① player_aaaa / player / mac_player / player_data JSON
            for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data']:
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

            # ③ iframe嵌入
            if not m3u8:
                m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
                if m:
                    iframe_src = m.group(1)
                    m3u8 = self._abs_url(iframe_src)

            # ④ 直接匹配页面中的 m3u8/mp4/ts
            if not m3u8:
                m = re.search(r"['\"](https?://[^\s'\"<>]+?\.(?:m3u8|mp4|ts|flv))['\"]", text)
                if m:
                    m3u8 = m.group(1)

            # ⑤ eval/unescape 解密
            if not m3u8:
                m = re.search(r"unescape\(['\"]([^'\"]+)['\"]\)", text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass

            # ⑥ 兜底：把播放页本身交回给APP二次解析
            if not m3u8:
                m3u8 = url

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

    # ================== m3u8 广告拦截清洗代理（从千媚宫移植）==================

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
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
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
        url = f'{self.host}/s/?wd={quote(key)}'
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

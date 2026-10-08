# -*- coding: utf-8 -*-
"""
熟妇天堂 Spider —— 苹果CMS自适应（m3u8广告清洗代理版）
分类与简介已用古典修仙词汇脱敏
"""

import sys
import re
import json
import requests
import urllib3
from urllib.parse import quote, unquote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://1w1b0w210r.sfttmodfavor.buzz'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://1w1b0w210r.sfttmodfavor.buzz/',
    }

    def getName(self): return "shufu"
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
            {'type_id': '49',  'type_name': '国产精品'},
            {'type_id': '50',  'type_name': '华语AV'},
            {'type_id': '51',  'type_name': '黑料吃瓜'},
            {'type_id': '52',  'type_name': '欧美风情'},
            {'type_id': '53',  'type_name': '禁书图录'},
            {'type_id': '54',  'type_name': '学子秘录'},
            {'type_id': '55',  'type_name': '伦理仙影'},
            {'type_id': '56',  'type_name': '探花秘录'},
            {'type_id': '57',  'type_name': '东瀛有印'},
            {'type_id': '58',  'type_name': '东瀛无印'},
            {'type_id': '59',  'type_name': '仙子直播'},
            {'type_id': '60',  'type_name': '东瀛素人'},
            {'type_id': '387', 'type_name': '网红主播'},
            {'type_id': '388', 'type_name': '国产传媒'},
            {'type_id': '389', 'type_name': '探花系列'},
            {'type_id': '390', 'type_name': '人妻仙侣'},
            {'type_id': '391', 'type_name': '东瀛无印'},
            {'type_id': '392', 'type_name': '美乳巨乳'},
            {'type_id': '393', 'type_name': '强制仙缘'},
            {'type_id': '394', 'type_name': '制服诱惑'},
            {'type_id': '395', 'type_name': '绝色佳人'},
            {'type_id': '396', 'type_name': '风俗泡泡浴'},
            {'type_id': '397', 'type_name': '家庭伦理'},
            {'type_id': '398', 'type_name': 'AV解说'},
            {'type_id': '399', 'type_name': '三级电影'},
            {'type_id': '400', 'type_name': '少女萝莉'},
            {'type_id': '401', 'type_name': 'SM调教'},
            {'type_id': '402', 'type_name': '绝顶潮吹'},
        ]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        text = self._fetch(self.host + '/vod/')
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
        url = f'{self.host}/vodtype/{tid}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid}.html'
        text = self._fetch(url)
        return self._parse_list(text, page)

    def _parse_list(self, text, page=1):
        items = []
        if not text:
            return self._empty_list(page)

        pattern = re.compile(
            r'<article class="excerpt excerpt-c5">.*?'
            r'<a class="thumbnail" href="/voddetail/(\d+)/".*?'
            r'<img[^>]+(?:src|data-src)="([^"]+)"[^>]*>.*?'
            r'<h2><a[^>]*>([^<]+)</a></h2>.*?(?:<footer><time>([^<]*)</time></footer>)?.*?</article>',
            re.S
        )
        for m in pattern.finditer(text):
            vid, pic, title, note = m.groups()
            if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'favicon']):
                pic = ''
            remark = note.strip() if note else ''
            items.append({
                'vod_id': vid,
                'vod_name': title.strip(),
                'vod_pic': pic,
                'vod_remarks': remark,
            })

        if not items:
            pattern2 = re.compile(
                r'<div class="vod">.*?<a[^>]+href="/voddetail/(\d+)/?".*?'
                r'<img[^>]+(?:data-original|src|data-src)="([^"]+)"[^>]*>.*?</div>.*?'
                r'<div class="vod-txt">.*?<a[^>]*>([^<]+)</a>',
                re.S
            )
            for m in pattern2.finditer(text):
                vid, pic, title = m.groups()
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'favicon']):
                    pic = ''
                items.append({
                    'vod_id': vid,
                    'vod_name': title.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        if not items:
            pattern3 = re.compile(
                r'<a[^>]+href="/voddetail/(\d+)/?"[^>]*(?:title="([^"]*)")?[^>]*>.*?'
                r'<img[^>]+(?:src|data-src|data-original)="([^"]+)"[^>]*>.*?</a>',
                re.S
            )
            seen = set()
            for m in pattern3.finditer(text):
                vid, title, pic = m.groups()
                if vid in seen:
                    continue
                seen.add(vid)
                if not title:
                    t = re.search(r'<h[1-6][^>]*>.*?<a[^>]+href="/voddetail/' + vid + r'/?"[^>]*>([^<]+)</a>', text, re.S)
                    title = t.group(1).strip() if t else f'未知道号{vid}'
                if pic and any(x in pic for x in ['loading', 'blank', 'logo', 'icon', 'favicon']):
                    pic = ''
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

    def _empty_list(self, page):
        return {'list': [], 'page': page, 'pagecount': page, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        return self._vod_detail(vid)

    def _vod_detail(self, vid):
        url = f'{self.host}/voddetail/{vid}/'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        all_h1 = re.findall(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        skip_words = ['站长推荐', '友情连接', '友情', '热门APP', 'APP推荐']
        for h in all_h1:
            t = re.sub(r'<[^>]+>', '', h).strip()
            if t and t not in skip_words and len(t) > 3:
                title = t
                break
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).split('详情介绍')[0].strip()
        if not title:
            title = f'仙缘录影{vid}'

        cover = ''
        for pat in [
            r'<div class="img-wrap".*?<img src="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"[^>]*class="[^"]*thumb',
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*thumb',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and 'loading' not in cover and 'favicon' not in cover:
                    break

        play_from_list = []
        play_url_list = []
        eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', text)
        if eps:
            urls = '#'.join([f'{name.strip() or "正片"}${href}' for href, name in eps])
            play_url_list.append(urls)
            play_from_list.append('主线路')
        else:
            play_url_list.append(f'正片$/vodplay/{vid}-1-1/')
            play_from_list.append('熟妇天堂')

        content = '此乃仙缘录影，采天地之灵气，集红尘之百态，供道友观摩修行。'
        if '黑料' in title or '吃瓜' in title:
            content = '红尘风波起，俗世秘闻录。道友可观此卷，以明心见性。'
        elif '探花' in title:
            content = '探花郎行走江湖，采撷百花之精华，留此影像以飨同道。'
        elif '传媒' in title or '制片' in title or '影业' in title:
            content = '传媒宗门倾力打造，仙法录制，画质通灵，乃上乘之作。'
        elif '人妻' in title or '熟女' in title:
            content = '人妻仙侣，风韵天成。此卷记录仙门道侣日常双修之景。'
        elif '学生' in title or '校园' in title:
            content = '学子秘录，青春年华。记录仙门弟子课余修行之趣事。'
        elif '主播' in title or '网红' in title:
            content = '网红仙子直播录影，展示仙法才艺，供道友鉴赏。'
        elif 'SM' in title or '调教' in title:
            content = 'SM仙法秘录，展示特殊双修法门，道友需谨慎观摩。'
        elif '欧美' in title:
            content = '西域风情录，展示异域仙子的修行风采，别开洞天。'
        elif '日本' in title or '东瀛' in title:
            content = '东瀛仙录，记录岛国仙子的修行秘法，别具一格。'
        elif '动漫' in title or '卡通' in title:
            content = '幻境动漫，以仙法绘制，展现二次元修行世界。'
        elif '三级' in title or '伦理' in title:
            content = '伦理仙影，探讨仙门中人伦天道，引人深思。'

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

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page == 1:
            url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}'
        else:
            url = f'{self.host}/vodsearch/{quote(key)}----------{page}---.html'
        text = self._fetch(url)
        items = self._parse_list(text, page=page).get('list', [])
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    # ========== 播放解析（含m3u8广告清洗代理） ==========
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
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\})\s*</script>', text, re.S)
            if m:
                try:
                    player = json.loads(m.group(1))
                    raw_url = player.get('url', '')
                    if raw_url and isinstance(raw_url, str) and raw_url.startswith('http'):
                        m3u8 = raw_url
                except Exception:
                    pass

            if not m3u8:
                for var_name in ['player_aaaa', 'player', 'mac_player', 'cms_player']:
                    m = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})\s*</script>', text, re.S)
                    if m:
                        try:
                            player = json.loads(m.group(1))
                            raw_url = player.get('url', '')
                            if raw_url and isinstance(raw_url, str):
                                decoded = raw_url.strip()
                                if re.match(r'^[A-Za-z0-9+/=]{20,}$', decoded):
                                    try:
                                        import base64
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
                m = re.search(r'["\'](https?://[^"\s<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
                if m:
                    m3u8 = m.group(1)

        m3u8 = self._sanitize_m3u8_url(m3u8)
        if not m3u8:
            return {
                'parse': 1,
                'url': url,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            }

        if m3u8.startswith('//'):
            m3u8 = 'https:' + m3u8
        elif not m3u8.startswith('http'):
            m3u8 = urljoin(self.host, m3u8)

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

    # ========== m3u8 广告清洗代理工具方法（来自千媚宫） ==========
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
            req_headers = {
                'User-Agent': self.headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': self.host,
                'Connection': 'keep-alive',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
            }
            resp = requests.get(url, headers=req_headers, timeout=10, allow_redirects=True, verify=False)
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

    # ========== TVBox 本地代理入口 ==========
    def localProxy(self, params):
        try:
            if not isinstance(params, dict):
                params = {}
            do = params.get('type') or params.get('action') or params.get('do')
            url = params.get('url', '')
            if do not in ['m3u8', 'py'] and not url:
                return [404, "text/plain", "not found"]
            referer = params.get('referer', '') or self.host
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

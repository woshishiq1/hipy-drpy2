# -*- coding: utf-8 -*-
#!/usr/bin/python
"""
熟女汇
地址: https://shunvhzuna.lol
"""

import sys, re, json, base64, html, time, random
from urllib.parse import quote, unquote, urljoin

try:
    import requests
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg='1'): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://shunvhzuna.lol"
        self.name = "熟女汇"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.cms_type = "custom"
        self.content_type = "video"
        self.seen_ids = set()
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s:
                self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi", ".wmv", ".mov"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF, {}]
        try:
            r = self.s.get(param, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.content, {}]
        except:
            return [200, 'image/gif', EMPTY_GIF, {}]

    def _fetch(self, url, referer=None, retries=3, timeout=15):
        if not self.s:
            return ''
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                headers = dict(self.headers)
                if referer:
                    headers['Referer'] = referer
                r = self.s.get(url, headers=headers, timeout=timeout, verify=False)
                r.encoding = r.apparent_encoding if r.apparent_encoding else 'utf-8'
                if r.status_code == 200:
                    if "Just a moment" in r.text or "cf-browser-verification" in r.text:
                        continue
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    continue
            except Exception:
                continue
        return ''

    def homeContent(self, filter):
        try:
            classes = [
			    
				{'type_name': '精品推荐', 'type_id': '224'},
				{'type_name': '国产色情', 'type_id': '225'},
				{'type_name': '主播直播', 'type_id': '227'},
				{'type_name': '亚洲无码', 'type_id': '229'},
				{'type_name': '亚洲有码', 'type_id': '231'},
				{'type_name': '中文有码', 'type_id': '233'},
				{'type_name': '巨乳美乳', 'type_id': '235'},
				{'type_name': '人妻系列', 'type_id': '237'},
				{'type_name': '强奸精品', 'type_id': '239'},
				{'type_name': '欧美精品', 'type_id': '241'},
				{'type_name': '萝莉少女', 'type_id': '243'},
				{'type_name': '伦理三级', 'type_id': '245'},
				{'type_name': '自拍偷拍', 'type_id': '249'},
				{'type_name': '制服丝袜', 'type_id': '251'},
				{'type_name': '口交颜射', 'type_id': '253'},
				{'type_name': '日本精品', 'type_id': '255'},
				{'type_name': 'Cosplay', 'type_id': '257'},
				{'type_name': '素人自拍', 'type_id': '259'},
				{'type_name': '台湾辣妹', 'type_id': '261'},
				{'type_name': '韩国御姐', 'type_id': '263'},
				{'type_name': '唯美港姐', 'type_id': '265'},
				{'type_name': '东南亚AV', 'type_id': '267'},
				{'type_name': '欺辱凌辱', 'type_id': '269'},
				{'type_name': '剧情介绍', 'type_id': '271'},
				{'type_name': '多人多P', 'type_id': '273'},
				{'type_name': '91探花', 'type_id': '275'},
				{'type_name': '网红流出', 'type_id': '276'},
				{'type_name': '野外露出', 'type_id': '277'},
				{'type_name': '古装扮演', 'type_id': '278'},
				{'type_name': '女优系列', 'type_id': '279'},
				{'type_name': '可爱学生', 'type_id': '280'},
				{'type_name': '风情旗袍', 'type_id': '281'},
				{'type_name': '兽耳系列', 'type_id': '282'},
				{'type_name': '瑜伽裤', 'type_id': '283'},
				{'type_name': '闷骚护士', 'type_id': '284'},
				{'type_name': '过膝袜', 'type_id': '285'},
				{'type_name': '网曝门', 'type_id': '286'},
				{'type_name': '传媒出品', 'type_id': '287'},
				{'type_name': '女同性恋', 'type_id': '288'},
				{'type_name': '男同性恋', 'type_id': '289'},
				{'type_name': '恋腿狂魔', 'type_id': '290'},
                {'type_name': '亚洲情色', 'type_id': '374'},
                {'type_name': '主播自拍', 'type_id': '375'},
                {'type_name': '国产偷拍', 'type_id': '376'},
                {'type_name': '无码系列', 'type_id': '377'},
                {'type_name': '欧美性爱', 'type_id': '378'},
                {'type_name': '熟女专区', 'type_id': '379'},
                {'type_name': '强奸系列', 'type_id': '380'},
                {'type_name': '巨乳系列', 'type_id': '381'},
                {'type_name': '中文大全', 'type_id': '382'},
                {'type_name': '制服学生', 'type_id': '383'},
                {'type_name': '女同蕾丝', 'type_id': '384'},
                {'type_name': '卡通动画', 'type_id': '385'},
                {'type_name': '视频伦理', 'type_id': '386'},
                {'type_name': '少女裸体', 'type_id': '387'},
                {'type_name': '重口色情', 'type_id': '388'},
                {'type_name': '人兽性交', 'type_id': '389'},
                {'type_name': '福利姬', 'type_id': '473'},
            ]
            filters = {}
            return {'class': classes, 'filters': filters}
        except Exception:
            return {'class': [], 'filters': {}}

    def homeVideoContent(self):
        try:
            url = f"{self.host}/"
            html_text = self._fetch(url)
            videos = self._parse_list(html_text) if html_text else []
            return {'list': videos}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}
            page = int(pg) if pg else 1
            if page == 1:
                url = f"{self.host}/type/id/{tid}.html"
            else:
                url = f"{self.host}/type/id/{tid}/{page}.html"           
            html_text = self._fetch(url)
            if not html_text:
                return result            
            videos = self._parse_list(html_text)
            total_pages = page + 1
            total_match = re.search(r'_总页数:(\d+),总行数:(\d+)_', html_text)
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                page_nums = re.findall(r'/type/id/\d+/(\d+)\.html', html_text)
                if page_nums:
                    total_pages = max(int(p) for p in page_nums)
                elif re.search(r'["\']?page["\']?\s*[:=]\s*\d+', html_text):
                    total_pages = page + 1            
            result.update({
                'list': videos,
                'page': page,
                'pagecount': total_pages,
                'limit': len(videos),
                'total': 999999
            })
            return result
        except Exception:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}

    def _parse_list(self, html_text):
        if not html_text:
            return []
        videos = []
        seen = set()        
        cards = re.findall(
            r'<div class="video-item">(.*?)<div class="video-info">(.*?)</div>\s*</div>',
            html_text, re.S | re.I
        )
        if not cards:
            cards = re.findall(
                r'<div class="video-item">(.*?)</div>\s*</div>',
                html_text, re.S | re.I
            )
            cards = [(c, '') for c in cards]       
        for card_thumb, card_info in cards:
            try:
                card = card_thumb + card_info
                href_match = re.search(r'href="(/info/id/(\d+)\.html)"', card)
                if not href_match:
                    continue               
                href = href_match.group(1)
                vid = href_match.group(2)
                if not vid or vid in seen:
                    continue
                seen.add(vid)               
                title = ''
                for t_pat in [
                    r'<a[^>]*title="([^"]+)"',
                    r'<h\d[^>]*class="[^"]*video-title[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>',
                ]:
                    m = re.search(t_pat, card, re.S | re.I)
                    if m:
                        title = clean_text(m.group(1))
                        if title:
                            break               
                pic = ''
                for p_pat in [
                    r'<img[^>]+src="([^"]+)"',
                    r'<img[^>]+data-src="([^"]+)"',
                    r'<img[^>]+data-original="([^"]+)"',
                ]:
                    m = re.search(p_pat, card, re.I)
                    if m:
                        pic = m.group(1).strip().strip('"').strip("'")
                        pic = fix_url(pic, self.host)
                        if pic:
                            break               
                remark = ''
                m = re.search(r'<time>(.*?)</time>', card, re.S | re.I)
                if m:
                    remark = clean_text(m.group(1))
                else:
                    m = re.search(r'<span[^>]*class="[^"]*video-duration[^"]*"[^>]*>(.*?)</span>', card, re.S | re.I)
                    if m:
                        remark = clean_text(m.group(1))                
                videos.append({
                    'vod_id': vid,
                    'vod_name': title or vid,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
            except Exception:
                continue       
        return videos

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {'list': []}           
            if vid.startswith('http'):
                url = vid
                m = re.search(r'/info/id/(\d+)\.html', vid)
                if m:
                    vid = m.group(1)
            else:
                url = f"{self.host}/info/id/{vid}.html"           
            html_text = self._fetch(url)
            if not html_text:
                return result           
            title = ''
            for t_pat in [
                r'<h4 class="video-detail-title">.*?<a[^>]*title="([^"]+)"',
                r'<h4 class="video-detail-title">(.*?)</h4>',
                r'<title>(.*?)</title>',
            ]:
                m = re.search(t_pat, html_text, re.S | re.I)
                if m:
                    title = clean_text(m.group(1))
                    if title:
                        break
            if title:
                title = title.split('-')[0].split('_')[0].strip()           
            cover = ''
            for c_pat in [
                r'<div class="video-detail-thumb">.*?<img[^>]+src="([^"]+)"',
                r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            ]:
                m = re.search(c_pat, html_text, re.S | re.I)
                if m:
                    cover = fix_url(m.group(1), self.host)
                    if cover:
                        break          
            content = ''
            m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html_text, re.S | re.I)
            if m:
                content = m.group(1)           
            play_urls = []
            play_match = re.search(r'href="(/play/id/\d+\.html)"', html_text)
            if play_match:
                play_url = play_match.group(1)
                if not play_url.startswith('http'):
                    play_url = urljoin(self.host, play_url)
                play_urls.append(('高清', play_url))
            else:
                play_urls.append(('高清', f"{self.host}/play/id/{vid}.html"))           
            if play_urls:
                sources = []
                urls = []
                for label, purl in play_urls:
                    sources.append(label)
                    urls.append(f'{label}${purl}')
                vod_play_from = '$$$'.join(sources)
                vod_play_url = '$$$'.join(urls)
            else:
                vod_play_from = '默认线路'
                vod_play_url = f'正片${url}'            
            result['list'].append({
                'vod_id': vid,
                'vod_name': title or vid,
                'vod_pic': cover,
                'vod_content': content,
                'vod_play_from': vod_play_from,
                'vod_play_url': vod_play_url,
            })
            return result
        except Exception:
            return {'list': []}

    def _extract_video_urls(self, html_text, page_url):
        play_urls = []
        seen_urls = set()
        
        def add_url(label, url):
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            play_urls.append((label, url))
        direct_links = re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|ts)(?:\?[^\s"\'<>]*)?)', html_text)
        for link in set(direct_links):
            add_url('直连', unquote(link))
        for var_name in ['player_data', 'player_aaaa', 'playerConfig', 'player', 'videoInfo', 'vodData', 'now']:
            pattern = rf'var\s+{re.escape(var_name)}\s*=\s*(\{{.*?\}});'
            m = re.search(pattern, html_text, re.S)
            if m:
                try:
                    pdata = json.loads(m.group(1))
                    def find_url(obj):
                        if isinstance(obj, str):
                            if obj.startswith('http') and self.isVideoFormat(obj):
                                return obj
                            decoded = unquote(obj)
                            if decoded.startswith('http') and self.isVideoFormat(decoded):
                                return decoded
                        elif isinstance(obj, dict):
                            for k in ['url', 'src', 'file', 'video', 'm3u8', 'mp4', 'link', 'play_url']:
                                if k in obj:
                                    res = find_url(obj[k])
                                    if res:
                                        return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_url(item)
                                if res:
                                    return res
                        return None
                    found = find_url(pdata)
                    if found:
                        add_url('主线路', found)
                except Exception:
                    pass
        simple_vars = ['playurl', 'play_url', 'video_url', 'vod_url', 'url', 'src', 'file']
        for var in simple_vars:
            m = re.search(rf'var\s+{re.escape(var)}\s*=\s*["\']([^"\']+)["\']', html_text)
            if m:
                u = m.group(1).strip()
                if u.startswith('http'):
                    add_url('解析', unquote(u))
        for m in re.finditer(r'<video[^>]+src=["\']([^"\']+)["\']', html_text, re.I):
            u = m.group(1)
            if u.startswith('http'):
                add_url('VIDEO', unquote(u))
        iframe_srcs = re.findall(r'<iframe[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html_text, re.I)
        for src in set(iframe_srcs):
            if any(k in src for k in ['play', 'm3u8', 'embed', 'player', 'video']):
                full = fix_url(src, self.host) if not src.startswith('http') else src
                iframe_html = self._fetch(full, referer=page_url)
                if iframe_html:
                    inner_urls = self._extract_video_urls(iframe_html, full)
                    for label, url in inner_urls:
                        add_url(f'嵌套-{label}', url)
                if not any(u == full for _, u in play_urls):
                    add_url('嵌套页', full)
        for b64 in re.findall(r'["\']([A-Za-z0-9+/]{40,}={0,2})["\']', html_text):
            try:
                decoded = self._b64decode(b64)
                if decoded.startswith('http') and self.isVideoFormat(decoded):
                    add_url('Base64', decoded)
            except Exception:
                pass      
        return play_urls

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}
            if not id:
                return result           
            if self.isVideoFormat(id):
                result['url'] = id
                result['header'] = json.dumps({
                    'Referer': self.host + '/',
                    'User-Agent': self.headers['User-Agent'],
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9'
                })
                return result            
            if id.startswith('magnet:'):
                result['parse'] = 1
                result['url'] = id
                return result          
            if 'play' in id or 'player' in id:
                html_text = self._fetch(id, referer=self.host + '/')
                if html_text:
                    inner = self._extract_video_urls(html_text, id)
                    if inner:
                        for label, url in inner:
                            if self.isVideoFormat(url):
                                result['url'] = url
                                result['header'] = json.dumps({
                                    'Referer': id,
                                    'User-Agent': self.headers['User-Agent']
                                })
                                return result
                    for pat in [r'var\s+player_[a-z]+\s*=\s*(\{.*?\});', r'player_[a-z]+\s*=\s*(\{.*?\})']:
                        m = re.search(pat, html_text, re.S)
                        if m:
                            try:
                                pdata = json.loads(m.group(1))
                                raw = pdata.get('url', '')
                                if raw:
                                    decoded = unquote(raw)
                                    if decoded.startswith('http'):
                                        result['url'] = decoded
                                        result['header'] = json.dumps({
                                            'Referer': id,
                                            'User-Agent': self.headers['User-Agent']
                                        })
                                        return result
                            except:
                                pass
                    m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html_text)
                    if m:
                        result['url'] = m.group(1)
                        result['header'] = json.dumps({
                            'Referer': id,
                            'User-Agent': self.headers['User-Agent']
                        })
                        return result          
            result['parse'] = 1
            result['url'] = id
            result['header'] = json.dumps({
                'Referer': id,
                'User-Agent': self.headers['User-Agent']
            })
            return result
        except Exception:
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': ''}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}
            page = int(pg) if pg else 1
            if page == 1:
                url = f"{self.host}/lookup/{quote(key)}.html"
            else:
                url = f"{self.host}/lookup/{quote(key)}/L/{page}.html"
            html_text = self._fetch(url)
            videos = self._parse_list(html_text) if html_text else []
            total_pages = page + 1
            total_match = re.search(r'_总页数:(\d+),总行数:(\d+)_', html_text) if html_text else None
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                page_nums = re.findall(r'/lookup/[^/]+/L/(\d+)\.html', html_text) if html_text else []
                if page_nums:
                    total_pages = max(int(p) for p in page_nums)            
            result.update({
                'list': videos,
                'page': page,
                'pagecount': total_pages,
                'limit': len(videos),
                'total': 999999
            })
            return result
        except Exception:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 24, 'total': 0}

    def _b64decode(self, s):
        try:
            padding = 4 - len(s) % 4
            if padding != 4:
                s += '=' * padding
            decoded = base64.b64decode(s)
            return decoded.decode('utf-8', errors='strict')
        except Exception:
            return ''

    def _unpack_eval(self, eval_code, full_html):
        try:
            m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\((.*?)\)\)", full_html, re.S)
            if not m:
                return None
            return None
        except Exception:
            return None

    def liveContent(self, url):
        pass

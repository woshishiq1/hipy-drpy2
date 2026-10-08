# -*- coding: utf-8 -*-
# XX01.COM 视频解析修复版 - 支持全分类
import os, json, re, sys, time, html as html_lib, urllib.parse
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    backend_parse = False
    category_mode = False
    categoryMode = False

    def init(self, extend="{}"):
        self.err = ""
        try:
            if isinstance(extend, dict):
                cfg = extend
            else:
                cfg = json.loads(extend) if extend else {}
        except Exception as e:
            cfg = {}
            self.err = f"config解析失败:{e}"
        
        self.host = cfg.get('site', 'https://xx01.com')
        self.headers = {
            'referer': f'{self.host}/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        }
        
        try:
            from pyquery import PyQuery as pq
            self.pq = pq
        except Exception as e:
            self.pq = None
            self.err += f";缺pyquery:{e}"
        
        try:
            import requests
            self.req = requests
            self.session = requests.Session()
        except Exception as e:
            self.req = None
            self.session = None
            self.err += f";缺requests:{e}"

    def getName(self):
        return "XX01"

    def isVideoFormat(self, url):
        return bool(re.search(
            r'(?:\.(?:m3u8|mp4|flv|ts)(?:\?|$)|(?:pl\d+\.vvvvvvvv\.top|ig\d+\.pppppppp\.top)/)',
            str(url or ''), re.IGNORECASE
        ))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def _log(self, msg):
        try:
            self.log(msg)
        except:
            pass

    def _get(self, url, referer=None):
        if not self.session:
            raise RuntimeError("requests不可用")
        headers = dict(self.headers)
        if referer:
            headers['referer'] = referer
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.get(
                    url, headers=headers, timeout=(10, 25), allow_redirects=True
                )
                if response.status_code == 200:
                    signature = response.text[:5000].lower()
                    if not any(marker in signature for marker in (
                        'just a moment', '_cf_chl_opt', 'cf-turnstile', 'cf-chl-widget'
                    )):
                        return response
                    last_error = RuntimeError("Cloudflare验证页")
                    response.close()
                else:
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    response.close()
            except Exception as e:
                last_error = e
            if attempt < 2:
                time.sleep(float(attempt + 1))
        raise last_error or RuntimeError("请求失败")

    def _full_url(self, value):
        return urllib.parse.urljoin(self.host + '/', str(value or '').strip())

    def _media_headers(self):
        return {
            'User-Agent': self.headers.get('user-agent', ''),
            'Referer': self.host + '/',
        }

    def _play_result(self, url, parse=0):
        return {
            'parse': parse,
            'jx': 0,
            'playUrl': '',
            'url': url,
            'header': self._media_headers(),
        }

    def _proxy_target(self, url):
        try:
            query = urllib.parse.parse_qs(
                urllib.parse.urlsplit(url).query, keep_blank_values=True
            )
            value = query.get('url', [''])[0].strip()
            if value.startswith('http') and '${' not in value:
                return value
        except Exception:
            pass
        return ''

    def _is_media_target(self, value, depth=0):
        value = urllib.parse.unquote(html_lib.unescape(str(value or ''))).strip()
        if not value or '${' in value or depth > 3:
            return False
        lower = value.lower()
        if re.search(r'https?://(?:pl\d+\.vvvvvvvv|ig\d+\.pppppppp)\.top/', lower):
            return self._is_media_target(self._proxy_target(value), depth + 1)
        return bool(re.search(r'\.(?:m3u8|mp4|flv|ts)(?:\?|$)', lower))

    def _normalize_media_url(self, value):
        value = html_lib.unescape(str(value or '')).replace('\\/', '/').strip()
        if not value or '${' in value or value.startswith('blob:'):
            return ''
        value = self._full_url(value)
        lower = value.lower()
        target = self._proxy_target(value)

        if re.search(r'https?://pl\d+\.vvvvvvvv\.top/', lower):
            if not target or not self._is_media_target(target):
                return ''
            if '/api/play' in lower and 'surrit.com' not in target.lower():
                return ''
            return value

        if re.search(r'https?://ig\d+\.pppppppp\.top/api/proxy/', lower):
            return value if target and self._is_media_target(target) else ''

        if 'stream.defeated.xxx/' in lower:
            encoded = urllib.parse.quote(value, safe=':/?&=%')
            return f'https://pl2.vvvvvvvv.top/?url={encoded}'

        if 'fourhoi.com/' in lower and re.search(r'\.(?:m3u8|mp4)(?:\?|$)', lower):
            encoded = urllib.parse.quote(value, safe=':/?&=%')
            return f'https://ig2.pppppppp.top/api/proxy/?url={encoded}'

        if re.search(r'\.(?:m3u8|mp4|flv|ts)(?:\?|$)', lower):
            return value
        return ''

    def _decode_packed_media(self, text):
        results = []
        packers = [
            re.compile(r"\}\('((?:\\.|[^'])*)',(\d+),(\d+),'((?:\\.|[^'])*)'\.split\('\|'\)"),
            re.compile(r'\}\("((?:\\.|[^"])*)",(\d+),(\d+),\'((?:\\.|[^\'])*)\'\.split\(\'\|\'\)'),
        ]
        alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'

        def base_key(number, radix):
            if number == 0:
                return '0'
            value = ''
            while number:
                value = alphabet[number % radix] + value
                number //= radix
            return value

        for packer in packers:
            for match in packer.finditer(text):
                payload = match.group(1).replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
                radix = int(match.group(2))
                count = int(match.group(3))
                words = match.group(4).split('|')
                if radix < 2 or radix > len(alphabet) or count > 5000:
                    continue
                for index in range(min(count, len(words)) - 1, -1, -1):
                    if words[index]:
                        payload = re.sub(
                            r'\b' + re.escape(base_key(index, radix)) + r'\b',
                            words[index], payload
                        )
                for name, media in re.findall(
                    r"\b(source1280|source842|source)\s*=\s*['\"](https?://[^'\"]+)['\"]",
                    payload
                ):
                    priority = {'source': 850, 'source1280': 820, 'source842': 780}[name]
                    results.append((media, priority))
        return results

    def homeContent(self, filter):
        try:
            if self.err:
                return self._error(self.err)
            if not self.req or not self.pq:
                return self._error("缺少requests或pyquery依赖")
            
            url = f"{self.host}/"
            self._log(f"req home: {url}")
            r = self._get(url)
            self._log(f"status: {r.status_code}")
            
            if r.status_code != 200:
                return self._error(f"HTTP {r.status_code}")
            
            html = self.pq(r.content)
            
            classes = [
                {"type_id": "chinese-subtitle", "type_name": "中文字幕"},
                {"type_id": "madou", "type_name": "国产AV"},
                {"type_id": "genres/外国女优", "type_name": "欧美大片"},
                {"type_id": "PLANTSVSCUNTS", "type_name": "猎奇"},
                {"type_id": "masem", "type_name": "马赛姆"},
                {"type_id": "kinostream", "type_name": "kinostream"},
                {"type_id": "TIMESTUDIO", "type_name": "时间工作室"},
                {"type_id": "anime", "type_name": "成人动漫"},
                {"type_id": "new", "type_name": "最近更新"},
                {"type_id": "release", "type_name": "新作上市"},
                {"type_id": "uncensored-leak", "type_name": "无码流出"},
                {"type_id": "genres", "type_name": "类型"},
                {"type_id": "VR", "type_name": "VR"},
                {"type_id": "avtalk", "type_name": "AV解说"},
                {"type_id": "siro", "type_name": "SIRO"},
                {"type_id": "luxu", "type_name": "LUXU"},
                {"type_id": "gana", "type_name": "GANA"},
                {"type_id": "maan", "type_name": "PRESTIGE PREMIUM"},
                {"type_id": "scute", "type_name": "S-CUTE"},
                {"type_id": "ara", "type_name": "ARA"},
                {"type_id": "fc2", "type_name": "FC2"},
                {"type_id": "heyzo", "type_name": "HEYZO"},
                {"type_id": "tokyohot", "type_name": "東京熱"},
                {"type_id": "1pondo", "type_name": "一本道"},
                {"type_id": "caribbeancom", "type_name": "Caribbeancom"},
                {"type_id": "caribbeancompr", "type_name": "Caribbeancompr"},
                {"type_id": "10musume", "type_name": "10musume"},
                {"type_id": "pacopacomama", "type_name": "pacopacomama"},
                {"type_id": "gachinco", "type_name": "Gachinco"},
                {"type_id": "xxxav", "type_name": "XXX-AV"},
                {"type_id": "marriedslash", "type_name": "人妻斬"},
                {"type_id": "naughty4610", "type_name": "頑皮4610"},
                {"type_id": "naughty0930", "type_name": "頑皮0930"},
                {"type_id": "twav", "type_name": "TWAV"},
                {"type_id": "furuke", "type_name": "Furuke"},
                {"type_id": "klive", "type_name": "韓國直播"},
                {"type_id": "clive", "type_name": "中國直播"},
                {"type_id": "tiktok", "type_name": "抖阴视频"},
                {"type_id": "starface", "type_name": "明星换脸"},
                {"type_id": "cnlive", "type_name": "主播直播,国产主播"},
                {"type_id": "cmedia", "type_name": "国产传媒"},
                {"type_id": "playgirl", "type_name": "玩偶姐姐,网红头条"},
                {"type_id": "netdoor", "type_name": "网-曝-门,网曝黑料"},
            ]
            
            return {
                'class': classes,
                'filters': {},
                'list': self._parse_list(html)
            }
        except Exception as e:
            self._log(f"homeErr:{e}")
            return self._error(str(e))

    def homeVideoContent(self):
        try:
            if self.err:
                return self._error(self.err)
            if not self.req or not self.pq:
                return self._error("缺少requests或pyquery依赖")
            
            url = f"{self.host}/"
            r = self._get(url)
            html = self.pq(r.content)
            return {'list': self._parse_list(html)}
        except Exception as e:
            self._log(f"homeVideoErr:{e}")
            return self._error(str(e))

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            url = f"{self.host}/{tid}"
            if pg > 1:
                url += f"?page={pg}"
            
            self._log(f"cat req: {url}")
            r = self._get(url)
            html = self.pq(r.content)
            pages = [pg]
            for link in html('a[href*="?page="]').items():
                match = re.search(r'[?&]page=(\d+)', link.attr('href') or '')
                if match:
                    pages.append(int(match.group(1)))
            return {
                'list': self._parse_list(html),
                'page': pg,
                'pagecount': max(pages),
                'limit': 90,
                'total': 0
            }
        except Exception as e:
            self._log(f"catErr:{e}")
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 90, 'total': 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0])
            if vid.startswith('atvp_detail:'):
                vid = vid[len('atvp_detail:'):]
            vid = vid.strip('/')
            url = f"{self.host}/{vid}"
            self._log(f"detail req: {url}")
            r = self._get(url)
            text = r.text
            html = self.pq(r.content)
            
            # ===== 标题提取 =====
            title = html('h1').text().strip()
            if not title:
                title = html('meta[property="og:title"]').attr('content')
            if not title:
                title = html('title').text().split('-')[0].strip()
            if not title:
                title = html('title').text().strip()
            if not title:
                title = vid
            title = re.sub(r'\s*[-|]\s*XX01\.?COM.*$', '', title, flags=re.IGNORECASE).strip()
            
            # ===== 简介提取 =====
            content = html('meta[name="description"]').attr('content') or ''
            if not content:
                content = html('meta[property="og:description"]').attr('content') or ''
            
            # ===== 封面提取（可选） =====
            pic = html('meta[property="og:image"]').attr('content') or ''
            if not pic:
                pic = html('.aspect-w-16 img').attr('data-src') or html('.aspect-w-16 img').attr('src') or ''
            
            candidates = []

            def add_candidate(value, priority):
                media = self._normalize_media_url(value)
                lower = media.lower()
                if not media or '/previews/' in lower or 'preview.' in lower:
                    return
                candidates.append((media, priority))

            # PyQuery 会还原 href/src 内的 HTML 实体，优先读取站点实际主播放器。
            for elem in html('video.player[src], video.player[data-src]').items():
                add_candidate(elem.attr('src') or elem.attr('data-src'), 1000)
            for elem in html('a[href*="vvvvvvvv.top"][href*="url="], a[href*="pppppppp.top"][href*="url="]').items():
                add_candidate(elem.attr('href'), 950)
            for elem in html('a[href*=".mp4"], a[href*=".m3u8"]').items():
                add_candidate(elem.attr('href'), 900)

            # 常规影片把真实 surrit 地址放在 Dean Edwards packer 中；仅做字典替换，不执行脚本。
            for media, priority in self._decode_packed_media(text):
                if 'surrit.com/' in media.lower():
                    media = 'https://pl3.vvvvvvvv.top/api/play?url=' + urllib.parse.quote(media, safe='')
                add_candidate(media, priority)

            decoded_text = html_lib.unescape(text).replace('\\/', '/')
            patterns = [
                r'(https?://pl\d+\.vvvvvvvv\.top/[^\s"\'<>]+)',
                r'(https?://ig\d+\.pppppppp\.top/api/proxy/\?url=[^\s"\'<>]+)',
                r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv)(?:\?[^\s"\'<>]*)?)',
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, decoded_text):
                    add_candidate(match.group(1), 200)

            deduped = {}
            for media, priority in candidates:
                deduped[media] = max(priority, deduped.get(media, 0))
            play = ''
            if deduped:
                play = max(deduped.items(), key=lambda item: item[1])[0]
                self._log(f"found {len(deduped)} playable candidates, best: {play[:160]}")

            if not play:
                play = f"嗅探${url}"
            
            play_name = re.sub(r'[$#]+', ' ', title).strip() or vid
            vod = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_actor': '',
                'vod_director': '',
                'vod_content': content,
                'vod_play_from': 'XX01',
                'vod_play_url': f"{play_name}${play}"
            }
            return {'list': [vod]}
        except Exception as e:
            self._log(f"detErr:{e}")
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
            url = f"{self.host}/search/{urllib.parse.quote(str(key), safe='')}"
            if pg > 1:
                url += f"?page={pg}"
            self._log(f"search req: {url}")
            r = self._get(url)
            html = self.pq(r.content)
            return {
                'list': self._parse_list(html),
                'page': pg
            }
        except Exception as e:
            self._log(f"searchErr:{e}")
            return {'list': [], 'page': 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            value = str(id or '').strip()
            if value.startswith('嗅探$'):
                return self._play_result(value[3:], parse=1)

            media = self._normalize_media_url(value)
            if media:
                # pl2/pl3/ig2 返回的是媒体流或 HLS 清单，不是待解析的网页。
                return self._play_result(media, parse=0)

            if value.startswith('http'):
                return self._play_result(value, parse=1)

            return self._play_result(value, parse=1)
        except Exception as e:
            self._log(f"playErr:{e}")
            return self._play_result(str(id or ''), parse=1)

    def _parse_list(self, html):
        ret = []
        seen = set()
        try:
            # 多选择器兼容不同分类版式
            selectors = [
                '.grid .thumbnail.group',
                '#list1 .thumbnail.group',
                '.thumbnail.group',
                '.item-wrapper .thumbnail.group',
                '.grid.grid-cols-2 .thumbnail.group'
            ]
            items = None
            for sel in selectors:
                items = html(sel)
                if items and len(items) > 0:
                    self._log(f"list selector: {sel}, count: {len(items)}")
                    break
            
            if not items or len(items) == 0:
                self._log("no list items found")
                return ret
            
            for item in items.items():
                try:
                    a = item.find('a').eq(0)
                    href = a.attr('href')
                    if not href:
                        continue
                    
                    absolute_href = self._full_url(href)
                    vid = urllib.parse.urlsplit(absolute_href).path.strip('/')
                    if not vid or vid in seen or vid.startswith('http') or vid.startswith('#') or vid.startswith('javascript'):
                        continue
                    seen.add(vid)
                    
                    name = ''
                    name_elem = item.find('.truncate a, .text-secondary').eq(0)
                    if name_elem:
                        name = name_elem.text().strip()
                    if not name:
                        name = a.attr('alt') or vid
                    
                    pic = ''
                    img = a.find('img')
                    if img and len(img) > 0:
                        pic = img.attr('data-src') or img.attr('src') or ''
                    else:
                        img = item.find('img').eq(0)
                        if img:
                            pic = img.attr('data-src') or img.attr('src') or ''
                    
                    if pic and pic.startswith('data:image'):
                        pic = ''
                    elif pic:
                        pic = self._full_url(pic)
                    
                    remark = ''
                    rb = item.find('.absolute.bottom-1.right-1').eq(0)
                    if rb:
                        remark = rb.text().strip()
                    if not remark:
                        lb = item.find('.absolute.bottom-1.left-1').eq(0)
                        if lb:
                            remark = lb.text().strip()
                    
                    ret.append({
                        'vod_id': vid,
                        'vod_name': name,
                        'vod_pic': pic,
                        'vod_year': '',
                        'vod_remarks': remark,
                        'style': {"type": "rect", "ratio": 1.33}
                    })
                except Exception as e:
                    self._log(f"parseItemErr:{e}")
                    continue
        except Exception as e:
            self._log(f"parseErr:{e}")
        self._log(f"parsed total: {len(ret)}")
        return ret

    def _error(self, msg):
        return {
            'class': [{"type_id": "PLANTSVSCUNTS", "type_name": "猎奇"}],
            'filters': {},
            'list': [{
                'vod_id': 'error',
                'vod_name': '【点我查看错误信息】',
                'vod_pic': '',
                'vod_remarks': msg[:40],
                'vod_content': f"错误详情：{msg}",
                'style': {"type": "rect", "ratio": 1.33}
            }]
        }

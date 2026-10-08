# coding=utf-8
import sys
import json
import re
import requests
import base64
from urllib.parse import unquote, quote, urljoin, urlparse

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider():
        def fetch(self, url, headers=None, timeout=10):
            try:
                res = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                res.encoding = 'utf-8'
                return res
            except Exception as e:
                print(f"fetch error: {e}")
                return None


class Spider(BaseSpider):
    def getName(self):
        return "精英突击"

    def init(self, extend=""):
        self.host = "https://xn--39s42yy7t.jyelemeniotech.xyz"
        print(f"[init] 当前使用域名: {self.host}")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        })

    def homeVideoContent(self):
        return {"list": []}

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
            print(f"[本地代理] 请求 m3u8: {url}")
            print(f"[本地代理] Referer: {referer}")
            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, "text/plain", f"m3u8 download failed\nurl: {url}\nreferer: {referer}"]
            cleaned = self._clean_m3u8(text, url, referer)
            print(f"[本地代理] 清洗完成，返回长度: {len(cleaned)}")
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"[本地代理异常] {e}\n{err}")
            return [500, "text/plain", f"proxy error: {e}"]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def fetch(self, url, headers=None, timeout=8):
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)
            res = self.session.get(url, headers=req_headers, timeout=timeout, allow_redirects=True)
            if not res.encoding or res.encoding.lower() == 'iso-8859-1':
                res.encoding = res.apparent_encoding or 'utf-8'
            return res
        except Exception as e:
            print(f"[请求失败] {url} -> {e}")
            return None

    def homeContent(self, filter):
        classes = [
            {"type_name": "国产精选", "type_id": "43"},
            {"type_name": "字幕剧情", "type_id": "35"},
            {"type_name": "欧美视频", "type_id": "39"},
            {"type_name": "日本无码", "type_id": "33"},
            {"type_name": "黑人视频", "type_id": "37"},
            {"type_name": "传媒拍摄", "type_id": "53"},
            {"type_name": "人妖性爱", "type_id": "29"},
            {"type_name": "萝莉少女", "type_id": "47"},
            {"type_name": "女同性恋", "type_id": "23"},
            {"type_name": "男同性恋", "type_id": "21"},
            {"type_name": "捆绑调教", "type_id": "31"},
            {"type_name": "三级伦理", "type_id": "55"},
            {"type_name": "卡通视频", "type_id": "59"},
            {"type_name": "重口猎奇", "type_id": "25"},
        ]
        return {'class': classes, 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 24, "total": 9999}

        if pg == 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"

        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            return result

        html = res.text
        vod_list = []

        cards = re.findall(
            r'<section[^>]*class="video_item_wrapper[^"]*"[^>]*>.*?'
            r'<h2[^>]*class="video_item_section_container"[^>]*>.*?<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>(.*?)</a>.*?</h2>.*?'
            r'<a[^>]*class="video_item_thumbnail[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"',
            html, re.DOTALL | re.I
        )
        if cards:
            for card in cards:
                href, vid, title_html, pic = card
                name = re.sub(r'<[^>]+>', '', title_html).strip()
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": name or "未知",
                    "vod_pic": pic.strip(),
                    "vod_remarks": ""
                })

        if not vod_list:
            blocks = re.findall(
                r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>.*?'
                r'<img[^>]*src="([^"]+)"[^>]*>.*?'
                r'(?:<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]*)</[^>]*>|alt="([^"]*)")',
                html, re.DOTALL | re.I
            )
            if blocks:
                for block in blocks:
                    href, vid, pic, name1, name2 = block
                    name = (name1 or name2 or "未知").strip()
                    vod_list.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": pic.strip(),
                        "vod_remarks": ""
                    })

        if not vod_list:
            blocks = re.findall(
                r'href="(/index\.php/vod/play/id/(\d+)/[^"]*)".*?'
                r'<img[^>]*src="([^"]+)"[^>]*>.*?'
                r'>([^<]{2,50})<',
                html, re.DOTALL | re.I
            )
            for block in blocks:
                href, vid, pic, name = block
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": name.strip(),
                    "vod_pic": pic.strip(),
                    "vod_remarks": ""
                })

        if not vod_list:
            blocks = re.findall(
                r'href="(/index\.php/vod/(?:play|detail)/id/(\d+)[^"]*)".*?>([^<]{2,50})<',
                html, re.DOTALL | re.I
            )
            for block in blocks:
                href, vid, name = block
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": name.strip(),
                    "vod_pic": "",
                    "vod_remarks": ""
                })

        seen = set()
        deduped = []
        for vod in vod_list:
            if vod['vod_id'] not in seen:
                seen.add(vod['vod_id'])
                deduped.append(vod)
        vod_list = deduped

        result['list'] = vod_list
        if not vod_list:
            result['pagecount'] = pg
        return result

    def _extract_title_from_html(self, html):
        """从HTML中提取最可能的标题，返回空字符串表示未找到"""
        if not html:
            return ""
        
        # 1. title标签（去掉站点名，通常用 | 或 - 分隔）
        m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        if m:
            raw = m.group(1)
            for sep in ['|', '-', '_', '—']:
                if sep in raw:
                    raw = raw.split(sep)[0]
                    break
            t = raw.strip()
            if t and t not in ['', '精英突击视频']:
                return t
        
        # 2. h1
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        
        # 3. 该模板特有的 h2.video_item_section_container
        m = re.search(r'<h2[^>]*class="[^"]*video_item_section_container[^"]*"[^>]*>(.*?)</h2>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        
        # 4. 通用 h2
        m = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        
        # 5. h3
        m = re.search(r'<h3[^>]*>(.*?)</h3>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        
        # 6. class包含 title / name / video-title
        m = re.search(r'<[^>]*class="[^"]*(?:title|name|video-title)[^"]*"[^>]*>(.*?)</(?:div|span|h[1-6]|p|a)>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        
        return ""

    def detailContent(self, ids):
        vid = ids[0]
        title = ""
        desc = "资源来自于网络"
        
        # 先请求详情页
        detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        res = self.fetch(detail_url, headers={'Referer': self.host})
        
        if res:
            html = res.text
            title = self._extract_title_from_html(html)
            desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.I)
            if desc_m:
                desc = desc_m.group(1)
        
        # 如果详情页没拿到标题，回退到播放页再试
        if not title:
            play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            print(f"[detailContent] 详情页无标题，尝试播放页: {play_url}")
            res2 = self.fetch(play_url, headers={'Referer': self.host})
            if res2:
                title = self._extract_title_from_html(res2.text)
        
        # 最终保底
        if not title:
            title = f"视频{vid}"
        
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_type": "视频",
            "vod_content": desc,
            "vod_play_from": "精英突击",
            "vod_play_url": f"播放${vid}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg=1):
        if pg == 1:
            url = f"{self.host}/index.php/vod/search/wd/{quote(key)}.html"
        else:
            url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"

        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            return {"list": []}

        html = res.text
        vod_list = []

        cards = re.findall(
            r'<section[^>]*class="video_item_wrapper[^"]*"[^>]*>.*?'
            r'<h2[^>]*class="video_item_section_container"[^>]*>.*?<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>(.*?)</a>.*?</h2>.*?'
            r'<a[^>]*class="video_item_thumbnail[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"',
            html, re.DOTALL | re.I
        )
        if cards:
            for card in cards:
                href, vid, title_html, pic = card
                name = re.sub(r'<[^>]+>', '', title_html).strip()
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": name or "未知",
                    "vod_pic": pic.strip(),
                    "vod_remarks": ""
                })

        if not vod_list:
            blocks = re.findall(
                r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>.*?'
                r'<img[^>]*src="([^"]+)"[^>]*>.*?'
                r'(?:<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]*)</[^>]*>|alt="([^"]*)")',
                html, re.DOTALL | re.I
            )
            if blocks:
                for block in blocks:
                    href, vid, pic, name1, name2 = block
                    name = (name1 or name2 or "未知").strip()
                    vod_list.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": pic.strip(),
                        "vod_remarks": ""
                    })

        if not vod_list:
            blocks = re.findall(
                r'href="(/index\.php/vod/(?:play|detail)/id/(\d+)[^"]*)".*?>([^<]{2,50})<',
                html, re.DOTALL | re.I
            )
            for block in blocks:
                href, vid, name = block
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": name.strip(),
                    "vod_pic": "",
                    "vod_remarks": ""
                })

        seen = set()
        deduped = []
        for vod in vod_list:
            if vod['vod_id'] not in seen:
                seen.add(vod['vod_id'])
                deduped.append(vod)
        return {"list": deduped}

    def playerContent(self, flag, id, vipFlags=None):
        vid = id
        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        print(f"[playerContent] 播放页: {play_url}")
        res = self.fetch(play_url, headers={'Referer': self.host}, timeout=8)
        if not res:
            print("[playerContent] 播放页请求失败")
            return {"parse": 1, "url": play_url}

        html = res.text
        m3u8_url = None

        direct_m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8(?:\?[^"\s\'<>&]*(?:&[^"\s\'<>&=]*=[^"\s\'<>&]*)*)?)', html, re.I)
        if direct_m3u8:
            m3u8_url = self._sanitize_m3u8_url(direct_m3u8.group(1))
            print(f"[playerContent] 直接匹配 m3u8: {m3u8_url}")

        if not m3u8_url:
            config = self._extract_player_config(html)
            if config:
                m3u8_url = self._sanitize_m3u8_url(config.get('url', ''))
                print(f"[playerContent] player_aaaa m3u8: {m3u8_url}")

        if not m3u8_url:
            match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)', html, re.DOTALL | re.I)
            if match:
                try:
                    m3u8_url = self._sanitize_m3u8_url(json.loads(match.group(1)).get('url', ''))
                    print(f"[playerContent] player_aaaa 兜底 m3u8: {m3u8_url}")
                except Exception as e:
                    print(f"[播放配置JSON兜底失败] {e}")

        if not m3u8_url:
            m3u8_url = self._sanitize_m3u8_url(self._js_decode(html))
            if m3u8_url:
                print(f"[playerContent] JS解码 m3u8: {m3u8_url}")

        if not m3u8_url:
            m3u8_url = self._sanitize_m3u8_url(self._sniff_xhr(html, play_url))
            if m3u8_url:
                print(f"[playerContent] XHR嗅探 m3u8: {m3u8_url}")

        if not m3u8_url:
            iframe_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if iframe_m:
                iframe_url = iframe_m.group(1)
                if iframe_url.startswith('//'):
                    iframe_url = 'https:' + iframe_url
                elif not iframe_url.startswith('http'):
                    iframe_url = urljoin(self.host, iframe_url)
                print(f"[iframe] 发现嵌套播放器: {iframe_url}")
                iframe_res = self.fetch(iframe_url, headers={'Referer': play_url}, timeout=8)
                if iframe_res:
                    iframe_html = iframe_res.text
                    m3u8_url = re.search(r'(https?://[^\s"\'<>]+\.m3u8(?:\?[^"\s\'<>&]*(?:&[^"\s\'<>&=]*=[^"\s\'<>&]*)*)?)', iframe_html, re.I)
                    if m3u8_url:
                        m3u8_url = self._sanitize_m3u8_url(m3u8_url.group(1))
                    else:
                        m3u8_url = self._sanitize_m3u8_url(self._extract_player_config(iframe_html).get('url', ''))
                    if not m3u8_url:
                        m3u8_url = self._sanitize_m3u8_url(self._sniff_xhr(iframe_html, iframe_url))
                    if not m3u8_url:
                        m3u8_url = self._sanitize_m3u8_url(self._js_decode(iframe_html))
                    if m3u8_url:
                        print(f"[iframe] 提取 m3u8: {m3u8_url}")

        if not m3u8_url:
            print(f"[解析失败] 未找到 m3u8，返回壳解析: {play_url}")
            return {"parse": 1, "url": play_url}

        m3u8_url = self._sanitize_m3u8_url(m3u8_url)
        if m3u8_url.startswith('//'):
            m3u8_url = 'https:' + m3u8_url
        elif not m3u8_url.startswith('http'):
            m3u8_url = urljoin(self.host, m3u8_url)

        print(f"[解析成功] 最终 m3u8: {m3u8_url}")

        media_header = {
            "User-Agent": self.session.headers['User-Agent'],
            "Referer": play_url,
            "Origin": self.host
        }

        proxy_url = self._proxy_m3u8_url(m3u8_url, play_url)
        print(f"[解析成功] 代理URL: {proxy_url}")
        return {
            "parse": 0,
            "playUrl": "",
            "url": proxy_url,
            "header": json.dumps(media_header, ensure_ascii=False)
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

    def _extract_player_config(self, html):
        try:
            m = re.search(r'var\s+player_aaaa\s*=\s*\{', html or '', re.I)
            if not m:
                return {}
            start = m.end() - 1
            depth = 0
            in_str = ''
            esc = False
            for i in range(start, len(html)):
                ch = html[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == in_str:
                        in_str = ''
                    continue
                if ch in ('"', "'"):
                    in_str = ch
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(html[start:i + 1])
        except Exception as e:
            print(f"[播放配置解析异常] {e}")
        return {}

    def _js_decode(self, js_str):
        b64_match = re.search(r'atob\s*\(\s*["\']([^"\']+)["\']\s*\)', js_str)
        if b64_match:
            try:
                decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                return decoded
            except:
                pass
        unescape_match = re.search(r'unescape\s*\(\s*["\']([^"\']+)["\']\s*\)', js_str)
        if unescape_match:
            try:
                decoded = unquote(unescape_match.group(1))
                return decoded
            except:
                pass
        url_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', js_str, re.I)
        if url_match:
            return url_match.group(1)
        return None

    def _sniff_xhr(self, html, page_url):
        patterns = [
            r'fetch\s*\(\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'XMLHttpRequest.*?\.open\s*\(\s*["\']GET["\']\s*,\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'\.get\s*\(\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]
        for pat in patterns:
            match = re.search(pat, html, re.I)
            if match:
                url = match.group(1)
                if not url.startswith('http'):
                    url = urljoin(page_url, url)
                return url

        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.I | re.S)
        for script_content in scripts:
            if script_content.strip():
                found = self._js_decode(script_content)
                if found and '.m3u8' in found:
                    return found
        return None

    def _proxy_m3u8_url(self, url, referer=''):
        try:
            if hasattr(self, 'getProxyUrl'):
                return self.getProxyUrl() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except Exception as e:
            print(f"[代理地址生成异常] {e}")
        return url

    def _get_m3u8_content(self, url, referer):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': self.host,
                'Connection': 'keep-alive',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
            }
            print(f"[下载m3u8] URL: {url}")
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            print(f"[下载m3u8] 状态码: {resp.status_code}")
            if resp.status_code == 200:
                text = resp.text
                print(f"[下载m3u8] 内容长度: {len(text)}")
                return text
            else:
                print(f"[下载m3u8] 非200响应")
                return None
        except Exception as e:
            import traceback
            print(f"[下载m3u8] 异常: {e}")
            print(traceback.format_exc())
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
        print(f"[m3u8清洗] 原片段:{len(segments)} 删除广告:{removed} 保留:{len(cleaned)}")
        return '\n'.join(new_lines) + '\n'

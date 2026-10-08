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
        return "怡红院"

    def init(self, extend=""):
        self.host = "https://uxzl.1hong.buzz"
        print(f"[init] 当前使用域名: {self.host}")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        })

    def homeVideoContent(self):
        """抓取首页今日推荐"""
        result = {"list": []}
        try:
            res = self.fetch(self.host, headers={'Referer': self.host})
            if res:
                result['list'] = self._parse_list_html(res.text)
        except Exception as e:
            print(f"[homeVideoContent] error: {e}")
        return result

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
            print(f"[本地代理] 处理完成，返回长度: {len(cleaned)}")
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
            {"type_name": "国产色情", "type_id": "20"},
            {"type_name": "日本无码", "type_id": "21"},
            {"type_name": "人妻熟女", "type_id": "23"},
            {"type_name": "欧美精品", "type_id": "25"},
            {"type_name": "中文字幕", "type_id": "36"},
            {"type_name": "吃瓜爆料", "type_id": "38"},
            {"type_name": "日本有码", "type_id": "35"},
            {"type_name": "自拍偷拍", "type_id": "22"},
            {"type_name": "乱伦中出", "type_id": "27"},
            {"type_name": "口爆颜射", "type_id": "29"},
            {"type_name": "岛国群交", "type_id": "34"},
            {"type_name": "伦理三级", "type_id": "54"},
            {"type_name": "传媒原创", "type_id": "28"},
            {"type_name": "直播裸聊", "type_id": "33"},
            {"type_name": "萝莉少女", "type_id": "31"},
            {"type_name": "岛国女优", "type_id": "30"},
            {"type_name": "重口调教", "type_id": "32"},
            {"type_name": "岛国素人", "type_id": "37"},
            {"type_name": "淫娃自慰", "type_id": "40"},
            {"type_name": "角色扮演", "type_id": "39"},
            {"type_name": "热门事件", "type_id": "41"},
            {"type_name": "卡通动漫", "type_id": "26"},
            {"type_name": "户外打野", "type_id": "43"},
            {"type_name": "AV解说", "type_id": "47"},
            {"type_name": "AI换脸", "type_id": "46"},
            {"type_name": "女同性恋", "type_id": "45"},
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

        result['list'] = self._parse_list_html(res.text)
        if not result['list']:
            result['pagecount'] = pg
        return result

    def _parse_list_html(self, html):
        """统一解析视频列表 HTML，返回 vod 字典列表"""
        vod_list = []
        seen = set()

        # 方案1：直接全局匹配 <a> 标签（不依赖外层 div 嵌套）
        cards = re.findall(
            r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*src="([^"]+)"[^>]*>',
            html, re.DOTALL | re.I
        )
        for card in cards:
            href, vid, title, pic = card
            if vid in seen:
                continue
            seen.add(vid)
            vod_list.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": ""
            })

        if vod_list:
            return vod_list

        # 方案2：兜底，更宽松的通用匹配
        blocks = re.findall(
            r'href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)".*?'
            r'<img[^>]*src="([^"]+)"[^>]*>.*?'
            r'>([^<]{2,50})<',
            html, re.DOTALL | re.I
        )
        for block in blocks:
            href, vid, pic, name = block
            if vid in seen:
                continue
            seen.add(vid)
            vod_list.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": ""
            })

        return vod_list

    def _extract_title_from_html(self, html):
        if not html:
            return ""
        m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        if m:
            raw = m.group(1)
            for sep in ['|', '-', '_', '—']:
                if sep in raw:
                    raw = raw.split(sep)[0]
                    break
            t = raw.strip()
            if t and t not in ['', '怡红院']:
                return t
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        m = re.search(r'<h4[^>]*class="[^"]*video-title[^"]*"[^>]*>(.*?)</h4>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        m = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.I | re.S)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if t:
                return t
        return ""

    def detailContent(self, ids):
        vid = ids[0]
        title = ""
        desc = "资源来自于网络"

        detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        res = self.fetch(detail_url, headers={'Referer': self.host})

        if res:
            html = res.text
            title = self._extract_title_from_html(html)
            desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.I)
            if desc_m:
                desc = desc_m.group(1)

        if not title:
            play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            print(f"[detailContent] 详情页无标题，尝试播放页: {play_url}")
            res2 = self.fetch(play_url, headers={'Referer': self.host})
            if res2:
                title = self._extract_title_from_html(res2.text)

        if not title:
            title = f"视频{vid}"

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_type": "视频",
            "vod_content": desc,
            "vod_play_from": "怡红院",
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

        return {"list": self._parse_list_html(res.text)}

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

        # 不启用代理，直接返回原始 m3u8 地址
        return {
            "parse": 0,
            "playUrl": "",
            "url": m3u8_url,
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

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer=''):
        """已取消代理和清洗，直接透传原始内容"""
        return m3u8_text or ''

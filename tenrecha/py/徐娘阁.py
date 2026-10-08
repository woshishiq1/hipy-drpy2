# coding=utf-8
import sys
import json
import re
import requests
import base64
from urllib.parse import quote, urljoin, urlparse, unquote

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
        return "徐娘阁"

    def init(self, extend=""):
        self.host = "https://1jpnygzply.xuniangex.buzz"
        self.publishUrl = "https://www.xuniangfin.info"
        print(f"[init] 当前使用域名: {self.host}")
        print(f"[init] 发布页: {self.publishUrl}")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        })

        self._check_domain_health()

    def _check_domain_health(self):
        try:
            test = self.session.get(self.host + '/vod/', timeout=5, allow_redirects=True)
            if test.status_code == 200 and 'wn_vodlist' in test.text:
                print(f"[域名检测] {self.host} 正常")
                return
        except Exception as e:
            print(f"[域名检测] {self.host} 失效: {e}")

        print(f"[域名检测] 尝试从发布页获取最新地址: {self.publishUrl}")
        try:
            res = self.session.get(self.publishUrl, timeout=10, allow_redirects=True)
            if res.status_code == 200:
                html = res.text
                domains = re.findall(r'(https?://[a-z0-9]+\.xuniangex\.buzz)', html, re.I)
                if domains:
                    new_host = domains[0].rstrip('/')
                    print(f"[域名检测] 发现新域名: {new_host}")
                    self.host = new_host
                else:
                    domains = re.findall(r'(https?://[a-z0-9]+\.[a-z]+)', html, re.I)
                    if domains:
                        new_host = domains[0].rstrip('/')
                        print(f"[域名检测] 发现备用域名: {new_host}")
                        self.host = new_host
        except Exception as e:
            print(f"[域名检测] 发布页访问失败: {e}")

    def _make_header(self):
        return {
            "User-Agent": self.session.headers.get('User-Agent', ''),
            "Referer": self.host
        }

    def _extract_pic(self, html_block):
        """多级回退提取图片，兼容懒加载，自动修复失效域名"""
        if not html_block:
            return ""
        pic = ""
        # 优先级: data-src > data-original > srcset > src
        for attr in ['data-src', 'data-original', 'srcset', 'src']:
            if pic:
                break
            pattern = r"<img[^>]*" + attr + r"=[\"\']([^\"\']+)[\"\']"
            m = re.search(pattern, html_block, re.I)
            if m:
                val = m.group(1).strip()
                if attr == 'srcset':
                    val = val.split(',')[0].split()[0].strip()
                if val and 'loading' not in val and 'blank' not in val and 'placeholder' not in val:
                    pic = val

        if not pic:
            return ""

        # 相对路径拼接为绝对路径
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif pic.startswith('/'):
            pic = urljoin(self.host, pic)
        elif not pic.startswith('http'):
            pic = urljoin(self.host, pic)

        # 域名健康替换: bwjpg.top 已失效(404)，尝试替换为 bwzy.tv 备用
        if 'bwjpg.top' in pic:
            backup = pic.replace('bwjpg.top', 'bwzy.tv')
            print(f"[图片修复] bwjpg.top 失效，尝试备用: {backup}")
            pic = backup

        return pic

    def homeVideoContent(self):
        result = {"list": []}
        try:
            res = self.fetch(self.host + '/vod/', headers={'Referer': self.host})
            if res:
                result['list'] = self._parse_home_html(res.text)
                result['header'] = self._make_header()
        except Exception as e:
            print(f"[homeVideoContent] error: {e}")
        return result

    def _parse_home_html(self, html):
        vod_list = []
        if not html:
            return vod_list
        # 首页遍历所有li，不限于wn_vodlist容器（首页wn_box多为广告）
        all_li = re.findall(r"<li[^>]*>(.*?)</li>", html, re.S)
        skipped = 0
        for li in all_li:
            if 'nofollow' in li:
                skipped += 1
                continue
            a = re.search(r"<a[^>]+href=[\"\'](/vodplay/[0-9]+-[0-9]+-[0-9]+/)[\"\'][^>]*title=[\"\']([^\"\']*)[\"\']", li)
            if not a:
                continue
            vid = a.group(1)
            title = a.group(2)
            if not title:
                continue
            pic = self._extract_pic(li)
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        seen = set()
        deduped = []
        for vod in vod_list:
            if vod['vod_id'] not in seen:
                seen.add(vod['vod_id'])
                deduped.append(vod)
        print(f"[_parse_home_html] 总li={len(all_li)} 跳过nofollow={skipped} 有效={len(deduped)}")
        return deduped[:30]

    def homeContent(self, filter):
        # 删除视频一区/二区/三区（用户要求），保留有实际意义的分类
        classes = [
            {"type_name": "91大神", "type_id": "4"},
            {"type_name": "热门事件", "type_id": "5"},
            {"type_name": "传媒自拍", "type_id": "6"},
            {"type_name": "日本无码", "type_id": "8"},
            {"type_name": "日韩主播", "type_id": "9"},
            {"type_name": "动漫肉番", "type_id": "10"},
            {"type_name": "女同性恋", "type_id": "11"},
            {"type_name": "中文字幕", "type_id": "12"},
            {"type_name": "熟女人妻", "type_id": "14"},
            {"type_name": "制服诱惑", "type_id": "15"},
            {"type_name": "AV解说", "type_id": "16"},
            {"type_name": "女星换脸", "type_id": "17"},
            {"type_name": "大地资源", "type_id": "18"},
            {"type_name": "日韩无码", "type_id": "19"},
            {"type_name": "强奸乱伦", "type_id": "20"},
        ]
        return {'class': classes, 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 30, "total": 9999}

        if pg == 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{pg}/"

        print(f"[categoryContent] 请求: {url}")
        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            print("[categoryContent] 请求失败")
            return result

        html = res.text
        result['list'] = self._parse_list_html(html)
        result['header'] = self._make_header()

        # 分页探测
        has_next = False
        if result['list']:
            has_next = re.search(rf"href=[\"\'][^\"\']*/vodtype/{tid}-{pg + 1}/[\"\']", html, re.I | re.S)
            if not has_next:
                has_next = re.search(r"<a[^>]*href=[\"\'][^\"\']*/vodtype/\d+-\d+/[\"\'][^>]*>[^<]*(?:下一页|&raquo;|›|»)[^<]*</a>", html, re.I | re.S)

        if not has_next:
            result['pagecount'] = pg
            print(f"[categoryContent] 无下一页，共 {pg} 页")
        else:
            print(f"[categoryContent] 存在下一页，继续")

        return result

    def _parse_list_html(self, html):
        vod_list = []
        if not html:
            return vod_list

        # 一级: wn_vodlist容器内wn_box
        container = re.search(r"<ul[^>]*class=[\"\'][^\"\']*wn_vodlist[^\"\']*[\"\'][^>]*>(.*?)</ul>", html, re.S)
        if container:
            items = re.findall(r"<li[^>]*class=[\"\'][^\"\']*wn_box[^\"\']*[\"\'][^>]*>(.*?)</li>", container.group(1), re.S)
            print(f"[_parse_list_html] wn_vodlist容器匹配到 {len(items)} 个项")
        else:
            items = []

        # 二级: 全页wn_box（搜索页等结构不同但class相同）
        if not items:
            items = re.findall(r"<li[^>]*class=[\"\'][^\"\']*wn_box[^\"\']*[\"\'][^>]*>(.*?)</li>", html, re.S)
            print(f"[_parse_list_html] 全页模式匹配到 {len(items)} 个项")

        skipped_nofollow = 0
        skipped_no_title = 0

        for item in items:
            if 'rel="nofollow"' in item:
                skipped_nofollow += 1
                continue

            a = re.search(r"<a[^>]+href=[\"\'](/vodplay/[0-9]+-[0-9]+-[0-9]+/)[\"\'][^>]*title=[\"\']([^\"\']*)[\"\']", item)
            if not a:
                a = re.search(r"<a[^>]+href=[\"\'](/vodplay/[0-9]+-[0-9]+-[0-9]+/)[\"\']", item)
                title_m = re.search(r"title=[\"\']([^\"\']*)[\"\']", item)
                if a and title_m:
                    title = title_m.group(1)
                else:
                    continue
            else:
                title = a.group(2)

            vid = a.group(1)
            if not title:
                skipped_no_title += 1
                continue

            pic = self._extract_pic(item)

            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })

        print(f"[_parse_list_html] 结果: 有效={len(vod_list)}, 跳过nofollow={skipped_nofollow}, 无标题={skipped_no_title}")

        # 三级: 暴力兜底
        if not vod_list:
            print("[_parse_list_html] 标准模式无结果，尝试暴力兜底模式...")
            all_links = re.findall(r"<a[^>]*href=[\"\'](/vodplay/[0-9]+-[0-9]+-[0-9]+/)[\"\'][^>]*title=[\"\']([^\"\']*)[\"\']", html, re.I)
            print(f"[_parse_list_html] 暴力模式匹配到 {len(all_links)} 个链接")
            seen = set()
            for vid, title in all_links:
                if vid in seen or not title:
                    continue
                seen.add(vid)
                pic = ""
                nearby = re.search(r"<a[^>]*href=[\"\']" + re.escape(vid) + r"[\"\'][^>]*>.*?</a>", html, re.S | re.I)
                if nearby:
                    pic = self._extract_pic(nearby.group(0))
                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            print(f"[_parse_list_html] 暴力模式最终有效: {len(vod_list)}")

        seen = set()
        deduped = []
        for vod in vod_list:
            if vod['vod_id'] not in seen:
                seen.add(vod['vod_id'])
                deduped.append(vod)
        return deduped

    def _extract_title_from_html(self, html):
        if not html:
            return ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if t:
                return t
        m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if m:
            raw = m.group(1)
            for sep in ['|', '-', '_', '—']:
                if sep in raw:
                    raw = raw.split(sep)[0]
                    break
            t = raw.strip()
            if t and t not in ['', '徐娘阁']:
                return t
        return ""

    def detailContent(self, ids):
        vid = ids[0]
        title = ""
        desc = "资源来自于网络"
        pic = ""

        detail_url = f"{self.host}{vid}" if vid.startswith('/') else vid
        res = self.fetch(detail_url, headers={'Referer': self.host})

        if res:
            html = res.text
            title = self._extract_title_from_html(html)
            desc_m = re.search(r"<meta\s+name=\"description\"\s+content=\"([^\"]*)\"", html, re.I)
            if desc_m:
                desc = desc_m.group(1)

            # 封面提取多级回退
            pic = ""
            for pat in [
                r"<img[^>]*src=[\"\']([^\"\']+)[\"\'][^>]*class=[\"\'][^\"\']*(?:pic|thumb|poster)[^\"\']*[\"\']",
                r"<img[^>]*class=[\"\'][^\"\']*(?:pic|thumb|poster)[^\"\']*[\"\'][^>]*src=[\"\']([^\"\']+)[\"\']",
                r"og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']",
                r"twitter:image[^>]+content=[\"\']([^\"\']+)[\"\']",
            ]:
                m = re.search(pat, html, re.I)
                if m:
                    pic = m.group(1).strip()
                    if pic:
                        break
            if not pic:
                all_imgs = re.findall(r"<img[^>]+src=[\"\']([^\"\']+)[\"\'][^>]*>", html, re.I)
                for img in all_imgs:
                    if 'upload/vod' in img and '.gif' not in img:
                        pic = img
                        break

            pic = self._normalize_pic(pic)

        if not title:
            title = f"视频{vid}"

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_type": "视频",
            "vod_content": desc,
            "vod_play_from": "在线播放",
            "vod_play_url": f"第1集${vid}"
        }
        return {"list": [vod]}

    def _normalize_pic(self, pic):
        """统一图片URL处理：拼接相对路径、修复失效域名"""
        if not pic:
            return ""
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif pic.startswith('/'):
            pic = urljoin(self.host, pic)
        elif not pic.startswith('http'):
            pic = urljoin(self.host, pic)
        if 'bwjpg.top' in pic:
            pic = pic.replace('bwjpg.top', 'bwzy.tv')
        return pic

    def searchContent(self, key, quick, pg=1):
        pg = int(pg)
        if pg == 1:
            url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}"
        else:
            url = f"{self.host}/vodsearch/{quote(key)}----------{pg}---/"

        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            return {"list": []}

        result = {"list": self._parse_list_html(res.text)}
        result['header'] = self._make_header()
        return result

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        vid = id
        play_url = f"{self.host}{vid}" if vid.startswith('/') else vid
        print(f"[playerContent] 播放页: {play_url}")
        res = self.fetch(play_url, headers={'Referer': self.host}, timeout=8)
        if not res:
            print("[playerContent] 播放页请求失败")
            return {"parse": 1, "url": play_url}

        html = res.text
        m3u8_url = None

        # 一级: player_data
        direct_m3u8 = re.search(r"var player_data=\{[^}]*\"url\"[:\"\']+([^,\"\'}]+)", html)
        if direct_m3u8:
            url = direct_m3u8.group(1).strip().strip('"').strip("'")
            url = url.replace('\\/', '/')
            if url.endswith('.m3u8') or url.endswith('.mp4'):
                m3u8_url = self._sanitize_m3u8_url(url)
                print(f"[playerContent] player_data m3u8: {m3u8_url}")

        # 二级: player_aaaa
        if not m3u8_url:
            match = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)", html, re.DOTALL | re.I)
            if match:
                try:
                    m3u8_url = self._sanitize_m3u8_url(json.loads(match.group(1)).get('url', ''))
                    print(f"[playerContent] player_aaaa m3u8: {m3u8_url}")
                except Exception as e:
                    print(f"[player_aaaa解析失败] {e}")

        # 三级: iframe
        if not m3u8_url:
            iframe_m = re.search(r"<iframe[^>]+src=[\"\']([^\"\']+)[\"\']", html, re.I)
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
                    m3u8_match = re.search(r"(https?://[^\s\"\'<>]+\.m3u8(?:\?[^\"\s\'<>&]*(?:&[^\"\s\'<>&=]*=[^\"\s\'<>&]*)*)?)", iframe_html, re.I)
                    if m3u8_match:
                        m3u8_url = self._sanitize_m3u8_url(m3u8_match.group(1))
                    else:
                        m3u8_url = self._sanitize_m3u8_url(self._extract_player_config(iframe_html).get('url', ''))
                    if m3u8_url:
                        print(f"[iframe] 提取 m3u8: {m3u8_url}")

        # 四级: video标签
        if not m3u8_url:
            video_match = re.search(r"<video[^>]+src=[\"\']([^\"\']+)[\"\']", html, re.I)
            if video_match:
                url = video_match.group(1)
                if '.m3u8' in url:
                    m3u8_url = self._sanitize_m3u8_url(url)
                    print(f"[playerContent] video标签 m3u8: {m3u8_url}")

        # 五级: JS解码
        if not m3u8_url:
            m3u8_url = self._js_decode(html)
            if m3u8_url:
                print(f"[playerContent] JS解码 m3u8: {m3u8_url}")

        # 六级: 直接正则
        if not m3u8_url:
            m = re.findall(r"[\"\']([^\"\']*\.(?:m3u8|mp4|flv)[^\"\']*)[\"\']", html)
            if m:
                m3u8_url = self._sanitize_m3u8_url(m[0].replace('\\/', '/'))
                print(f"[playerContent] 正则兜底 m3u8: {m3u8_url}")

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

    def _extract_player_config(self, html):
        try:
            m = re.search(r"var\s+player_aaaa\s*=\s*\{", html or '', re.I)
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
        b64_match = re.search(r"atob\s*\(\s*[\"\']([^\"\']+)[\"\']\s*\)", js_str)
        if b64_match:
            try:
                decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                return decoded
            except:
                pass
        url_match = re.search(r"(https?://[^\s\"\']+\.m3u8[^\s\"\']*)", js_str, re.I)
        if url_match:
            return url_match.group(1)
        return None

    def _sanitize_m3u8_url(self, url):
        if not url:
            return url
        url = unquote(url)
        url = re.sub(r"&[Cc]over=.*", "", url)
        url = re.sub(r"&[Pp]oster=.*", "", url)
        url = re.sub(r"&[Tt]humb=.*", "", url)
        url = re.sub(r"&[Pp]ic=.*", "", url)
        url = url.rstrip('&?')
        return url

    def _proxy_m3u8_url(self, url, referer=''):
        try:
            if hasattr(self, 'getProxyUrl'):
                base = self.getProxyUrl()
                return base + '&type=m3u8&url=' + quote(url, safe='/') + '&referer=' + quote(referer or self.host, safe='/')
        except Exception as e:
            print(f"[代理地址生成异常] {e}")
        return url

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

    def localProxy(self, params):
        """
        TVBox 本地代理入口。必须返回 [status:int, content_type:str, body:str]。
        严防 params 中 url/referer 为 Java null（Jython 映射为 None）导致异常，
        进而使 Java 层拿到 null Response 触发 NanoHTTPD Status can't be null 崩溃。
        """
        try:
            if not isinstance(params, dict):
                params = {}

            raw_url = params.get('url', '') or ''
            raw_ref = params.get('referer', '') or self.host
            do = params.get('type') or params.get('action') or params.get('do') or ''

            if isinstance(raw_url, list):
                raw_url = raw_url[0] if raw_url else ''
            if isinstance(raw_ref, list):
                raw_ref = raw_ref[0] if raw_ref else self.host
            if not isinstance(raw_url, str):
                raw_url = str(raw_url) if raw_url else ''
            if not isinstance(raw_ref, str):
                raw_ref = str(raw_ref) if raw_ref else self.host

            url = unquote(raw_url) if raw_url else ''
            referer = unquote(raw_ref) if raw_ref else self.host

            if do not in ['m3u8', 'py']:
                return [404, 'text/plain', 'not found']
            if not url:
                return [400, 'text/plain', 'url required']
            if not url.startswith('http'):
                return [400, 'text/plain', 'invalid url']

            print(f"[localProxy] 代理 m3u8: {url}")
            print(f"[localProxy] Referer: {referer}")

            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, 'text/plain', f"m3u8 download failed\nurl: {url}\nreferer: {referer}"]

            cleaned = self._clean_m3u8(text, url, referer)
            if cleaned is None:
                cleaned = text
            print(f"[localProxy] 清洗完成，返回长度: {len(cleaned)}")
            return [200, 'application/vnd.apple.mpegurl', cleaned]

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"[localProxy] 异常: {e}\n{err}")
            return [500, 'text/plain', f"proxy error: {e}"]

    def _get_m3u8_content(self, url, referer):
        """统一使用 self.fetch (session)，避免独立 requests 导致 Header 不一致"""
        try:
            h = {
                'User-Agent': self.session.headers.get('User-Agent', ''),
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
            resp = self.fetch(url, headers=h, timeout=10)
            if resp and resp.status_code == 200:
                text = resp.text
                print(f"[下载m3u8] 状态码: {resp.status_code} 长度: {len(text)}")
                return text
            else:
                sc = resp.status_code if resp else 'None'
                print(f"[下载m3u8] 非200响应: {sc}")
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
            'pre', 'preroll', '片头', '广告', '/gg/', '_gg', '/adv/',
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
                m = re.search(r"#EXTINF:\s*([\d.]+)", line)
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
            path = re.sub(r"/[^/]*$", "/", p.path or "/")
            return (p.netloc.lower(), path.lower())
        except:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlparse(m3u8_url).path
            m = re.search(r"(/\d{8}/[^/]+/\d+kb/hls/)", p)
            if m:
                return m.group(1).lower()
            m = re.search(r"(/\d{8}/[^/]+/)", p)
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
                    tag = re.sub(r"URI=\"([^\"]+)\"", _fix_uri, tag)
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

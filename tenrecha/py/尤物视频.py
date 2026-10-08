# -*- coding: utf-8 -*-
"""
兼容 FongMi/TV (T3) 和 WebHomeTV/PeekPro (T4) 的 Python Spider
站点: 尤物视频 (youwu47.top)
"""
import sys
import json
import re
import base64
import time

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=30, **kw)
            r.encoding = 'utf-8'
            return r

try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class Spider(Spider):
    def getName(self):
        return "尤物视频"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''

        # 将 host 统一为带 /ywsp 的基础路径，简化 _url 逻辑
        self.host = "https://xn--0810wu-4x4a.youwu47.top/ywsp"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/',
            'Connection': 'keep-alive',
        }

        self._aes_key = b'1234567898882222'
        self._aes_iv = b'1234567898882222'

        self._home_cache = []
        self._home_cache_time = 0

    def _url(self, path):
        if not path:
            return self.host + '/'
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            return self.host + path
        return self.host + '/' + path

    def _txt(self, url, referer=None, timeout=30):
        headers = dict(self.header)
        if referer:
            headers['Referer'] = referer
        try:
            rsp = self.fetch(url, headers=headers, timeout=timeout)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            return rsp.text
        except Exception:
            return ""

    def _decrypt_page(self, html_text):
        if not HAS_CRYPTO:
            return html_text

        m = re.search(r'<div id="app" style="display:none;">(.*?)</div>', html_text, re.S)
        if not m:
            return html_text

        data = m.group(1).strip()
        try:
            cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
            decrypted = cipher.decrypt(base64.b64decode(data))
            pad_len = decrypted[-1]
            if 0 < pad_len <= 16:
                decrypted = decrypted[:-pad_len]
            html = decrypted.decode('utf-8', errors='ignore')
            start = html.find('<html')
            if start > 0:
                html = html[start:]
            return html
        except Exception:
            return html_text

    # ===== 工具：标准化 href，去掉 /ywsp 前缀 =====
    def _normalize_path(self, href):
        """去掉 /ywsp 前缀，返回纯相对路径供 _url() 使用"""
        if not href:
            return ''
        href = href.strip()
        if href.startswith('/ywsp'):
            href = href[5:]  # 去掉 /ywsp
        if not href.startswith('/'):
            href = '/' + href
        return href

    # ========== 首页分类 ==========
    def homeContent(self, filter):
        classes = [
            {"type_id": "/index.php/vod/type/id/170.html", "type_name": "国产自拍"},
            {"type_id": "/index.php/vod/type/id/172.html", "type_name": "日本无码"},
            {"type_id": "/index.php/vod/type/id/173.html", "type_name": "中文字幕"},
            {"type_id": "/index.php/vod/type/id/174.html", "type_name": "欧美情色"},
        ]
        return {
            "class": classes,
            "filters": {},
        }

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {"list": self._home_cache[:72]}

        html_enc = self._txt(self._url('/'), timeout=20)
        html = self._decrypt_page(html_enc)

        # 尝试提取最近更新区域，失败则用全部列表
        videos = self._parse_video_list(html, only_recent=True)
        if len(videos) < 20:
            videos = self._parse_video_list(html)

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {"list": self._home_cache}

    # ========== 分类列表 ==========
    def categoryContent(self, tid, pg, filter, extend):
        if pg == "1":
            url = self._url(tid)
        else:
            # 翻页：/index.php/vod/type/id/170.html → /index.php/vod/type/id/170/page/2.html
            base = re.sub(r'\.html$', '', tid)
            url = self._url(base + '/page/' + pg + '.html')

        html_enc = self._txt(url, referer=self.host + '/', timeout=30)
        html = self._decrypt_page(html_enc)
        videos = self._parse_video_list(html)

        pagecount = 99
        # 末页链接匹配：匹配 /page/N.html 且后面跟着"末页"文字
        last_page_match = re.search(r'/page/(\d+)\.html[^>]*>?\s*末页\s*<', html)
        if not last_page_match:
            last_page_match = re.search(r'末页[^<]*</a>.*?/page/(\d+)\.html', html, re.S)
        if last_page_match:
            pagecount = int(last_page_match.group(1))

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ========== 详情页 ==========
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = ids[0]

        url = self._url(vod_id) if not vod_id.startswith('http') else vod_id
        html_enc = self._txt(url, referer=self.host + '/', timeout=30)
        html = self._decrypt_page(html_enc)

        vod = self._parse_detail(html, vod_id)
        return {"list": [vod]}

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        url = self._url('/index.php/vod/search.html?wd=' + key + '&page=' + pg)
        html_enc = self._txt(url, referer=self.host + '/', timeout=30)
        html = self._decrypt_page(html_enc)
        videos = self._parse_video_list(html)

        return {
            "list": videos,
            "page": pg,
            "pagecount": 10,
            "limit": 20,
            "total": len(videos),
        }

    # ========== 播放解析 ==========
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "playUrl": "", "url": ""}

        url = id if str(id).startswith("http") else self._url(id)

        if self._is_direct_media(url):
            return {
                "parse": 0, "playUrl": "", "url": url,
                "header": dict(self.header),
                "format": "application/x-mpegURL" if ".m3u8" in url else "",
                "contentType": "application/x-mpegURL" if ".m3u8" in url else "",
            }

        html_enc = self._txt(url, referer=self.host + '/', timeout=30)
        html = self._decrypt_page(html_enc)

        real_url = ""
        m = re.search(r"var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})\s*</script>", html, re.S)
        if m:
            try:
                player_data = json.loads(m.group(1))
                real_url = player_data.get("url", "")
                encrypt = player_data.get("encrypt", 0)
                if encrypt in [1, 2] and real_url:
                    try:
                        real_url = base64.b64decode(real_url).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                real_url = real_url.replace("\\/", "/")
            except Exception:
                pass

        if not real_url:
            m = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
            if m:
                real_url = m.group(1)

        if real_url:
            return {
                "parse": 0, "playUrl": "", "url": real_url,
                "header": {
                    "User-Agent": self.header["User-Agent"],
                    "Referer": url,
                },
                "format": "application/x-mpegURL" if ".m3u8" in real_url else "",
                "contentType": "application/x-mpegURL" if ".m3u8" in real_url else "",
            }

        return {
            "parse": 1, "playUrl": "", "url": url,
            "header": dict(self.header),
        }

    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        pass

    def close(self):
        self.destroy()

    def _is_direct_media(self, url):
        url = (url or "").lower()
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or ".mkv" in url

    def _strip_tags(self, text):
        if not text:
            return ""
        return re.sub(r'<[^>]+>', '', text).strip()

    def _is_ad_card(self, li_html):
        if re.search(r'id=["\']link[0-9]+["\']|id=["\']text[0-9]+["\']', li_html):
            return True
        href_match = re.search(r'href=["\']([^"\']+)["\']', li_html)
        if href_match:
            href = href_match.group(1)
            if href in ('/', '/ '):
                return True
            if href.startswith('http') and not href.startswith(self.host):
                return True
        return False

    def _parse_video_list(self, html, only_recent=False):
        videos = []
        seen = set()

        if only_recent:
            # 放宽最近更新区域匹配
            recent_match = re.search(
                r'<h3[^>]*>最近更新</h3>(.*?)(?=<h3|</div>\s*</div>\s*</div>)',
                html, re.S
            )
            if recent_match:
                html = recent_match.group(1)

        lis = re.findall(r'(<li>.*?</li>)', html, re.S)

        for li in lis:
            if self._is_ad_card(li):
                continue

            # 放宽href匹配：同时匹配 /ywsp/index.php/... 和 /index.php/... 两种格式
            href_match = re.search(
                r'href=["\'](?:/ywsp)?(/?index\.php/vod/detail/id/\d+\.html)["\']',
                li
            )
            if not href_match:
                continue

            raw_href = href_match.group(1)
            href = self._normalize_path(raw_href)
            if not href:
                continue

            img_match = re.search(r'<img[^>]+(?:src|data-original)=["\']([^"\']+)["\']', li)
            img = img_match.group(1) if img_match else ""
            if img and not img.startswith('http'):
                img = self._url(img)

            alt_match = re.search(r'<img[^>]+alt=["\']([^"\']*)["\']', li)
            alt_title = alt_match.group(1) if alt_match else ""

            title_match = re.search(r'<h5>.*?<a[^>]*>(.*?)</a>', li, re.S)
            title = ""
            if title_match:
                title = self._strip_tags(title_match.group(1))

            final_title = title or alt_title

            tag_match = re.search(r'<p>(.*?)</p>', li)
            tag = self._strip_tags(tag_match.group(1)) if tag_match else ""

            if href in seen:
                continue
            seen.add(href)

            videos.append({
                "vod_id": href,
                "vod_name": final_title or "未知",
                "vod_pic": img,
                "vod_remarks": tag,
            })

        return videos

    def _parse_detail(self, html, vod_id):
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        name_match = re.search(r'<li>片名[：:](.*?)</li>', html)
        if name_match:
            vod["vod_name"] = self._strip_tags(name_match.group(1))

        type_match = re.search(r'<li><label>类型[：:]</label>(.*?)</li>', html)
        if type_match:
            vod["type_name"] = self._strip_tags(type_match.group(1))

        date_match = re.search(r'<li><label>更新[：:]</label>(.*?)</li>', html)
        if date_match:
            vod["vod_remarks"] = self._strip_tags(date_match.group(1))

        # 封面：优先从详情页大图提取
        pic_match = re.search(
            r'<img[^>]+(?:src|data-original)=["\'](https?://[^"\']+)["\']',
            html
        )
        if pic_match:
            vod["vod_pic"] = pic_match.group(1)
        else:
            pic_match = re.search(r'<img[^>]+(?:src|data-original)=["\']([^"\']+)["\']', html)
            if pic_match:
                raw = pic_match.group(1)
                vod["vod_pic"] = self._url(raw) if not raw.startswith('http') else raw

        # ===== 播放链接提取（修复：正则是非贪婪，且统一路径）=====
        play_from = []
        play_url_parts = []

        # 匹配播放链接：同时兼容 /ywsp/ 前缀和不带前缀的格式
        play_links = re.findall(
            r'href=["\'](?:/ywsp)?(/?index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)["\'][^>]*>([^<]+)</a>',
            html
        )

        if play_links:
            roads_dict = {}
            for raw_href, sid, nid, name in play_links:
                name_clean = self._strip_tags(name).strip()
                if not name_clean:
                    continue
                href = self._normalize_path(raw_href)
                roads_dict.setdefault(sid, []).append(f"{name_clean}${href}")

            # 提取线路名：从播放源 tab 中找
            source_tabs = re.findall(
                r'<li[^>]*>.*?<a[^>]*href=["\']#playlist\d*["\'][^>]*>([^<]+)</a>',
                html, re.S
            )
            if not source_tabs:
                source_tabs = re.findall(
                    r'<a[^>]*href=["\']#playlist\d*["\'][^>]*>([^<]+)</a>',
                    html
                )

            sid_order = sorted(roads_dict.keys(), key=lambda x: int(x))
            for i, sid in enumerate(sid_order):
                road_name = source_tabs[i].strip() if i < len(source_tabs) else f"线路{sid}"
                road_name = self._strip_tags(road_name) or f"线路{sid}"
                play_from.append(road_name)
                play_url_parts.append("#".join(roads_dict[sid]))

        else:
            # 单集兜底：从详情页vod_id提取数字ID
            id_match = re.search(r'id/(\d+)\.html', vod_id)
            if id_match:
                vid = id_match.group(1)
                play_from.append("默认线路")
                play_url_parts.append(
                    f"播放${self._url('/index.php/vod/play/id/' + vid + '/sid/1/nid/1.html')}"
                )

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url_parts)

        content_match = re.search(
            r'class=["\'][^"\']*(?:content|desc|intro|summary)["\'][^>]*>(.*?)</div>',
            html, re.S
        )
        if content_match:
            vod["vod_content"] = self._strip_tags(content_match.group(1))[:500]

        return vod

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Address：https://51aw23.com/
Descript：51暗网 - 黑料吃瓜图文站,内嵌 DPlayer 视频
Author：drpy-writer
"""
import base64
import json
import re
import sys
from html import unescape
from urllib.parse import quote, urljoin

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    name = "51aw"
    base_url = "https://burden.gtrazibvz.com"
    site_url = "https://51aw23.com"

    class_name = [
        "今日吃瓜", "全网热搜", "暗网爆料", "暗网网红", "每日大赛",
        "AI短剧", "暗网反差", "暗网校园", "暗网乱伦", "暗网视频",
        "海外大片", "暗网AV解说", "暗网猎奇", "探花偷拍", "每日top",
        "寸止挑战", "动漫天堂", "暗史档案", "世界杯",
    ]
    class_url = [
        "jrrg", "qwrs", "awcg", "dywh", "mrds",
        "aidj", "fcll", "xycg", "anwangluanlun", "sxzq",
        "hwaw", "awdz", "awlq", "tanhua", "meiri-top",
        "cunzhi", "dmtt", "dark-history", "sjb",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    timeout = 15
    page_size = 20

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.base_url
        self.session = requests.Session()
        self._line_checked = False
        self._selecting_line = False

    def getName(self):
        return self.name

    def init(self, extend=''):
        try:
            config = extend if isinstance(extend, dict) else json.loads(extend or '{}')
        except Exception:
            config = {}
        host = str(config.get('host') or config.get('siteUrl') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
            self._line_checked = True
        else:
            self._select_line()
        return None

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def getDependence(self):
        return []

    def homeLayout(self):
        return 0

    def isVideoFormat(self, url):
        return any(x in str(url or '').lower() for x in ('.m3u8', '.mp4', '.m3u', '.mpd'))

    def manualVideoCheck(self):
        return False

    def _decode_publish_page(self, text):
        match = re.search(r"Base64\.decode\(['\"]([^'\"]+)", text or "", re.I)
        if not match:
            return text or ""
        try:
            return base64.b64decode(match.group(1)).decode("utf-8", errors="replace")
        except Exception:
            return text or ""

    def _line_candidates(self):
        candidates = [self.host, self.base_url]
        try:
            response = self.session.get(
                self.site_url + "/", headers=self.headers,
                timeout=8, allow_redirects=True,
            )
            page = self._decode_publish_page(response.content.decode("utf-8", errors="replace"))
            # 发布页直接下发的固定线路，当前主要是 line4Target。
            for host in re.findall(r'line4Target\s*=\s*["\']([a-zA-Z0-9.-]+)', page, re.I):
                if "." in host:
                    candidates.insert(0, "https://" + host.strip("/"))
            # 兼容发布页未来直接输出完整线路链接。
            for host in re.findall(r'https?://([a-zA-Z0-9.-]+)', page, re.I):
                if any(x in host for x in ("gtrazibvz.com", "cloudfront.net", "cvmmahzip.com", "wmwrtmwk.com")):
                    candidates.insert(0, "https://" + host.strip("/"))
        except Exception:
            pass
        # 已验证过的同站线路作为发布页异常时的快速兜底。
        candidates.extend([
            "https://adjust.gtrazibvz.com",
            "https://burden.gtrazibvz.com",
            "https://borrow.gtrazibvz.com",
            "https://bite.gtrazibvz.com",
        ])
        result = []
        for item in candidates:
            item = str(item or "").strip().rstrip("/")
            if item.startswith(("http://", "https://")) and item not in result:
                result.append(item)
        return result

    def _line_alive(self, host):
        try:
            response = self.session.get(
                host + "/", headers=self.headers,
                timeout=6, allow_redirects=True,
            )
            text = response.content.decode("utf-8", errors="replace")
            return response.status_code == 200 and bool(
                re.search(r'/archives/\d+/', text) and "post-card-title" in text
            )
        except Exception:
            return False

    def _select_line(self, force=False):
        if self._selecting_line or (self._line_checked and not force):
            return self.host
        self._selecting_line = True
        try:
            for candidate in self._line_candidates():
                if self._line_alive(candidate):
                    self.host = candidate
                    self._line_checked = True
                    return self.host
            self.host = self.base_url
            self._line_checked = True
            return self.host
        finally:
            self._selecting_line = False

    def _get(self, url, headers=None):
        h = headers or self.headers
        original_host = self.host
        try:
            if not self._line_checked and not self._selecting_line:
                self._select_line()
                if str(url).startswith(original_host):
                    url = self.host + str(url)[len(original_host):]
            resp = self.session.get(url, headers=h, timeout=self.timeout, allow_redirects=True)
            if resp.status_code != 200:
                raise RuntimeError("HTTP %s" % resp.status_code)
            raw = resp.content
            # 尝试从 Content-Type 或 <meta charset> 检测编码
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            if "charset=" in ct:
                charset = ct.split("charset=")[-1].split(";")[0].strip().lower()
            elif b"charset=" in raw[:1024]:
                m = re.search(rb"charset=[\"']?([a-zA-Z0-9-]+)", raw[:1024])
                if m:
                    charset = m.group(1).decode("ascii").lower()
            return raw.decode(charset, errors="replace")
        except Exception as e:
            # 当前线路失效时重新选线，并使用相同路径重试一次。
            try:
                if not self._selecting_line and str(url).startswith(original_host):
                    path = str(url)[len(original_host):]
                    self._line_checked = False
                    self._select_line(force=True)
                    if self.host != original_host:
                        response = self.session.get(
                            self.host + path, headers=h,
                            timeout=self.timeout, allow_redirects=True,
                        )
                        if response.status_code == 200:
                            return response.content.decode("utf-8", errors="replace")
            except Exception:
                pass
            print(f"请求失败: {e}")
            return None

    def _image_url(self, url):
        if not url:
            return ""
        real = urljoin(self.host + "/", unescape(str(url)).replace("\\/", "/"))
        try:
            encoded = base64.urlsafe_b64encode(real.encode("utf-8")).decode("ascii")
            return "%s&url=%s&type=img" % (self.getProxyUrl(), encoded)
        except Exception:
            return real

    def _strip_html(self, text):
        text = unescape(str(text or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_articles(self, html):
        """从列表页 HTML 提取文章卡片"""
        result = []
        if not html:
            return result
        articles = re.findall(r"<article[^>]*>(.*?)</article>", html, re.DOTALL)
        for art in articles:
            # 标题
            title_m = re.search(
                r'<h2[^>]*class="[^"]*post-card-title[^"]*"[^>]*>(.*?)</h2>',
                art,
                re.DOTALL,
            )
            title = self._strip_html(title_m.group(1)) if title_m else ""
            if not title:
                continue
            # 链接
            link_m = re.search(r'href=["\'](?:https?://[^/]+)?(/archives/\d+/)["\']', art, re.I)
            link = link_m.group(1) if link_m else ""
            if not link:
                continue
            # 图片：支持 src/data-src/JS 懒加载
            pic_m = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)', art, re.I)
            if not pic_m:
                pic_m = re.search(r"(?:loadBannerDirect|loadImage)\(['\"]([^'\"]+)", art, re.I)
            pic = self._image_url(pic_m.group(1)) if pic_m else ""
            # 日期
            date_m = re.search(r"(\d{4}\s*年\s*\d{2}\s*月\s*\d{2}\s*日)", art)
            date = date_m.group(1).replace(" ", "") if date_m else ""
            # 分类标签
            cats = re.findall(r"<span[^>]*>([^<]+)</span>", art)
            cat_tag = ""
            for c in cats:
                c = c.strip()
                if c and not c.startswith("•") and "年" not in c and "月" not in c:
                    cat_tag = c
                    break

            result.append(
                {
                    "vod_id": link,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": date or cat_tag or "",
                }
            )
        return result

    def _parse_pagecount(self, html):
        """从分页导航提取总页数"""
        if not html:
            return 1
        m = re.search(r'class=["\'][^"\']*page-current[^"\']*["\'][^>]*>\s*(\d+)\s*/\s*(\d+)', html, re.I)
        if not m:
            m = re.search(r'<span[^>]+class=["\'][^"\']*page-current[^"\']*["\'][^>]*>\s*(\d+)\s*/\s*(\d+)', html, re.I)
        if m:
            try:
                return int(m.group(2))
            except:
                pass
        # fallback: 找最后一页链接
        pages = re.findall(r'href="[^"]*page/(\d+)[^"]*"', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _extract_video_urls(self, html):
        """兼容新版 data-config JSON 与旧版 Base64 DPlayer 变量。"""
        urls = []
        if not html:
            return urls
        seen = set()

        # 新版：每个 data-config 对应网页中的一个播放器，只取一条主播放地址。
        configs = re.findall(r'data-config\s*=\s*(["\'])(.*?)\1', html, re.I | re.S)
        for _, raw in configs:
            try:
                config = json.loads(unescape(raw))
                video = config.get("video") or {}
                url = video.get("url")
                if not url:
                    h265 = config.get("video_h265")
                    if isinstance(h265, dict):
                        url = h265.get("url")
                    elif isinstance(h265, list):
                        url = next((x.get("url") for x in h265 if isinstance(x, dict) and x.get("url")), "")
                url = str(url or "").replace("\\/", "/").replace("\\u0068", "h")
                if url.startswith("http") and url not in seen:
                    seen.add(url)
                    urls.append(url)
            except Exception:
                pass

        # 只有新版播放器完全未解析到时，才扫描全页媒体地址，避免把 H265 备用流算成额外视频。
        if not urls:
            decoded = unescape(html).replace("\\/", "/").replace("\\u0068", "h")
            for url in re.findall(r'["\']url["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)', decoded, re.I):
                if url.startswith("http") and url not in seen:
                    seen.add(url)
                    urls.append(url)

        # 旧版 Base64 仅作为新版结构不存在时的兼容兜底。
        if not urls:
            for _, value in re.findall(r"var\s+dp_video_url(_\d+)?\s*=\s*['\"]([^'\"]+)['\"]", html):
                try:
                    url = base64.b64decode(value).decode("utf-8")
                except Exception:
                    continue
                if url.startswith("//"):
                    url = "https:" + url
                if url.startswith("http") and url not in seen:
                    seen.add(url)
                    urls.append(url)
        return urls

    # ── 五接口 ──────────────────────────────────────────

    def homeContent(self, filter=False):
        classes = [
            {"type_name": name, "type_id": slug}
            for name, slug in zip(self.class_name, self.class_url)
        ]
        videos = []
        try:
            videos = self._extract_articles(self._get(self.host + "/"))
        except Exception:
            pass
        return {"class": classes, "filters": {}, "list": videos}

    def homeVideoContent(self):
        try:
            html = self._get(self.host + "/")
            return {"list": self._extract_articles(html)}
        except Exception as e:
            print(f"首页推荐失败: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        slug = self.class_url[int(tid)] if str(tid).isdigit() and int(tid) < len(self.class_url) else str(tid)
        result = {"list": [], "page": pg, "pagecount": 1, "limit": self.page_size, "total": 0}
        try:
            if pg == 1:
                url = f"{self.host}/category/{slug}/"
            else:
                url = f"{self.host}/category/{slug}/{pg}/"
            html = self._get(url)
            result["list"] = self._extract_articles(html)
            result["pagecount"] = self._parse_pagecount(html)
            result["total"] = result["pagecount"] * self.page_size
        except Exception as e:
            print(f"分类失败: {e}")
        return result

    def detailContent(self, ids):
        result = []
        try:
            vod_id = ids if isinstance(ids, str) else (ids[0] if ids else "")
            if not vod_id:
                return result
            if not vod_id.startswith("http"):
                url = self.host + vod_id
            else:
                url = vod_id
            html = self._get(url)
            if not html:
                return result

            # 标题
            title_m = re.search(r"<h1[^>]*class=\"[^\"]*post-title[^\"]*\"[^>]*>(.*?)</h1>", html, re.DOTALL)
            title = self._strip_html(title_m.group(1)) if title_m else ""

            # 图片
            pic_m = re.search(r"<meta\s+property=\"og:image\"\s+content=\"([^\"]+)\"", html)
            pic = self._image_url(pic_m.group(1)) if pic_m else ""

            # 日期
            date_m = re.search(r"<li[^>]*>\s*(\d{4}\s*年\s*\d{2}\s*月\s*\d{2}\s*日)", html)
            date = date_m.group(1).replace(" ", "") if date_m else ""

            # 分类
            cat_m = re.findall(r'<a[^>]+href="/category/[^"]+"[^>]*>([^<]+)</a>', html)
            cat = cat_m[0] if cat_m else ""

            # 描述
            desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            desc = desc_m.group(1)[:200] if desc_m else ""

            # 视频
            video_urls = self._extract_video_urls(html)

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_year": date[:4] if len(date) >= 4 else "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_type": cat,
                "vod_remarks": date,
                "vod_content": desc,
            }

            if video_urls:
                lines = []
                for i, vurl in enumerate(video_urls):
                    lines.append(f"视频{i+1}${vurl}")
                vod["vod_play_from"] = "51暗网"
                vod["vod_play_url"] = "#".join(lines)
            else:
                vod["vod_play_from"] = "51暗网"
                vod["vod_play_url"] = ""

            return {"list": [vod]}
        except Exception as e:
            print(f"详情失败: {e}")
        return {"list": []}

    def searchContent(self, key, pg, filter=False):
        pg = int(pg) if pg else 1
        result = {"list": [], "page": pg, "pagecount": 1, "limit": self.page_size, "total": 0}
        if not key:
            return result
        try:
            if pg == 1:
                url = f"{self.host}/search/{quote(str(key), safe='')}/"
            else:
                url = f"{self.host}/search/{quote(str(key), safe='')}/{pg}/"
            html = self._get(url)
            result["list"] = self._extract_articles(html)
            result["pagecount"] = self._parse_pagecount(html)
            result["total"] = result["pagecount"] * self.page_size
        except Exception as e:
            print(f"搜索失败: {e}")
        return result

    def _decrypt_image(self, data):
        if not data or data.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8", b"RIFF")):
            return data
        keys = (
            (b"f5d965df75336270", b"97b60394abc2fbe1"),
            (b"75336270f5d965df", b"abc2fbe197b60394"),
        )
        for key, iv in keys:
            try:
                decoded = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data), 16)
                if decoded.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8", b"RIFF")):
                    return decoded
            except Exception:
                pass
            try:
                decoded = unpad(AES.new(key, AES.MODE_ECB).decrypt(data), 16)
                if decoded.startswith((b"\xff\xd8", b"\x89PNG", b"GIF8", b"RIFF")):
                    return decoded
            except Exception:
                pass
        return data

    def _image_mime(self, data, url=""):
        if data.startswith(b"\xff\xd8"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG"):
            return "image/png"
        if data.startswith(b"GIF8"):
            return "image/gif"
        if data.startswith(b"RIFF"):
            return "image/webp"
        clean_url = str(url).lower().split("?", 1)[0]
        return "image/png" if clean_url.endswith(".png") else "image/jpeg"

    def localProxy(self, param):
        try:
            if str(param.get("type") or "") != "img":
                return [404, "text/plain", b""]
            encoded = str(param.get("url") or "")
            if not encoded:
                return [404, "text/plain", b""]
            try:
                url = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
            except Exception:
                url = encoded
            headers = dict(self.headers)
            headers["Referer"] = self.host + "/"
            response = self.session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            if response.status_code != 200:
                return [response.status_code, "text/plain", b""]
            content = self._decrypt_image(response.content)
            content_type = self._image_mime(content, url)
            return [200, content_type, content]
        except Exception:
            return [404, "text/plain", b""]

    def playerContent(self, flag, id, vipFlags=None):
        try:
            # 直接媒体 URL
            if ".m3u8" in id or ".mp4" in id:
                return {
                    "parse": 0,
                    "url": id,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    },
                }
            # 详情页 URL — 二次提取
            if id.startswith("http") or id.startswith("/"):
                if not id.startswith("http"):
                    url = self.host + id
                else:
                    url = id
                html = self._get(url)
                if html:
                    video_urls = self._extract_video_urls(html)
                    if video_urls:
                        return {
                            "parse": 0,
                            "url": video_urls[0],
                            "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    },
                        }
            return {"parse": 1, "url": id, "header": {}}
        except Exception as e:
            print(f"播放失败: {e}")
            return {"parse": 1, "url": id, "header": {}}

# coding: utf-8
# 酒与花 - TVBox爬虫
# 站点: https://caywfd.jyh9.yachts/
# 分类ID: 20自拍视频 21强奸乱伦 22无码视频 23有码视频 24人妻熟女 25制服诱惑 26口交颜射 27SM重味 28日韩视频 29欧美视频 30动漫视频 31伦理影片

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://caywfd.jyh9.yachts"
        self.site_name = "酒与花"
        
        self.classes = [
            {"type_id": "20", "type_name": "自拍视频"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "无码视频"},
            {"type_id": "23", "type_name": "有码视频"},
            {"type_id": "24", "type_name": "人妻熟女"},
            {"type_id": "25", "type_name": "制服诱惑"},
            {"type_id": "26", "type_name": "口交颜射"},
            {"type_id": "27", "type_name": "SM重味"},
            {"type_id": "28", "type_name": "日韩视频"},
            {"type_id": "29", "type_name": "欧美视频"},
            {"type_id": "30", "type_name": "动漫视频"},
            {"type_id": "31", "type_name": "伦理影片"},
        ]
        
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "酒与花"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/cn/home/web/")
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/vodtype/{tid}.html"
        if pg != "1":
            url = f"{self.host}/vodtype/{tid}-{pg}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html) or 99
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]) if isinstance(ids, list) else str(ids)
        
        detail_url = f"{self.host}/{vid}.html"
        html = self._fetch_html(detail_url)
        
        title = self._extract_title(html) or f"视频{vid}"
        play_url = self._extract_m3u8_from_html(html)
        
        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${detail_url}",
            }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/s/index.html"
        data = f"wd={quote(key)}"
        html = self._post_html(url, data)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(id), 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        
        if id and id.startswith("http"):
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0, 
                    "url": self._m3u8_proxy_url(play_url), 
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": id, "header": self.headers}
        
        detail_url = f"{self.host}/{id}.html"
        html = self._fetch_html(detail_url)
        play_url = self._extract_m3u8_from_html(html)
        if play_url:
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(play_url), 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        return {"parse": 1, "url": detail_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = urllib.parse.unquote(str(target or ""))
            
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            
            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 第1层：图片流伪装检测（分片为 .jpg/.png 等）
        has_image_ext = False
        for line in lines:
            if line and not line.startswith("#"):
                low = line.lower().split("?")[0]
                if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    has_image_ext = True
                    break
        
        if has_image_ext:
            # 还原扩展名，但保留KEY信息
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts")
            # 继续后续过滤
            text = restored
            lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
            if not lines:
                return "#EXTM3U\n"
        
        # 第2层：多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        # 第3层：正片目录锚点（优先KEY URI目录）
        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"
        
        main_dir = source_dir
        key_uri = None
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    key_uri = m.group(1)
                    key_path = urllib.parse.urlparse(
                        key_uri if key_uri.startswith("http") else urllib.parse.urljoin(source_url, key_uri)
                    ).path
                    key_dir = posixpath.dirname(key_path)
                    if key_dir and key_dir != "/":
                        main_dir = key_dir + "/"
                        break
        
        # 第4层：分片过滤
        segments = []
        pending = []
        removed = 0
        kept = 0
        key_line = None
        
        for line in lines:
            # 保留KEY行
            if line.startswith("#EXT-X-KEY"):
                key_line = self._rewrite_m3u8_tag(line, source_url)
                segments.append(key_line)
                continue
            
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                # 判断是否正片：路径以main_dir开头 或 包含KEY目录
                if media_parsed.path.startswith(main_dir) or main_dir in media_parsed.path:
                    # 重写分片地址为绝对地址
                    for p in pending:
                        if p.startswith("#EXTINF"):
                            segments.append(p)
                        else:
                            segments.append(self._rewrite_m3u8_tag(p, source_url))
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)
        
        # 第5层：全滤兜底
        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"
        
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
        
        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _post_html(self, url, data):
        try:
            resp = self.post(url, data=data, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        
        # 匹配 .thumb 卡片
        thumb_pattern = r'<div[^>]*class="[^"]*thumb[^"]*"[^>]*>(.*?)</div>\s*</div>'
        thumb_blocks = re.findall(thumb_pattern, html, re.DOTALL)
        
        for block in thumb_blocks:
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', block)
            if not link_match:
                continue
            link = link_match.group(1)
            
            img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', block)
            pic = img_match.group(1) if img_match else ""
            
            title_match = re.search(r'<span[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</span>', block)
            if not title_match:
                title_match = re.search(r'title="([^"]+)"', block)
            if not title_match:
                continue
            title = title_match.group(1).strip()
            
            vid_match = re.search(r'/(\d+)\.html$', link)
            if vid_match:
                vid = vid_match.group(1)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        
        if not items:
            pattern = r'<a[^>]*href="/(\d+)\.html"[^>]*title="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>'
            matches = re.findall(pattern, html, re.DOTALL)
            for vid, title, pic in matches:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*href="[^"]*page[^"]*"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            nums = [int(m) for m in matches]
            return max(nums)
        return 1

    def _extract_title(self, html):
        if not html:
            return None
        pattern = r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return None

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r'const\s+rawUrl\s*=\s*[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]'
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            if url.startswith("http"):
                return url
        pattern2 = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        match2 = re.search(pattern2, html)
        if match2:
            return match2.group(0)
        return None

    def siteInfo(self):
        return {
            "name": "酒与花",
            "host": self.host,
            "content_type": "影视",
            "description": "成人影视聚合站",
            "last_verified": "2026-08-31",
            "source": "用户提供"
        }
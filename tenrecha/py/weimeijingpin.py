# coding: utf-8
# 唯美精品 - TVBox/FongMi 爬虫
# 站点: https://shiresm.lol/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://shiresm.lol"
        self.site_name = "唯美精品"
        self.classes = [
            {"type_id": "1", "type_name": "国产乱伦"},
            {"type_id": "2", "type_name": "制服诱惑"},
            {"type_id": "3", "type_name": "中文字幕"},
            {"type_id": "4", "type_name": "精品推荐"},
            {"type_id": "5", "type_name": "成人动漫"},
            {"type_id": "6", "type_name": "日韩专区"},
            {"type_id": "7", "type_name": "国产高清"},
            {"type_id": "8", "type_name": "欧美极品"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_video_list(html, is_home=True)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
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
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        
        # 请求详情页获取标题
        detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(detail_url)
        
        # 提取标题
        title = f"视频{vid}"
        if html:
            # 从title标签提取
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                full_title = title_match.group(1)
                # 去掉"详情介绍"、"在线观看"、"迅雷下载"等后缀
                for suffix in ["详情介绍", "在线观看", "迅雷下载", " - 唯美精品"]:
                    full_title = full_title.replace(suffix, "")
                # 取第一个有效片段
                parts = full_title.split("-")
                if parts:
                    title = parts[0].strip()
                    if not title:
                        title = f"视频{vid}"
        
        # 提取封面图片
        pic = ""
        if html:
            pic_match = re.search(r'<img[^>]*class="[^"]*video-pic[^"]*"[^>]*data-original="([^"]+)"', html)
            if not pic_match:
                pic_match = re.search(r'property="og:image"\s+content="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1)
                if not pic.startswith("http"):
                    pic = self.host + pic
        
        # 提取备注
        remark = ""
        if html:
            remark_match = re.search(r'<span[^>]*class="[^"]*note[^"]*"[^>]*>([^<]+)</span>', html)
            if remark_match:
                remark = remark_match.group(1).strip()
        
        # 构造播放URL
        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        # 如果id是m3u8链接，直接返回
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        # 如果id是播放页URL，提取m3u8
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
        # 如果id是vod_id，构造播放页URL
        play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
        html = self._fetch_html(play_url)
        m3u8_url = self._extract_m3u8_from_html(html)
        if m3u8_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(m3u8_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        return {"parse": 1, "url": play_url, "header": self.headers}

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
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urlencode(params)
            else:
                full_url = url + "?" + urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _parse_video_list(self, html, is_home=False):
        items = []
        if not html:
            return items

        # 首页和分类页结构略有不同，但核心相同
        # 使用更通用的正则：匹配 li 标签内的视频卡片
        pattern = r'<li[^>]*class="[^"]*col-md-2[^"]*"[^>]*>.*?<a[^>]*href="[^"]*detail/id/(\d+)\.html"[^>]*>.*?<a[^>]*class="video-pic[^"]*"[^>]*data-original="([^"]+)"[^>]*>.*?<h5[^>]*>.*?<a[^>]*title="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for vid, pic, title_full, title in matches:
            if vid and title:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic if pic.startswith("http") else self.host + pic,
                    "vod_remarks": ""
                })
        return items
    def _parse_page_count(self, html):
        if not html:
            return 1
        # 从分页区域提取总页数
        pattern = r'共\s*(\d+)\s*条数据,当前\s*(\d+)\s*/\s*(\d+)\s*页'
        match = re.search(pattern, html)
        if match:
            return int(match.group(3))
        return 1

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        # 方法1: 从 player_aaaa 中提取
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except:
                pass
        # 方法2: 直接提取url字段
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                return url
        # 方法3: 查找任何m3u8链接
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None

    def destroy(self):
        pass

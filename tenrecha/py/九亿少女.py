# coding: utf-8
# 九亿少女 - TVBox/FongMi 爬虫源
# 站点: https://dmm.jysn3.mom/cn/home/web/
# 类型: MacCMS 标准影视站

import re
import json
import urllib.parse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://dmm.jysn3.mom"
        self.site_name = "九亿少女"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "*/*",
        }
        
        # 分类列表（从首页导航提取）
        self.classes = [
            {"type_id": "20", "type_name": "美女写真"},
            {"type_id": "21", "type_name": "国产精品"},
            {"type_id": "22", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "中文字幕"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "亚洲情色"},
            {"type_id": "27", "type_name": "制服丝袜"},
            {"type_id": "28", "type_name": "SM捆绑"},
            {"type_id": "29", "type_name": "自淫系列"},
            {"type_id": "30", "type_name": "三级伦理"},
        ]
        self.filters = {}

    def getName(self):
        return "九亿少女"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从最近更新获取"""
        html = self._fetch_html(f"{self.host}/cn/home/web/")
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表"""
        pg = str(pg) if pg else "1"
        url = f"{self.host}/cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html"
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
        """详情页"""
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        
        detail_url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(detail_url)
        
        title = self._extract_title(html) or f"视频{vid}"
        pic = self._extract_pic(html) or ""
        play_url = self._extract_m3u8_from_html(html)
        
        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            # 降级：返回详情页URL
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${detail_url}",
            }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        """搜索 - 使用专门解析逻辑"""
        pg = str(pg) if pg else "1"
        kw = urllib.parse.quote(key.strip())
        url = f"{self.host}/cn/home/web/index.php/vod/search/page/{pg}/wd/{kw}.html"
        html = self._fetch_html(url)
        items = self._parse_search_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, vid, vipFlags):
        """播放 - 直接返回子m3u8代理URL，减少请求链路"""
        m3u8_url = None
        
        # 如果传入的是m3u8地址
        if vid and vid.startswith("http") and ".m3u8" in vid:
            m3u8_url = vid
        
        # 如果传入的是数字ID
        if not m3u8_url and vid and vid.isdigit():
            detail_url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            html = self._fetch_html(detail_url)
            m3u8_url = self._extract_m3u8_from_html(html)
        
        if m3u8_url:
            # 检测是否是多码率索引，如果是则直接提取子m3u8
            final_url = self._get_final_m3u8_url(m3u8_url)
            if final_url:
                proxy_url = self._m3u8_proxy_url(final_url)
                return {
                    "parse": 0,
                    "url": proxy_url,
                    "header": self.headers
                }
            # 如果提取子m3u8失败，使用原始URL
            proxy_url = self._m3u8_proxy_url(m3u8_url)
            return {
                "parse": 0,
                "url": proxy_url,
                "header": self.headers
            }
        
        # 降级
        if vid and vid.isdigit():
            detail_url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            return {"parse": 1, "url": detail_url, "header": self.headers}
        return {"parse": 1, "url": vid, "header": self.headers}

    def recommendContent(self, ids, pg="1"):
        """相关推荐"""
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        detail_url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(detail_url)
        items = self._parse_recommend_list(html)
        return {"list": items}

    def getProxyUrl(self):
        """获取代理服务器地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """将m3u8 URL转换为代理URL"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")
    def destroy(self):
        pass
    def localProxy(self, param):
        """m3u8广告过滤代理 + KEY文件透传"""
        import urllib.parse
        import posixpath
        
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            
            # 解析代理参数
            if target.startswith("url="):
                target = target[4:]
            if "?do=py&url=" in target:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = urllib.parse.unquote(str(target or ""))
            
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            
            # 构建完整的请求头（防盗链）
            fetch_headers = {
                "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
                "Referer": self.host,
                "Origin": self.host,
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
            
            # 如果是KEY文件请求，直接透传
            if target.endswith(".key") or target.endswith(".bin") or "/key.key" in target:
                resp = self.fetch(target, headers=fetch_headers, timeout=15)
                if not resp:
                    return [502, "text/plain", b"key fetch failed"]
                content = getattr(resp, "content", b"") or b""
                if not content and hasattr(resp, "text") and resp.text:
                    content = resp.text.encode("utf-8", errors="ignore")
                if not content:
                    return [502, "text/plain", b"key empty"]
                return [200, "application/octet-stream", content]
            
            # 获取m3u8内容
            resp = self.fetch(target, headers=fetch_headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            
            if not content:
                return [502, "text/plain", b"empty content"]
            
            # 检查是否为m3u8
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            # 非m3u8内容，直接返回
            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith(".jpg") or target.endswith(".png"):
                content_type = "image/jpeg"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            elif target.endswith(".key") or target.endswith(".bin"):
                content_type = "application/octet-stream"
            return [200, content_type, content]
            
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """过滤m3u8广告分片 - 使用技能包标准实现"""
        import posixpath
        import urllib.parse
        
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 检查是否为多码率
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        # 单码率过滤 - 使用技能包标准方法
        parsed = urllib.parse.urlparse(source_url)
        dir_path = posixpath.dirname(parsed.path)
        if not dir_path.endswith('/'):
            dir_path += '/'
        
        def is_valid_segment(url):
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.path.startswith(dir_path)
        
        result = []
        pending_extinf = []
        removed = 0
        kept = 0
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # 处理KEY标签 - 直接保留并补全URI
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                line = self._rewrite_m3u8_tag(line, source_url)
                result.append(line)
                i += 1
                continue
            
            # 跳过DISCONTINUITY（广告标记）
            if "#EXT-X-DISCONTINUITY" in line:
                i += 1
                continue
            
            # 处理EXTINF
            if line.startswith("#EXTINF"):
                pending_extinf = [line]
                i += 1
                # 收集后续的标签（如#EXT-X-DISCONTINUITY）
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.startswith("#"):
                        # 如果是DISCONTINUITY，跳过
                        if "#EXT-X-DISCONTINUITY" in next_line:
                            i += 1
                            continue
                        pending_extinf.append(next_line)
                        i += 1
                    else:
                        # 分片URL
                        media_url = urllib.parse.urljoin(source_url, next_line)
                        if is_valid_segment(media_url):
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                            kept += 1
                        else:
                            removed += 1
                        i += 1
                        break
                continue
            
            # 普通行直接保留
            if line and not line.startswith("#") and not line.startswith("#EXT"):
                # 单独的分片URL（没有EXTINF）
                media_url = urllib.parse.urljoin(source_url, line)
                if is_valid_segment(media_url):
                    result.append(media_url)
                    kept += 1
                else:
                    removed += 1
                i += 1
                continue
            
            result.append(line)
            i += 1
        
        if removed:
            self.log(f"九亿少女 m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
        
        return "\n".join(result) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI为绝对路径"""
        import urllib.parse
        
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

    # ============================================================
    # 内部辅助函数
    # ============================================================

    def _fetch_html(self, url, params=None):
        """发送HTTP请求"""
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urllib.parse.urlencode(params)
            else:
                full_url = url + "?" + urllib.parse.urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "text"):
                return resp.text
        except Exception as e:
            pass
        return ""

    def _parse_video_list(self, html):
        """解析视频列表"""
        items = []
        if not html:
            return items
        
        # 匹配视频卡片
        pattern = r'<a class="fed-list-pics[^"]*" href="([^"]+)" data-original="([^"]+)"[^>]*>.*?<a class="fed-list-title[^"]*" href="[^"]+"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        if not matches:
            # 备用匹配
            pattern2 = r'<a class="fed-list-pics[^"]*" href="([^"]+)" data-original="([^"]+)"[^>]*>'
            href_matches = re.findall(pattern2, html)
            for href, pic in href_matches:
                # 提取标题
                title_pattern = r'<a class="fed-list-title[^"]*" href="[^"]+"[^>]*>(.*?)</a>'
                title_match = re.search(title_pattern, html[html.find(href):html.find(href)+500])
                if title_match:
                    title = title_match.group(1).strip()
                    # 提取ID
                    vid = re.search(r'/id/(\d+)/', href)
                    if vid:
                        items.append({
                            "vod_id": vid.group(1),
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": ""
                        })
            return items
        
        for href, pic, title in matches:
            # 提取ID
            vid_match = re.search(r'/id/(\d+)/', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title:
                continue
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        
        return items
    def _parse_search_list(self, html):
        """解析搜索列表 - 搜索页面结构不同"""
        items = []
        if not html:
            return items
        
        # 搜索页面使用不同的HTML结构
        # 匹配: <a href=".../vod/play/id/XXX/..." data-original="封面图">
        pattern = r'<a[^>]+href="([^"]*\/vod\/play\/id/(\d+)[^"]*)"[^>]*>.*?data-original="([^"]+)"[^>]*>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        if not matches:
            return items
        
        for href, vid, pic in matches:
            # 提取标题（在链接附近）
            # 查找标题：<a class="fed-list-title" href="...">标题</a>
            title_pattern = r'<a[^>]+class="[^"]*fed-list-title[^"]*"[^>]+href="[^"]*"/id/' + vid + r'/[^"]*"[^>]*>(.*?)</a>'
            title_match = re.search(title_pattern, html, re.DOTALL)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            else:
                # 备用：从链接文本提取
                title = ""
                link_pattern = r'<a[^>]+href="[^"]*/id/' + vid + r'/[^"]+"[^>]*>(.*?)</a>'
                link_match = re.search(link_pattern, html, re.DOTALL)
                if link_match:
                    title = re.sub(r'<[^>]+>', '', link_match.group(1)).strip()
            
            if not title:
                continue
            
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        
        return items
    def _get_final_m3u8_url(self, m3u8_url):
        """从多码率索引中提取子m3u8 URL"""
        try:
            resp = self.fetch(m3u8_url, headers=self.headers, timeout=10)
            if not resp or not resp.text:
                return None
            content = resp.text
            # 检查是否是多码率索引
            if '#EXT-X-STREAM-INF' in content:
                # 提取第一个子m3u8 URL
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and '.m3u8' in line:
                        # 补全URL
                        if line.startswith('/'):
                            parsed = urllib.parse.urlparse(m3u8_url)
                            base = f"{parsed.scheme}://{parsed.netloc}"
                            return base + line
                        elif line.startswith('http'):
                            return line
                        else:
                            base_url = m3u8_url[:m3u8_url.rfind('/')+1]
                            return urllib.parse.urljoin(base_url, line)
                # 如果没有找到子m3u8，返回原URL
                return m3u8_url
            # 不是多码率索引，直接返回
            return m3u8_url
        except Exception as e:
            return m3u8_url

    def _parse_recommend_list(self, html):
        """解析相关推荐"""
        items = []
        if not html:
            return items
        
        # 查找相关推荐区域
        block_match = re.search(r'<h2 class="fed-font-xvi">相关热播</h2>.*?<ul class="fed-list-info[^"]*">(.*?)</ul>', html, re.DOTALL)
        if not block_match:
            return items
        
        block_html = block_match.group(1)
        pattern = r'<a class="fed-list-pics[^"]*" href="([^"]+)" data-original="([^"]+)"[^>]*>.*?<a class="fed-list-title[^"]*" href="[^"]+"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, block_html, re.DOTALL)
        
        for href, pic, title in matches:
            vid_match = re.search(r'/id/(\d+)/', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title:
                continue
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        
        return items[:10]

    def _parse_page_count(self, html):
        """解析总页数"""
        if not html:
            return 1
        
        # 从分页导航提取
        m = re.search(r'共\s*(\d+)\s*个影片', html)
        if m:
            total = int(m.group(1))
            return (total + 19) // 20
        
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        
        # 查找页码链接
        matches = re.findall(r'href="[^"]*/page/(\d+)\.html"', html)
        if matches:
            pages = [int(p) for p in matches if p.isdigit()]
            if pages:
                return max(pages)
        
        return 1

    def _extract_title(self, html):
        """提取标题"""
        if not html:
            return None
        # 从title标签提取
        m = re.search(r'<title>([^<]+)</title>', html)
        if m:
            title = m.group(1).strip()
            # 去除后缀
            title = re.sub(r'\s*第\d+集.*$', '', title)
            title = re.sub(r'\s*[-—]\s*(?:国产精品|九亿少女).*$', '', title)
            return title
        return None

    def _extract_pic(self, html):
        """提取封面图"""
        if not html:
            return None
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            return m.group(1)
        return None

    def _extract_m3u8_from_html(self, html):
        """从HTML中提取m3u8播放地址"""
        if not html:
            return None
        
        # 方法1: player_data 对象 (可能包含转义斜杠)
        # 匹配 var player_data={...} 或 var player_data = {...}
        m = re.search(r'var\s+player_data\s*=\s*(\{[^;]+\});', html, re.DOTALL)
        if m:
            try:
                # 处理转义的斜杠
                json_str = m.group(1)
                json_str = json_str.replace('\\/', '/')
                data = json.loads(json_str)
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except:
                pass
        
        # 方法2: 直接查找m3u8链接 (可能被转义)
        m = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if m:
            return m.group(0)
        
        # 方法3: 查找被转义的m3u8链接 (\/)
        m = re.search(r'https?:\\/\\/[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if m:
            return m.group(0).replace('\\/', '/')
        
        return None

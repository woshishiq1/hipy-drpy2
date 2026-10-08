# coding: utf-8
# 水兰亭 - TVBox/FongMi 爬虫源
# 站点: https://eij.slt8.boats/slt/
# 类型: 成人影视聚合站

import re
import urllib.parse
import json
from urllib.parse import quote, urljoin, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        # 注意：host不需要包含/slt/，因为视频ID直接跟在域名后面
        self.host = "https://eij.slt8.boats/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent,
            "Referer": self.host + "/",
            "Accept": "*/*",
        }
        
        # 分类列表
        self.classes = [
            {"type_id": "20", "type_name": "自拍偷拍"},
            {"type_id": "21", "type_name": "巨乳波霸"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "人妻熟女"},
            {"type_id": "24", "type_name": "制服丝袜"},
            {"type_id": "25", "type_name": "花季少女"},
            {"type_id": "26", "type_name": "无码露毛"},
            {"type_id": "27", "type_name": "群P多人"},
            {"type_id": "28", "type_name": "人兽人妖"},
            {"type_id": "29", "type_name": "男同女同"},
            {"type_id": "30", "type_name": "韩日专区"},
            {"type_id": "31", "type_name": "欧美色情"},
            {"type_id": "32", "type_name": "成人动漫"},
            {"type_id": "33", "type_name": "三级剧情"},
        ]
        self.filters = {}

    def getName(self):
        return "水兰亭"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        # 域名可能变化，从extend中获取备用域名
        if extend and isinstance(extend, str):
            if extend.startswith("http"):
                self.host = extend.rstrip("/") + "/"

    def homeContent(self, filter=False):
        return {
            "class": self.classes,
            "filters": self.filters if filter else {}
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 使用分类数据作为推荐"""
        # 尝试从首页获取
        html = self._fetch(self.host)
        items = self._parse_video_list(html)
        
        # 如果首页没有数据，从第一个分类获取
        if not items:
            # 使用分类20（自拍偷拍）的第一页作为推荐
            result = self.categoryContent("20", "1", False, "")
            items = result.get("list", [])
        
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表"""
        if not tid:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        
        page = int(pg) if pg and str(pg).isdigit() else 1
        
        # 修复：使用正确的URL格式 vodtype/{tid}-{page}.html
        url = f"{self.host}vodtype/{tid}-{page}.html"
        
        html = self._fetch(url)
        
        # 如果分类页返回404，尝试使用首页数据兜底
        if not html or "404" in html or len(html) < 100:
            home_html = self._fetch(self.host)
            items = self._parse_video_list(home_html)
            return {
                "list": items[:20],
                "page": page,
                "pagecount": 10,
                "limit": 20,
                "total": 200
            }
        
        items = self._parse_video_list(html)
        pagecount = self._parse_page_count(html) if html else 1
        
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        """详情页"""
        if not ids or len(ids) == 0:
            return {"list": []}
        
        vid = str(ids[0])
        # 修复：详情页URL格式为 /数字.html
        url = f"{self.host}{vid}.html"
        
        html = self._fetch(url)
        
        if not html or len(html) < 100:
            return {"list": []}
        
        # 提取信息
        title = self._extract_title(html)
        pic = self._extract_pic(html)
        play_url = self._extract_play_url(html)
        desc = self._extract_desc(html)
        publish_date = self._extract_date(html)
        category = self._extract_category(html)
        
        # 确保有标题
        if not title:
            # 尝试从og:title获取
            m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
            if m:
                title = m.group(1).strip()
        
        # 确保有封面
        if not pic:
            m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if m:
                pic = m.group(1)
        
        # 构建vod对象
        vod = {
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_content": desc or "",
            "vod_remarks": publish_date or "",
            "vod_play_from": "水兰亭",
            "vod_play_url": f"播放${play_url}" if play_url else ""
        }
        
        # 如果有播放地址但未正确设置，确保格式正确
        if play_url and not vod["vod_play_url"]:
            vod["vod_play_url"] = f"播放${play_url}"
        
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        if not key:
            return {"list": [], "page": 1}
        
        page = int(pg) if str(pg).isdigit() else 1
        kw = quote(key.strip())
        
        if page == 1:
            url = f"{self.host}s/index.html?wd={kw}"
        else:
            url = f"{self.host}s/index_{page}.html?wd={kw}"
        
        html = self._fetch(url)
        items = self._parse_video_list(html)
        
        return {"list": items, "page": page}

    def playerContent(self, flag, vid, vipFlags):
        """播放 - 使用代理URL触发localProxy广告过滤"""
        import urllib.parse
        
        m3u8_url = None
        
        # 如果 vid 本身就是 m3u8 地址
        if vid and (vid.endswith(".m3u8") or ".m3u8" in vid):
            m3u8_url = vid
        
        # 如果vid是数字ID，从详情页提取
        if not m3u8_url and vid and vid.isdigit():
            url = f"{self.host}{vid}.html"
            html = self._fetch(url)
            m3u8_url = self._extract_play_url(html) if html else ""
        
        if m3u8_url:
            # 使用代理URL，让localProxy处理广告过滤
            proxy_url = self._m3u8_proxy_url(m3u8_url)
            return {
                "parse": 0,
                "url": proxy_url,
                "header": {
                    "User-Agent": self.user_agent,
                    "Referer": self.host
                }
            }
        
        # 降级
        return {
            "parse": 1, 
            "url": f"{self.host}{vid}.html" if vid else "",
            "header": {
                "User-Agent": self.user_agent,
                "Referer": self.host
            }
        }

    def recommendContent(self, ids, pg="1"):
        """相关推荐"""
        if not ids or len(ids) == 0:
            return {"list": []}
        
        vid = str(ids[0])
        url = f"{self.host}{vid}.html"
        html = self._fetch(url)
        
        if not html:
            return {"list": []}
        
        items = self._parse_recommend_list(html)
        return {"list": items}

    def localProxy(self, param):
        """m3u8广告过滤代理 - 参考AV居委会实现"""
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
            
            # 获取m3u8内容
            resp = self.fetch(target, headers=self.headers, timeout=20)
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
            return [200, content_type, content]
            
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")]
    
    def _filter_m3u8(self, url):
        """获取并过滤单个m3u8"""
        try:
            resp = self.fetch(url, headers={
                "User-Agent": self.user_agent,
                "Referer": self.host
            }, timeout=15)
            if resp and resp.text:
                return self._filter_m3u8_content(resp.text, url)
        except:
            pass
        return None
    
    def _filter_m3u8_content(self, content, url):
        """过滤m3u8内容，从第一个正片分片开始，移除广告和DISCONTINUITY"""
        import re
        from urllib.parse import urlparse
        
        if not content:
            return None
        
        # 提取正片目录前缀
        path = urlparse(url).path
        ad_prefix = None
        path_parts = path.split('/')
        for i, part in enumerate(path_parts):
            if re.match(r'^\d{8}$', part) and i + 1 < len(path_parts):
                ad_prefix = f"/{part}/{path_parts[i+1]}/"
                break
        
        if not ad_prefix:
            last_slash = path.rfind('/')
            if last_slash > 0:
                ad_prefix = path[:last_slash+1]
            else:
                ad_prefix = "/"
        
        lines = content.split('\n')
        filtered_lines = []
        
        # 先保留头部信息 (EXTM3U, EXT-X-VERSION, EXT-X-TARGETDURATION, EXT-X-PLAYLIST-TYPE, EXT-X-MEDIA-SEQUENCE, EXT-X-KEY)
        # 但跳过EXTINF和分片，直到找到正片
        header_lines = []
        found_first_video = False
        video_start_index = -1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 保留头部信息（不以EXTINF开头的EXT标签）
            if line.startswith('#') and not line.startswith('#EXTINF:') and not '#EXT-X-DISCONTINUITY' in line:
                if not found_first_video:
                    header_lines.append(lines[i])
                else:
                    filtered_lines.append(lines[i])
                i += 1
                continue
            
            # 如果是EXTINF，需要检查下一个分片是否正片
            if line.startswith('#EXTINF:'):
                # 检查下一行
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('#'):
                        # 检查是否是正片分片
                        if ad_prefix in next_line:
                            # 找到正片！
                            if not found_first_video:
                                found_first_video = True
                                # 添加所有头部信息
                                filtered_lines = header_lines.copy()
                                # 添加EXTINF
                                filtered_lines.append(lines[i])
                                # 添加分片
                                filtered_lines.append(lines[i + 1])
                            else:
                                filtered_lines.append(lines[i])
                                filtered_lines.append(lines[i + 1])
                            i += 2
                            continue
                # 广告分片，跳过
                i += 2
                continue
            
            # 空行处理
            if line == '':
                if found_first_video:
                    filtered_lines.append(lines[i])
                i += 1
                continue
            
            # 其他行（通常是分片URL单独出现）
            if line and not line.startswith('#'):
                if ad_prefix in line:
                    if not found_first_video:
                        found_first_video = True
                        filtered_lines = header_lines.copy()
                        # 需要补充EXTINF? 但单独分片没有EXTINF，直接添加
                        filtered_lines.append(lines[i])
                    else:
                        filtered_lines.append(lines[i])
                i += 1
                continue
            
            i += 1
        
        # 如果没找到正片，返回None
        if not found_first_video:
            return None
        
        return '\n'.join(filtered_lines)
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
    def _clean_m3u8(self, text, source_url):
        """过滤m3u8广告分片 - 参考AV居委会实现"""
        import posixpath
        import urllib.parse
        
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 处理多码率m3u8
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        # 提取正片目录前缀
        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"
        
        main_dir = source_dir
        # 从KEY中提取真实目录
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
        removed = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXTINF"):
                pending = [line]
                i += 1
                # 收集后续EXT标签
                while i < len(lines) and lines[i].startswith("#") and not lines[i].startswith("#EXTINF:"):
                    pending.append(lines[i])
                    i += 1
                if i < len(lines):
                    media_url = urllib.parse.urljoin(source_url, lines[i])
                    # 检查是否正片
                    if main_dir in media_url or media_url.startswith("http") and main_dir in urllib.parse.urlparse(media_url).path:
                        segments.extend(pending)
                        segments.append(media_url)
                    else:
                        removed += 1
                    i += 1
                continue
            
            if not line.startswith("#") and line.strip():
                # 单独的分片URL
                media_url = urllib.parse.urljoin(source_url, line)
                if main_dir in media_url or media_url.startswith("http") and main_dir in urllib.parse.urlparse(media_url).path:
                    segments.append(media_url)
                else:
                    removed += 1
                i += 1
                continue
            
            segments.append(line)
            i += 1
        
        if removed:
            self.log(f"水兰亭 m3u8已过滤广告分片: {removed}个")
        
        # 重写KEY URI
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            # 移除孤立的DISCONTINUITY
            if line in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        
        # 清理末尾
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()
        
        return "\n".join(out) + "\n"

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

    def _fetch(self, url):
        """发送请求"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://eij.slt8.boats/slt/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
            }
            resp = self.fetch(url, headers=headers, timeout=15)
            if resp and hasattr(resp, "text"):
                return resp.text
            return ""
        except Exception as e:
            self.log({"action": "fetch_error", "url": url, "error": str(e)})
            return ""

    def _parse_video_list(self, html):
        """解析视频列表 - 适配分类页和首页"""
        items = []
        if not html:
            return items
        
        # 匹配视频卡片 - 从分类页/首页提取
        # 模式: <a class="m-cd-i" href="/数字.html" title="标题">
        #        <div class="pic lazy" data-original="图片地址">
        #        <h3 class="tit h">标题</h3>
        #        <p class="desc">更新时间</p>
        pattern = r'<a\s+class="m-cd-i"[^>]*href="/(\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?<div[^>]*class="pic[^"]*"[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*class="tit[^"]*"[^>]*>(.*?)</h3>.*?<p[^>]*class="desc"[^>]*>(.*?)</p>'
        
        matches = re.findall(pattern, html, re.DOTALL)
        if not matches:
            # 尝试简化匹配（只匹配必要的字段）
            pattern_simple = r'<a\s+class="m-cd-i"[^>]*href="/(\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?<div[^>]*class="pic[^"]*"[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*class="tit[^"]*"[^>]*>(.*?)</h3>'
            matches = re.findall(pattern_simple, html, re.DOTALL)
            for match in matches:
                href = match[0]
                title = match[1] or match[3] if len(match) > 3 else ""
                pic = match[2] if len(match) > 2 else ""
                
                if not href or not title:
                    continue
                
                vid = href.replace(".html", "")
                if not vid:
                    continue
                
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            return items
        
        for match in matches:
            href = match[0]
            title = match[1] or match[3]
            pic = match[2]
            desc = match[4] if len(match) > 4 else ""
            
            if not href or not title:
                continue
            
            vid = href.replace(".html", "")
            if not vid:
                continue
            
            # 提取播放次数或更新时间作为备注
            remark = ""
            if desc:
                # 提取更新时间
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', desc)
                if time_match:
                    remark = time_match.group(1)
                else:
                    # 提取播放次数
                    count_match = re.search(r'(\d+)次', desc)
                    if count_match:
                        remark = count_match.group(1) + "次播放"
            
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark
            })
        
        return items

    def _parse_recommend_list(self, html):
        """解析相关推荐"""
        items = []
        if not html:
            return items
        
        # 查找推荐区域
        block_match = re.search(r'<section id="blockRelate">(.*?)</section>', html, re.DOTALL)
        if not block_match:
            return items
        
        block_html = block_match.group(1)
        
        pattern = r'<a\s+class="m-cd-i"[^>]*href="/(\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?<div[^>]*class="pic[^"]*"[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*class="tit[^"]*"[^>]*>(.*?)</h3>'
        
        matches = re.findall(pattern, block_html, re.DOTALL)
        for match in matches:
            href = match[0]
            title = match[1] or match[3]
            pic = match[2]
            
            if not href or not title:
                continue
            
            vid = href.replace(".html", "")
            if not vid:
                continue
            
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        
        return items

    def _extract_title(self, html):
        """提取标题"""
        if not html:
            return ""
        
        # 方法1: h1.title .j-video-name
        m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>.*?<span[^>]*class="j-video-name"[^>]*>(.*?)</span>', html, re.DOTALL)
        if m:
            return m.group(1).strip()
        
        # 方法2: h1.title 直接提取
        m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            # 去除内部span标签
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if title:
                return title
        
        # 方法3: og:title
        m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if m:
            return m.group(1).strip()
        
        # 方法4: title标签
        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        if m:
            title = m.group(1).strip()
            # 去除后缀 "-自拍偷拍-视频播放"
            title = re.sub(r'\s*[-—]\s*(?:自拍偷拍|视频播放|水兰亭).*$', '', title)
            return title
        
        return ""

    def _extract_pic(self, html):
        """提取封面图"""
        if not html:
            return ""
        
        # 方法1: 从播放器数据获取 posterImg
        m = re.search(r'"posterImg"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)
        
        # 方法2: og:image
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m:
            return m.group(1)
        
        # 方法3: 从详情页的图片标签获取
        m = re.search(r'<div[^>]*class="pic[^"]*"[^>]*data-original="([^"]+)"', html)
        if m:
            return m.group(1)
        
        # 方法4: 从视频播放器的poster属性获取
        m = re.search(r'poster\s*[:=]\s*["\']([^"\']+)["\']', html)
        if m:
            return m.group(1)
        
        return ""

    def _extract_play_url(self, html):
        """提取播放地址（m3u8）"""
        if not html:
            return ""
        
        # 方法1: 从 rawUrl 变量提取（最可靠）
        m = re.search(r'const\s+rawUrl\s*=\s*[\'"]?([^\'"\s]+\.m3u8[^\'"\s]*)[\'"]?', html)
        if m:
            url = m.group(1)
            # 处理可能的转义字符
            url = url.replace('\\/', '/')
            return url
        
        # 方法2: 从 playUrl 变量提取
        m = re.search(r'playUrl\s*[:=]\s*[\'"]?([^\'"\s]+\.m3u8[^\'"\s]*)[\'"]?', html)
        if m:
            url = m.group(1)
            url = url.replace('\\/', '/')
            return url
        
        # 方法3: 从 url 字段提取
        m = re.search(r'url\s*[:=]\s*[\'"]?([^\'"\s]+\.m3u8[^\'"\s]*)[\'"]?', html)
        if m:
            url = m.group(1)
            url = url.replace('\\/', '/')
            return url
        
        # 方法4: 直接查找 m3u8 链接
        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m:
            url = m.group(1)
            url = url.replace('\\/', '/')
            return url
        
        # 方法5: 查找相对路径的 m3u8
        m = re.search(r'[\'"]?([^\'"\s]+\.m3u8[^\'"\s]*)[\'"]?', html)
        if m:
            url = m.group(1)
            url = url.replace('\\/', '/')
            # 如果是相对路径，补全域名
            if url.startswith('/'):
                host = self.host.rstrip('/')
                url = host + url
            return url
        
        return ""

    def _extract_desc(self, html):
        """提取描述"""
        if not html:
            return ""
        
        # 方法1: 从播放次数获取
        m = re.search(r'<p[^>]*class="desc j-video-vv"[^>]*>.*?(\d+)次播放', html, re.DOTALL)
        if m:
            return f"播放次数：{m.group(1)}"
        
        # 方法2: meta description
        m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
        if m:
            return m.group(1).strip()
        
        # 方法3: 从信息列表获取
        m = re.search(r'<p[^>]*class="desc"[^>]*>(.*?)</p>', html, re.DOTALL)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if desc:
                return desc
        
        return ""

    def _extract_date(self, html):
        """提取日期"""
        if not html:
            return ""
        
        # 方法1: 出版日期
        m = re.search(r'出版日期[：:]\s*([^<>\n]+)', html)
        if m:
            return m.group(1).strip()
        
        # 方法2: 更新时间
        m = re.search(r'更新时间[：:]\s*([^<>\n]+)', html)
        if m:
            return m.group(1).strip()
        
        # 方法3: 从desc中提取日期
        m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', html)
        if m:
            return m.group(1)
        
        return ""

    def _extract_date(self, html):
        """提取日期"""
        m = re.search(r'出版日期[：:]\s*([^<]+)', html)
        if m:
            return m.group(1).strip()
        return ""

    def _extract_category(self, html):
        """提取分类"""
        m = re.search(r'系列[：:]\s*<[^>]*>([^<]+)</a>', html)
        if m:
            return m.group(1).strip()
        return ""

    def _parse_page_count(self, html):
        """解析总页数 - 从分页导航中提取"""
        if not html:
            return 1
        
        # 方法1: 从尾页链接提取 "尾页2/1182" 或 "尾页X/YYY"
        m = re.search(r'尾页\s*(\d+)/(\d+)', html)
        if m:
            return int(m.group(2))
        
        # 方法2: 从分页链接中提取最大页码
        m = re.search(r'href="[^"]*/vodtype/\d+-(\d+)\.html"[^>]*>\s*(\d+)\s*</a>', html)
        if m:
            return int(m.group(1))
        
        # 方法3: 查找所有分页链接
        matches = re.findall(r'href="[^"]*/vodtype/\d+-(\d+)\.html"', html)
        if matches:
            pages = [int(p) for p in matches if p.isdigit()]
            if pages:
                return max(pages)
        
        # 方法4: 查找 "共X页" 或 "总页数X"
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        
        # 默认返回1
        return 1

    def _parse_extend(self, extend):
        """解析extend参数"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}
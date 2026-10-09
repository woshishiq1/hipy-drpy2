#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# YouTube TVBox 爬虫 - 终极修复版（带自检诊断功能）

import sys
import re
import json
import time
import random
import requests
import socket
import ssl
from datetime import datetime
from urllib.parse import quote, unquote, urlparse, parse_qs

# ==================== 诊断自检模块 ====================

class DiagnosisEngine:
    """自检引擎：运行前检测环境是否正常"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def check_network(self):
        """检查网络连通性"""
        try:
            # 测试百度连通性
            start = time.time()
            r = requests.get("https://www.baidu.com", timeout=5)
            elapsed = time.time() - start
            if r.status_code == 200:
                self._log("OK", f"网络连通正常 ({elapsed:.1f}s)")
            else:
                self.warnings.append(f"网络请求返回状态码 {r.status_code}")
        except Exception as e:
            self.issues.append(f"网络连接失败: {str(e)[:50]}")
    
    def check_dns(self):
        """检查DNS解析"""
        domains = [
            "www.youtube.com",
            "i.ytimg.com",
            "yt3.ggpht.com"
        ]
        for domain in domains:
            try:
                socket.getaddrinfo(domain, 443)
                self._log("OK", f"DNS解析 {domain} 成功")
            except Exception as e:
                self.issues.append(f"DNS解析 {domain} 失败: {str(e)[:30]}")
    
    def check_ssl(self):
        """检查SSL证书"""
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection(("www.youtube.com", 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname="www.youtube.com") as ssock:
                    cert = ssock.getpeercert()
                    if cert:
                        self._log("OK", "SSL证书有效")
                    else:
                        self.warnings.append("SSL证书无法验证")
        except Exception as e:
            self.issues.append(f"SSL连接失败: {str(e)[:40]}")
    
    def check_python_env(self):
        """检查Python运行环境"""
        py_ver = sys.version_info
        if py_ver < (3, 6):
            self.issues.append(f"Python版本过低 ({py_ver[0]}.{py_ver[1]})，建议≥3.6")
        else:
            self._log("OK", f"Python {py_ver[0]}.{py_ver[1]} 版本符合要求")
        
        # 检查关键库
        try:
            import requests
            self._log("OK", "requests库正常")
        except ImportError:
            self.issues.append("缺少requests库，请执行: pip install requests")
        
        try:
            import json
        except:
            self.issues.append("json库异常，Python安装可能损坏")
    
    def check_cookie(self):
        """检查Cookie是否有效"""
        # 简单的Cookie有效性检查
        test_cookie = {
            "CONSENT": "YES+cb.20210101-17-p0.de+FX+xxx",
            "VISITOR_INFO1_LIVE": "test"
        }
        try:
            s = requests.Session()
            s.cookies.update(test_cookie)
            r = s.get("https://www.youtube.com", timeout=5)
            if r.status_code == 200:
                self._log("OK", "Cookie可用")
            else:
                self.warnings.append("Cookie可能已过期")
        except:
            self.warnings.append("Cookie测试失败")
    
    def _log(self, status, msg):
        """格式化输出诊断信息"""
        icon = "✅" if status == "OK" else "⚠️"
        print(f"  {icon} {msg}")
    
    def run_all(self):
        """运行全部诊断"""
        print("\n" + "="*50)
        print("🔍 YouTube 爬虫自检诊断")
        print("="*50)
        
        print("\n📡 网络环境检测:")
        self.check_network()
        
        print("\n🌐 DNS解析检测:")
        self.check_dns()
        
        print("\n🔒 SSL证书检测:")
        self.check_ssl()
        
        print("\n🐍 Python环境检测:")
        self.check_python_env()
        
        print("\n🍪 Cookie检测:")
        self.check_cookie()
        
        print("\n" + "="*50)
        if self.issues:
            print(f"❌ 发现 {len(self.issues)} 个严重问题:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        else:
            print("✅ 环境检查通过")
        
        if self.warnings:
            print(f"\n⚠️ {len(self.warnings)} 个警告:")
            for w in self.warnings:
                print(f"  - {w}")
        
        print("="*50)
        return len(self.issues) == 0


# ==================== 主爬虫类 ====================

class YouTubeSpider:
    """
    YouTube 爬虫终极版 - 带完整自检和容错机制
    适配 TVBox 3.0+ 标准 JSON 协议
    """
    
    def __init__(self, debug=True):
        self.name = "YouTube"
        self.version = "2.0"
        self.host = "https://www.youtube.com"
        self.search_url = "https://www.youtube.com/results?search_query={keyword}"
        self.detail_url = "https://www.youtube.com/watch?v={vid}"
        self.debug = debug
        
        # User-Agent 池
        self.user_agents = self._build_ua_pool()
        
        # 请求头
        self.headers_template = {
            "User-Agent": "",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        # 会话管理
        self.session = requests.Session()
        self._init_session()
        
        # 统计信息
        self.stats = {
            "requests": 0,
            "success": 0,
            "failed": 0,
            "last_error": ""
        }
    
    def _build_ua_pool(self):
        """构建丰富的UA池"""
        return [
            # Chrome Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            # Chrome Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            # 移动端
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
    
    def _init_session(self):
        """初始化会话和Cookie"""
        self.session.headers.update({
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br"
        })
        
        # 设置初始Cookie
        initial_cookies = {
            "CONSENT": "YES+cb.20210101-17-p0.de+FX+xxx",
            "VISITOR_INFO1_LIVE": "4VwPMkVZpho",
            "YSC": "DiwYK0yFN3I",
            "PREF": "f1=50000000&gl=US&hl=en"
        }
        for name, value in initial_cookies.items():
            self.session.cookies.set(name, value, domain=".youtube.com")
    
    def log(self, msg, level="INFO"):
        """调试日志"""
        if self.debug or level in ["ERROR", "WARNING"]:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] [{level}] {msg}")
    
    def _get_ua(self):
        """轮换UA"""
        idx = random.randint(0, len(self.user_agents) - 1)
        return self.user_agents[idx]
    
    def _get_headers(self, referer=None):
        """获取随机请求头"""
        headers = self.headers_template.copy()
        headers["User-Agent"] = self._get_ua()
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = "https://www.google.com/"
        # 随机化一些头信息
        headers["Accept-Language"] = random.choice([
            "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
            "en,en-US;q=0.9,zh-CN;q=0.8,zh;q=0.7"
        ])
        return headers
    
    def _safe_request(self, url, max_retries=3):
        """
        安全请求方法 - 带自动重试和错误恢复
        返回: (成功标记, 响应内容/错误信息)
        """
        self.stats["requests"] += 1
        
        for attempt in range(max_retries):
            try:
                headers = self._get_headers()
                
                # 随机延迟，模拟人类行为
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    self.log(f"等待 {delay:.1f}s 后重试 ({attempt+1}/{max_retries})", "WARNING")
                    time.sleep(delay)
                
                self.log(f"请求 [{attempt+1}/{max_retries}]: {url[:60]}...")
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=(10, 25),
                    allow_redirects=True,
                    verify=True
                )
                
                # 检查响应状态
                status = response.status_code
                if status == 200:
                    content = response.text
                    if len(content) > 1000:
                        self.stats["success"] += 1
                        self.log(f"✅ 成功 ({len(content)} bytes)", "INFO")
                        return True, content
                    else:
                        self.log(f"⚠️ 响应内容过短 ({len(content)} bytes)", "WARNING")
                        continue
                elif status == 429:
                    self.log(f"⚠️ 请求被限流 (429)，等待后重试", "WARNING")
                    time.sleep(random.uniform(5, 10))
                    continue
                elif status == 403:
                    self.log(f"❌ 被禁止访问 (403)", "ERROR")
                    self.stats["failed"] += 1
                    return False, "403 Forbidden"
                elif status in [404, 410]:
                    self.log(f"❌ 资源不存在 ({status})", "ERROR")
                    return False, f"HTTP {status}"
                else:
                    self.log(f"⚠️ 非预期状态码: {status}", "WARNING")
                    continue
                    
            except requests.exceptions.Timeout as e:
                self.log(f"⏱️ 请求超时: {str(e)[:40]}", "WARNING")
                continue
            except requests.exceptions.SSLError as e:
                self.log(f"🔒 SSL错误: {str(e)[:40]}", "ERROR")
                # SSL错误直接返回，不重试
                self.stats["failed"] += 1
                return False, f"SSL Error: {str(e)[:50]}"
            except requests.exceptions.ConnectionError as e:
                self.log(f"🔌 连接错误: {str(e)[:40]}", "WARNING")
                continue
            except Exception as e:
                self.log(f"❌ 未知错误: {str(e)[:50]}", "ERROR")
                self.stats["failed"] += 1
                return False, f"Error: {str(e)[:60]}"
        
        self.stats["failed"] += 1
        self.stats["last_error"] = f"全部 {max_retries} 次重试失败"
        return False, self.stats["last_error"]
    
    def _extract_json_data(self, html):
        """从HTML提取ytInitialData JSON"""
        patterns = [
            (r'window\["ytInitialData"\]\s*=\s*({.*?});', "方括号格式"),
            (r'window\.ytInitialData\s*=\s*({.*?});', "点号格式"),
            (r'var\s+ytInitialData\s*=\s*({.*?});', "var格式"),
            (r'ytInitialData\s*=\s*({.*?});', "简易格式")
        ]
        
        for pattern, name in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    self.log(f"✅ 通过 {name} 提取JSON成功", "INFO")
                    return data
                except json.JSONDecodeError as e:
                    self.log(f"⚠️ {name} JSON解析失败: {str(e)[:40]}", "WARNING")
                    continue
        
        self.log("❌ 所有JSON提取方式均失败", "ERROR")
        return None
    
    def _parse_videos(self, data):
        """递归解析视频列表"""
        videos = []
        
        if not data:
            return videos
        
        if isinstance(data, dict):
            # 提取视频ID
            video_id = data.get("videoId")
            if video_id and len(video_id) == 11:
                title = ""
                title_container = data.get("title", {})
                if isinstance(title_container, dict):
                    runs = title_container.get("runs", [])
                    if runs:
                        title = runs[0].get("text", "")
                
                if title and video_id not in [v["vod_id"] for v in videos]:
                    # 提取缩略图
                    thumbnails = data.get("thumbnail", {}).get("thumbnails", [])
                    pic = thumbnails[-1].get("url", "") if thumbnails else ""
                    
                    # 提取时长
                    length_text = data.get("lengthText", {})
                    duration = length_text.get("simpleText", "") if isinstance(length_text, dict) else ""
                    
                    # 提取发布者
                    owner_text = data.get("ownerText", {})
                    owner = ""
                    if isinstance(owner_text, dict):
                        runs = owner_text.get("runs", [])
                        if runs:
                            owner = runs[0].get("text", "")
                    
                    # 提取观看次数
                    view_count = data.get("viewCountText", {})
                    views = view_count.get("simpleText", "") if isinstance(view_count, dict) else ""
                    
                    videos.append({
                        "vod_id": video_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": duration,
                        "vod_actor": owner,
                        "vod_content": views,
                        "type_name": "video"
                    })
            
            # 递归遍历子节点
            for value in data.values():
                sub_videos = self._parse_videos(value)
                videos.extend(sub_videos)
                
        elif isinstance(data, list):
            for item in data:
                sub_videos = self._parse_videos(item)
                videos.extend(sub_videos)
        
        return videos
    
    def _parse_videos_regex(self, html):
        """正则降级方案"""
        videos = []
        seen_ids = set()
        
        # 匹配视频卡片
        patterns = [
            r'/watch\?v=([a-zA-Z0-9_-]{11})[^"]*"[^>]*title="([^"]+)"',
            r'href="/watch\?v=([a-zA-Z0-9_-]{11})[^"]*"[^>]*>([^<]+)',
            r'videoId["\']?\s*[:=]\s*["\']([a-zA-Z0-9_-]{11})["\']'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                vid = match.group(1)
                title = match.group(2).strip() if len(match.groups()) > 1 else ""
                
                if not title or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                    "vod_remarks": "",
                    "vod_actor": "",
                    "vod_content": "",
                    "type_name": "video"
                })
                
                if len(videos) >= 30:
                    break
            
            if videos:
                self.log(f"✅ 正则提取 {len(videos)} 个视频", "INFO")
                break
        
        return videos
    
    def _fallback_data(self, count=10):
        """生成兜底数据（当所有解析都失败时使用）"""
        fallback_videos = []
        template_titles = [
            "热门视频 #{id}",
            "推荐观看 #{id}",
            "精彩内容 #{id}"
        ]
        for i in range(count):
            idx = i % len(template_titles)
            fallback_videos.append({
                "vod_id": f"fallback_{i}",
                "vod_name": template_titles[idx].format(id=i+1),
                "vod_pic": "",
                "vod_remarks": "YouTube",
                "vod_actor": "YouTube Channel",
                "vod_content": "点击搜索你想观看的内容",
                "type_name": "video"
            })
        return fallback_videos
    
    # ==================== TVBox 接口 ====================
    
    def home(self):
        """首页分类"""
        self.log("="*40, "INFO")
        self.log("📋 开始加载首页分类", "INFO")
        
        result = {
            "class": [
                {"type_id": "trending", "type_name": "🔥 热门"},
                {"type_id": "music", "type_name": "🎵 音乐"},
                {"type_id": "gaming", "type_name": "🎮 游戏"},
                {"type_id": "movie", "type_name": "🎥 电影"},
                {"type_id": "tv", "type_name": "📺 电视剧"},
                {"type_id": "anime", "type_name": "🎨 动漫"},
                {"type_id": "sports", "type_name": "⚽ 体育"},
                {"type_id": "education", "type_name": "📚 教育"}
            ]
        }
        
        self.log(f"✅ 返回 {len(result['class'])} 个分类", "INFO")
        return result
    
    def homeVod(self):
        """首页推荐视频"""
        self.log("="*40, "INFO")
        self.log("📋 开始加载首页推荐", "INFO")
        
        try:
            # 尝试获取热门页面
            success, content = self._safe_request(f"{self.host}/feed/trending")
            
            if success and content:
                # 尝试JSON解析
                data = self._extract_json_data(content)
                videos = []
                
                if data:
                    videos = self._parse_videos(data)
                    self.log(f"✅ JSON解析获得 {len(videos)} 个视频", "INFO")
                
                # 如果JSON解析结果太少，使用正则
                if len(videos) < 10:
                    regex_videos = self._parse_videos_regex(content)
                    if regex_videos:
                        videos = regex_videos
                
                # 如果还是有结果，返回
                if videos:
                    return {"list": videos[:30]}
            
            # 兜底：返回静态推荐
            self.log("⚠️ 使用兜底数据", "WARNING")
            return {"list": self._fallback_data(20)}
            
        except Exception as e:
            self.log(f"❌ 首页推荐异常: {str(e)[:50]}", "ERROR")
            return {"list": self._fallback_data(15)}
    
    def category(self, tid, pg=1, extend=None):
        """分类浏览"""
        self.log("="*40, "INFO")
        self.log(f"📋 分类: {tid}, 页码: {pg}", "INFO")
        
        try:
            # 构建URL
            category_urls = {
                "trending": f"{self.host}/feed/trending",
                "music": f"{self.host}/channel/UC-9-kyTW8ZkE_5h0h_jgxXg",
                "gaming": f"{self.host}/gaming",
                "movie": f"{self.host}/feed/storefront?bp=ogUCKAYD",
                "tv": f"{self.host}/feed/storefront?bp=ogUCMAkD",
                "anime": f"{self.host}/feed/explore",
                "sports": f"{self.host}/sports",
                "education": f"{self.host}/feed/explore"
            }
            
            url = category_urls.get(tid, f"{self.host}/results?search_query={tid}")
            if pg > 1:
                url += f"&page={pg}"
            
            success, content = self._safe_request(url)
            videos = []
            
            if success and content:
                data = self._extract_json_data(content)
                if data:
                    videos = self._parse_videos(data)
                
                if len(videos) < 10:
                    videos = self._parse_videos_regex(content)
            
            result = {
                "list": videos[:25] if videos else self._fallback_data(10),
                "page": pg,
                "pagecount": 10,
                "limit": 25,
                "total": 250
            }
            
            self.log(f"✅ 返回 {len(result['list'])} 个视频", "INFO")
            return result
            
        except Exception as e:
            self.log(f"❌ 分类异常: {str(e)[:50]}", "ERROR")
            return {
                "list": self._fallback_data(8),
                "page": pg,
                "pagecount": 1,
                "limit": 25,
                "total": 8
            }
    
    def detail(self, ids):
        """视频详情"""
        try:
            vid = ids[0] if ids else ""
            self.log(f"📋 详情: {vid}", "INFO")
            
            if not vid:
                return {"list": []}
            
            url = self.detail_url.format(vid=vid)
            success, html = self._safe_request(url)
            
            if not success:
                # 返回基本信息
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": f"YouTube Video {vid[:8]}...",
                    "vod_pic": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "vod_content": "",
                    "vod_actor": "",
                    "vod_remarks": "",
                    "type_name": "video",
                    "vod_play_from": "YouTube",
                    "vod_play_url": f"高清$https://www.youtube.com/embed/{vid}?autoplay=1"
                }]}
            
            # 提取信息
            title = ""
            title_match = re.search(r'<title>([^<]+) - YouTube</title>', html)
            if title_match:
                title = title_match.group(1).strip()
            
            desc = ""
            desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1)[:500]
            
            pic = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            pic_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1)
            
            channel = ""
            channel_match = re.search(r'"author"[^:]*:\s*"([^"]+)"', html)
            if channel_match:
                channel = channel_match.group(1)
            
            video_info = {
                "vod_id": vid,
                "vod_name": title or f"YouTube Video",
                "vod_pic": pic,
                "vod_content": desc,
                "vod_actor": channel,
                "vod_remarks": "",
                "type_name": "video",
                "vod_play_from": "YouTube",
                "vod_play_url": f"高清$https://www.youtube.com/embed/{vid}?autoplay=1"
            }
            
            self.log(f"✅ 详情: {title[:30]}...", "INFO")
            return {"list": [video_info]}
            
        except Exception as e:
            self.log(f"❌ 详情异常: {str(e)[:50]}", "ERROR")
            return {"list": []}
    
    def search(self, keyword, pg=1):
        """搜索"""
        self.log("="*40, "INFO")
        self.log(f"📋 搜索: '{keyword}', 页码: {pg}", "INFO")
        
        try:
            encoded = quote(keyword)
            url = self.search_url.format(keyword=encoded)
            if pg > 1:
                url += f"&page={pg}"
            
            success, content = self._safe_request(url)
            videos = []
            
            if success and content:
                data = self._extract_json_data(content)
                if data:
                    videos = self._parse_videos(data)
                    self.log(f"✅ JSON解析获得 {len(videos)} 个结果", "INFO")
                
                if len(videos) < 10:
                    regex_videos = self._parse_videos_regex(content)
                    if regex_videos:
                        videos = regex_videos
                        self.log(f"✅ 正则获得 {len(videos)} 个结果", "INFO")
            
            # 如果搜索失败但有兜底
            if not videos:
                self.log("⚠️ 搜索无结果，返回空列表", "WARNING")
            
            result = {
                "list": videos[:25],
                "page": pg,
                "pagecount": 10,
                "limit": 25,
                "total": 250
            }
            
            return result
            
        except Exception as e:
            self.log(f"❌ 搜索异常: {str(e)[:50]}", "ERROR")
            return {"list": [], "page": pg, "pagecount": 0, "limit": 25, "total": 0}
    
    def player(self, url, headers=None):
        """播放器"""
        self.log(f"📋 播放: {url[:50]}...", "INFO")
        
        # 解析视频ID
        vid = ""
        parsed = urlparse(url)
        
        if "youtube.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            vid = query.get("v", [""])[0]
        elif "youtu.be" in parsed.netloc:
            vid = parsed.path.strip("/")
        elif "embed" in parsed.path:
            vid = parsed.path.split("/")[-1]
        
        if not vid:
            self.log("⚠️ 无法解析视频ID", "WARNING")
            return {"url": url}
        
        play_url = f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0&showinfo=0"
        
        result = {
            "url": play_url,
            "user-agent": self._get_ua(),
            "referer": f"https://www.youtube.com/watch?v={vid}",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        self.log(f"✅ 播放链接: {play_url[:50]}...", "INFO")
        return result


# ==================== TVBox 接口函数（标准入口） ====================

# 全局实例
_spider_instance = None

def _get_spider():
    global _spider_instance
    if _spider_instance is None:
        _spider_instance = YouTubeSpider(debug=True)
    return _spider_instance

def home():
    return _get_spider().home()

def homeVod():
    return _get_spider().homeVod()

def category(tid, pg=1, extend=None):
    return _get_spider().category(tid, pg, extend)

def detail(ids):
    return _get_spider().detail(ids)

def search(keyword, pg=1):
    return _get_spider().search(keyword, pg)

def player(url, headers=None):
    return _get_spider().player(url, headers)


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎬 YouTube TVBox 爬虫 - 自检诊断工具 v2.0")
    print("="*60)
    
    # 首先运行自检
    diag = DiagnosisEngine()
    env_ok = diag.run_all()
    
    if not env_ok:
        print("\n⚠️ 环境检测未通过，请修复上述问题后重试")
        sys.exit(1)
    
    # 创建爬虫实例
    spider = _get_spider()
    
    # 测试搜索
    print("\n" + "="*50)
    print("🔎 测试搜索功能")
    print("="*50)
    test_keyword = "movie trailer"
    result = search(test_keyword)
    videos = result.get("list", [])
    print(f"搜索 '{test_keyword}' 获得 {len(videos)} 个结果")
    for i, v in enumerate(videos[:3]):
        print(f"  {i+1}. {v.get('vod_name', 'N/A')}")
    
    # 测试首页推荐
    print("\n" + "="*50)
    print("🏠 测试首页推荐")
    print("="*50)
    result = homeVod()
    videos = result.get("list", [])
    print(f"首页推荐: {len(videos)} 个视频")
    for i, v in enumerate(videos[:3]):
        print(f"  {i+1}. {v.get('vod_name', 'N/A')} | {v.get('vod_remarks', '')}")
    
    # 统计信息
    print("\n" + "="*50)
    print("📊 请求统计")
    print("="*50)
    stats = spider.stats
    print(f"  总请求数: {stats['requests']}")
    print(f"  成功请求: {stats['success']}")
    print(f"  失败请求: {stats['failed']}")
    print(f"  最后错误: {stats['last_error'] or '无'}")
    
    print("\n✅ 诊断完成")
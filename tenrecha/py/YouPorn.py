# coding=utf-8
import re
import sys
import urllib.parse
import json
import base64
from pyquery import PyQuery as pq
import requests

sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.youporn.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        # 预定义分类列表（YouPorn 热门分类）
        self.categories = [
            {"name": "Recommended", "id": "recommended", "url": "/"},
            {"name": "Most Viewed", "id": "most_viewed", "url": "/most_viewed/"},
            {"name": "Top Rated", "id": "top_rated", "url": "/top_rated/"},
            {"name": "Amateur", "id": "amateur", "url": "/category/1/amateur/"},
            {"name": "Anal", "id": "anal", "url": "/category/2/anal/"},
            {"name": "Asian", "id": "asian", "url": "/category/3/asian/"},
            {"name": "BBW", "id": "bbw", "url": "/category/4/bbw/"},
            {"name": "Big Butt", "id": "big_butt", "url": "/category/5/big-butt/"},
            {"name": "Big Tits", "id": "big_tits", "url": "/category/6/big-tits/"},
            {"name": "Blonde", "id": "blonde", "url": "/category/7/blonde/"},
            {"name": "Blowjob", "id": "blowjob", "url": "/category/8/blowjob/"},
            {"name": "Brunette", "id": "brunette", "url": "/category/9/brunette/"},
            {"name": "Casting", "id": "casting", "url": "/category/10/casting/"},
            {"name": "Compilation", "id": "compilation", "url": "/category/11/compilation/"},
            {"name": "Creampie", "id": "creampie", "url": "/category/12/creampie/"},
            {"name": "Cumshots", "id": "cumshots", "url": "/category/13/cumshots/"},
            {"name": "Double Penetration", "id": "dp", "url": "/category/14/double-penetration/"},
            {"name": "Ebony", "id": "ebony", "url": "/category/15/ebony/"},
            {"name": "Euro", "id": "euro", "url": "/category/16/euro/"},
            {"name": "Facial", "id": "facial", "url": "/category/17/facial/"},
            {"name": "Fetish", "id": "fetish", "url": "/category/18/fetish/"},
            {"name": "Fingering", "id": "fingering", "url": "/category/19/fingering/"},
            {"name": "Funny", "id": "funny", "url": "/category/20/funny/"},
            {"name": "Gangbang", "id": "gangbang", "url": "/category/21/gangbang/"},
            {"name": "Group", "id": "group", "url": "/category/22/group/"},
            {"name": "Handjob", "id": "handjob", "url": "/category/23/handjob/"},
            {"name": "Hardcore", "id": "hardcore", "url": "/category/24/hardcore/"},
            {"name": "HD", "id": "hd", "url": "/category/25/hd/"},
            {"name": "Hentai", "id": "hentai", "url": "/category/26/hentai/"},
            {"name": "Interracial", "id": "interracial", "url": "/category/27/interracial/"},
            {"name": "Latina", "id": "latina", "url": "/category/28/latina/"},
            {"name": "Lesbian", "id": "lesbian", "url": "/category/29/lesbian/"},
            {"name": "Massage", "id": "massage", "url": "/category/30/massage/"},
            {"name": "Masturbation", "id": "masturbation", "url": "/category/31/masturbation/"},
            {"name": "Mature", "id": "mature", "url": "/category/32/mature/"},
            {"name": "MILF", "id": "milf", "url": "/category/33/milf/"},
            {"name": "POV", "id": "pov", "url": "/category/34/pov/"},
            {"name": "Public", "id": "public", "url": "/category/35/public/"},
            {"name": "Redhead", "id": "redhead", "url": "/category/36/redhead/"},
            {"name": "Solo", "id": "solo", "url": "/category/37/solo/"},
            {"name": "Squirting", "id": "squirting", "url": "/category/38/squirting/"},
            {"name": "Teen", "id": "teen", "url": "/category/39/teen/"},
            {"name": "Threesome", "id": "threesome", "url": "/category/40/threesome/"},
            {"name": "Toys", "id": "toys", "url": "/category/41/toys/"},
            {"name": "Vintage", "id": "vintage", "url": "/category/42/vintage/"},
            {"name": "Webcam", "id": "webcam", "url": "/category/43/webcam/"},
        ]

    # ========= 工具方法 =========

    def _abs_url(self, base, url):
        """转换为绝对URL"""
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.base_url + url
        return base.rsplit('/', 1)[0] + '/' + url

    def _get_thumb(self, title):
        """生成占位缩略图"""
        text = urllib.parse.quote(title[:20])
        return f"https://via.placeholder.com/480x270/FF4500/FFFFFF?text={text}"

    def _extract_videos(self, html, base_url):
        """从HTML中提取视频列表"""
        doc = pq(html)
        videos = []
        
        # YouPorn 视频列表项通常包含在 .video-list .video-box 或类似结构中
        selectors = [
            '.video-list .video-box',
            '.video-list-item',
            '.video-item',
            '[data-video-id]',
            '.container .video',
        ]
        
        items = []
        for sel in selectors:
            items = doc(sel)
            if items:
                break
        
        if not items:
            # 兜底：尝试找包含 /watch/ 链接的 a 标签
            items = doc('a[href*="/watch/"]').parent()
        
        for item in items:
            try:
                item_pq = pq(item)
                
                # 提取链接
                link_elem = item_pq('a[href*="/watch/"]').eq(0)
                if not link_elem:
                    continue
                href = link_elem.attr('href') or ''
                if not href:
                    continue
                vid_id = href.strip('/').split('/')[-2] if '/watch/' in href else href.strip('/').split('/')[-1]
                detail_url = self._abs_url(base_url, href)
                
                # 提取标题
                title = link_elem.attr('title') or link_elem.text() or 'Unknown'
                title = title.strip()
                
                # 提取缩略图
                thumb = ''
                img = item_pq('img').eq(0)
                if img:
                    thumb = img.attr('data-src') or img.attr('data-original') or img.attr('src') or ''
                    thumb = self._abs_url(base_url, thumb)
                if not thumb:
                    thumb = self._get_thumb(title)
                
                # 提取时长
                duration = ''
                duration_sel = item_pq('.duration, .video-duration, .time, [class*="duration"]').eq(0)
                if duration_sel:
                    duration = duration_sel.text().strip()
                
                # 提取观看数/评分等备注
                remarks = duration if duration else 'HD'
                
                videos.append({
                    'vod_id': detail_url,
                    'vod_name': title,
                    'vod_pic': thumb,
                    'vod_remarks': remarks,
                })
            except Exception:
                continue
        
        return videos

    def _extract_video_source(self, html):
        """从视频详情页提取播放源 - 增强版"""
        if not html:
            return ''
        
        # 策略1: 尝试提取 JSON-LD 中的 contentUrl
        try:
            ld_json_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
            if ld_json_match:
                ld_data = json.loads(ld_json_match.group(1))
                if isinstance(ld_data, dict):
                    if 'contentUrl' in ld_data and ld_data['contentUrl']:
                        return ld_data['contentUrl']
                    if 'embedUrl' in ld_data and ld_data['embedUrl']:
                        return ld_data['embedUrl']
                elif isinstance(ld_data, list):
                    for item in ld_data:
                        if isinstance(item, dict):
                            if 'contentUrl' in item and item['contentUrl']:
                                return item['contentUrl']
        except Exception:
            pass
        
        # 策略2: 从 videoData / flashvars / player 等变量提取
        patterns = [
            r'var\s+videoData\s*=\s*(\{.*?\});',
            r'var\s+flashvars\s*=\s*(\{.*?\});',
            r'var\s+player\s*=\s*(\{.*?\});',
            r'var\s+video_player\s*=\s*(\{.*?\});',
            r'"mediaDefinitions":\s*(\[.*?\])',
            r'"videoUrl":\s*"([^"]+)"',
            r'"contentUrl":\s*"([^"]+)"',
            r'"url":\s*"([^"]+\.mp4[^"]*)"',
            r'"url":\s*"([^"]+\.m3u8[^"]*)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    if match.startswith('http'):
                        return match
                    data = json.loads(match)
                    if isinstance(data, dict):
                        # 尝试各种可能的字段
                        for key in ['videoUrl', 'contentUrl', 'url', 'src', 'file', 'video_url', 'media_url']:
                            if key in data and data[key]:
                                val = data[key]
                                if isinstance(val, str) and val.startswith('http'):
                                    return val
                                elif isinstance(val, list) and val:
                                    # 取最高质量
                                    val.sort(key=lambda x: x.get('quality', 0) if isinstance(x, dict) else 0, reverse=True)
                                    url = val[0].get('videoUrl', '') if isinstance(val[0], dict) else val[0]
                                    if url and url.startswith('http'):
                                        return url
                        
                        # mediaDefinitions 特殊处理
                        if 'mediaDefinitions' in data:
                            defs = data['mediaDefinitions']
                            if defs and isinstance(defs, list):
                                defs.sort(key=lambda x: x.get('quality', 0) if isinstance(x, dict) else 0, reverse=True)
                                for d in defs:
                                    if isinstance(d, dict):
                                        url = d.get('videoUrl', '') or d.get('url', '')
                                        if url and url.startswith('http'):
                                            return url
                    elif isinstance(data, list):
                        # mediaDefinitions 数组
                        if data and isinstance(data, list):
                            data.sort(key=lambda x: x.get('quality', 0) if isinstance(x, dict) else 0, reverse=True)
                            for d in data:
                                if isinstance(d, dict):
                                    url = d.get('videoUrl', '') or d.get('url', '')
                                    if url and url.startswith('http'):
                                        return url
                except Exception:
                    continue
        
        # 策略3: 直接匹配 mp4/m3u8/flv URL（包括被转义的）
        url_patterns = [
            r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'(https?://[^\s"\'<>]+\.flv[^\s"\'<>]*)',
        ]
        for pattern in url_patterns:
            matches = re.findall(pattern, html)
            if matches:
                # 去重并返回第一个
                seen = set()
                for m in matches:
                    # 处理 HTML 转义
                    m = m.replace('\\/', '/').replace('&amp;', '&')
                    if m not in seen:
                        seen.add(m)
                        return m
        
        # 策略4: 从 <video> 标签提取
        try:
            doc = pq(html)
            video = doc('video').eq(0)
            if video:
                src = video.attr('src') or ''
                if src and src.startswith('http'):
                    return src
                source = video.find('source').eq(0)
                if source:
                    src = source.attr('src') or ''
                    if src and src.startswith('http'):
                        return src
        except Exception:
            pass
        
        # 策略5: 尝试 base64 解码的 URL
        b64_patterns = [
            r'"videoUrl":"([A-Za-z0-9+/=]+)"',
            r'"url":"([A-Za-z0-9+/=]{50,})"',
            r'data-video="([A-Za-z0-9+/=]+)"',
        ]
        for pattern in b64_patterns:
            matches = re.findall(pattern, html)
            for m in matches:
                try:
                    decoded = base64.b64decode(m).decode('utf-8')
                    if decoded.startswith('http'):
                        return decoded
                except Exception:
                    continue
        
        return ''

    def _try_get_video_url(self, page_url):
        """尝试从页面 URL 获取真实视频地址"""
        try:
            resp = self.session.get(page_url, timeout=15)
            resp.raise_for_status()
            return self._extract_video_source(resp.text)
        except Exception as e:
            print(f"[ERROR] 获取视频源失败: {e}")
            return ''

    # ========= Spider接口实现 =========

    def getName(self):
        return "YouPorn"

    def init(self, extend):
        pass

    def homeContent(self, filter):
        """返回分类列表"""
        classes = []
        for cat in self.categories:
            classes.append({
                'type_name': cat['name'],
                'type_id': cat['id'],
            })
        return {'class': classes}

    def homeVideoContent(self):
        """首页推荐"""
        try:
            resp = self.session.get(self.base_url, timeout=10)
            resp.raise_for_status()
            videos = self._extract_videos(resp.text, self.base_url)
            return {'list': videos[:20]}  # 首页显示前20个
        except Exception as e:
            print(f"[ERROR] 首页获取失败: {e}")
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        pg = int(pg)
        
        # 查找分类URL
        cat_url = '/'
        for cat in self.categories:
            if cat['id'] == tid:
                cat_url = cat['url']
                break
        
        # 构建分页URL
        page_suffix = f"?page={pg}" if pg > 1 else ""
        url = self.base_url + cat_url + page_suffix
        
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            videos = self._extract_videos(resp.text, url)
            
            # YouPorn 通常有分页，通过判断是否有下一页
            has_next = len(videos) >= 20  # 假设每页20个
            
            return {
                'list': videos,
                'page': pg,
                'pagecount': 999 if has_next else pg,
                'limit': 20,
                'total': 99999,
            }
        except Exception as e:
            print(f"[ERROR] 分类获取失败: {e}")
            return {
                'list': [],
                'page': pg,
                'pagecount': pg,
                'limit': 20,
                'total': 0,
            }

    def detailContent(self, array):
        """详情页"""
        if not array or not array[0]:
            return {'list': []}
        
        detail_url = array[0]
        
        try:
            resp = self.session.get(detail_url, timeout=10)
            resp.raise_for_status()
            html = resp.text
            
            # 提取标题
            doc = pq(html)
            title = doc('h1').eq(0).text().strip() or 'Unknown'
            
            # 提取缩略图
            thumb = ''
            og_image = doc('meta[property="og:image"]').attr('content')
            if og_image:
                thumb = og_image
            else:
                thumb = self._get_thumb(title)
            
            # 提取视频源
            video_url = self._extract_video_source(html)
            
            # 提取描述
            desc = doc('meta[name="description"]').attr('content') or ''
            
            # 如果提取到真实视频地址，使用它；否则用详情页 URL（让 playerContent 二次处理）
            play_url = video_url if video_url else detail_url
            
            vod = {
                'vod_id': detail_url,
                'vod_name': title,
                'vod_pic': thumb,
                'vod_remarks': 'HD',
                'vod_content': desc,
                'vod_play_from': 'YouPorn',
                'vod_play_url': f'{title}${play_url}',
            }
            
            return {'list': [vod]}
        except Exception as e:
            print(f"[ERROR] 详情页获取失败: {e}")
            return {'list': []}

    def searchContent(self, key, quick, page='1'):
        """搜索功能"""
        if not key:
            return {'list': []}
        
        page = int(page)
        search_url = f"{self.base_url}/search/?query={urllib.parse.quote(key)}"
        if page > 1:
            search_url += f"&page={page}"
        
        try:
            resp = self.session.get(search_url, timeout=10)
            resp.raise_for_status()
            videos = self._extract_videos(resp.text, search_url)
            return {'list': videos}
        except Exception as e:
            print(f"[ERROR] 搜索失败: {e}")
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        """播放器内容 - 关键修复"""
        result = {
            "parse": 1,
            "playUrl": "",
            "url": id,
            "header": {
                "User-Agent": self.session.headers.get('User-Agent'),
                "Referer": self.base_url
            }
        }
        
        # 如果 id 已经是视频直链，直接播放
        if self.isVideoFormat(id):
            result["parse"] = 0
            return result
        
        # 如果 id 是页面地址，尝试主动提取视频源
        if id.startswith('http'):
            video_url = self._try_get_video_url(id)
            if video_url and self.isVideoFormat(video_url):
                result["parse"] = 0
                result["url"] = video_url
                return result
        
        # 兜底：让播放器 WebView 嗅探
        return result

    def isVideoFormat(self, url):
        """判断是否为视频格式 - 增强版"""
        if not url or not isinstance(url, str):
            return False
        video_exts = ['.mp4', '.m3u8', '.flv', '.mkv', '.ts', '.webm', '.mov', '.avi']
        url_lower = url.lower()
        # 检查常见视频后缀
        for ext in video_exts:
            if ext in url_lower:
                return True
        # 检查视频流特征
        if 'video' in url_lower and ('url' in url_lower or 'play' in url_lower or 'stream' in url_lower):
            return True
        if 'manifest' in url_lower or 'playlist' in url_lower:
            return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """本地代理 - 用于处理视频请求的 Referer 和 Header"""
        import urllib.request
        import urllib.error
        
        try:
            url = param.get('url', '') if isinstance(param, dict) else ''
            if not url:
                return {}
            
            # 构建请求
            req = urllib.request.Request(url)
            req.add_header('User-Agent', self.session.headers.get('User-Agent', ''))
            req.add_header('Referer', self.base_url)
            req.add_header('Accept', '*/*')
            req.add_header('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')
            
            # 处理 Range 请求（支持断点续传）
            if isinstance(param, dict) and param.get('Range'):
                req.add_header('Range', param.get('Range'))
            
            response = urllib.request.urlopen(req, timeout=30)
            
            # 返回代理响应
            return {
                'url': url,
                'code': response.getcode(),
                'header': dict(response.info()),
                'body': response.read()
            }
        except Exception as e:
            print(f"[ERROR] 代理请求失败: {e}")
            return {}
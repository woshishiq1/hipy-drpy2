# coding=utf-8
import sys
import requests
from bs4 import BeautifulSoup
import re
import json
import math

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "WhosTV(女优作品集)"

    def init(self, extend=""):
        self.host = "https://whos.tv"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

    # ---------- 辅助方法 ----------
    def _get_soup(self, url, params=None):
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            # 调试时可打印异常
            # print(f"请求失败: {url}, 错误: {e}")
            return None

    def _extract_total_pages(self, soup, default=1):
        """从分页控件或页面文本中提取总页数"""
        # 1. 常见分页链接数字
        pagination = soup.select('nav[aria-label="Pagination"] a, .pagination a, .page-link, .pages a')
        pages = []
        for a in pagination:
            text = a.get_text(strip=True)
            if text.isdigit():
                pages.append(int(text))
        if pages:
            return max(pages)
        # 2. 从“共xx页”文本中提取
        page_text = soup.get_text()
        match = re.search(r'共\s*(\d+)\s*页|page\s*(\d+)\s*of\s*(\d+)', page_text, re.I)
        if match:
            if match.group(1):
                return int(match.group(1))
            elif match.group(3):
                return int(match.group(3))
        return default

    # ---------- 首页：仅返回女优库 ----------
    def homeContent(self, filter):
        return {
            "class": [{"type_id": "actresses", "type_name": "女优库"}],
            "list": []
        }

    # ---------- 分类页：女优列表（完整分页） ----------
    def categoryContent(self, tid, pg, filter, extend):
        if tid != "actresses":
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        pg = int(pg)
        url = f"{self.host}/actresses"
        params = {"page": pg} if pg > 1 else {}
        soup = self._get_soup(url, params)
        if not soup:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        total_pages = self._extract_total_pages(soup, default=1)

        # 提取所有女优卡片（兼容多种结构）
        actress_items = []
        # 候选选择器列表（按优先级）
        selectors = [
            '.grid a[href^="/actresses/"]',
            '.actress-grid a[href^="/actresses/"]',
            'a.actress-card',
            '.actress-item a',
            'a[href*="/actresses/"]:not([href*="?"])'
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                break

        for a in cards:
            href = a.get('href')
            if not href or '?' in href or href.count('/') > 2:
                continue
            vod_id = href.split('/')[-1]
            if not vod_id or vod_id == 'actresses':
                continue

            # 提取图片
            img = a.select_one('img')
            pic = img.get('src') if img else ""
            if pic and pic.startswith('/'):
                pic = self.host + pic

            # 提取名字：优先使用 .name, .title, img[alt], 最后用链接末尾
            name = None
            name_elem = a.select_one('.name, .title, .actress-name')
            if name_elem:
                name = name_elem.get_text(strip=True)
            if not name and img and img.get('alt'):
                name = img.get('alt')
            if not name:
                name = vod_id.replace('-', ' ').title()

            actress_items.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "女优"
            })

        # 去重
        seen = set()
        unique_items = []
        for item in actress_items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                unique_items.append(item)

        return {
            "list": unique_items,
            "page": pg,
            "pagecount": total_pages,
            "limit": 20,
            "total": total_pages * 20
        }

    # ---------- 详情页：爬取指定女优的所有作品，生成播放列表 ----------
    def detailContent(self, ids):
        actress_id = ids[0]
        base_url = f"{self.host}/actresses/{actress_id}"
        soup = self._get_soup(base_url)
        if not soup:
            return {"list": [{
                "vod_id": actress_id,
                "vod_name": actress_id,
                "vod_play_from": "无数据",
                "vod_play_url": ""
            }]}

        total_pages = self._extract_total_pages(soup, default=1)
        all_video_links = []
        seen_videos = set()

        for page in range(1, total_pages + 1):
            if page == 1:
                page_soup = soup
            else:
                page_soup = self._get_soup(base_url, params={"page": page})
                if not page_soup:
                    continue

            # 提取作品链接（每个作品卡片包含 /videos/xxx）
            video_cards = page_soup.select('a[href^="/videos/"]')
            for card in video_cards:
                href = card.get('href')
                if not href:
                    continue
                vod_id = href.split('/')[-1]
                if vod_id in seen_videos:
                    continue
                seen_videos.add(vod_id)

                # 获取真实播放地址
                video_url = self._extract_video_url(vod_id)
                if not video_url:
                    # 若无法提取，将作品详情页作为备选
                    video_url = f"{self.host}/videos/{vod_id}"

                # 作品标题
                title_elem = card.select_one('.title, img[alt], .video-title')
                title = title_elem.get_text(strip=True) if title_elem else vod_id.upper()
                all_video_links.append(f"{title}${video_url}")

        if all_video_links:
            play_url = "#".join(all_video_links)
            play_from = "女优作品集"
        else:
            play_url = ""
            play_from = "无可用链接"

        vod = {
            "vod_id": actress_id,
            "vod_name": actress_id,
            "vod_pic": "",
            "vod_type": "女优作品",
            "vod_content": f"共获取 {len(all_video_links)} 部作品",
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }
        return {"list": [vod]}

    # ---------- 从作品详情页提取实际视频链接（增强版） ----------
    def _extract_video_url(self, vod_id):
        detail_url = f"{self.host}/videos/{vod_id}"
        soup = self._get_soup(detail_url)
        if not soup:
            return None

        # 1. 直接查找 video 标签或 source
        video_tag = soup.select_one('video source, video[src]')
        if video_tag:
            src = video_tag.get('src') or video_tag.get('data-src')
            if src:
                return self._normalize_url(src)

        # 2. 查找 iframe 嵌入（可能是播放器）
        iframe = soup.select_one('iframe[src*="player"], iframe[src*="embed"], iframe[src*="video"]')
        if iframe:
            src = iframe.get('src')
            if src:
                return self._normalize_url(src)

        # 3. 查找磁力链接或直接 mp4/m3u8 链接
        direct_link = soup.select_one('a[href*="magnet:"], a[href$=".mp4"], a[href$=".m3u8"]')
        if direct_link:
            href = direct_link.get('href')
            if href:
                return href

        # 4. 从页面文本中正则提取磁力链
        magnet_pattern = r'magnet:\?xt=urn:btih:[a-fA-F0-9]+'
        magnet_match = re.search(magnet_pattern, soup.text)
        if magnet_match:
            return magnet_match.group(0)

        # 5. 尝试从 <script> 中提取 JSON 数据（常见于 Nuxt 等框架）
        scripts = soup.find_all('script', type='application/json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                video_url = self._deep_search_video_url(data)
                if video_url:
                    return video_url
            except:
                pass

        # 6. 尝试从普通 script 中提取 video_url 变量
        for script in soup.find_all('script'):
            if not script.string:
                continue
            # 匹配类似 video_url = "https://..." 或 "url":"https://..."
            patterns = [
                r'video_url\s*=\s*["\'](https?://[^"\']+)["\']',
                r'url\s*:\s*["\'](https?://[^"\']+\.(?:mp4|m3u8))["\']',
                r'file\s*:\s*["\'](https?://[^"\']+)["\']'
            ]
            for pat in patterns:
                match = re.search(pat, script.string)
                if match:
                    return self._normalize_url(match.group(1))

        # 7. 最后返回 None（上层会使用作品详情页作为备选）
        return None

    def _normalize_url(self, url):
        """补全相对路径"""
        if not url:
            return url
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return self.host + url
        return url

    def _deep_search_video_url(self, obj, depth=0):
        """递归搜索 JSON 对象中的视频链接字段"""
        if depth > 6:
            return None
        if isinstance(obj, dict):
            for key, val in obj.items():
                if isinstance(val, str):
                    if val.startswith('http') and ('.mp4' in val or '.m3u8' in val or 'player' in val):
                        return val
                    if val.startswith('magnet:'):
                        return val
                elif isinstance(val, (dict, list)):
                    result = self._deep_search_video_url(val, depth+1)
                    if result:
                        return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._deep_search_video_url(item, depth+1)
                if result:
                    return result
        return None

    # ---------- 搜索（精简） ----------
    def searchContent(self, key, quick, pg=1):
        return {"list": []}

    # ---------- 播放器：直接返回 URL ----------
    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id, "header": ""}
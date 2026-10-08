# -*- coding: utf-8 -*-
# 兼容 OK影视/影视仓/TVBox 等 Python 爬虫壳
# DJGEM音乐网  https://www.djgem.com/  (实际走 m.djgem.com 移动端)

from base.spider import Spider
import requests
import re
import urllib3
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site_url = "https://m.djgem.com"
        self.default_pic = "https://tp.pgdjz.fun//attachment/logo/1.jpg"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + '/',
        }
        self.categories = [
            {"type_name": "车载视频", "type_id": "18"},
            {"type_name": "串烧舞曲", "type_id": "1"},
            {"type_name": "车载音乐", "type_id": "22"},
            {"type_name": "酒吧串烧", "type_id": "6"},
            {"type_name": "车载连版", "type_id": "5"},
            {"type_name": "中文Remix", "type_id": "8"},
            {"type_name": "外文Remix", "type_id": "13"},
            {"type_name": "中文Disco", "type_id": "23"},
        ]

    def init(self, extend=""):
        pass

    def getName(self):
        return "DJGEM音乐网"

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        url = str(url).lower()
        return any(url.endswith(s) for s in ['.m3u8', '.mp4', '.mp3', '.m4a', '.flv', '.avi', '.mkv', '.mov', '.ts'])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}

    # ---------- 工具 ----------

    def _fetch(self, url):
        s = requests.Session()
        s.trust_env = False
        r = s.get(url, headers=self.headers, timeout=20, verify=False)
        r.encoding = 'utf-8'
        return r.text

    @staticmethod
    def _extract_id(href):
        m = re.search(r'/music/(\d+)\.html', href)
        return m.group(1) if m else ''

    @staticmethod
    def _clean_name(name):
        name = re.sub(r'<[^>]+>', '', name)
        name = re.sub(r'[\s#$]+', ' ', name).strip()
        return name or '未知舞曲'

    def _parse_song_menu(self, soup):
        """解析 .song-menu 通用列表项（分类/首页/搜索）"""
        videos = []
        seen = set()
        for item in soup.find_all('div', class_='song-menu'):
            # 封面与ID
            left_a = item.find('div', class_='left')
            if not left_a:
                continue
            left_a = left_a.find('a', href=re.compile(r'/music/\d+\.html'))
            if not left_a:
                continue
            img = left_a.find('img')
            pic = img.get('src') or img.get('data-src') or self.default_pic if img else self.default_pic
            sid_left = self._extract_id(left_a.get('href', ''))

            # 标题
            right = item.find('div', class_='right')
            if not right:
                continue
            h3_a = right.find('h3')
            if h3_a:
                h3_a = h3_a.find('a', href=re.compile(r'/music/\d+\.html'))
            if not h3_a:
                continue
            title = self._clean_name(h3_a.get_text(strip=True))
            sid = self._extract_id(h3_a.get('href', '')) or sid_left
            if not sid or sid in seen:
                continue
            seen.add(sid)

            # 描述
            remarks = ''
            info_div = right.find('div', class_='info')
            if info_div:
                spans = [s.get_text(strip=True) for s in info_div.find_all('span')]
                remarks = ' | '.join([s for s in spans if s])

            videos.append({
                "vod_id": sid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    def _get_pagecount(self, html, pattern):
        m = re.search(pattern, html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        pages = []
        for mm in re.finditer(r'lists-\d+-(\d+)\.html', html):
            try:
                pages.append(int(mm.group(1)))
            except Exception:
                pass
        return max(pages) if pages else 9999

    # ---------- 首页 ----------

    def homeContent(self, filter):
        return {
            'class': self.categories,
            'filters': {},
            'list': []
        }

    def homeVideoContent(self):
        result = {
            'list': [],
            'page': 1,
            'pagecount': 1,
            'limit': 30,
            'total': 30
        }
        try:
            html = self._fetch(self.site_url + '/')
            soup = BeautifulSoup(html, 'html.parser')
            result['list'] = self._parse_song_menu(soup)
        except Exception:
            pass
        return result

    # ---------- 分类列表 ----------

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }
        url = f"{self.site_url}/dance/lists-{tid}-{pg}.html"
        try:
            html = self._fetch(url)
            soup = BeautifulSoup(html, 'html.parser')
            result['list'] = self._parse_song_menu(soup)
            result['pagecount'] = self._get_pagecount(html, r'lists-\d+-(\d+)\.html[^>]*>尾页')
        except Exception:
            pass
        return result

    # ---------- 详情 ----------

    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids, (list, tuple)) else ids
        result = {}
        try:
            vod = self._single_detail(rid)
            result['list'] = [vod]
        except Exception as e:
            result['list'] = [{
                "vod_id": str(rid),
                "vod_name": "加载失败",
                "vod_content": f"加载失败: {str(e)}",
                "vod_remarks": "加载失败",
                "vod_actor": "未知",
                "vod_play_from": "DJGEM音乐网",
                "vod_play_url": "",
                "vod_pic": self.default_pic,
            }]
        return result

    def _single_detail(self, sid):
        url = f"{self.site_url}/music/{sid}.html"
        html = self._fetch(url)
        soup = BeautifulSoup(html, 'html.parser')

        # 标题：优先 .pathing a[title]，其次 <title>
        name = '未知舞曲'
        path_a = soup.find('div', class_='pathing')
        if path_a:
            path_a = path_a.find('a', href=re.compile(r'/music/\d+\.html'))
            if path_a:
                name = self._clean_name(path_a.get('title') or path_a.get_text(strip=True))
        if name == '未知舞曲':
            title_tag = soup.find('title')
            if title_tag:
                name = self._clean_name(title_tag.get_text(strip=True).split('_')[0])

        # 信息区 .title-info
        content_lines = []
        for info in soup.find_all('div', class_='title-info'):
            for span in info.find_all('span'):
                text = span.get_text(strip=True)
                if text and len(text) < 200:
                    content_lines.append(text)
        content_str = '\n'.join(content_lines[:8]) if content_lines else '暂无简介'

        # 发布日期
        date = ''
        for m in re.finditer(r'更新\s*[:：]?\s*(\d{4}-\d{2}-\d{2})', html):
            date = m.group(1)
            break

        # 封面：详情页没有大图，用默认
        pic = self.default_pic

        return {
            "vod_id": sid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content_str,
            "vod_remarks": date or 'DJ舞曲',
            "vod_actor": name,
            "vod_play_from": "DJGEM音乐网",
            "vod_play_url": f"{name}${sid}",
        }

    # ---------- 播放 ----------

    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": "",
            "header": {},
            "pic": "",
            "name": "",
        }
        sid = id

        try:
            play_page_url = f"{self.site_url}/music/{sid}.html"
            html = self._fetch(play_page_url)
            soup = BeautifulSoup(html, 'html.parser')

            # 标题
            name = ''
            path_a = soup.find('div', class_='pathing')
            if path_a:
                path_a = path_a.find('a', href=re.compile(r'/music/\d+\.html'))
                if path_a:
                    name = self._clean_name(path_a.get('title') or path_a.get_text(strip=True))
            if not name:
                title_tag = soup.find('title')
                if title_tag:
                    name = self._clean_name(title_tag.get_text(strip=True).split('_')[0])

            play_url = ''

            # 1. 优先 <audio src="..."> / <video src="...">
            for media in soup.find_all(['audio', 'video']):
                src = media.get('src') or ''
                if src:
                    play_url = src
                    break

            # 2. 没有 media 标签则正则兜底 <audio|video src=...>
            if not play_url:
                m = re.search(r'<(?:audio|video)[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if m:
                    play_url = m.group(1)

            # 3. 视频类可能是 <source src="...mp4"> 或页面中的 mp4 直链
            if not play_url:
                for pat in [
                    r'<source[^>]*src=["\']([^"\']+\.(?:mp4|m3u8|mp3|m4a))["\']',
                    r'src=["\']((https?:)?//[^"\']+\.(?:mp4|m3u8|mp3|m4a|flv|avi|mov|ts))["\']',
                    r'["\']((https?:)?//[^"\']+\.(?:mp4|m3u8|mp3|m4a|flv|avi|mov|ts))["\']',
                ]:
                    m = re.search(pat, html, re.I)
                    if m:
                        play_url = m.group(1)
                        break

            if play_url:
                if play_url.startswith('//'):
                    play_url = 'https:' + play_url
                result.update({
                    "url": play_url,
                    "header": self.headers,
                    "name": name,
                    "pic": self.default_pic,
                })
                return result
        except Exception:
            pass

        return result

    # ---------- 搜索 ----------

    def searchContent(self, key, quick, pg=1):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }
        # 站点 form action="/search/dj"
        url = f"{self.site_url}/search/dj?key={quote(key)}&page={pg}"
        try:
            html = self._fetch(url)
            soup = BeautifulSoup(html, 'html.parser')
            result['list'] = self._parse_song_menu(soup)
            # 分页
            pages = []
            for a in soup.find_all('a', href=re.compile(r'page=')):
                pm = re.search(r'page=(\d+)', a.get('href', ''))
                if pm:
                    try:
                        pages.append(int(pm.group(1)))
                    except Exception:
                        pass
            if pages:
                result['pagecount'] = max(pages)
        except Exception:
            pass
        return result

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

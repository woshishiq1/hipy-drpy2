# -*- coding: utf-8 -*-
# 兼容 OK影视/影视仓/TVBox 等 Python 爬虫壳
# 啊哈DJ网  https://www.ahadj.com/

from base.spider import Spider
import requests
import re
import base64
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site_url = "https://www.ahadj.com"
        self.cdn_url = "https://st.pgdjz.fun"
        self.default_pic = "https://tp.pgdjz.fun//attachment/logo/1.jpg"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Referer': self.site_url + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        # 用户指定的分类与分页地址
        self.categories = [
            {"type_name": "超清视频", "type_id": "12"},
            {"type_name": "车载视频", "type_id": "123"},
            {"type_name": "抖音歌曲", "type_id": "145"},
            {"type_name": "国内舞曲", "type_id": "4"},
            {"type_name": "国外舞曲", "type_id": "2"},
            {"type_name": "无损舞曲", "type_id": "1"},
            {"type_name": "环绕舞曲", "type_id": "109"},
            {"type_name": "交谊舞曲", "type_id": "24"},
            {"type_name": "歌曲伴奏", "type_id": "111"},
            {"type_name": "Disco舞曲", "type_id": "115"},
            {"type_name": "8倍音乐", "type_id": "136"},
        ]

    def init(self, extend=""):
        pass

    def getName(self):
        return "啊哈DJ网"

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
        r = s.get(url, headers=self.headers, timeout=15, verify=False)
        r.encoding = 'utf-8'
        return r.text

    @staticmethod
    def _strencode(encoded, key='asdf4454545'):
        """复现 /res/play/js/wap.js 中的 strencode 解密（视频 XOR+base64）"""
        try:
            b = base64.b64decode(encoded)
            key_bytes = key.encode('utf-8')
            out = bytes([b[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(b))])
            return base64.b64decode(out).decode('utf-8', errors='ignore')
        except Exception:
            return ''

    @staticmethod
    def _extract_id(href):
        m = re.search(r'/music/(\d+)\.html', href)
        return m.group(1) if m else ''

    @staticmethod
    def _clean_name(name):
        name = re.sub(r'<[^>]+>', '', name)
        name = re.sub(r'[\s#$]+', ' ', name).strip()
        return name or '未知舞曲'

    def _get_pagecount(self, html, pattern):
        """从分页 HTML 中提取尾页页码"""
        m = re.search(pattern, html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 9999

    def _parse_table_body(self, html):
        """解析 div.table_body 列表（分类/搜索通用）"""
        videos = []
        seen = set()
        soup = BeautifulSoup(html, 'html.parser')
        for div in soup.find_all('div', class_='table_body'):
            ul = div.find('ul', class_='clearfix')
            if not ul:
                continue
            lis = ul.find_all('li')
            if len(lis) < 4:
                continue

            a = lis[2].find('a', href=re.compile(r'/music/\d+\.html'))
            if not a:
                continue

            href = a.get('href', '')
            sid = self._extract_id(href)
            if not sid or sid in seen:
                continue
            seen.add(sid)

            title = a.get_text(strip=True)
            name = self._clean_name(title)

            views = lis[3].get_text(strip=True) if len(lis) > 3 else ''
            date = lis[4].get_text(strip=True) if len(lis) > 4 else ''
            remarks = ' | '.join([x for x in [views, date] if x])

            videos.append({
                "vod_id": sid,
                "vod_name": name,
                "vod_pic": self.default_pic,
                "vod_remarks": remarks,
            })
        return videos

    # ---------- 首页 ----------

    def homeContent(self, filter):
        return {
            'class': self.categories,
            'filters': {},
            'list': []
        }

    def homeVideoContent(self):
        return self.categoryContent("12", 1, False, {})

    # ---------- 分类列表 ----------

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }
        url = f"{self.site_url}/music/id-{tid}-{pg}.html"
        try:
            html = self._fetch(url)
            result['list'] = self._parse_table_body(html)
            result['pagecount'] = self._get_pagecount(html, r'/music/id-\d+-(\d+)\.html[^>]*>尾页')
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
                "vod_play_from": "啊哈DJ网",
                "vod_play_url": "",
                "vod_pic": self.default_pic,
            }]
        return result

    def _single_detail(self, sid):
        url = f"{self.site_url}/music/{sid}.html"
        html = self._fetch(url)
        soup = BeautifulSoup(html, 'html.parser')

        # 标题：您在视听：<span>Title</span>
        name = '未知舞曲'
        for h2 in soup.find_all('h2'):
            text = h2.get_text(strip=True)
            if '您在视听' in text:
                span = h2.find('span')
                if span:
                    name = self._clean_name(span.get_text(strip=True))
                else:
                    name = self._clean_name(text.replace('您在视听：', '').replace('您在视听', ''))
                break

        # 兜底取 title / h1
        if name == '未知舞曲':
            title_tag = soup.find('title')
            if title_tag:
                name = self._clean_name(title_tag.get_text(strip=True).split('-')[0])

        # 信息区
        content = []
        for div in soup.find_all('div', class_=re.compile(r'author_hint|m_author')):
            text = div.get_text('\n', strip=True)
            if text:
                content.append(text)
        content_str = '\n'.join(content) if content else '暂无简介'

        # 发布日期
        date = ''
        for m in re.finditer(r'发布日期', html):
            start = max(0, m.start() - 20)
            end = min(len(html), m.end() + 50)
            snippet = re.sub(r'<[^>]+>', ' ', html[start:end]).strip()
            if '：' in snippet:
                date = snippet.split('：', 1)[-1].strip()[:10]
                break

        return {
            "vod_id": sid,
            "vod_name": name,
            "vod_pic": self.default_pic,
            "vod_content": content_str,
            "vod_remarks": date or 'DJ舞曲',
            "vod_actor": name,
            "vod_play_from": "啊哈DJ网",
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
            # 取播放页基本信息（封面/标题）
            play_page_url = f"{self.site_url}/music/{sid}.html"
            html = self._fetch(play_page_url)

            name = ''
            for h2 in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.S | re.I):
                if '您在视听' in h2:
                    span = re.search(r'<span[^>]*>(.*?)</span>', h2, re.S)
                    if span:
                        name = self._clean_name(span.group(1))
                    break

            # ---------- 视频类型（超清/车载等 MP4） ----------
            m_vios = re.search(r'var\s+vIosurl\s*=\s*"([^"]+)"', html)
            if m_vios:
                server_url = f"{self.site_url}/dj/server/{sid}.html"
                server_html = self._fetch(server_url)
                serverpath = ''
                play_key = 'asdf4454545'
                m_sp = re.search(r'var\s+serverpath\s*=\s*"([^"]+)"', server_html)
                m_pk = re.search(r'var\s+play_key\s*=\s*"([^"]+)"', server_html)
                if m_sp:
                    serverpath = m_sp.group(1)
                if m_pk:
                    play_key = m_pk.group(1)

                if serverpath:
                    vios = unquote(m_vios.group(1))
                    base = self._strencode(serverpath, play_key)
                    if base:
                        play_url = base.rstrip('/') + '/' + vios.lstrip('/')
                        result.update({
                            "url": play_url,
                            "header": self.headers,
                            "name": name,
                            "pic": self.default_pic,
                        })
                        return result

            # ---------- 音频类型（MP3/M4A 等） ----------
            m_audio = re.search(r"danceFilePath\s*=\s*'([^']+)'", html)
            if not m_audio:
                m_audio = re.search(r'danceFilePath\s*=\s*"([^"]+)"', html)
            if m_audio:
                api_url = f"{self.site_url}/index.php/api/server/{sid}"
                api_html = self._fetch(api_url)
                m_asp = re.search(r'var\s+serverpath\s*=\s*"([^"]+)"', api_html)
                base = ''
                if m_asp:
                    base = m_asp.group(1)
                if not base:
                    base = self.cdn_url
                audio_path = m_audio.group(1)
                play_url = base.rstrip('/') + '/' + audio_path.lstrip('/')
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
        url = f"{self.site_url}/search/?key={quote(key)}&page={pg}.html"
        try:
            html = self._fetch(url)
            result['list'] = self._parse_table_body(html)
            result['pagecount'] = self._get_pagecount(html, r'page=(\d+)\.html[^>]*>尾页')
        except Exception:
            pass
        return result

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, urllib.parse, json, base64
from bs4 import BeautifulSoup
from base.spider import Spider
class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://wbbb1.com"
        self.limit = 24
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': self.site_url}
        self.categories = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "剧集"},
            {"type_id": "3", "type_name": "动漫"},
            {"type_id": "4", "type_name": "综艺"}
        ]
    
    def _fetch(self, url):
        try:
            import requests
            r = requests.get(url, headers=self.headers, timeout=15)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r
        except:
            return None
    
    def _parse_video_card(self, card):
        link_elem = card.select_one('a') or card
        href = link_elem.get('href', '')
        match = re.search(r'/detail/(\d+)\.html', href)
        if not match: return None
        vod_id = match.group(1)
        title_elem = card.select_one('.module-item-title') or card.select_one('.module-poster-item-title')
        vod_name = title_elem.get_text(strip=True) if title_elem else ''
        img_elem = card.select_one('img')
        vod_pic = (img_elem.get('data-original', '') or img_elem.get('data-src', '') or img_elem.get('src', '')) if img_elem else ''
        tag_elem = card.select_one('.module-item-note') or card.select_one('.module-item-text')
        vod_remarks = tag_elem.get_text(strip=True) if tag_elem else ''
        return {"vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic, "vod_remarks": vod_remarks}
    
    def homeContent(self, filter):
        url = f"{self.site_url}/"
        resp = self._fetch(url)
        video_list = []
        if resp:
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('.module-items .module-item') or soup.select('.module-items a.module-poster-item')
            for card in cards[:24]:
                item = self._parse_video_card(card)
                if item: video_list.append(item)
        return {"class": self.categories, "list": video_list, "filters": {}}
    
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = f"{self.site_url}/type/{tid}.html" if page == 1 else f"{self.site_url}/type/{tid}/{page}.html"
        resp = self._fetch(url)
        if not resp: return {"list": [], "page": page, "pagecount": 1, "limit": self.limit, "total": 0}
        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = []
        cards = soup.select('.module-items .module-item') or soup.select('.module-items a.module-poster-item')
        for card in cards:
            item = self._parse_video_card(card)
            if item: video_list.append(item)
        pagecount = 1
        for a in soup.select('.page-link') or soup.select('.pagination a'):
            if a.get_text(strip=True).isdigit(): pagecount = max(pagecount, int(a.get_text(strip=True)))
        return {"list": video_list, "page": page, "pagecount": pagecount, "limit": self.limit, "total": 0}
    
    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = ids[0]
        url = f"{self.site_url}/detail/{vod_id}.html"
        resp = self._fetch(url)
        if not resp: return {"list": []}
        soup = BeautifulSoup(resp.text, 'html.parser')
        vod_name = (t.get_text(strip=True) for t in [soup.select_one('.module-info-heading h1')] if t)
        vod_name = next(vod_name, '')
        img_elem = soup.select_one('.module-info-poster img')
        vod_pic = (img_elem.get('data-original', '') or img_elem.get('src', '')) if img_elem else ''
        desc_elem = soup.select_one('.module-info-introduction-content p')
        vod_content = desc_elem.get_text(strip=True) if desc_elem else ''
        vod_director = vod_actor = ''
        for item in soup.select('.module-info-item'):
            ts = item.select_one('.module-info-item-title')
            cd = item.select_one('.module-info-item-content')
            if not ts or not cd: continue
            l = ts.get_text(strip=True)
            if '导演' in l: vod_director = cd.get_text(strip=True)
            if '主演' in l: vod_actor = cd.get_text(strip=True)
        tab_items = soup.select('.module-tab-item')
        play_containers = soup.select('.module-list.sort-list.tab-list')
        play_from_list, play_url_list = [], []
        if tab_items and play_containers and len(tab_items) == len(play_containers):
            for idx, tab in enumerate(tab_items):
                source_name = tab.get('data-dropdown-value', '') or tab.get_text(strip=True)
                episodes = [f"{a.get_text(strip=True)}${a.get('href', '')}" for a in play_containers[idx].select('a.module-play-list-link') if a.get('href', '')]
                if episodes: play_from_list.append(source_name); play_url_list.append('#'.join(episodes))
        else:
            all_items = soup.select('.module-play-list-content a.module-play-list-link')
            if all_items:
                episodes = [f"{a.get_text(strip=True)}${a.get('href', '')}" for a in all_items if a.get('href', '')]
                if episodes: play_from_list.append('默认线路'); play_url_list.append('#'.join(episodes))
        return {"list": [{"vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic, "vod_content": vod_content, "vod_director": vod_director, "vod_actor": vod_actor, "vod_play_from": '$$$'.join(play_from_list), "vod_play_url": '$$$'.join(play_url_list)}]}
    
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f"{self.site_url}/search/{urllib.parse.quote(key)}-------------.html" if page == 1 else f"{self.site_url}/search/{urllib.parse.quote(key)}----------{page}---.html"
        resp = self._fetch(url)
        if not resp: return {"list": [], "page": page, "pagecount": 1}
        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = []
        for card in soup.select('.module-items .module-item') or soup.select('.module-items a.module-poster-item'):
            item = self._parse_video_card(card)
            if item: video_list.append(item)
        return {"list": video_list, "page": page, "pagecount": 1}
    
    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith('http') else self.site_url + id
        resp = self._fetch(url)
        if not resp: return {"parse": 1, "url": url, "header": self.headers}
        html = resp.text
        player_match = re.search(r'var player_aaaa=(\{.*?\})', html)
        if not player_match: return {"parse": 1, "url": url, "header": self.headers}
        try:
            player_data = json.loads(player_match.group(1))
            encrypt = player_data.get('encrypt', '0')
            play_url = player_data.get('url', '')
            if encrypt == '1':
                play_url = urllib.parse.unquote(play_url)
            elif encrypt == '2':
                play_url = urllib.parse.unquote(base64.b64decode(play_url).decode('utf-8'))
            # 构建解析器URL，包含next和title参数
            next_url = player_data.get('link_next', '')
            title = player_data.get('vod_name', '') or player_data.get('title', '')
            parse_url = f"https://xn--qvr2v.850088.xyz/player/?url={play_url}&next={urllib.parse.quote(next_url)}&title={urllib.parse.quote(title)}"
            return {"parse": 1, "url": parse_url, "header": self.headers}
        except:
            return {"parse": 1, "url": url, "header": self.headers}
    
    def getName(self):
        return "歪比巴卜"

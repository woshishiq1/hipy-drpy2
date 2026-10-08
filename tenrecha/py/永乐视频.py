import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

class Spider:
    
    def __init__(self):
        self.name = "永乐视频"
        self.home_url = "https://www.59v.net"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; M2102J2SC Build/UKQ1.240624.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.86 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': self.home_url
        }
        self.categories = {
            "电影": "1",
            "剧集": "2",
            "综艺": "3", 
            "动漫": "4"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def getName(self):
        return self.name
    
    def getDependence(self):
        return ["json", "re", "requests", "bs4"]
    
    def init(self, extend):
        return True
    
    def isVideoFormat(self, url):
        video_formats = ['.mp4', '.m3u8', '.flv', '.avi', '.mkv', '.ts']
        return any(fmt in url.lower() for fmt in video_formats)
    
    def manualVideoCheck(self):
        return False
    
    def homeContent(self, filter):
        result = {"class": []}
        for name, cid in self.categories.items():
            result["class"].append({
                "type_id": cid,
                "type_name": name
            })
        return result
    
    def homeVideoContent(self):
        videos = []
        try:
            resp = self.session.get(self.home_url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            items = soup.select('.module-item')
            for item in items:
                a_tag = item if item.name == 'a' else item.select_one('a')
                if not a_tag: continue
                    
                url = a_tag.get('href', '')
                if not url.startswith('/voddetail/'): continue
                
                title = a_tag.get('title', '')
                if not title:
                    title_div = a_tag.select_one('.module-poster-item-title')
                    if title_div: title = title_div.text.strip()
                
                img_tag = a_tag.select_one('img')
                pic = ''
                if img_tag:
                    pic = img_tag.get('data-original') or img_tag.get('src', '')
                
                note_tag = a_tag.select_one('.module-item-note')
                remark = note_tag.text.strip() if note_tag else ''
                
                videos.append({
                    "vod_id": url,
                    "vod_name": title,
                    "vod_pic": urljoin(self.home_url, pic),
                    "vod_remarks": remark
                })
        except Exception:
            pass
            
        return {'list': videos}
    
    def categoryContent(self, cid, pg, filter, ext):
        videos = []
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
            url = f"{self.home_url}/vodshow/{cid}--------{page}---/"
            
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            items = soup.select('.module-item')
            for item in items:
                a_tag = item if item.name == 'a' else item.select_one('a')
                if not a_tag: continue
                    
                href = a_tag.get('href', '')
                if not href.startswith('/voddetail/'): continue
                
                title = a_tag.get('title', '')
                img_tag = a_tag.select_one('img')
                pic = img_tag.get('data-original') or img_tag.get('src', '') if img_tag else ''
                
                note_tag = a_tag.select_one('.module-item-note')
                remark = note_tag.text.strip() if note_tag else ''
                
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": urljoin(self.home_url, pic),
                    "vod_remarks": remark
                })
        except Exception:
            pass
            
        return {
            'list': videos,
            'page': page,
            'pagecount': 999 if len(videos) >= 20 else page,
            'limit': 40,
            'total': 999999
        }
    
    def detailContent(self, ids):
        if not ids:
            return {'list': []}
            
        try:
            vid = ids[0]
            url = urljoin(self.home_url, vid)
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            vod = {
                "vod_id": vid,
                "vod_name": "未知"
            }
            
            title_tag = soup.select_one('.module-info-heading h1') or soup.select_one('.page-title')
            if title_tag:
                vod['vod_name'] = title_tag.text.strip()
                
            img_tag = soup.select_one('.module-info-poster img') or soup.select_one('.module-item-pic img')
            if img_tag:
                vod['vod_pic'] = urljoin(self.home_url, img_tag.get('data-original') or img_tag.get('src', ''))
                
            intro = soup.select_one('.module-info-introduction-content p')
            if intro:
                vod['vod_content'] = intro.text.strip()
                
            info_items = soup.select('.module-info-item')
            for item in info_items:
                text = item.text
                if '导演：' in text: vod['vod_director'] = text.replace('导演：', '').strip()
                elif '主演：' in text: vod['vod_actor'] = text.replace('主演：', '').strip()
                elif '上映：' in text: vod['vod_year'] = text.replace('上映：', '').strip()
                elif '连载：' in text: vod['vod_remarks'] = text.replace('连载：', '').strip()
            
            play_sources = []
            
            tab_box = soup.select_one('.module-tab-items-box')
            if tab_box:
                for tab in tab_box.select('.tab-item'):
                    span = tab.select_one('span')
                    if span:
                        name = span.text.strip()
                    else:
                        small = tab.select_one('small')
                        name = tab.text.replace(small.text, '').strip() if small else tab.text.strip()
                        
                    if name and name not in play_sources:
                        play_sources.append(name)
            else:
                for tab in soup.select('.module-tab-item.tab-item'):
                    span = tab.select_one('span')
                    name = span.text.strip() if span else tab.text.strip()
                    name = re.sub(r'\d+$', '', name).strip()
                    if name and name not in play_sources:
                        play_sources.append(name)
                        
            play_lists = []
            list_divs = soup.select('.module-play-list-content')
            for list_div in list_divs:
                links = list_div.select('a.module-play-list-link')
                episodes = []
                for link in links:
                    span = link.select_one('span')
                    ep_name = span.text.strip() if span else link.text.strip()
                    ep_url = link.get('href', '')
                    episodes.append(f"{ep_name}${ep_url}")
                if episodes:
                    play_lists.append("#".join(episodes))
            
            if play_sources and play_lists:
                valid_len = min(len(play_sources), len(play_lists))
                vod['vod_play_from'] = "$$$".join(play_sources[:valid_len])
                vod['vod_play_url'] = "$$$".join(play_lists[:valid_len])
            
            return {'list': [vod]}
        except Exception:
            pass
        return {'list': []}
            
    def searchContent(self, key, quick, pg="1"):
        try:
            encoded_key = quote(key)
            if str(pg) == "1":
                url = f"{self.home_url}/vodsearch/{encoded_key}-------------/"
            else:
                url = f"{self.home_url}/vodsearch/{encoded_key}----------{pg}---/"
                
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            videos = []
            items = soup.select('.module-card-item')
            if not items:
                items = soup.select('.module-item')
                
            for idx, item in enumerate(items):
                try:
                    a_tag = item.select_one('.module-card-item-poster') or item.select_one('.module-card-item-title a') or item.select_one('a')
                    if not a_tag:
                        continue
                        
                    href = a_tag.get('href', '')
                    if not href.startswith('/voddetail/'):
                        continue
                    
                    title = ''
                    title_tag = item.select_one('.module-card-item-title strong') or item.select_one('.module-card-item-title a')
                    if title_tag:
                        title = title_tag.text.strip()
                    
                    img_tag = item.select_one('img')
                    if not title and img_tag:
                        title = img_tag.get('alt', '')
                        
                    pic = img_tag.get('data-original') or img_tag.get('src', '') if img_tag else ''
                    
                    note_tag = item.select_one('.module-item-note')
                    remark = note_tag.text.strip() if note_tag else ''
                    
                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": urljoin(self.home_url, pic),
                        "vod_remarks": remark
                    })
                except Exception:
                    pass
                
            return {'list': videos}
        except Exception:
            pass
        return {'list': []}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        try:
            url = urljoin(self.home_url, id)
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            
            match = re.search(r'var\s+player_aaaa\s*=\s*({.+?})</script>', resp.text)
            if match:
                player_data = json.loads(match.group(1))
                real_url = player_data.get('url', '')
                
                if real_url.endswith('.m3u8') or real_url.endswith('.mp4'):
                    return {
                        'parse': 0,
                        'url': real_url,
                        'header': ''
                    }
                    
            return {'parse': 1, 'url': url}
        except Exception:
            pass
        return {'parse': 1, 'url': id}
            
    def localProxy(self, params):
        return None

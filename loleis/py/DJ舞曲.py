# -*- coding: utf-8 -*-
#作者 千城-爱折腾 🚓 内容均从互联网收集而来 仅供交流学习使用 请24小时内删除，版权归原网站所有 如侵犯了您的权益 请通知作者 将及时删除侵权内容
#          =============================3995912587@qq.com===================

import re
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.host = 'https://m.xiaomidj.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Referer': self.host,
        }
        self.default_pic = 'https://raw.giteeusercontent.com/xianluyuan/WP/raw/master/image_download_1767716901851.jpg?metadata=eyJyIjoibWFzdGVyIiwiZnAiOiJpbWFnZV9kb3dubG9hZF8xNzY3NzE2OTAxODUxLmpwZyIsInVpZCI6MTYwMTU2NzEsInBpZCI6NDMxOTI0MDgsInN0byI6ImdpdC1zaGFyZGluZy1zdG8tMTB0LTA0MSIsInJwIjoicmVwb3MvYWEvZWEvYWFlYWJmM2IxODE0YjJjNjc0OTcyODM3ZGU2YThjZDkxYjc1MjYxZjUxNWJhNTg5OGIyOGI3YmZjZjA0NTgzMy5naXQiLCJpc3AiOnRydWUsImV4cGlyZV9hdCI6MTc4MDc1NjgwMH0&signature=cEOlUwSkvyXHiEVgFLk9cgEauGonjpnvdQALP9qkPsc'
        self.type_map = {
            '串烧车载': '1', '国潮改版': '2', '外文Remix': '3',
            '视频舞曲': '31', '酒吧视频': '32', '跳舞视频': '33',
            '前场Deep': '38', 'Hiphop': '39', 'Dubstep': '40',
            '酒吧串烧': '14', '包房串烧': '15', '包房嗨曲': '41',
            '越南电鼓': '5', '前场套曲': '42', '主场套曲': '43',
            '后场套曲': '44', '派对歌路': '45', '综合套曲': '46',
            '伤感串烧': '9', '劲爆舞曲': '10', '电音车载': '11',
            '试音车载': '12', '车载连版': '13', '中文ProgHouse': '17',
            '中文FunkyHouse': '18', '中文Electro': '19', '中文Dance&Club': '20',
            '中文Disco': '47', '中文越南鼓': '21', '中文综合': '22',
            '外文Electro&House': '24', '外文Dance&Club': '25', '外文Disco': '26',
            '外文综合': '27', '韩国风Bounce': '28', '反差/变速': '29',
            '开场音乐': '30', '私房串烧': '35', '私房单曲': '36', '越南风': '34',
        }

    def getName(self):
        return "精彩DJ"

    def homeContent(self, filter):
        classes = [{'type_id': cid, 'type_name': name} for name, cid in self.type_map.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        return self._get_home_recommend()

    def _get_home_recommend(self):
        url = self.host
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        for box in soup.select('.index_list_box'):
            block_name_tag = box.select_one('.huititle .ztitle li')
            if not block_name_tag:
                continue
            block_name = block_name_tag.get_text(strip=True)
            for dl in box.select('.modiv2 dl'):
                link = dl.select_one('dt a')
                if not link:
                    continue
                href = link.get('href')
                if '/' in href:
                    song_id = href.strip('/').split('/')[-1].replace('.html', '')
                else:
                    song_id = href.replace('.html', '')
                title = link.get('title', '').strip()
                date_tag = dl.select_one('.d2 font')
                date = date_tag.get_text(strip=True) if date_tag else ''
                items.append({
                    'vod_id': song_id,
                    'vod_name': title,
                    'vod_pic': self.default_pic,
                    'vod_remarks': date,
                    'vod_year': '',
                    'type_name': block_name
                })
        return {'list': items, 'pagecount': 1, 'page': 1}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/dj/id-{tid}-{pg}.html"
        print(f"[DEBUG] 请求分类页: {url}")
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        items = []
        # 多种选择器适配不同结构
        dls = soup.select('.modiv2 dl')
        if not dls:
            dls = soup.select('.songs_list dl')
        if not dls:
            dls = soup.select('.index_list_box .modiv2 dl')
        if not dls:
            dls = [dl for dl in soup.find_all('dl') if dl.find('dt') and dl.find('dt').find('a')]

        print(f"[DEBUG] 找到 {len(dls)} 个条目")

        for dl in dls:
            link = dl.select_one('dt a')
            if not link:
                continue
            href = link.get('href')
            if '/' in href:
                song_id = href.strip('/').split('/')[-1].replace('.html', '')
            else:
                song_id = href.replace('.html', '')
            title = link.get('title', '').strip()
            if not title:
                title = link.get_text(strip=True)

            date_tag = dl.select_one('.d2 font')
            if not date_tag:
                date_tag = dl.select_one('.date')
            date = date_tag.get_text(strip=True) if date_tag else ''

            items.append({
                'vod_id': song_id,
                'vod_name': title,
                'vod_pic': self.default_pic,
                'vod_remarks': date,
                'vod_year': '',
            })

        # 分页
        total_page = 99
        pagination = soup.select('.pagination a')
        if not pagination:
            pagination = soup.select('.page-list a')
        if pagination:
            last_link = pagination[-1].get('href')
            if last_link:
                match = re.search(r'-(\d+)\.html', last_link)
                if match:
                    total_page = int(match.group(1))
                elif 'page=' in last_link:
                    total_page = int(last_link.split('page=')[-1].split('&')[0])
        return {
            'list': items,
            'pagecount': total_page,
            'page': int(pg)
        }

    def detailContent(self, ids):
        song_id = ids[0]
        url = f"{self.host}/dj/{song_id}.html"
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.encoding = 'utf-8'
        html = resp.text

        mp3_url = None
        match = re.search(r"var firstplay\s*=\s*'([^']+)'", html)
        if match:
            mp3_url = match.group(1)

        title = ''
        title_match = re.search(r'<div class="center music-name">\s*<<span>(.*?)</span>', html, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        else:
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.select_one('.music-name span')
            if title_tag:
                title = title_tag.get_text(strip=True)

        pic = ''
        pic_match = re.search(r'<img src="([^"]+)" class="[^"]*">', html)
        if pic_match:
            pic = pic_match.group(1)
        else:
            soup = BeautifulSoup(html, 'html.parser')
            img = soup.select_one('.music-player__img img')
            if img and img.get('src'):
                pic = img['src']

        # 兜底：如果页面没抓到图，就用默认图
        if not pic:
            pic = self.default_pic

        video = {
            'vod_id': song_id,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': '',
            'vod_year': '',
            'vod_area': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': '',
            'vod_play_from': '精彩DJ',
            'vod_play_url': f'正片${mp3_url}' if mp3_url else ''
        }
        return {'list': [video]}

    def playerContent(self, flag, vid, vipFlags):
        if not vid.startswith('http'):
            song_id = vid
            url = f"{self.host}/dj/{song_id}.html"
            resp = requests.get(url, headers=self.headers, timeout=15)
            html = resp.text
            match = re.search(r"var firstplay\s*=\s*'([^']+)'", html)
            if match:
                mp3_url = match.group(1)
            else:
                mp3_url = ''
        else:
            mp3_url = vid
        return {'jx': 0, 'parse': 0, 'url': mp3_url, 'header': self.headers}

    def searchContent(self, key, quick, pg='1'):
        url = f"{self.host}/search/dj"
        params = {'key': key, 'page': pg}
        resp = requests.get(url, headers=self.headers, params=params, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        for dl in soup.select('.modiv2 dl'):
            link = dl.select_one('dt a')
            if not link:
                continue
            href = link.get('href')
            if '/' in href:
                song_id = href.strip('/').split('/')[-1].replace('.html', '')
            else:
                song_id = href.replace('.html', '')
            title = link.get('title', '').strip()
            items.append({
                'vod_id': song_id,
                'vod_name': title,
                'vod_pic': self.default_pic,
                'vod_remarks': '',
                'vod_year': '',
            })
        return {'list': items, 'page': pg}

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass

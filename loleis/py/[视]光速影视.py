"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '光速影视',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
import re, sys
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=''):
        self.host = 'https://www.4kzaixian.top'

    def getName(self):
        return '光速影视'

    def homeContent(self, filter):
        html = self.fetch(self.host + '/').text
        return {
            'class': [
                {"type_name": "电视剧", "type_id": "2"},
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"}
            ],
            'filters': {},
            'list': self.get_vod_list(html)
        }

    def homeVideoContent(self):
        return self.get_vod_list(self.fetch(self.host + '/').text)

    def categoryContent(self, tid, pg, filter, extend):
        if pg == 1:
            url = self.host + '/list/?' + tid + '.html'
        else:
            url = self.host + '/list/?' + tid + '-' + str(pg) + '.html'
        return {
            'list': self.get_vod_list(self.fetch(url).text),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def detailContent(self, ids):
        url = ids[0] if ids[0].startswith('http') else self.host + ids[0]
        html = self.fetch(url).text
        if len(html) < 500: return {'list': []}
        
        t = re.search(r'class="movie-title"[^>]*>([^<]+)<span', html)
        if not t: t = re.search(r'<title>[《]([^》]+)[》]', html)
        name = t.group(1).strip() if t else '未知'
        
        pic = re.search(r'class="img-thumbnail"[^>]+src="([^"]+)"', html)
        desc = re.search(r'class="summary"[^>]*>([\s\S]*?)</p>', html)
        
        # 播放列表
        all_plays = re.findall(r'title="([^"]+)"[^>]+href="(/video/[^"]+)"', html)
        
        if all_plays:
            from collections import defaultdict
            lines = defaultdict(list)
            for title, play_url in all_plays:
                if title.strip() and '/video/' in play_url:
                    m = re.search(r'/video/[^"]*-(\d+)-\d+\.html', play_url)
                    if m:
                        line_id = m.group(1)
                        lines[line_id].append(title + '$' + self.host + play_url)
            
            line_names = {'0': 'mtm3u8', '1': '电影天堂云', '2': 'jsyun'}
            play_from = [line_names.get(k, '线路' + k) for k in sorted(lines.keys())]
            play_url = ['#'.join(lines[k]) for k in sorted(lines.keys())]
        else:
            play_from = ["光速影视"]
            mid = re.search(r'/detail/\?(\d+)', url)
            play_url = ['播放$' + self.host + '/video/?' + mid.group(1) + '-0-0.html'] if mid else [""]
        
        return {
            'list': [{
                "vod_id": url,
                "vod_name": name,
                "vod_pic": pic.group(1) if pic else '',
                "vod_content": desc.group(1)[:500].strip() if desc else '',
                "vod_play_from": '$$$'.join(play_from),
                "vod_play_url": '$$$'.join(play_url)
            }]
        }

    def searchContent(self, key, quick, pg='1'):
        url = self.host + '/search.php?searchword=' + quote(key)
        return {
            'list': self.get_vod_list(self.fetch(url).text),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith('http') else self.host + id
        html = self.fetch(url).text
        m3u8 = re.search(r'var now\s*=\s*["\u0027]([^"\u0027]+\.m3u8[^"\u0027]*)["\u0027]', html)
        if m3u8:
            return {'parse': 0, 'url': m3u8.group(1), 'header': {'Referer': self.host}}
        return {'parse': 1, 'url': url, 'header': {'Referer': self.host}}

    def get_vod_list(self, html):
        videos, seen = [], set()
        for m in re.finditer(r'href="(/detail/\?\d+\.html)"[^>]+title="([^"]+)"', html):
            url, title = m.group(1), m.group(2)
            if url in seen: continue
            seen.add(url)
            ctx = html[max(0, m.start()-200):m.end()+200]
            pic_m = re.search(r'src="(https?://[^\s"]+\.(jpg|webp|png))"', ctx)
            remark_m = re.search(r'class="hdtag"[^>]*>([^<]+)</button>', ctx)
            videos.append({
                "vod_id": self.host + url,
                "vod_name": title,
                "vod_pic": pic_m.group(1) if pic_m else '',
                "vod_remarks": remark_m.group(1).strip() if remark_m else ''
            })
        return videos
"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '天天影院',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
import re, sys, json
from urllib.parse import quote, urljoin
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=''):
        self.host = 'https://m.rvm2.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Referer': self.host + '/',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }

    def getName(self):
        return '天天影院'

    def homeContent(self, filter):
        html = self.clean(self.get_html(self.host + '/'))
        return {
            'class': [
                {"type_name": "电影", "type_id": "dianyingyuan"},
                {"type_name": "电视剧", "type_id": "dianshiju"},
                {"type_name": "短剧", "type_id": "duanju"},
                {"type_name": "动漫", "type_id": "dongman"},
                {"type_name": "综艺", "type_id": "zongyi"}
            ],
            'filters': {},
            'list': self.vod_list(html)[:30]
        }

    def homeVideoContent(self):
        html = self.clean(self.get_html(self.host + '/'))
        return self.vod_list(html)[:30]

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = self.host + "/vodtype/" + tid + ".html"
        else:
            url = self.host + "/vodtype/" + tid + "-" + str(pg) + ".html"
        html = self.clean(self.get_html(url))
        return {
            'list': self.vod_list(html),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def detailContent(self, ids):
        url = ids[0] if ids[0].startswith('http') else urljoin(self.host, ids[0])
        html = self.clean(self.get_html(url))
        if len(html) < 500:
            return {'list': []}

        name = "未知影片"
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()

        pic = ""
        m = re.search(r'class="aspect-\[2/3\]"[\s\S]*?<img[^>]+src="([^"]+)"', html)
        if not m:
            m = re.search(r'og:image"[^>]+content="([^"]+)"', html)
        if m:
            pic = self.fix_url(m.group(1))

        desc = ""
        m = re.search(r'class="text-sm text-gray-700 leading-relaxed mb-3"[^>]*>(.+?)</p>', html, re.DOTALL)
        if not m:
            m = re.search(r'og:description"[^>]+content="([^"]+)"', html)
        if m:
            desc = m.group(1).strip()[:500]

        pf, pu = self.play_list(html)

        return {
            'list': [{
                "vod_id": url,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": '$$$'.join(pf),
                "vod_play_url": '$$$'.join(pu)
            }]
        }

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg) if pg else 1
        url = self.host + "/vodsearch/-------------.html?wd=" + quote(key) + "&page=" + str(pg)
        html = self.clean(self.get_html(url))
        return {
            'list': self.vod_list(html),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith('http') else urljoin(self.host, id)
        html = self.clean(self.get_html(play_url))

        m = re.search(r'player_aaaa\s*=\s*(\{.+?\});', html, re.DOTALL)
        if m:
            try:
                json_str = m.group(1).replace("\u0027", "\"")
                data = json.loads(json_str)
                if data.get('url'):
                    return {'parse': 0, 'url': data['url'], 'header': {'Referer': self.host}}
            except:
                pass

        return {'parse': 1, 'url': play_url, 'header': {'Referer': self.host}}

    def get_html(self, url):
        return self.fetch(url, headers=self.headers).text

    def clean(self, html):
        html = html.replace(r'\u003c', '<').replace(r'\u003e', '>')
        return html

    def fix_url(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def vod_list(self, html):
        vods = []
        seen = {}
        items = re.findall(r'href="(/voddetail/\d+\.html)"[^>]+title="([^"]+)"[\s\S]*?<img[^>]+src="([^"]+)"', html)
        
        for href, title, pic in items:
            full_url = self.host + href
            if seen.get(full_url):
                continue
            seen[full_url] = True
            name = title.strip()
            if not name:
                continue
            
            remark = ""
            idx = html.find(href)
            if idx > 0:
                seg = html[idx:idx + 300]
                rm = re.search(r'class="badge-orange"[^\u003e]*\u003e([^<]+)\u003c/span\u003e', seg)
                if rm:
                    remark = rm.group(1).strip()
            
            vods.append({
                'vod_id': full_url,
                'vod_name': name,
                'vod_pic': self.fix_url(pic),
                'vod_remarks': remark
            })
        
        return vods

    def play_list(self, html):
        pf = []
        pu = []
        
        # 提取所有tab-btn
        tab_btns = re.findall(r'player-tab-btn[\s\S]*?data-player="(\d+)"[\s\S]*?\u003cspan\u003e([^<]+)\u003c/span\u003e', html)
        
        # 提取所有play-list-box内容
        all_boxes = re.findall(r'play-list-box[^\"]*"[^\u003e]*\u003e(.+?)(?=play-list-box|detail-playlist|$)', html, re.DOTALL)
        
        tab_count = len(tab_btns)
        box_count = len(all_boxes)
        
        for i in range(tab_count):
            pid, tab_name = tab_btns[i]
            pf.append(tab_name.strip())
            
            # 找对应player的集数
            if i < box_count:
                block = all_boxes[i]
                links = re.findall(r'href="(/vodplay/[^"]+)"[^\u003e]*title="([^"]+)"', block)
                if not links:
                    links = re.findall(r'href="(/vodplay/[^"]+)"[^\u003e]*\u003e([^<]+)\u003c/a>', block)
                eps = [title.strip() + "$" + self.host + href for href, title in links if title.strip()]
                pu.append("#".join(eps) if eps else "播放$" + self.host)
            else:
                pu.append("播放$" + self.host)
        
        # 兜底
        if not pf:
            pf.append("默认线路")
            links = re.findall(r'href="(/vodplay/[^"]+)"[^\u003e]*title="([^"]+)"', html)
            if not links:
                links = re.findall(r'href="(/vodplay/[^"]+)"[^\u003e]*\u003e([^<]+)\u003c/a>', html)
            eps = [title.strip() + "$" + self.host + href for href, title in links if title.strip()]
            pu.append("#".join(eps) if eps else "播放$" + self.host)
        
        return (pf, pu)
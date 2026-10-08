#coding=utf-8
import sys
import re
import json
import html as html_module
import requests
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site = 'https://cn1.xgcartoon.com'
        self.video_base = 'https://xgct-video.bzcdn.net'
        self.frame_base = 'https://pframe.xgcartoon.com'
        self.session = requests.Session()
        self.ua = 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        self.session.headers.update({'User-Agent': self.ua})
        self.cateManual = {}

    def _fetch_categories(self):
        html = self._get(f'{self.site}/classify')
        if not html:
            return
        for m in re.finditer(r'href="/classify\?type=([^&"]+)[^"]*"[^>]*>([^<]*)<', html):
            tid = m.group(1).replace('%2a', '*').strip()
            name = m.group(2).strip()
            if name and name != '\u5168\u90e8' and tid != '*' and tid not in self.cateManual:
                self.cateManual[tid] = name

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = html_module.unescape(text)
        text = text.replace('&amp;', '&').replace('\xa0', ' ').replace('\u3000', ' ')
        text = ' '.join(text.split())
        return text.strip()

    def _get(self, url):
        try:
            r = self.session.get(url, timeout=15, headers={'Referer': self.site})
            r.encoding = 'utf-8'
            return r.text
        except:
            return ''

    def _fetch_api_list(self, page, tid='', limit=36):
        videos = []
        api_type = tid if tid else '*'
        url = f'{self.site}/api/amp_query_cartoon_list?type={api_type}&region=*&filter=*&filter=*&page={page}&limit={limit}&language=cn'
        html = self._get(url)
        if not html:
            return videos, 0
        try:
            data = json.loads(html)
            items = data.get('items', [])
            next_url = data.get('next', '')
            has_more = 1 if next_url else 0
        except:
            return videos, 0
        for item in items:
            cartoon_id = item.get('cartoon_id', '')
            name = item.get('name', '')
            author = item.get('author', '')
            region = item.get('region_name', '')
            topic_img = item.get('topic_img', '')
            type_names = item.get('type_names', [])
            if not cartoon_id or not name:
                continue
            pic = f'https://static-a.xgcartoon.com/cover/{topic_img}' if topic_img else ''
            tag_str = '/'.join(type_names[:2]) if type_names else ''
            remarks = author if author else region
            if tag_str:
                remarks = f'{remarks} {tag_str}' if remarks else tag_str
            videos.append({
                'vod_id': cartoon_id,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks[:40]
            })
        return videos, has_more

    def _extract_list(self, html):
        videos = []
        seen = set()
        for m in re.finditer(r'href="/detail/([^"]+)"', html):
            vid = m.group(1).strip()
            if vid in seen:
                continue
            seen.add(vid)
            snippet = html[m.start():m.start()+1000]
            title = ''
            tm = re.search(r'class="h3[^"]*"[^>]*>\s*(.*?)\s*</h3>', snippet, re.DOTALL)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'class="h3[^"]*"[^>]*>\s*(.*?)\s*</div>', snippet, re.DOTALL)
                if tm:
                    title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'class="title"[^>]*>\s*(.*?)\s*</(?:a|h\d|div)>', snippet, re.DOTALL)
                if tm:
                    title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'<h2[^>]*>(.*?)</h2>', snippet, re.DOTALL)
                if tm:
                    title = self._clean(tm.group(1))
            pic = ''
            pm = re.search(r'src="(https://static-a\.xgcartoon\.com/[^"]+\.jpg[^"]*)"', snippet)
            if pm:
                pic = pm.group(1).strip().replace('&amp;', '&')
            tags = re.findall(r'class="tag[^"]*"[^>]*>\s*(.*?)\s*<', snippet)
            tag_str = ' '.join(t.strip() for t in tags if t.strip())[:30]
            author = ''
            am = re.search(r'(?:class="author"|topic-list-item--author)[^>]*>\s*(.*?)\s*<', snippet, re.DOTALL)
            if am:
                author = self._clean(am.group(1))
            remarks = tag_str
            if author:
                remarks = (author + ' ' + remarks) if remarks else author
            if title and pic:
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks[:40]
                })
        return videos

    def init(self, extend=''):
        pass

    def getName(self):
        return '西瓜卡通'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        if not self.cateManual:
            self._fetch_categories()
        for tid, name in self.cateManual.items():
            result['class'].append({'type_id': str(tid), 'type_name': str(name)})
        return result

    def homeVideoContent(self):
        result = {'list': [], 'parse': 0, 'jx': 0}
        videos, _ = self._fetch_api_list(1)
        result['list'] = videos
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        videos, has_more = self._fetch_api_list(page, tid=tid)
        result['list'] = videos
        result['page'] = page
        result['pagecount'] = page + 1 if has_more else page
        result['limit'] = len(videos)
        result['total'] = len(videos)
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ''
        if isinstance(ids, list):
            vid = ids[0] if ids else ''
        elif ids:
            vid = str(ids)
        if not vid:
            return result

        detail_html = self._get(f'{self.site}/detail/{vid}')

        title = ''
        tm = re.search(r'<h1[^>]*class="h1"[^>]*>(.*?)</h1>', detail_html, re.DOTALL)
        if tm:
            title = self._clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>([^<]+)', detail_html)
            if tm:
                title = self._clean(re.sub(r'\s*[-–—|].*$', '', tm.group(1)))

        pic = ''
        pm = re.search(r'src="(https://static-a\.xgcartoon\.com/[^"]+\.jpg[^"]*)"', detail_html)
        if pm:
            pic = pm.group(1).strip().replace('&amp;', '&')

        tags = re.findall(r'class="tag[^"]*"[^>]*>\s*(.*?)\s*</div>', detail_html, re.DOTALL)
        tag_str = ' / '.join(self._clean(t) for t in tags if self._clean(t))

        desc = ''
        desc_block = re.search(r'detail-right__desc[^>]*data-v[^>]*>.*?</div>\s*<p[^>]*>\s*(.*?)\s*</p>', detail_html, re.DOTALL)
        if desc_block:
            desc = self._clean(desc_block.group(1))

        author = ''
        am = re.search(r'</h1>\s*<div[^>]*>\s*(.*?)\s*</div>', detail_html, re.DOTALL)
        if am:
            author = self._clean(am.group(1))
        if not author:
            am = re.search(r'detail-right__title.*?<div[^>]*>\s*(.*?)\s*</div>', detail_html, re.DOTALL)
            if am:
                author = self._clean(am.group(1))

        episodes = []
        seen_ch = set()
        for em in re.finditer(r'href="(/user/page_direct\?[^"]+)"[^>]*title="([^"]*)"', detail_html):
            href = em.group(1).replace('&amp;', '&')
            label = self._clean(em.group(2))
            cm = re.search(r'chapter_id=([^&]+)', href)
            cid = cm.group(1) if cm else ''
            if cid in seen_ch:
                continue
            seen_ch.add(cid)
            if not label:
                label = cid
            episodes.append(f'{label}${href}')

        if not episodes:
            for em in re.finditer(r'iframe[^>]*src="https://pframe\.xgcartoon\.com/player\.htm\?vid=([^&"]+)', detail_html):
                v_id = em.group(1)
                if v_id not in seen_ch:
                    seen_ch.add(v_id)
                    m3u8 = f'{self.video_base}/{v_id}/playlist.m3u8'
                    episodes.append(f'\u64ad\u653e${m3u8}')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': tag_str,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': author,
            'vod_actor': author,
            'vod_director': bytes.fromhex('e6989fe6b2b3').decode('utf-8'),
            'vod_content': desc,
            'vod_play_from': '\u64ad\u653e',
            'vod_play_url': '#'.join(episodes) if episodes else ''
        }
        result['list'].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            if id.startswith('http') and '.m3u8' in id:
                result['parse'] = 0
                result['url'] = id
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': self.ua,
                    'Referer': self.frame_base + '/'
                }
                return result

            if not id.startswith('http'):
                play_url = self.site + id
            else:
                play_url = id

            html = self._get(play_url)
            m = re.search(r'iframe[^>]*src="https://pframe\.xgcartoon\.com/player\.htm\?vid=([^&"]+)', html)
            if m:
                vid = m.group(1)
                m3u8 = f'{self.video_base}/{vid}/playlist.m3u8'
                result['parse'] = 0
                result['url'] = m3u8
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': self.ua,
                    'Referer': self.frame_base + '/'
                }
                return result

            result['parse'] = 1
            result['url'] = play_url
            result['jx'] = 0
            result['header'] = {
                'User-Agent': self.ua,
                'Referer': self.site + '/'
            }
        except Exception as e:
            print(f'playerContent error: {e}')

        if not result:
            result = {'parse': 1, 'url': '', 'jx': 0, 'header': {}}
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'parse': 0, 'jx': 0}
        wd = requests.utils.quote(key)
        url = f'{self.site}/search?q={wd}'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]

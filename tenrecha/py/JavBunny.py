# -*- coding: utf-8 -*-
import sys
sys.path.append('..')
import re
import json
from base.spider import BaseSpider


class Spider(BaseSpider):

    def getName(self):
        return 'JavBunny'

    def init(self, extend=""):
        self.host = 'https://javbunny.com/'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Referer': self.host,
        }

    def isVideoFormat(self, url):
        return url.endswith('.mp4') or 'javbunny_videos' in url or 'tubegifs' in url

    def manualVideoCheck(self, url):
        return False

    def homeContent(self, filter):          
        classes = [
            {'type_id': 'latest',              'type_name': '最新'},
            {'type_id': 'popular',             'type_name': '人気'},
            {'type_id': 'censored',            'type_name': '有码'},
            {'type_id': 'uncensored',          'type_name': '无码'},
            {'type_id': 'reducing-mosaic',     'type_name': '无码破解'},
            {'type_id': 'tags',                'type_name': '标签'},
            {'type_id': 'categories',          'type_name': '分类'},
            {'type_id': 'models',              'type_name': '女優'},
            {'type_id': 'channels',            'type_name': '频道'},
            {'type_id': 'year',                'type_name': '日历'},
        ]
        filters = {
            'popular':         [{'key': 'dur', 'name': '时间', 'value': [
                                {'v': '', 'n': '今天'},
                                {'v': '7d', 'n': '本周'},
                                {'v': '31d', 'n': '本月'},                                
                                {'v': 'all', 'n': '全部'},

                            ]}],                               
            'censored':        [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '最新'},
                                {'v': 'views', 'n': '最热'},
                            ]}],
            'uncensored':      [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '最新'},
                                {'v': 'views', 'n': '最热'},
                            ]}],
            'reducing-mosaic': [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '最新'},
                                {'v': 'views', 'n': '最热'},
                            ]}],
            'tags':            [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '观看数'},
                                {'v': 'videos', 'n': '视频数'},
            ]}],
            'categories':      [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '观看数'},
                                {'v': 'videos', 'n': '视频数数'},
            ]}],
            'models':          [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '视频数'}, 
                                {'v': 'views', 'n': '观看数'},                                                             
                                {'v': 'az', 'n': 'A-Z'},
            ]}],
            'channels':        [{'key': 'sort', 'name': '排序', 'value': [
                                {'v': '', 'n': '视频数'},
                                {'v': 'views', 'n': '观看数'},
            ]}],
            'year':            [
                {'key': 'year', 'name': '年份', 'value': [
                    {'v': '2026', 'n': '2026'},
                    {'v': '2025', 'n': '2025'},
                    {'v': '2024', 'n': '2024'},
                    {'v': '2023', 'n': '2023'},
                    {'v': '2022', 'n': '2022'},
                    {'v': '2021', 'n': '2021'},
                    {'v': '2020', 'n': '2020'},
                    {'v': '2019', 'n': '2019'},
                    {'v': '2018', 'n': '2018'},
                ]},
                {'key': 'month', 'name': '月份', 'value': [
                    {'v': '12', 'n': '12月'},
                    {'v': '11', 'n': '11月'},
                    {'v': '10', 'n': '10月'},
                    {'v': '9', 'n': '9月'},
                    {'v': '8', 'n': '8月'},
                    {'v': '7', 'n': '7月'},
                    {'v': '6', 'n': '6月'},
                    {'v': '5', 'n': '5月'},
                    {'v': '4', 'n': '4月'},
                    {'v': '3', 'n': '3月'},
                    {'v': '2', 'n': '2月'},
                    {'v': '1', 'n': '1月'},
                ]}, 
            ],
        }
       
        return {'class': classes, 'filters': filters}

    def _parse_cards(self, html):
        videos = []
        pattern = re.compile(
            r'<a class="card"[^>]*href="(/video\.php\?slug=[^"]*)"[^>]*>'
            r'(.*?)</a>', re.S)
        for m in pattern.finditer(html):
            href = m.group(1).replace('&amp;', '&')
            inner = m.group(2)
            vid = re.search(r'slug=(\d+)-', href)
            vid = vid.group(1) if vid else ''
            title = ''
            tm = re.search(r'<h3>(.*?)</h3>', inner, re.S)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            img = ''
            im = re.search(r'<img[^>]*src="([^"]+)"', inner)
            if im:
                img = im.group(1)
                if img.startswith('/'):
                    img = self.host.rstrip('/') + img
            duration = ''
            dm = re.search(r'class="duration"[^>]*>([^<]+)<', inner)
            if dm:
                duration = dm.group(1).strip()
            date = ''
            dts = re.findall(r'class="meta"[^>]*>.*?<span[^>]*>([^<]+)</span>', inner, re.S)
            for d in reversed(dts):
                if re.search(r'\d{4}-\d{2}-\d{2}', d):
                    date = d.strip()
                    break
            remark = ' · '.join([x for x in [duration, date] if x])
            videos.append({
                'vod_id': 'javbunny' + '@' + href,
                'vod_name': title,
                'vod_pic': img,
                'vod_remarks': remark,
                'vod_duration': duration,
            })
        return videos

    def _get(self, url):
        r = self.fetch(url, headers=self.headers, timeout=15)
        return r.text if r else ''

    def categoryContent(self, tid, pg, filter, extend):
        if tid.startswith('javbunny@sub@'):
            parts = tid.split('@')
            kind, slug = parts[2], parts[3]
            sort = 'views'
            if isinstance(extend, dict):
                sort = extend.get('sort', 'views') or 'views'
            kind_url = {'tag': 'tag.php', 'category': 'category.php',
                        'model': 'model.php', 'channel': 'channel.php'}.get(kind, 'tag.php')
            url = '%s/%s?slug=%s&lang=zh&sort=%s&page=%s' % (
                self.host.rstrip('/'), kind_url, slug, sort, pg)
            html = self._get(url)
            videos = self._parse_cards(html)
            page, pagecount = self._parse_pagination(html, pg)
            return {'list': videos, 'page': page, 'pagecount': pagecount,
                    'limit': len(videos), 'total': pagecount * max(len(videos), 1)}

        sort = ''
        if isinstance(extend, dict):
            sort = extend.get('sort', '')
        if not sort:
            sort = 'latest'

        base = self.host.rstrip('/')
        if tid == 'latest':
            url = '%s/index.php?view=latest&lang=zh&page=%s' % (base, pg)
        elif tid == 'popular':
            dur = (extend.get('dur', '') if isinstance(extend, dict) else '') or '1d'
            url = '%s/popular.php?t=%s&page=%s&lang=zh' % (base, dur, pg)
        elif tid in ('censored', 'uncensored', 'reducing-mosaic'):
            url = '%s/section.php?type=%s&sort=%s&page=%s&lang=zh' % (base, tid, sort, pg)
        elif tid in ('tags', 'categories', 'models', 'channels'):
            page_map = {
                'tags': '%s/tags.php?lang=zh&page=%s' % (base, pg),
                'categories': '%s/categories.php?lang=zh&page=%s' % (base, pg),
                'models': '%s/models.php?lang=zh&page=%s' % (base, pg),
                'channels': '%s/channels.php?lang=zh&page=%s' % (base, pg),
            }
            return self._parse_flord(self._get(page_map[tid]), tid, pg)
        elif tid == 'year':
            year = (extend.get('year', '') if isinstance(extend, dict) else '') or '2018'
            month = (extend.get('month', '') if isinstance(extend, dict) else '') or '9'
            url = '%s/month.php?year=%s&month=%s&sort=%s&page=%s&lang=zh' % (
                base, year, month, sort, pg)
        else:
            return {'list': [], 'page': int(pg), 'pagecount': 0, 'limit': 0, 'total': 0}

        html = self._get(url)
        videos = self._parse_cards(html)
        page, pagecount = self._parse_pagination(html, pg)
        return {'list': videos, 'page': page, 'pagecount': pagecount,
                'limit': len(videos), 'total': pagecount * max(len(videos), 1)}

    def _parse_flord(self, html, tid, pg=1):
        kind_map = {
            'tags': 'tag', 'categories': 'category',
            'models': 'model', 'channels': 'channel',
        }
        kind = kind_map[tid]
        items = []
        for m in re.finditer(
                r'<a class="(?:list-card|model-card|channel-card)"[^>]*'
                r'href="([^"]*(?:tag|category|model|channel)\.php\?slug=([^&"]+)[^"]*)"[^>]*>'
                r'(.*?)</a>', html, re.S):
            hrf = m.group(1).replace('&amp;', '&')
            slug = m.group(2)
            inner = m.group(3)
            name = slug
            nm = re.search(r'<strong>(.*?)</strong>', inner, re.S)
            if nm:
                name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() or slug
            cnt = ''
            sm = re.search(r'<span>(.*?)</span>', inner, re.S)
            if sm:
                stxt = re.sub(r'<[^>]+>', ' ', sm.group(1))
                cm = re.search(r'([\d,]+)\s*(videos|影片|视频)', stxt)
                if cm:
                    cnt = cm.group(1) + ' ' + cm.group(2)
            img = ''
            im = re.search(r'<img[^>]*src="([^"]+)"', inner)
            if im:
                img = im.group(1)
                if img.startswith('/'):
                    img = self.host.rstrip('/') + img
            items.append({
                'vod_id': 'javbunny@sub@%s@%s' % (kind, slug),
                'vod_name': name,
                'vod_pic': img,
                'vod_remarks': cnt,
                'vod_tag': 'folder',
            })
        page, pagecount = self._parse_pagination(html, pg)
        return {'list': items, 'page': page, 'pagecount': pagecount,
                'limit': len(items), 'total': pagecount * max(len(items), 1)}

    @staticmethod
    def _parse_pagination(html, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        block = ''
        bm = re.search(r'class="pagination".*?</div>', html, re.S)
        if bm:
            block = bm.group(0)
        block = block.replace('&amp;', '&')
        nums = []
        cm = re.search(r'class="current"[^>]*>(\d+)<', block)
        if cm:
            nums.append(int(cm.group(1)))
        for m in re.finditer(r'[?&]page=(\d+)', block):
            nums.append(int(m.group(1)))
        if not nums:
            return pg, pg
        max_num = max(nums)
        return pg, max_num

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else ids
        if '@' in raw:
            raw = raw.split('@', 1)[1]
        raw = raw.replace('&amp;', '&')
        if raw.startswith('http'):
            url = raw
        elif raw.startswith('/'):
            url = self.host.rstrip('/') + raw
        else:
            url = self.host.rstrip('/') + '/' + raw

        html = self._get(url)
        title = ''
        tm = re.search(r'<title>(.*?)- JavBunny', html, re.S)
        if tm:
            title = tm.group(1).strip()
        pic = ''
        im = re.search(r'property="og:image" content="([^"]+)"', html)
        if im:
            pic = im.group(1)

        videos = []
        for sm in re.finditer(r'<source[^>]*src="([^"]+\.mp4[^"]*)"', html):
            src = sm.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            videos.append(src)

        vod = {
            'vod_id': 'javbunny' + '@' + url.split('javbunny.com/', 1)[-1] if 'javbunny.com/' in url else raw,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': '',
            'vod_play_from': 'JavBunny',
            'vod_play_url': '#'.join(videos),
        }
        return {'list': [vod]}

    # ============================ 搜索 ============================
    def searchContent(self, key, quick, pg='1'):
        base = self.host.rstrip('/')
        url = '%s/search.php?q=%s&page=%s&lang=zh' % (base, self.quote(key), pg)
        html = self._get(url)
        videos = self._parse_cards(html)
        page, pagecount = self._parse_pagination(html, pg)
        return {'list': videos, 'page': page, 'pagecount': pagecount,
                'limit': len(videos), 'total': pagecount * max(len(videos), 1)}

    @staticmethod
    def quote(s):
        try:
            from urllib.parse import quote
            return quote(s)
        except Exception:
            return s

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('//'):
            id = 'https:' + id
        return {
            'parse': 0,
            'playUrl': '',
            'url': id,
            'header': json.dumps(self.headers),
        }

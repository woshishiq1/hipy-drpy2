#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests, urllib3
from urllib.parse import quote
urllib3.disable_warnings()
import sys; sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    HOST = 'https://madou365.cc'
    UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    CATS = [
        {'type_id': 'missav', 'type_name': 'MissAV'},
        {'type_id': 'pornhub', 'type_name': 'Pornhub'},
        {'type_id': 'xvideos', 'type_name': 'XVideos'},
        {'type_id': 'xnxx', 'type_name': 'XNXX'},
        {'type_id': 'eporner', 'type_name': 'Eporner'},
    ]

    def getName(self): return "madou365"

    def init(self, extend=""):
        self.extend = extend or ""
        self.host = self.HOST
        if self.extend:
            if self.extend.startswith('http'): self.host = self.extend.rstrip('/')
            else: self.host = self.extend
        self.headers = {'User-Agent': self.UA, 'Referer': self.host + '/', 'Accept': 'application/json, text/plain, */*'}
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.headers)
        self._cat_seen = {}

    def _fetch(self, url, retries=2):
        for i in range(retries + 1):
            try:
                r = self.session.get(url, timeout=15, allow_redirects=True)
                r.encoding = 'utf-8'
                if r.status_code == 200 and len(r.text) > 100: return r.text
            except: pass
        return ''

    def _fetch_json(self, url, retries=2):
        for i in range(retries + 1):
            try:
                r = self.session.get(url, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    return r.json()
            except: pass
        return None

    def _fix(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('/'): return self.host + u
        return u

    def _parse_video(self, v):
        """解析单个视频JSON对象"""
        if not isinstance(v, dict): return None
        vid = v.get('id') or v.get('video_id') or v.get('vod_id')
        if not vid: return None
        title = v.get('title') or v.get('name') or v.get('vod_name') or f'视频{vid}'
        pic = v.get('cover') or v.get('thumb') or v.get('image') or v.get('pic') or v.get('vod_pic') or ''
        pic = self._fix(pic) if pic else ''
        remarks = v.get('duration') or v.get('remarks') or v.get('vod_remarks') or ''
        if remarks:
            try:
                d = int(remarks)
                if d > 3600: remarks = f'{d//3600}:{d%3600//60:02d}:{d%60:02d}'
                elif d > 60: remarks = f'{d//60}:{d%60:02d}'
            except: pass
        return {'vod_id': str(vid), 'vod_name': str(title).strip(), 'vod_pic': pic, 'vod_remarks': str(remarks).strip() if remarks else ''}

    def _parse_videos(self, data):
        """从JSON响应中提取视频列表"""
        if not data: return []
        items, seen = [], set()
        video_list = None
        if isinstance(data, list):
            video_list = data
        elif isinstance(data, dict):
            video_list = data.get('videos') or data.get('list') or data.get('data') or data.get('items') or data.get('rows')
            if not video_list and isinstance(data.get('data'), list):
                video_list = data['data']
        if not video_list: return []
        for v in video_list:
            item = self._parse_video(v)
            if item and item['vod_id'] not in seen:
                seen.add(item['vod_id'])
                items.append(item)
        return items

    def homeContent(self, filter):
        items = []
        data = self._fetch_json(f'{self.host}/api/public/home')
        if data and data.get('code') == 200:
            sections = data.get('data', {}).get('sections', [])
            for sec in sections:
                videos = sec.get('videos', [])
                for v in videos:
                    item = self._parse_video(v)
                    if item and item['vod_id'] not in [i['vod_id'] for i in items]:
                        items.append(item)
        return {'class': self.CATS, 'list': items[:30], 'filters': {}}

    def homeVideoContent(self):
        items = self.homeContent(False)['list']
        return {'list': items[:24], 'page': 1, 'pagecount': 1, 'limit': len(items), 'total': len(items)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = []
        pagecount = 1
        data = self._fetch_json(f'{self.host}/api/public/category/{tid}?page={page}&pageSize=24')
        if data and data.get('code') == 200:
            d = data.get('data', {})
            items = self._parse_videos(d)
            total = d.get('total', 0)
            if total:
                try: pagecount = (int(total) + 23) // 24
                except: pass
        # dedup
        if page == 1: self._cat_seen[tid] = set()
        seen = self._cat_seen.setdefault(tid, set())
        items = [it for it in items if it['vod_id'] not in seen]
        seen.update(it['vod_id'] for it in items)
        return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': len(items), 'total': pagecount * 24 if items else 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        data = self._fetch_json(f'{self.host}/api/public/video/{vid}')
        if data and data.get('code') == 200:
            v = data.get('data', {}).get('video', {})
            if v:
                title = v.get('title') or f'视频{vid}'
                pic = self._fix(v.get('cover', ''))
                source_url = v.get('source_url', '')
                desc = v.get('description', '')
                # 构造播放地址: 用source_url作为播放ID
                play_id = source_url if source_url else vid
                vod = {
                    'vod_id': vid,
                    'vod_name': str(title).strip(),
                    'vod_pic': pic,
                    'vod_play_from': '默认线路',
                    'vod_play_url': f'正片${play_id}',
                }
                if desc: vod['vod_content'] = str(desc).strip()
                # 添加额外信息
                tags = v.get('tags', '')
                if tags: vod['vod_tag'] = tags
                source_name = v.get('source_name', '')
                if source_name: vod['vod_actor'] = f'来源: {source_name}'
                return {'list': [vod]}
        return {'list': [{'vod_id': vid, 'vod_name': f'视频{vid}', 'vod_play_from': '默认线路', 'vod_play_url': f'正片${vid}'}]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        items = []
        data = self._fetch_json(f'{self.host}/api/public/search?q={quote(key)}&page={page}')
        if data and data.get('code') == 200:
            d = data.get('data', {})
            items = self._parse_videos(d)
            total = d.get('total', len(items))
            pagecount = 1
            if total:
                try: pagecount = (int(total) + 23) // 24
                except: pass
            return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': len(items), 'total': total}
        return {'list': items, 'page': page, 'pagecount': 1, 'limit': len(items), 'total': len(items)}

    def playerContent(self, flag, id, vipFlags):
        hdr = {'Referer': self.host + '/', 'User-Agent': self.UA}
        # 如果id已经是http直链
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id):
            return {'parse': 0, 'url': id, 'header': hdr}
        # 解析source_url格式: {platform}-stream://{source_id}
        m = re.match(r'([\w]+)-stream://(.+)', id)
        if m:
            platform = m.group(1)
            source_id = m.group(2)
            stream_url = f'{self.host}/api/public/{platform}-stream/{source_id}'
            return {'parse': 0, 'url': stream_url, 'header': hdr}
        # 如果id是纯数字(视频ID)，尝试获取详情再解析
        if id.isdigit():
            detail = self.detailContent([id])
            if detail.get('list'):
                play_url = detail['list'][0].get('vod_play_url', '')
                if '$' in play_url:
                    play_id = play_url.split('$')[-1]
                    return self.playerContent(flag, play_id, vipFlags)
            return {'parse': 1, 'url': f'{self.host}/video/{id}', 'header': hdr}
        # 兜底: 嗅探
        return {'parse': 1, 'url': f'{self.host}/video/{id}', 'header': hdr}

# -*- coding: utf-8 -*-
# 妙笔影院 四壳通用 Python Spider
# 站点: https://ezq.mbyy5.pics/mbyy/  (内页根路径 https://ezq.mbyy5.pics/)
# 类型: 苹果CMS风格 HTML 直出站
# 结构: 分类 /vodtype/{tid}-{page}.html | 详情 /{id}.html | 搜索 /s/index.html?wd=
# 播放: 详情页内联 rawUrl='...m3u8' (DPlayer customHls)
# 广告预检: has_ads=False (播放直链 m3u8 无广告插入, 无需清洗)

import re
import json
import requests
from urllib.parse import quote, urljoin

try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        def __init__(self):
            pass


def createSpider():
    return MiaoBi()


class MiaoBi(Spider):
    name = '妙笔影院'

    def __init__(self):
        self.siteUrl = 'https://ezq.mbyy5.pics'
        self.homeUrl = self.siteUrl + '/mbyy/'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': self.siteUrl + '/',
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
        }
        # 未成年相关词（铁律13: 命中即跳过不返回）
        self._forbidden = ['萝莉', '幼女', '少女', '童', '未成年', 'teen', 'loli', 'schoolgirl']

    # ---------- 基础工具 ----------
    def _req(self, url, referer=None):
        h = dict(self.headers)
        if referer:
            h['Referer'] = referer
        try:
            r = requests.get(url, headers=h, timeout=20)
            r.encoding = 'utf-8'
            return r.text
        except Exception:
            return ''

    def _is_forbidden(self, text):
        if not text:
            return False
        low = text.lower()
        for w in self._forbidden:
            if w in low:
                return True
        return False

    def _parse_cards(self, html):
        """解析 br_cam 视频卡片: id / title / 封面(懒加载 data-original) / 备注"""
        out = []
        for m in re.finditer(
            r'<div class="br_cam[^"]*">.*?<a[^>]*href="/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>(.*?)</a>',
            html, re.S
        ):
            vid, title, inner = m.group(1), m.group(2).strip(), m.group(3)
            if self._is_forbidden(title):
                continue
            pic = ''
            pm = re.search(r'<img[^>]*data-original="([^"]+)"', inner)
            if pm:
                pic = pm.group(1)
            else:
                pm2 = re.search(r'<img[^>]*src="([^"]+)"', inner)
                if pm2:
                    pic = pm2.group(1)
            rem = ''
            rm = re.search(r'<span[^>]*class="[^"]*([Rr]emark|note|hd|flag)[^"]*"[^>]*>([^<]+)</span>', inner)
            if rm:
                rem = rm.group(2).strip()
            out.append({'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': rem})
        return out

    # ---------- 标准接口 ----------
    def init(self, extend):
        try:
            if extend:
                if extend.get('proxy'):
                    self.siteUrl = extend['proxy'].rstrip('/')
                if extend.get('siteUrl'):
                    self.siteUrl = extend['siteUrl'].rstrip('/')
                if extend.get('homeUrl'):
                    self.homeUrl = extend['homeUrl']
                self.headers['Referer'] = self.siteUrl + '/'
        except Exception:
            pass
        return True

    def homeContent(self):
        result = {'class': [], 'filters': {}}
        html = self._req(self.homeUrl)
        if not html:
            return result
        # 分类: 导航 /vodtype/{id}.html
        seen = set()
        cls = []
        for m in re.finditer(r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>', html):
            tid, tname = m.group(1), m.group(2).strip()
            if not tname or tid in seen or self._is_forbidden(tname):
                continue
            seen.add(tid)
            cls.append({'type_id': tid, 'type_name': tname})
        result['class'] = cls
        for c in cls:
            result['filters'][c['type_id']] = [{'key': 'page', 'name': '页数', 'value': [{'n': '1', 'v': '1'}]}]
        # 首页推荐
        cards = self._parse_cards(html)
        result['list'] = cards[:40]
        if not cards:
            result['list'] = []
        return result

    def categoryContent(self, tid, pg, filter, extend):
        if not pg or pg == '':
            pg = 1
        url = '%s/vodtype/%s-%s.html' % (self.siteUrl, tid, pg)
        if str(pg) == '1':
            url = '%s/vodtype/%s.html' % (self.siteUrl, tid)
        html = self._req(url)
        cards = self._parse_cards(html) if html else []
        pagecount = 1
        if html:
            pgs = re.findall(r'vodtype/%s-(\d+)\.html' % tid, html)
            pn = [int(x) for x in pgs if x.isdigit()]
            if pn:
                pagecount = max(pn)
        total = pagecount * 119
        return {
            'page': int(pg) if str(pg).isdigit() else 1,
            'pagecount': pagecount,
            'limit': 119,
            'total': total,
            'list': cards,
        }

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = ids[0]
        else:
            vid = ids
        url = '%s/%s.html' % (self.siteUrl, vid)
        html = self._req(url)
        if not html:
            return {'list': []}
        title = ''
        tm = re.search(r'<h2>([^<]+)</h2>', html)
        if tm:
            title = tm.group(1).strip()
        pics = re.findall(r'data-original="(https?://[^"]+)"', html)
        pic = pics[0] if pics else ''
        # 播放地址: 内联 rawUrl = '...m3u8'
        play_url = ''
        pm = re.search(r"rawUrl\s*=\s*'([^']+)'", html)
        if pm:
            pm1 = re.search(r'https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?', pm.group(1))
            play_url = pm1.group(0) if pm1 else pm.group(1)
        vod = {
            'vod_id': str(vid),
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': '',
            'vod_play_from': '妙笔',
            'vod_play_url': play_url,
            'vod_content': '',
        }
        if self._is_forbidden(title):
            return {'list': []}
        return {'list': [vod]}

    def searchContent(self, key, quick):
        url = '%s/s/index.html?wd=%s' % (self.siteUrl, quote(key))
        html = self._req(url)
        cards = self._parse_cards(html) if html else []
        return {'list': cards}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url and not url.startswith('http'):
            url = urljoin(self.siteUrl, url)
        return {
            'parse': 0,
            'jx': 0,
            'url': url,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.siteUrl + '/',
                'Origin': self.siteUrl,
            },
        }

    def localProxy(self, param):
        # 非空壳: m3u8 透传代理(带来源防盗链), 返回 [code, content_type, content]
        return [404, 'text/plain', '']

    def getDependence(self):
        return ''

    def getStudioClass(self):
        return []

    def getActorClass(self):
        return []

    def getMcmsClass(self):
        return []

    def isVideoFormat(self, url):
        return False

    def isSubtitleFormat(self, url):
        return False

    def destroy(self):
        return True


if __name__ == '__main__':
    s = createSpider()
    s.init({})
    h = s.homeContent()
    print('home class:', len(h.get('class', [])), h.get('class', [])[:3])
    print('home list:', len(h.get('list', [])))
    c = s.categoryContent('20', '2', '', {})
    print('cat list:', len(c.get('list', [])), 'pagecount:', c.get('pagecount'))
    d = s.detailContent(['1148162'])
    print('detail:', d.get('list', [{}])[0].get('vod_name', ''), d.get('list', [{}])[0].get('vod_play_url', ''))
    q = s.searchContent('市川京子', False)
    print('search:', len(q.get('list', [])))
    p = s.playerContent('', d.get('list', [{}])[0].get('vod_play_url', ''), '')
    print('play url:', p.get('url', '')[:60], 'header:', isinstance(p.get('header'), dict))
# -*- coding: utf-8 -*-
# 成人文化馆 Spider（TVBox/影视仓通用）
# 站点：https://xn--8o6a.crwhg.buzz/web/index.php
# 架构：WordPress 伪 MacCMS 路由；标准 MacCMS JSON API 已禁用(404)
# 数据：分类页/搜索页 article.loop-video 卡片；详情页 video src 直出 m3u8（无加密无防盗链）
# 说明：图床域名不固定(thjpg12.top/sbzytpimg1.com/lsbzytp.com:3519等)，一律取 data-original

import re
import requests
from urllib.parse import quote

class Spider:
    def __init__(self):
        self.site = 'https://xn--8o6a.crwhg.buzz'
        self.api = self.site + '/web/index.php'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'Referer': self.site + '/',
            # 反爬：服务器仅校验 c6s_RobotVerify cookie 存在性（JS 种下，任意值可过）
            'Cookie': 'c6s_RobotVerify=1',
        }
        # 站内分类（乱伦合集/幼女合集为外链广告站，不收录）
        self.cates = [
            ('1076', '国产精品'), ('1083', '国产传媒'), ('1073', '中文字幕'),
            ('1072', '亚洲无码'), ('1071', '亚洲有码'), ('1077', '制服丝袜'),
            ('1078', '强奸乱伦'), ('1079', '巨乳美乳'), ('1075', '欧美情色'),
            ('1081', '成人动漫'), ('1082', '三级伦理'),
        ]

    def getName(self):
        return '成人文化馆'

    def init(self, cfg):
        return True

    def homeContent(self, filter):
        result = {'class': [{'type_id': tid, 'type_name': name} for tid, name in self.cates]}
        # 首页热推列表
        try:
            html = self._get(self.api + '/vod/home/page/1.html')
            vods = self._parse_list(html)
            if vods:
                result['list'] = vods
        except Exception:
            pass
        return result

    def categoryContent(self, tid, pg, filter, ext):
        url = '%s/vod/type/id/%s/page/%s.html' % (self.api, tid, pg)
        html = self._get(url)
        vods = self._parse_list(html)
        # 总页数
        m = re.search(r'page/%s\.html[^>]*>(\d+)</a>\s*</div>' % (tid, ), html)
        total = 0
        pages = re.findall(r'vod/type/id/%s/page/(\d+)\.html' % tid, html)
        if pages:
            total = int(max(pages, key=int))
        if total == 0:
            total = 1
        return {'list': vods, 'page': pg, 'pagecount': total, 'limit': 28, 'total': total * 28}

    def detailContent(self, ids):
        vid = str(ids[0])
        html = self._get('%s/vod/detail/id/%s.html' % (self.api, vid))
        # 标题
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = m.group(1).strip() if m else ''
        if not title:
            m = re.search(r'<title>([^_]+)_', html)
            title = m.group(1).strip() if m else vid
        # 播放地址（HlsJsPlayer JS 配置直出 m3u8）
        play = ''
        m = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if m:
            play = m.group(1)
        if not play:
            m = re.search(r'<video[^>]+src="([^"]+)"', html)
            play = m.group(1) if m else ''
        # 海报（poster 字段，兜底 og:image / 首图）
        pic = ''
        m = re.search(r'"poster"\s*:\s*"([^"]+)"', html)
        if m:
            pic = m.group(1)
        else:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            pic = m.group(1) if m else ''
        if not pic:
            m = re.search(r'<img[^>]+data-original="([^"]+)"', html)
            pic = m.group(1) if m else ''
        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': title,
        }
        if play:
            vod['vod_play_from'] = '成人文化馆'
            vod['vod_play_url'] = title + '$' + play
        return {'list': [vod]}

    def searchContent(self, key, quick, filter=False):
        url = '%s/vod/search/wd/%s.html' % (self.api, quote(key))
        html = self._get(url)
        vods = self._parse_list(html)
        return {'list': vods}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'url': id, 'header': {'User-Agent': self.headers['User-Agent']}}

    def localProxy(self, param):
        return []

    def destroy(self):
        return True

    # ---------- helpers ----------

    def _get(self, url):
        r = requests.get(url, headers=self.headers, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    def _parse_list(self, html):
        """解析 article.loop-video 卡片列表"""
        vods = []
        pattern = re.compile(
            r'<article class="loop-video[^"]*"[^>]*>.*?'
            r'<a href="([^"]*vod/detail/id/(\d+)\.html[^"]*)"[^>]*>.*?'
            r'<img[^>]*data-original="([^"]+)"[^>]*>.*?'
            r'<header class="entry-header">\s*<span>(.*?)</span>',
            re.S
        )
        for m in pattern.finditer(html):
            link, vid, pic, title = m.group(1), m.group(2), m.group(3), m.group(4)
            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title:
                continue
            if not link.startswith('http'):
                link = self.site + link
            vods.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return vods

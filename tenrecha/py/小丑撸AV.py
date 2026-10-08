# -*- coding: utf-8 -*-
"""
作者：飞鱼
小丑撸AV 爬虫 (播放页直接嗅探版 & 飞鱼专线明文版)
适配壳子: TVBox / 猫影视 / 影视壳 / PeekPro(羊壳)
"""
import sys
import re
import json
import base64
import requests
import urllib3
import time
import html
from urllib.parse import quote, urljoin, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    host = 'https://jokerlu.com'
    session = requests.Session()
    _debug = True
    _categories = []
    
    # 内存缓存：用于在点击进入详情页时，完美复用列表页带有的准确标题和封面
    _cache_vod_info = {}

    AD_TITLE_FILTER = ['广告', '推广', 'APP', '下载', '注册', '菠菜', '博彩', '棋牌', '入口', '导航', '会所', '小丑撸轻便版']

    def _log(self, msg):
        if self._debug:
            print(f'[小丑撸AV] {msg}')

    def getName(self):
        return '小丑撸AV'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url)

    def manualVideoCheck(self):
        return True

    def destroy(self):
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
            self.session = None

    def _clean_text(self, text):
        if not text:
            return ''
        clean = re.sub(r'<[^>]+>', '', text)
        clean = html.unescape(clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/'
        }

    def _fetch(self, url, referer=None, retries=2):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(0.5)
                r = self.session.get(url, headers=self._get_headers(referer), timeout=(10, 15), verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                self._log(f'请求异常: {e} -> {url}')
                continue
        return ''

    def _extract_categories_from_html(self, html_str):
        categories = []
        if not html_str:
            return categories
        cate_matches = re.findall(r'<a\s+href="(/vodtype/(\d+)/?)"[^>]*>(.*?)</a>', html_str, re.S | re.I)
        seen = set()
        for path, t_id, name in cate_matches:
            clean_name = self._clean_text(name)
            if t_id not in seen and clean_name and not any(k in clean_name for k in ['首页', 'HOME']):
                seen.add(t_id)
                categories.append({
                    'type_id': str(t_id),
                    'type_name': str(clean_name)
                })
        return categories

    def init(self, extend=''):
        self._log('初始化模块...')
        self.session = requests.Session()
        home_html = self._fetch(self.host)
        dynamic_cates = self._extract_categories_from_html(home_html)

        if dynamic_cates:
            self._categories = dynamic_cates
        else:
            self._categories = [
                {'type_id': '424', 'type_name': '麻豆视频'},
                {'type_id': '425', 'type_name': '91制片厂'},
                {'type_id': '426', 'type_name': '天美传媒'},
                {'type_id': '427', 'type_name': '蜜桃传媒'},
                {'type_id': '439', 'type_name': 'EDmosaic'},
                {'type_id': '443', 'type_name': '果冻传媒'},
                {'type_id': '2', 'type_name': '国产视频'},
                {'type_id': '7', 'type_name': '日本有码'},
                {'type_id': '8', 'type_name': '日本无码'}
            ]

    def _parse_item_list(self, html_str):
        items = []
        if not html_str:
            return items

        # 优化切片：以每个 col-md-2 视频网格为一个独立 block
        blocks = re.split(r'(?=<div[^>]+class="[^"]*col-md-2[^"]*")', html_str, flags=re.I)

        for block in blocks:
            if 'col-md-2' not in block:
                continue

            href_m = re.search(r'<a[^>]+href="([^"]+)"', block, re.I)
            if not href_m:
                continue
            href = href_m.group(1).strip()

            title = ''
            title_m = re.search(r'class="[^"]*title[^"]*">([^<]+)</a>', block, re.I)
            if title_m:
                title = self._clean_text(title_m.group(1))
            else:
                a_title_m = re.search(r'<a[^>]+title="([^"]+)"', block, re.I)
                if a_title_m:
                    title = self._clean_text(a_title_m.group(1))
                else:
                    a_text_m = re.search(r'<a[^>]+href="[^"]+"[^>]*>(.*?)</a>', block, re.S | re.I)
                    if a_text_m:
                        title = self._clean_text(a_text_m.group(1))

            if not title or any(k in title for k in self.AD_TITLE_FILTER):
                continue

            # 精准针对 .resent-grid-img 区域及内部 img 的 data-src 提取
            img = ''
            img_container = re.search(r'class="[^"]*resent-grid-img[^"]*"[^>]*>(.*?)</(?:div|a)>', block, re.S | re.I)
            target_html = img_container.group(1) if img_container else block

            img_m = re.search(r'<img[^>]+data-src="([^"]+)"', target_html, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+data-src="([^"]+)"', block, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+src="([^"]+)"', target_html, re.I)
            if not img_m:
                img_m = re.search(r'data-src="([^"]+)"', block, re.I)
            
            if img_m:
                img = img_m.group(1)

            if img and not img.startswith('http'):
                img = urljoin(self.host, img)

            time_m = re.search(r'class="[^"]*time[^"]*".*?(?:<p>|<span[^>]*>)(.*?)(?:</p>|</span>)', block, re.S | re.I)
            views_m = re.search(r'class="[^"]*views[^"]*">([^<]+)</p>', block, re.S | re.I)

            time_str = self._clean_text(time_m.group(1)) if time_m else ''
            views_str = self._clean_text(views_m.group(1)) if views_m else ''

            remarks = []
            if time_str:
                remarks.append(f"📅{time_str}")
            if views_str:
                remarks.append(f"🔥{views_str}")

            if 'voddetail' in href:
                href = href.replace('voddetail', 'vodplay')
            
            match_id = re.search(r'/(\d+)', href)
            if match_id and '-1-1' not in href:
                v_id = match_id.group(1)
                href = f"/vodplay/{v_id}-1-1/"

            full_href = urljoin(self.host, href)

            # 将列表抓取到的准确标题和封面缓存起来
            self._cache_vod_info[full_href] = {
                'title': title,
                'pic': img
            }

            if not any(i['vod_id'] == full_href for i in items):
                items.append({
                    'vod_id': str(full_href),
                    'vod_name': str(title),
                    'vod_pic': str(img),
                    'vod_remarks': ' '.join(remarks)
                })

        return items

    def homeContent(self, filter=False):
        try:
            if not self._categories:
                self.init()
            html_str = self._fetch(self.host)
            items = self._parse_item_list(html_str)
            return {
                'class': self._categories,
                'list': items[:20] if items else []
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        html_str = self._fetch(self.host)
        return {'list': self._parse_item_list(html_str)[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg) if pg else 1
            if page > 1:
                url = f"{self.host}/vodtype/{tid}-{page}.html"
            else:
                url = f"{self.host}/vodtype/{tid}/"

            html_str = self._fetch(url)
            items = self._parse_item_list(html_str)

            return {
                'list': items,
                'page': page,
                'pagecount': page + 1 if len(items) >= 10 else page,
                'limit': 20,
                'total': 999
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def detailContent(self, ids):
        try:
            url = ids[0] if isinstance(ids, list) else ids
            if not url.startswith('http'):
                url = urljoin(self.host, url)

            # 优先从内存缓存中获取列表页保存的准确标题与封面
            cached = self._cache_vod_info.get(url, {})
            title = cached.get('title', '')
            cover = cached.get('pic', '')

            # 如果是通过直接搜索或缓存未命中，则回退解析网页标题
            if not title:
                html_str = self._fetch(url)
                if html_str:
                    title_m = re.search(r'<title>(.*?)</title>', html_str, re.S)
                    if title_m:
                        title = self._clean_text(title_m.group(1)).split('-')[0].strip()
                    
                    img_m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html_str, re.I)
                    if not img_m:
                        img_m = re.search(r'<img[^>]+data-src="([^"]+)"', html_str, re.I)
                    if img_m:
                        cover = img_m.group(1)
                if not title:
                    title = '未知视频'

            return {'list': [{
                'vod_id': str(url),
                'vod_name': str(title),
                'vod_pic': str(cover),
                'vod_content': str(title),
                'vod_play_from': '飞鱼专线',
                'vod_play_url': f'正片${url}'
            }]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            return {
                'parse': 1,
                'url': id,
                'header': self._get_headers(id)
            }
        except Exception as e:
            return {'parse': 1, 'url': id}

    def searchContent(self, key, quick, pg='1'):
        try:
            url = f"{self.host}/index.php/ajax/suggest?mid=1&wd={quote(key)}"
            headers = self._get_headers()
            headers['X-Requested-With'] = 'XMLHttpRequest'

            r = self.session.get(url, headers=headers, timeout=10, verify=False)
            items = []

            if r.status_code == 200:
                data = r.json()
                if data and 'list' in data:
                    for item in data['list']:
                        v_id = item.get('id', '')
                        play_url = f"{self.host}/vodplay/{v_id}-1-1/"
                        name = item.get('name', '')
                        pic = item.get('pic', '')
                        
                        # 记录搜索结果的标题和封面到缓存中
                        self._cache_vod_info[play_url] = {
                            'title': name,
                            'pic': pic
                        }

                        items.append({
                            'vod_id': str(play_url),
                            'vod_name': str(name),
                            'vod_pic': str(pic),
                            'vod_remarks': ''
                        })

            return {
                'list': items,
                'page': 1,
                'pagecount': 1
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1}

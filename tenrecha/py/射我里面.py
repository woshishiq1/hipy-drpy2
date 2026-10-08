# -*- coding: utf-8 -*-
"""
射我里面(spider for shewo) 爬虫
适配域名: kdlt8i1n.shewo39.cc 等同系列
"""
import sys
import re
import json
import requests
import urllib3
import time
import random
from urllib.parse import quote, urljoin, unquote, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # 主域名，自动从页面获取或手动更新
    hosts = ['https://kdlt8i1n.shewo39.cc']
    host = hosts[0]
    session = requests.Session()
    _debug = True
    _categories = []

    # 广告过滤黑名单：标题包含以下关键词的条目将被丢弃
    AD_TITLE_FILTER = ['广告', '推广', '合作', 'APP', '下载', '注册', '菠菜', '博彩', '棋牌']
    # 播放线路名称过滤：包含这些关键词的线路按钮将被跳过
    AD_LINE_FILTER = ['广告', '推广', 'APP', '下载', '合作', '菠菜', '博彩']
    # 播放地址域名黑名单（常见广告域名片段）
    AD_DOMAIN_FILTER = ['doubleclick', 'adservice', 'adsystem', 'adnxs', 'openx', 'casalemedia']

    def _log(self, msg):
        if self._debug:
            print(f'[shewo] {msg}')

    def getName(self):
        return '射我里面'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
            self.session = None

    # ---------- 本地代理（可选，仅做图片代理） ----------
    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF]
        try:
            r = self.session.get(param, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': self.host + '/'
            }, timeout=(10, 15))
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', 'application/octet-stream')
            return [200, content_type, r.content]
        except:
            return [200, 'image/gif', EMPTY_GIF]

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/'
        }

    def _fetch(self, url, referer=None, retries=3):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=self._get_headers(referer), timeout=(10, 20), verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                else:
                    self._log(f'请求失败 [{r.status_code}] {url}')
                    return ''
            except Exception as e:
                self._log(f'请求异常 {e}，重试 {attempt+1}')
                continue
        return ''

    # ---------- 分类解析 ----------
    def _parse_categories(self, html):
        """从导航区提取 /vodtype/ 分类，过滤外部广告"""
        cats = []
        # 定位导航区域：div.listlinks > div.mato
        mato_match = re.search(r'<div[^>]+class="mato"[^>]*>(.*?)</div>', html, re.S)
        if mato_match:
            links_html = mato_match.group(1)
        else:
            links_html = html
        links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', links_html, re.S)
        for href, text in links:
            m = re.search(r'/vodtype/(\d+)\.html', href)
            if not m:
                continue
            tid = m.group(1)
            name = re.sub(r'<[^>]+>', '', text).strip()
            if not name or len(name) > 15:
                continue
            # 过滤掉非视频分类的杂物（原有的过滤）
            if name in ('首页', '搜索', '全部', '更多', '排行', '留言', '帮助', '返回首页', '发布页', '传送门'):
                continue
            # 新增：过滤名称含广告关键词的分类
            if any(k in name for k in self.AD_TITLE_FILTER):
                continue
            cats.append({
                'type_id': tid,
                'type_name': name,
                'type': 'vod'
            })
        return self._dedup(cats)

    def _dedup(self, cats):
        seen = set()
        unique = []
        for c in cats:
            tid = c['type_id']
            if tid not in seen:
                seen.add(tid)
                unique.append(c)
        return unique

    def init(self, extend=''):
        self._log('正在初始化...')
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
        self.session = requests.Session()
        # 尝试从主页获取分类
        html = self._fetch(self.host + '/')
        if html:
            cats = self._parse_categories(html)
            if cats:
                self._categories = cats
                self._log(f'分类获取成功: {len(cats)} 个')
                return
        # 备用：直接请求一个分类页
        html = self._fetch(self.host + '/vodtype/55.html')
        if html:
            cats = self._parse_categories(html)
            if cats:
                self._categories = cats
                self._log(f'备用页分类获取成功: {len(cats)} 个')
                return
        # 硬编码兜底（取自你提供的 HTML 中的站内分类）
        self._categories = [
            {'type_id': '55', 'type_name': '国产精品', 'type': 'vod'},
            {'type_id': '63', 'type_name': '华语精品', 'type': 'vod'},
            {'type_id': '58', 'type_name': '黑料吃瓜', 'type': 'vod'},
            {'type_id': '60', 'type_name': '欧美大屌', 'type': 'vod'},
            {'type_id': '57', 'type_name': '动漫禁漫', 'type': 'vod'},
            {'type_id': '65', 'type_name': '学生合集', 'type': 'vod'},
            {'type_id': '64', 'type_name': '乱伦精品', 'type': 'vod'},
            {'type_id': '61', 'type_name': '探花约炮', 'type': 'vod'},
            {'type_id': '86', 'type_name': '日本无码', 'type': 'vod'},
            {'type_id': '80', 'type_name': '日本有码', 'type': 'vod'},
            {'type_id': '81', 'type_name': '主播网红', 'type': 'vod'},
            {'type_id': '12', 'type_name': '国产色情', 'type': 'vod'},
            {'type_id': '20', 'type_name': '日本无码', 'type': 'vod'},
            {'type_id': '21', 'type_name': '自拍偷拍', 'type': 'vod'},
            {'type_id': '22', 'type_name': '人妻熟女', 'type': 'vod'},
            {'type_id': '23', 'type_name': '黑人洋屌', 'type': 'vod'},
            {'type_id': '24', 'type_name': '欧美精品', 'type': 'vod'},
            {'type_id': '69', 'type_name': '卡通动漫', 'type': 'vod'},
            {'type_id': '70', 'type_name': '乱伦中出', 'type': 'vod'},
            {'type_id': '71', 'type_name': '传媒原创', 'type': 'vod'},
            {'type_id': '72', 'type_name': '口爆颜射', 'type': 'vod'},
            {'type_id': '25', 'type_name': '岛国女优', 'type': 'vod'},
            {'type_id': '26', 'type_name': '萝莉少女', 'type': 'vod'},
            {'type_id': '88', 'type_name': '重口调教', 'type': 'vod'},
            {'type_id': '56', 'type_name': '国产直播', 'type': 'vod'},
            {'type_id': '73', 'type_name': '岛国群交', 'type': 'vod'},
            {'type_id': '74', 'type_name': '日本有码', 'type': 'vod'},
            {'type_id': '75', 'type_name': '中文字幕', 'type': 'vod'},
            {'type_id': '76', 'type_name': '吃瓜爆料', 'type': 'vod'},
            {'type_id': '77', 'type_name': '角色扮演', 'type': 'vod'},
            {'type_id': '78', 'type_name': '淫娃自慰', 'type': 'vod'},
            {'type_id': '84', 'type_name': '韩国直播', 'type': 'vod'},
            {'type_id': '85', 'type_name': '公开漏出', 'type': 'vod'},
            {'type_id': '89', 'type_name': '户外打野', 'type': 'vod'},
        ]
        self._log('使用硬编码分类')

    # ---------- 视频列表解析（已增强广告过滤） ----------
    def _parse_video_list(self, html):
        items = []
        # 每个视频卡片在 div.pornkvideos 中
        blocks = re.findall(r'<div[^>]+class="pornkvideos"[^>]*>(.*?)</div>\s*</div>', html, re.S)
        if not blocks:
            # 尝试更宽松的匹配
            blocks = re.findall(r'<div[^>]+class="[^"]*pornkvideos[^"]*"[^>]*>(.*?)(?=<div[^>]+class="pornkvideos|$)', html, re.S)
        for block in blocks:
            # 提取链接和图片、标题
            link_match = re.search(r'<a[^>]+href="(/voddetail/(\d+)\.html)"', block)
            img_match = re.search(r'<img[^>]+data-src="([^"]*)"', block)
            title_match = re.search(r'<h2[^>]*>(.*?)</h2>', block)
            if not link_match or not title_match:
                continue
            vid = link_match.group(2)
            href = link_match.group(1)
            img = img_match.group(1) if img_match else ''
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            # ----- 广告清洗逻辑开始 -----
            # 1. 标题包含广告关键词
            if any(k in title for k in self.AD_TITLE_FILTER):
                self._log(f'过滤广告视频: {title}')
                continue
            # 2. 图片链接指向已知广告域名
            if img:
                img_lower = img.lower()
                if any(ad_domain in img_lower for ad_domain in self.AD_DOMAIN_FILTER):
                    self._log(f'过滤广告图片: {img}')
                    continue
            # 3. 视频链接不在本站（防止外部广告链接）
            if href and not href.startswith('/voddetail/'):
                self._log(f'过滤外部链接: {href}')
                continue
            # ----- 广告清洗逻辑结束 -----

            if img and not img.startswith('http'):
                img = urljoin(self.host, img)
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': img,
                'vod_remarks': '',
            })
        return items

    # ---------- 首页内容 ----------
    def homeContent(self, filter=False):
        try:
            if not self._categories:
                self.init()
            html = self._fetch(self.host + '/')
            items = self._parse_video_list(html) if html else []
            return {'class': self._categories, 'list': items[:20]}
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        html = self._fetch(self.host + '/')
        items = self._parse_video_list(html) if html else []
        return {'list': items[:20]}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=''):
        try:
            page = int(pg) if pg else 1
            if page > 1:
                url = f'{self.host}/vodtype/{tid}-{page}.html'
            else:
                url = f'{self.host}/vodtype/{tid}.html'
            html = self._fetch(url)
            items = self._parse_video_list(html) if html else []
            # 计算总页数（从分页链接中提取最大页码）
            total_pages = page
            if html:
                page_links = re.findall(r'/vodtype/{}[-_](\d+)\.html'.format(tid), html)
                if page_links:
                    total_pages = max(int(p) for p in page_links)
                else:
                    total_pages = page + 1
            return {'list': items, 'page': page, 'pagecount': max(total_pages, page)}
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    # ---------- 播放地址提取（从 vodplay 页面，已增强广告过滤） ----------
    def _extract_m3u8(self, html):
        urls = []
        if not html:
            return urls
        # 标准 player_aaaa 变量
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.S)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                raw = data.get('url', '')
                if raw:
                    decoded = unquote(raw)
                    # 修复 JSON 转义的正斜杠 \/
                    decoded = decoded.replace('\\/', '/')
                    if decoded.startswith('http'):
                        urls.append(decoded)
            except:
                pass
        # 直接写在页面中的 m3u8 链接
        direct = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        urls.extend(direct)
        # 有时链接在 iframe 中
        iframe_src = re.findall(r'<iframe[^>]+src="([^"]*)"', html)
        for src in iframe_src:
            if '.m3u8' in src:
                urls.append(src)
        # JSON 格式的 url
        json_urls = re.findall(r'''["\']url["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']''', html)
        urls.extend(json_urls)

        # ----- 广告清洗逻辑开始 -----
        # 去重并修复转义，同时过滤广告域名
        seen = set()
        clean = []
        for u in urls:
            u = u.replace('\\/', '/')  # 统一处理 \/ → /
            if not u.startswith('http'):
                continue
            # 检查域名是否在黑名单中
            if any(ad in u.lower() for ad in self.AD_DOMAIN_FILTER):
                self._log(f'过滤广告播放地址: {u}')
                continue
            if u not in seen:
                seen.add(u)
                clean.append(u)
        # ----- 广告清洗逻辑结束 -----
        return clean

    # ---------- 视频详情（已增强线路过滤） ----------
    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            html = self._fetch(f'{self.host}/voddetail/{vid}.html')
            if not html:
                return {'list': [{'vod_id': vid, 'vod_name': '未知影片', 'vod_play_from': '错误', 'vod_play_url': ''}]}
            return self._video_detail(vid, html)
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': [{'vod_id': vid, 'vod_name': '错误', 'vod_play_from': '错误', 'vod_play_url': ''}]}

    def _video_detail(self, vid, html):
        # 标题
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>(.*?)</title>', html)
            if m:
                title = m.group(1).strip()
        # 封面
        cover = ''
        m = re.search(r'<img[^>]*data-src="([^"]*)"', html)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if m:
                cover = m.group(1)
        if cover and not cover.startswith('http'):
            cover = urljoin(self.host, cover)

        # 播放线路（按钮 -> vodplay 页）
        # 匹配类似 /vodplay/21061-1-1.html 的链接
        play_links = re.findall(r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', html)
        if not play_links:
            # 简单匹配所有 /vodplay/ 链接
            play_links = re.findall(r'href="(/vodplay/\d+[^"]*)"[^>]*>(.*?)</a>', html)
        if not play_links:
            # 兜底：自己构造一个默认链接（第一集）
            play_links = [(f'/vodplay/{vid}-1-1.html', '立即播放')]

        line_map = {}
        cache = {}
        for href, btn_name in play_links:
            btn_name = re.sub(r'<[^>]+>', '', btn_name).strip() or '播放'
            # ----- 广告线路过滤：按钮名称包含广告关键词则跳过 -----
            if any(k in btn_name for k in self.AD_LINE_FILTER):
                self._log(f'过滤广告线路: {btn_name}')
                continue
            # -------------------------------------------------
            play_url = urljoin(self.host, href)

            if href not in cache:
                play_html = self._fetch(play_url)
                m3u8_list = self._extract_m3u8(play_html) if play_html else []
                cache[href] = m3u8_list
                self._log(f'播放页 {href} 提取到 {len(m3u8_list)} 个地址')
            else:
                m3u8_list = cache[href]

            if m3u8_list:
                for i, m3u8 in enumerate(m3u8_list):
                    name = btn_name if i == 0 else f'{btn_name}_{i+1}'
                    line_map.setdefault(btn_name, []).append((name, m3u8))
            else:
                # 如果没提取到 m3u8，保留播放页 URL 作为备用（也可能被广告过滤拦截，但保留至少有一个线路）
                line_map.setdefault(btn_name, []).append((btn_name, play_url))

        if not line_map:
            return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': cover,
                              'vod_play_from': '错误', 'vod_play_url': '未找到播放地址'}]}

        # 组装 TVBox 格式
        from_lines = []
        url_lines = []
        for line_name, episodes in line_map.items():
            from_lines.append(line_name)
            ep_str = '#'.join([f'{ep_name}${ep_url}' for ep_name, ep_url in episodes])
            url_lines.append(ep_str)
        vod_play_from = '#'.join(from_lines)
        vod_play_url = '$$$'.join(url_lines)

        return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': cover,
                          'vod_play_from': vod_play_from, 'vod_play_url': vod_play_url}]}

    # ---------- 播放器接口（已增强转义修复） ----------
    def playerContent(self, flag, id, vipFlags=None):
        # 传入的 id 可能是转义过的链接，统一修复
        if id:
            id = id.replace('\\/', '/')
        # 额外检查：如果解析后的 id 是广告域名，返回空
        if any(ad in id.lower() for ad in self.AD_DOMAIN_FILTER):
            self._log(f'播放器过滤广告地址: {id}')
            return {'parse': 0, 'url': '', 'header': {}}
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id or '.ts' in id):
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
        else:
            return {'parse': 1, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}'
            html = self._fetch(url)
            items = self._parse_video_list(html) if html else []
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}
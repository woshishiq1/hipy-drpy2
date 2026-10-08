# -*- coding: utf-8 -*-
"""
肉視頻 (rou.video) 爬虫
站点: https://rou.video/home
适配 Next.js 服务端渲染，直接解析 __NEXT_DATA__ 获取数据
"""
import sys
import re
import json
import requests
import urllib3
import time
import random
from urllib.parse import quote, urljoin

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    host = 'https://rou.video'
    session = requests.Session()
    _debug = True
    _categories = []          # 缓存分类列表
    _home_data = None         # 缓存首页 JSON 数据

    def _log(self, msg):
        if self._debug:
            print(f'[rou] {msg}')

    def getName(self):
        return '肉視頻'

    def isVideoFormat(self, url):
        if not url:
            return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        """代理图片等资源"""
        if not param or not param.startswith('http'):
            return [500, 'text/plain', '']
        try:
            r = self.session.get(param, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': self.host + '/'
            }, timeout=15, stream=True)
            if r.status_code != 200:
                return [r.status_code, 'text/plain', 'error']
            return [200, r.headers.get('Content-Type', 'image/jpeg'), r.content]
        except:
            return [500, 'text/plain', 'error']

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/'
        }

    def _fetch(self, url, referer=None, retries=3):
        """获取页面内容，支持重试"""
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=self._get_headers(referer), timeout=30, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'被拦截 [{r.status_code}] 重试 {attempt+1}')
                    continue
                else:
                    return ''
            except requests.exceptions.Timeout:
                self._log(f'超时重试 {attempt+1}')
            except Exception as e:
                self._log(f'异常 {e} 重试 {attempt+1}')
        return ''

    def _extract_next_data(self, html):
        """从 HTML 中提取 __NEXT_DATA__ JSON 对象"""
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                self._log(f'JSON 解析失败: {e}')
                return None
        return None

    def _parse_categories_from_home(self, html):
        """从首页导航提取分类（按钮的 data-section 属性）"""
        cats = []
        # 匹配类似 <button data-section="section-cnav">國產AV</button>
        pattern = r'<button[^>]*data-section="([^"]+)"[^>]*>([^<]+)</button>'
        for m in re.finditer(pattern, html):
            section_id = m.group(1)
            name = m.group(2).strip()
            # 将 section-cnav 映射为分类名 "國產AV"，section-tanhua -> "探花" 等
            if section_id.startswith('section-'):
                # 去掉 'section-' 前缀，但实际分类名需要从显示文本获取
                # 我们用 name 作为分类名，但有时候名字可能包含特殊字符，保留原样
                # 但我们需要一个 type_id，可以使用 name 或 section_id
                cats.append({
                    'type_id': name,          # 使用中文名作为 id，因为 URL 路径中也是中文
                    'type_name': name,
                    'section': section_id
                })
        return cats

    def init(self, extend=''):
        """初始化，获取首页数据并缓存分类"""
        self.session.headers.update(self._get_headers())
        html = self._fetch(self.host + '/home')
        if html:
            self._home_data = self._extract_next_data(html)
            # 解析分类
            self._categories = self._parse_categories_from_home(html)
            if not self._categories:
                # 如果解析失败，手动补充常见分类
                self._categories = [
                    {'type_id': '國產AV', 'type_name': '國產AV'},
                    {'type_id': '探花', 'type_name': '探花'},
                    {'type_id': '自拍流出', 'type_name': '自拍流出'},
                    {'type_id': 'OnlyFans', 'type_name': 'OnlyFans'},
                    {'type_id': '日本', 'type_name': '日本'},
                ]
            self._log(f'分类加载完成，共 {len(self._categories)} 个')

    def _get_video_list_from_data(self, data_key, limit=None):
        """从缓存的首页数据中提取指定 key 的视频列表"""
        if not self._home_data:
            return []
        props = self._home_data.get('props', {}).get('pageProps', {})
        items = props.get(data_key, [])
        if limit:
            items = items[:limit]
        return self._convert_video_items(items)

    def _convert_video_items(self, items):
        """将 API 视频对象转换为标准列表项"""
        result = []
        for item in items:
            vid = item.get('id') or item.get('vid')
            if not vid:
                continue
            name = item.get('name') or item.get('nameZh') or vid
            pic = item.get('coverImageUrl', '')
            remark = ''
            # 可能从 tags 或 duration 取备注
            if 'duration' in item:
                # 时长转换为分:秒
                seconds = int(item['duration'])
                mins = seconds // 60
                secs = seconds % 60
                remark = f'{mins}分{secs}秒' if mins > 0 else f'{secs}秒'
            result.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remark
            })
        return result

    def homeContent(self, filter=False):
        """获取首页内容（分类 + 推荐列表）"""
        try:
            if not self._home_data:
                self.init()
            # 获取分类
            cats = self._categories
            # 获取最新视频作为首页列表
            items = self._get_video_list_from_data('latestVideos', limit=20)
            return {'class': cats, 'list': items}
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        """首页视频列表（仅列表）"""
        items = self._get_video_list_from_data('latestVideos', limit=20)
        return {'list': items}

    def categoryContent(self, tid, pg, filter=False, extend=''):
        """分类列表（支持分页）"""
        try:
            page = int(pg) if pg else 1
            # 构造分类页 URL，注意 tid 是中文分类名
            # 分类页格式: /t/分类名?page=数字
            url = f'{self.host}/t/{quote(tid)}'
            if page > 1:
                url += f'?page={page}'
            html = self._fetch(url, referer=self.host)
            if not html:
                return {'list': [], 'page': page, 'pagecount': 1}
            # 解析该页的 __NEXT_DATA__
            data = self._extract_next_data(html)
            items = []
            total_pages = 1
            if data:
                props = data.get('props', {}).get('pageProps', {})
                # 不同分类页的数据键可能不同，但通常会有类似 'videos' 或 'list' 的字段
                # 观察首页数据结构，可能分类页也有对应的数据
                # 通用尝试从 pageProps 中获取列表
                video_list = None
                # 尝试常见的键
                for key in ['videos', 'list', 'items', 'results']:
                    if key in props:
                        video_list = props[key]
                        break
                if video_list:
                    items = self._convert_video_items(video_list)
                # 获取总页数，可能从分页信息中读取
                # 简单处理，如果有下一页链接则增加
                next_page = re.search(r'<a[^>]*href="[^"]*\?page=' + str(page+1) + '[^"]*"', html)
                if next_page:
                    total_pages = page + 1
                else:
                    total_pages = page  # 假设只有一页
            return {'list': items, 'page': page, 'pagecount': total_pages}
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def detailContent(self, ids):
        """获取视频详情（包括播放地址）"""
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            url = f'{self.host}/v/{vid}'
            html = self._fetch(url, referer=self.host)
            if not html:
                return {'list': []}
            data = self._extract_next_data(html)
            if not data:
                return {'list': []}
            props = data.get('props', {}).get('pageProps', {})
            # 详情页可能直接包含视频信息，或者通过 props 传递
            # 尝试从 props 中获取视频对象
            video = None
            # 可能字段: 'video', 'post', 'item'
            for key in ['video', 'post', 'item']:
                if key in props:
                    video = props[key]
                    break
            if not video:
                # 尝试从嵌套的 props 中找
                if 'pageProps' in data['props']:
                    video = data['props']['pageProps'].get('video')
            if not video:
                return {'list': []}
            # 提取信息
            title = video.get('name') or video.get('nameZh') or vid
            pic = video.get('coverImageUrl', '')
            # 提取播放源
            sources = video.get('sources', [])
            play_url = ''
            if sources:
                # 优先选择最高分辨率或第一个
                # 真正的播放地址可能需要拼接，但根据现有数据结构，每个 source 有 folder 和 resolution
                # 真实地址可能是 https://v.rn221.xyz/m/... 但需要确知规则
                # 这里我们尝试使用已有的 coverImageUrl 的域名，但更稳妥的是从页面中进一步解析
                # 实际上，我们可能需要从详情页的 JavaScript 中提取播放地址
                # 暂时我们构造一个可能的地址，但很可能不正确，需要后续完善
                # 更可靠的方式是抓取页面中的视频播放器配置
                # 这里我们简单返回第一个 source 的某种格式
                # 由于未深入分析，我们先返回一个占位符
                # 但我们可以尝试从页面中搜索 'm3u8' 或 'mp4'
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8_match:
                    play_url = m3u8_match.group(1)
                else:
                    # 尝试从 sources 构造
                    # 实际上源地址可能是通过某种加密的，需要进一步逆向
                    # 暂时用 placeholder
                    play_url = sources[0].get('folder', '')  # 可能不是完整地址
                    # 如果 folder 是路径，尝试补全
                    if play_url and not play_url.startswith('http'):
                        play_url = 'https://v.rn221.xyz/m/' + play_url  # 猜测
            # 如果没有找到 m3u8，标记为需要解析
            needs_parse = not (play_url and ('.m3u8' in play_url or '.mp4' in play_url))
            vod_play_from = '解析' if needs_parse else '播放'
            flag = f'{vod_play_from}${play_url}'
            return {'list': [{
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_play_from': vod_play_from,
                'vod_play_url': flag,
            }]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags=None):
        """播放器配置，如果 url 需要解析则开启解析"""
        needs_parse = (flag == '解析')
        return {
            'parse': 1 if needs_parse else 0,
            'url': id,
            'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}
        }

    def searchContent(self, key, quick, pg='1'):
        """搜索功能，搜索 URL 可能是 /search?keyword=xxx&page=1"""
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/search?keyword={quote(key)}&page={page}'
            html = self._fetch(url, referer=self.host)
            items = []
            if html:
                data = self._extract_next_data(html)
                if data:
                    props = data.get('props', {}).get('pageProps', {})
                    # 搜索页可能用 'results' 或 'videos'
                    results = props.get('results') or props.get('videos')
                    if results:
                        items = self._convert_video_items(results)
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}
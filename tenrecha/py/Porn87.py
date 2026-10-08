# -*- coding: utf-8 -*-
import json
import re
import sys
from base64 import b64encode, b64decode
from urllib.parse import quote, unquote
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        try:
            self.proxies = json.loads(extend)
        except:
            self.proxies = {}

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

        self.host = 'https://porn87.com'
        self.headers.update({
            'Origin': self.host,
            'Referer': f"{self.host}/"
        })

    def getName(self):
        return "Porn87"

    def isVideoFormat(self, url):
        return any(ext in (url or '') for ext in ['.m3u8', '.mp4', '.ts'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter):
        classes = [
            {'type_name': '最新影片', 'type_id': '/main/tag?lineup=create_time'},
            {'type_name': '最热门', 'type_id': '/main/tag?lineup=recent_views'},
            {'type_name': '标签分类', 'type_id': 'tags'},
        ]

        try:
            response = requests.get(
                self.host,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code == 200:
                videos = self.parse_video_list(response.text)
                return {'class': classes, 'list': videos}
        except Exception as e:
            print(f"homeContent error: {e}")

        return {'class': classes, 'list': []}

    def homeVideoContent(self):
        try:
            response = requests.get(
                self.host,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code == 200:
                videos = self.parse_video_list(response.text)
                return {'list': videos}
        except Exception:
            pass

        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 30
        result['total'] = 999999

        try:
            # 处理标签列表页面
            if tid == 'tags':
                return self.getTagsContent(pg)

            # 处理点击标签后的视频列表
            elif 'tag_click_' in tid:
                tag_url = tid.replace('tag_click_', '')
                if '?' in tag_url:
                    url = f"{self.host}{tag_url}&page={pg}" if pg != '1' else f"{self.host}{tag_url}"
                else:
                    url = f"{self.host}{tag_url}?page={pg}" if pg != '1' else f"{self.host}{tag_url}"

                response = requests.get(
                    url,
                    headers=self.headers,
                    proxies=self.proxies,
                    timeout=15
                )

                if response.status_code == 200:
                    videos = self.parse_video_list(response.text)
                    pagecount = self.detect_page_count(response.text, pg)
                    result['list'] = videos
                    result['pagecount'] = pagecount
                    return result

            # 处理普通分类
            else:
                if '?' in tid:
                    base_url = f"{self.host}{tid}"
                    url = f"{base_url}&page={pg}" if pg != '1' else base_url
                else:
                    url = f"{self.host}{tid}"
                    if pg != '1':
                        url = f"{url}?page={pg}"

                response = requests.get(
                    url,
                    headers=self.headers,
                    proxies=self.proxies,
                    timeout=15
                )

                if response.status_code == 200:
                    videos = self.parse_video_list(response.text)
                    pagecount = self.detect_page_count(response.text, pg)
                    result['list'] = videos
                    result['pagecount'] = pagecount
                    return result

        except Exception as e:
            print(f"categoryContent error: {e}")

        result['list'] = []
        result['pagecount'] = 1
        return result

    def getTagsContent(self, pg="1"):
        """获取所有标签列表 - 使用 folder 类型"""
        try:
            # 标签列表只有一页
            if pg != "1":
                return {'list': [], 'page': pg, 'pagecount': 1}

            url = f"{self.host}/main/all_tags"
            response = requests.get(
                url,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code != 200:
                return {'list': [], 'page': pg, 'pagecount': 1}

            doc = pq(response.text)
            tags = []

            # 提取所有标签链接
            for tag_elem in doc('a[href*="/main/tag?name="]').items():
                tag_href = tag_elem.attr('href') or ''
                tag_name = tag_elem.text().strip()

                if not tag_name or not tag_href:
                    continue

                # 提取标签URL - 避免引号嵌套问题
                tag_pattern = r'(/main/tag\?name=[^&"\'>]+)'
                tag_match = re.search(tag_pattern, tag_href)
                if tag_match:
                    tag_url = tag_match.group(1)
                    # 使用 tag_click_ 前缀标识这是一个标签文件夹
                    tags.append({
                        'vod_id': f'tag_click_{tag_url}',
                        'vod_name': tag_name,
                        'vod_pic': '',
                        'vod_remarks': '标签分类',
                        'vod_tag': 'folder',  # 关键：设置为 folder 类型
                        'style': {"type": "rect", "ratio": 1.33}
                    })

            return {
                'list': tags,
                'page': pg,
                'pagecount': 1,
                'limit': len(tags),
                'total': len(tags)
            }
        except Exception as e:
            print(f"getTagsContent error: {e}")
            return {'list': [], 'page': pg, 'pagecount': 1}

    def detect_page_count(self, html, current_page):
        """检测总页数"""
        try:
            # 查找下一页链接
            next_page = int(current_page) + 1
            if f'page={next_page}' in html:
                return 99999
            return int(current_page)
        except:
            return 1

    def parse_video_list(self, html):
        """解析视频列表"""
        videos = []

        try:
            # 提取所有视频信息
            pattern = r'<a href="/main/html\?id=(\d+)">.*?<img[^>]+src="([^"]+)".*?<span[^>]*>([^<]+)</span>'
            matches = re.findall(pattern, html, re.DOTALL)

            for video_id, img_url, title in matches:
                title = title.strip()
                if not title:
                    continue

                videos.append({
                    'vod_id': video_id,
                    'vod_name': title,
                    'vod_pic': img_url,
                    'vod_remarks': '',
                    'vod_tag': '',
                    'style': {"type": "rect", "ratio": 1.33}
                })
        except Exception as e:
            print(f"parse_video_list error: {e}")

        return videos

    def detailContent(self, ids):
        """获取视频详情"""
        try:
            video_id = ids[0]

            url = f"{self.host}/main/html?id={video_id}"
            response = requests.get(
                url,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code != 200:
                return {
                    'list': [{
                        'vod_id': video_id,
                        'vod_name': '加载失败',
                        'vod_play_from': 'Porn87',
                        'vod_play_url': f'播放${video_id}'
                    }]
                }

            doc = pq(response.text)

            title = doc('title').text() or f'视频 {video_id}'
            title = title.replace(' Porn87 Player', '').strip()

            # 提取标签并创建可点击的标签链接（使用 folder 类型）
            tags = []
            for tag_elem in doc('a[href*="/main/tag?name="]').items():
                tag_name = tag_elem.text().strip()
                tag_href = tag_elem.attr('href') or ''
                if tag_name and tag_href:
                    # 提取完整的标签URL - 避免引号嵌套
                    tag_pattern = r'(/main/tag\?name=[^&"\'>]+)'
                    tag_match = re.search(tag_pattern, tag_href)
                    if tag_match:
                        tag_url = tag_match.group(1)
                        # 使用 tag_click_ 前缀，这样点击标签会进入该标签的视频列表
                        tag_id = f'tag_click_{tag_url}'
                        tags.append(
                            '[a=cr:' + json.dumps({'id': tag_id, 'name': tag_name}, ensure_ascii=False) + '/]' + 
                            tag_name + '[/a]'
                        )

            vod_content = ' '.join(tags) if tags else title

            vod = {
                'vod_id': video_id,
                'vod_name': title,
                'vod_pic': '',
                'vod_content': vod_content,
                'vod_play_from': 'Porn87',
                'vod_play_url': f'播放${video_id}'
            }

            return {'list': [vod]}

        except Exception as e:
            print(f"detailContent error: {e}")
            return {
                'list': [{
                    'vod_id': ids[0] if ids else '',
                    'vod_name': '加载失败',
                    'vod_play_from': 'Porn87',
                    'vod_play_url': f'播放${ids[0] if ids else ""}'
                }]
            }

    def playerContent(self, flag, id, vipFlags):
        """获取播放链接"""
        try:
            url = f"{self.host}/main/embed?id={id}"
            response = requests.get(
                url,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code != 200:
                return {'parse': 1, 'url': url}

            # 提取m3u8链接
            m3u8_match = re.search(r'<video[^>]+src="([^"]+\.m3u8[^"]*)"', response.text)

            if m3u8_match:
                m3u8_url = m3u8_match.group(1)
                return {
                    'parse': 0,
                    'url': m3u8_url,
                    'header': self.headers
                }

            # 备用匹配模式
            m3u8_pattern = r'(https?://[^\s"<>]+\.m3u8[^\s"<>]*)'
            m3u8_match = re.search(m3u8_pattern, response.text)
            if m3u8_match:
                return {
                    'parse': 0,
                    'url': m3u8_match.group(1),
                    'header': self.headers
                }

            return {'parse': 1, 'url': url}

        except Exception as e:
            print(f"playerContent error: {e}")
            return {'parse': 1, 'url': f"{self.host}/main/embed?id={id}"}

    def searchContent(self, key, quick, pg="1"):
        """搜索功能 - 修复：使用正确的 /main/search?name= 格式"""
        try:
            # URL编码搜索关键词
            encoded_key = quote(key)

            # 构建正确的搜索URL：/main/search?name=关键词
            if pg == "1":
                url = f"{self.host}/main/search?name={encoded_key}"
            else:
                url = f"{self.host}/main/search?name={encoded_key}&page={pg}"

            response = requests.get(
                url,
                headers=self.headers,
                proxies=self.proxies,
                timeout=15
            )

            if response.status_code != 200:
                return {'list': [], 'page': pg, 'pagecount': 1}

            # 解析搜索结果
            videos = self.parse_video_list(response.text)

            # 检测分页
            pagecount = self.detect_page_count(response.text, pg)

            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 30,
                'total': 999999
            }
        except Exception as e:
            print(f"searchContent error: {e}")
            return {'list': [], 'page': pg, 'pagecount': 1}

    def localProxy(self, param):
        """本地代理功能（可选）"""
        return [404, 'text/plain', '']

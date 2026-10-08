# coding=utf-8
"""
目标站: 善解人衣 (https://bep.sjry7.pics/cn/home/web/)
057jx013_wtpl 模板架构，动态分类、精准播放解析
"""
import re
import sys
import json
import urllib.parse
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://bep.sjry7.pics"
        self.base_url = "https://bep.sjry7.pics/cn/home/web/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        self.categories = [
            {"type_id": "20", "type_name": "自拍视频"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "无码视频"},
            {"type_id": "23", "type_name": "有码视频"},
            {"type_id": "24", "type_name": "人妻熟女"},
            {"type_id": "25", "type_name": "制服诱惑"},
            {"type_id": "26", "type_name": "口交颜射"},
            {"type_id": "27", "type_name": "SM重味"},
            {"type_id": "28", "type_name": "日韩视频"},
            {"type_id": "29", "type_name": "欧美视频"},
            {"type_id": "30", "type_name": "动漫视频"},
            {"type_id": "31", "type_name": "伦理影片"}
        ]

    def _parse_video_list(self, soup, max_count=0):
        """通用视频列表解析器 - 适配057jx013_wtpl模板"""
        video_list = []
        
        # 模板特征: div.col-sm-6.col-md-4.col-lg-3
        items = soup.select('.col-sm-6.col-md-4.col-lg-3 .well')
        if not items:
            items = soup.select('.well')
        if not items:
            items = soup.select('.col-sm-6')
        
        if not items:
            return video_list
        
        for item in items:
            link = item.select_one('a[href*=".html"]')
            if not link:
                continue
            
            href = link.get('href', '')
            vid = re.search(r'/(\d+)\.html', href)
            if not vid:
                continue
            vid = vid.group(1)
            
            # 提取标题 - 从img的alt属性获取
            title = ''
            img = item.select_one('img')
            if img:
                title = img.get('alt', '')
            if not title:
                title = link.get('title', '')
            if not title:
                title_elem = item.select_one('.title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
            if not title:
                continue
            
            # 提取图片
            pic = ''
            if img:
                pic = img.get('data-original', '')
                if not pic:
                    pic = img.get('src', '')
            if not pic:
                pic = link.get('data-original', '')
            
            # 提取备注
            remark = ''
            remark_elem = item.select_one('.hd-text') or item.select_one('.remarks')
            if remark_elem:
                remark = remark_elem.get_text(strip=True)
            
            video_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
            if max_count > 0 and len(video_list) >= max_count:
                break
        
        return video_list

    def homeContent(self, filter):
        url = self.base_url
        resp = self.fetch(url, headers=self.headers)
        video_list = []
        if resp:
            soup = BeautifulSoup(resp.text, 'html.parser')
            video_list = self._parse_video_list(soup, max_count=36)
        return {"class": self.categories, "list": video_list, "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page <= 1:
            url = f"{self.site_url}/vodtype/{tid}.html"
        else:
            url = f"{self.site_url}/vodtype/{tid}.html?page={page}"
        
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}

        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = self._parse_video_list(soup)

        # 分页计算
        pagecount = page
        pagination = soup.select('.page a') or soup.select('.pagination a')
        for a in pagination:
            text = a.get_text(strip=True)
            if text.isdigit():
                pagecount = max(pagecount, int(text))
        
        # 检查是否有下一页
        has_next = f'?page={page+1}' in resp.text or f'page={page+1}' in resp.text
        if has_next:
            pagecount = page + 1
        
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": len(video_list) * pagecount
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.site_url}/{vod_id}.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 标题
        vod_name = vod_id
        title_elem = soup.select_one('h1') or soup.select_one('.title')
        if title_elem:
            vod_name = title_elem.get_text(strip=True)
        if vod_name == vod_id:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                vod_name = og_title.get('content', vod_id)

        # 图片
        vod_pic = ''
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image:
            vod_pic = og_image.get('content', '')
        if not vod_pic:
            img_elem = soup.select_one('.vodimg img') or soup.select_one('.well img')
            if img_elem:
                vod_pic = img_elem.get('data-original', '') or img_elem.get('src', '')

        # 简介
        vod_content = ''
        desc_elem = soup.select_one('.desc') or soup.select_one('.fed-part-esan')
        if desc_elem:
            vod_content = desc_elem.get_text(' ', strip=True)
        if not vod_content:
            og_desc = soup.select_one('meta[property="og:description"]')
            if og_desc:
                vod_content = og_desc.get('content', '')

        # 演员
        vod_actor = ''
        actor_elem = soup.select_one('.actor a') or soup.select_one('a[href*="/actor/"]')
        if actor_elem:
            vod_actor = actor_elem.get_text(strip=True)

        # 播放列表
        play_from_list = []
        play_url_list = []

        # 方法1: 从video标签直接提取
        video_tag = soup.select_one('video')
        if video_tag:
            src = video_tag.get('src', '')
            if src:
                play_from_list.append('默认线路')
                play_url_list.append(f"正片${src}")

        # 方法2: 从播放列表块提取
        if not play_url_list:
            play_blocks = soup.select('.playlist') or soup.select('.fed-play-list')
            if not play_blocks:
                play_blocks = soup.select('.episode-list')
            if not play_blocks:
                play_blocks = soup.select('ul.list-unstyled')
            
            if play_blocks:
                for idx, block in enumerate(play_blocks):
                    line_name = f"线路{idx+1}"
                    episodes = []
                    for a in block.select('a'):
                        href = a.get('href', '')
                        if not href or 'javascript:' in href or href.startswith('#'):
                            continue
                        ep_name = a.get_text(strip=True) or a.get('title', '')
                        if not ep_name:
                            continue
                        if not href.startswith('http'):
                            href = self.site_url + href if href.startswith('/') else self.site_url + '/' + href
                        episodes.append(f"{ep_name}${href}")
                    if episodes:
                        play_from_list.append(line_name)
                        play_url_list.append('#'.join(episodes))

        # 方法3: 从所有a标签提取播放链接
        if not play_url_list:
            play_links = soup.select('a[href*="/play/"]') or soup.select('a[href*=".m3u8"]')
            if play_links:
                episodes = []
                for a in play_links[:30]:
                    href = a.get('href', '')
                    ep_name = a.get_text(strip=True) or a.get('title', '')
                    if not href or not ep_name:
                        continue
                    if not href.startswith('http'):
                        href = self.site_url + href if href.startswith('/') else self.site_url + '/' + href
                    episodes.append(f"{ep_name}${href}")
                if episodes:
                    play_from_list.append('默认线路')
                    play_url_list.append('#'.join(episodes))

        vod_play_from = '$$$'.join(play_from_list) if play_from_list else '默认源'
        vod_play_url = '$$$'.join(play_url_list) if play_url_list else f"播放${vod_id}"

        result = [{
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_director": '',
            "vod_area": '',
            "vod_year": '',
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/s/index.html?wd={encoded_key}"
        if page > 1:
            url += f"&page={page}"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}

        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = self._parse_video_list(soup)
        return {"list": video_list, "page": page, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        # 如果是m3u8链接直接返回
        if id and '.m3u8' in id:
            return {"parse": 0, "url": id, "header": self.headers}
        
        # 如果id是URL，尝试解析
        if id and id.startswith('http'):
            resp = self.fetch(id, headers=self.headers)
            if resp:
                html = resp.text
                # 提取video标签中的m3u8
                video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
                if video_src:
                    return {"parse": 0, "url": video_src.group(1), "header": self.headers}
                # 提取m3u8
                m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8:
                    return {"parse": 0, "url": m3u8.group(1), "header": self.headers}
                # 提取iframe
                iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe:
                    iframe_url = iframe.group(1)
                    if not iframe_url.startswith('http'):
                        iframe_url = self.site_url + iframe_url if iframe_url.startswith('/') else self.site_url + '/' + iframe_url
                    iframe_resp = self.fetch(iframe_url, headers=self.headers)
                    if iframe_resp:
                        iframe_html = iframe_resp.text
                        m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', iframe_html)
                        if m3u8:
                            return {"parse": 0, "url": m3u8.group(1), "header": self.headers}
                        video_src = re.search(r'<video[^>]+src="([^"]+)"', iframe_html)
                        if video_src:
                            return {"parse": 0, "url": video_src.group(1), "header": self.headers}
        
        # 构造播放URL
        if id and not id.startswith('http'):
            if id.startswith('/'):
                play_url = self.site_url + id
            else:
                play_url = f"{self.site_url}/{id}.html"
        else:
            play_url = id
        
        return {"parse": 1, "url": play_url, "header": self.headers}
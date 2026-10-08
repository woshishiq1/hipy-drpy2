#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作者: 飞鱼
站名: hubff
发布页: https://hubff.com/
"""

import sys
import json
import re
import time
from urllib.parse import urljoin, quote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://hubff.com/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; 2407FRK8EC Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
            "Origin": self.siteUrl,
            "Referer": self.siteUrl
        }
        self.playHeaders = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; 2407FRK8EC Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
            "Referer": self.siteUrl
        }
        self.timeout = 22

    def getName(self):
        return "hubff"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = []
        try:
            html = self.fetch(self.siteUrl, headers=self.headers, timeout=self.timeout).text
            dropdown = self.html(html).find('.dropdown-content, #class')
            if dropdown:
                for a in dropdown.find('a'):
                    a_pq = self.html(a)
                    title = a_pq.text().strip()
                    href = a_pq.attr('href')
                    
                    if title and href and title not in ["首頁", "網站首頁", "免費註冊", "會員登錄"]:
                        type_id = href.replace(self.siteUrl, "").lstrip('/')
                        classes.append({
                            "type_name": title,
                            "type_id": type_id
                        })
        except Exception as e:
            print(f"homeContent error: {e}")

        if not classes:
            classes = [
                {"type_name": "最新", "type_id": "update.php?tags=latest"},
                {"type_name": "热门", "type_id": "update.php?tags=hot"},
                {"type_name": "国产", "type_id": "tag.php?tags=國產"}
            ]

        result['class'] = classes
        result['filters'] = {}
        return result

    def homeVideoContent(self):
        """首页推荐：直接抓取网站真实首页的推荐视频数据"""
        result = {}
        try:
            html = self.fetch(self.siteUrl, headers=self.headers, timeout=self.timeout).text
            videos = self.parse_video_list(html)
        except Exception as e:
            print(f"homeVideoContent error: {e}")
            videos = []

        result['list'] = videos
        return result

    def parse_video_list(self, html):
        """通用精准去广告提取函数（含观看量与更新时间拼接）"""
        videos = []
        pq_html = self.html(html)
        
        for ul in pq_html.find('.list_box ul'):
            ul_pq = self.html(ul)
            
            # 1. 过滤：链接指向首页或为空的广告卡片
            a = ul_pq.find('a')
            link = a.attr('href') if a else ""
            if not link or link.strip('/') == self.siteUrl.strip('/'):
                continue
                
            # 2. 过滤：标题含有“廣告”字样
            title = ul_pq.find('.title').text().strip()
            if '廣告' in title or '广告' in title:
                continue

            # 3. 过滤：非正常详情页地址 (正常项均包含 view.php)
            if 'view.php' not in link:
                continue

            # 4. 提取封面图
            img = ul_pq.find('img')
            pic = img.attr('img') or img.attr('src') if img else ""

            # 5. 提取并拼接副标题 (观看量 + 更新时间)
            views = ul_pq.find('.intro .view').text().strip()
            
            timeago = ul_pq.find('.intro .timeago').attr('title')
            if timeago and len(timeago) >= 10:
                pub_time = timeago[5:10]
            else:
                pub_time = ul_pq.find('.intro .time').text().strip()

            remarks = f"👁 {views} | {pub_time}" if views and pub_time else (views or pub_time)

            if title and link:
                videos.append({
                    "vod_id": self.absoluteUrl(link),
                    "vod_name": title,
                    "vod_pic": self.absoluteUrl(pic),
                    "vod_remarks": remarks
                })
                
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        try:
            if not tid or tid in ["首頁", "/"]:
                tid = "update.php?tags=latest"

            url = urljoin(self.siteUrl, tid)

            if "page=" in url:
                url = re.sub(r'page=\d+', f'page={pg}', url)
            else:
                delimiter = "&" if "?" in url else "?"
                url = f"{url}{delimiter}page={pg}"

            html = self.fetch(url, headers=self.headers, timeout=self.timeout).text
            videos = self.parse_video_list(html)
        except Exception as e:
            print(f"categoryContent error: {e}")
            videos = []

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = len(videos)
        result['total'] = 999999
        return result

    def detailContent(self, array):
        result = {}
        try:
            vid = array[0]
            html = self.fetch(vid, headers=self.headers, timeout=self.timeout).text

            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            play_url = iframe_match.group(1) if iframe_match else vid

            if play_url and not play_url.startswith('http'):
                play_url = urljoin(self.siteUrl, play_url)

            title_match = re.search(r'<title>([^<]+)</title>', html)
            title = title_match.group(1).strip() if title_match else "未知"

            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*poster', html)
            if not img_match:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
            pic = img_match.group(1) if img_match else ""

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self.absoluteUrl(pic),
                "vod_remarks": "",
                "vod_content": vid,
                "vod_play_from": "飞鱼",
                "vod_play_url": f"高清${play_url}"
            }
            result['list'] = [vod]
        except Exception as e:
            print(f"detailContent error: {e}")
        return result

    def searchContent(self, key, quick, pg=1):
        result = {}
        try:
            encoded_key = quote(key)
            url = f"{self.siteUrl}tag.php?tags={encoded_key}&page={pg}"
            html = self.fetch(url, headers=self.headers, timeout=self.timeout).text
            videos = self.parse_video_list(html)
        except Exception as e:
            print(f"searchContent error: {e}")
            videos = []

        result['list'] = videos
        return result

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playContent(self, flag, id, vipFlags):
        """直连提取核心：清洗 HTML 注释，提取 Aliplayer 中的真实 m3u8 并绑定 Header"""
        result = {}
        try:
            if id.startswith('http'):
                req_headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 15; 2407FRK8EC Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
                    "Referer": self.siteUrl
                }
                html = self.fetch(id, headers=req_headers, timeout=self.timeout).text

                # 移除 HTML 注释，排除废弃脚本干扰
                clean_html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

                # 匹配 Aliplayer 内的 source
                ali_match = re.search(r'source:\s*["\']([^"\']+)["\']', clean_html, re.I)
                if ali_match:
                    real_url = ali_match.group(1).strip()
                    if real_url.startswith('//'):
                        real_url = 'https:' + real_url

                    result["parse"] = 0
                    result["playUrl"] = ""
                    result["url"] = real_url
                    result["header"] = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 15; 2407FRK8EC Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
                        "Referer": "https://hubff.com/",
                        "Origin": "https://hubff.com"
                    }
                    return result

            # 二次备用解析
            result["parse"] = 1
            result["playUrl"] = ""
            result["url"] = id
            result["header"] = self.playHeaders
        except Exception as e:
            print(f"playContent error: {e}")
            result["parse"] = 1
            result["playUrl"] = ""
            result["url"] = id
            result["header"] = self.playHeaders
        return result

    def playerContent(self, flag, id, vipFlags):
        """兼容旧版框架方法名拼写"""
        return self.playContent(flag, id, vipFlags)

    def localProxy(self, param):
        pass

    def absoluteUrl(self, url):
        if not url:
            return ""
        if url.startswith('http'):
            return url
        return urljoin(self.siteUrl, url)

    def html(self, content):
        from pyquery import PyQuery as pq
        return pq(content)

    def fetch(self, url, headers=None, timeout=10):
        import requests
        return requests.get(url, headers=headers or self.headers, timeout=timeout)

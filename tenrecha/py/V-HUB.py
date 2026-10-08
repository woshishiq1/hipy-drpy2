# -*- coding: utf-8 -*-
# TVBox爬虫 - V-HUB (newxvideos.pages.dev)
# 类型：视频聚合站，直链 m3u8/mp4

import sys
import json
import re
import requests
import urllib.parse
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "V-HUB"

    def init(self, extend=""):
        self.baseUrl = "https://newxvideos.pages.dev"
        self.session = requests.Session()
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.headers = {
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.baseUrl + '/',
        }
        # 分类列表（从网站源码提取）
        self.categories = [
            {"id": "Arab-159", "name": "阿拉伯"},
            {"id": "Mature-38", "name": "成熟"},
            {"id": "Cuckold-237", "name": "出轨背叛"},
            {"id": "Femdom-235", "name": "调教"},
            {"id": "Anal-12", "name": "肛交"},
            {"id": "Brunette-25", "name": "褐发"},
            {"id": "Black_Woman-30", "name": "黑人"},
            {"id": "Redhead-31", "name": "红发"},
            {"id": "Fucked_Up_Family-81", "name": "家庭乱搞"},
            {"id": "Blonde-20", "name": "金发"},
            {"id": "Big_Cock-34", "name": "巨屌"},
            {"id": "Big_Tits-23", "name": "巨乳"},
            {"id": "Big_Ass-24", "name": "巨臀"},
            {"id": "Blowjob-15", "name": "口交"},
            {"id": "Latina-16", "name": "拉丁裔"},
            {"id": "Milf-19", "name": "辣妈"},
            {"id": "Gapes-167", "name": "裂开"},
            {"id": "Ass-14", "name": "美臀"},
            {"id": "Lesbian-26", "name": "女同"},
            {"id": "bbw-51", "name": "胖女"},
            {"id": "Squirting-56", "name": "喷出"},
            {"id": "Fisting-165", "name": "拳交"},
            {"id": "Gangbang-69", "name": "群交"},
            {"id": "Teen-13", "name": "少女"},
            {"id": "Cumshot-18", "name": "射颜"},
            {"id": "Cam_Porn-58", "name": "摄像头"},
            {"id": "Bi_Sexual-62", "name": "双性恋"},
            {"id": "Stockings-28", "name": "丝袜"},
            {"id": "Oiled-22", "name": "涂油"},
            {"id": "Lingerie-83", "name": "性感内衣"},
            {"id": "Asian_Woman-32", "name": "亚洲"},
            {"id": "Amateur-65", "name": "业余"},
            {"id": "Interracial-27", "name": "异族"},
            {"id": "Indian-89", "name": "印度"},
            {"id": "Creampie-40", "name": "中出"},
            {"id": "Solo_and_Masturbation-33", "name": "自慰"},
            {"id": "AI-239", "name": "AI"},
            {"id": "ASMR-229", "name": "ASMR"},
        ]

    def get_header(self, url=None):
        h = self.headers.copy()
        if url:
            h['Referer'] = url
        return h

    def _fetch_api(self, params):
        """请求API接口"""
        try:
            url = f"{self.baseUrl}/api?{urllib.parse.urlencode(params)}"
            print(f"[V-HUB] 请求: {url}")
            r = self.session.get(url, headers=self.get_header(url), timeout=15)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            print(f"[V-HUB] API请求失败: {e}")
            return None

    def homeContent(self, filter):
        """首页分类"""
        classes = []
        for cat in self.categories:
            classes.append({
                "type_id": cat["id"],
                "type_name": cat["name"]
            })
        return {"class": classes}

    def homeVideoContent(self):
        """首页推荐：请求推荐列表"""
        data = self._fetch_api({"play": "list", "page": "1"})
        if not data:
            return {"list": []}
        videos = data.get("videos", []) if isinstance(data, dict) else data
        return {"list": self._parse_videos(videos)}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        pg = int(pg) if pg else 1
        data = self._fetch_api({"play": "class", "c": tid, "page": str(pg)})
        if not data:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        videos = data.get("videos", []) if isinstance(data, dict) else data
        parsed = self._parse_videos(videos)
        return {
            "list": parsed,
            "page": pg,
            "pagecount": 999,
            "limit": len(parsed),
            "total": 9999
        }

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        pg = int(pg) if pg else 1
        data = self._fetch_api({"play": "k", "k": key, "page": str(pg)})
        if not data:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        videos = data.get("videos", []) if isinstance(data, dict) else data
        parsed = self._parse_videos(videos)
        return {
            "list": parsed,
            "page": pg,
            "pagecount": 999,
            "limit": len(parsed),
            "total": 9999
        }

    def _parse_videos(self, videos):
        """解析视频列表"""
        items = []
        for v in videos:
            try:
                # 提取 xvid
                url = v.get("url", "")
                xvid = None
                if "xvid=" in url:
                    xvid = url.split("xvid=")[-1].split("&")[0]
                if not xvid:
                    continue
                # 提取标题
                title = v.get("title", "未知视频")
                # 提取封面
                img = v.get("img", "")
                if img and img.startswith("//"):
                    img = "https:" + img
                # 提取时长
                duration = v.get("time", "")
                items.append({
                    "vod_id": xvid,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": duration,
                })
            except:
                continue
        return items

    def detailContent(self, ids):
        """详情页：获取视频播放地址"""
        xvid = ids[0]
        # 如果传入的是完整URL，提取xvid
        if "xvid=" in xvid:
            xvid = xvid.split("xvid=")[-1].split("&")[0]

        data = self._fetch_api({"xvid": xvid})
        if not data:
            return {"list": []}

        # 获取播放地址（优先 hls，其次 hight，最后 low）
        play_url = data.get("hls") or data.get("hight") or data.get("low") or ""

        if not play_url:
            return {"list": []}

        # 补全协议
        if play_url.startswith("//"):
            play_url = "https:" + play_url

        return {
            "list": [{
                "vod_id": xvid,
                "vod_name": "视频",
                "vod_pic": "",
                "vod_play_from": "V-HUB",
                "vod_play_url": f"全集${play_url}"
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        """播放：直接返回直链"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        if "$" in id:
            id = id.split("$", 1)[1]
        # 补全协议
        if id.startswith("//"):
            id = "https:" + id
        return {
            "parse": 0,
            "url": id,
            "header": json.dumps({
                "User-Agent": self.ua,
                "Referer": self.baseUrl + "/",
                "Origin": self.baseUrl,
            })
        }

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None
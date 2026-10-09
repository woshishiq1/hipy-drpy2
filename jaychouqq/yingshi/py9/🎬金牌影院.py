# -*- coding: utf-8 -*-

import sys
import hashlib
import time
import requests
import re
import json
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "Aidianying"

    def init(self, extend):
        self.home_url = 'https://www.lwdys.com'
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.error_url = "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        # 完整 39 個分類直接扁平化寫入
        classes = [
            # 第一大類: 电影
            {"type_id": "1_class_喜剧", "type_name": "喜剧片"},
            {"type_id": "1_class_动作", "type_name": "动作片"},
            {"type_id": "1_class_爱情", "type_name": "爱情片"},
            {"type_id": "1_class_科幻", "type_name": "科幻片"},
            {"type_id": "1_class_悬疑", "type_name": "悬疑片"},
            {"type_id": "1_class_奇幻", "type_name": "奇幻片"},
            {"type_id": "1_class_恐怖", "type_name": "恐怖片"},
            {"type_id": "1_class_剧情", "type_name": "剧情片"},
            {"type_id": "1_class_犯罪", "type_name": "犯罪片"},
            {"type_id": "1_class_动画", "type_name": "动画片"},
            {"type_id": "1_class_惊悚", "type_name": "惊悚片"},
            {"type_id": "1_class_战争", "type_name": "战争片"},
            {"type_id": "1_class_冒险", "type_name": "冒险片"},
            {"type_id": "1_class_灾难", "type_name": "灾难片"},
            {"type_id": "1_class_伦理", "type_name": "伦理片"},
            {"type_id": "1_class_其他", "type_name": "其他片"},

            # 第二大類: 电视剧
            {"type_id": "2_type_14", "type_name": "国产剧"},
            {"type_id": "2_type_15", "type_name": "欧美剧"},
            {"type_id": "2_type_16", "type_name": "港台剧"},
            {"type_id": "2_type_62", "type_name": "日韩剧"},
            {"type_id": "2_type_68", "type_name": "其他剧"},

            # 第三大類: 综艺
            {"type_id": "3_type_69", "type_name": "国产综艺"},
            {"type_id": "3_type_70", "type_name": "港台综艺"},
            {"type_id": "3_type_72", "type_name": "日韩综艺"},
            {"type_id": "3_type_73", "type_name": "欧美综艺"},

            # 第四大類: 动漫
            {"type_id": "4_type_75", "type_name": "国产动漫"},
            {"type_id": "4_type_76", "type_name": "日韩动漫"},
            {"type_id": "4_type_77", "type_name": "欧美动漫"},

            # 第五大類: 短剧 (88)
            {"type_id": "88_type_100", "type_name": "喜剧短剧"},
            {"type_id": "88_type_99", "type_name": "奇幻短剧"},
            {"type_id": "88_type_98", "type_name": "惊悚短剧"},
            {"type_id": "88_type_97", "type_name": "悬疑短剧"},
            {"type_id": "88_type_96", "type_name": "古装短剧"},
            {"type_id": "88_type_94", "type_name": "剧情短剧"},
            {"type_id": "88_type_95", "type_name": "爱情短剧"}
        ]

        filters = {}
        # 為所有分類綁定「排序」過濾器
        sort_filter = [{'key': 'by', 'name': '排序', 'value': [{'n': '最近更新', 'v': '/sortType/1/sortOrder/0'}, {'n': '人气高低', 'v': '/sortType/3/sortOrder/0'}, {'n': '评分高低', 'v': '/sortType/4/sortOrder/0'}]}]
        
        for cls in classes:
            filters[cls['type_id']] = sort_filter

        return {
            'class': classes,
            'filters': filters if filter else {}
        }

    def homeVideoContent(self):
        video_list = []
        t = str(int(time.time() * 1000))
        data = f'key=cb808529bae6b6be45ecfab29a4889bc&t={t}'
        data_md5 = hashlib.md5(data.encode()).hexdigest()
        data_sha1 = hashlib.sha1(data_md5.encode()).hexdigest()
        h = {
            "User-Agent": self.ua,
            'referer': self.home_url, 't': t, 'sign': data_sha1}
        try:
            res = requests.get(f'{self.home_url}/api/mw-movie/anonymous/home/hotSearch', headers=h)
            data_list = res.json()['data']
            for i in data_list:
                video_list.append(
                    {
                        'vod_id': i['vodId'],
                        'vod_name': i['vodName'],
                        'vod_pic': i['vodPic'],
                        'vod_remarks': i['vodVersion'] if i['typeId1'] == 1 else i['vodRemarks']
                    }
                )
        except requests.RequestException as e:
            return {'list': [], 'parse': 0, 'jx': 0}

        return {'list': video_list, 'parse': 0, 'jx': 0}

    def categoryContent(self, cid, page, filter, ext):
        ext = ext if isinstance(ext, dict) else {}
        
        tid_str = str(cid)
        t = tid_str
        _type = ''
        __class = ''

        # 自動解析我們自訂的 type_id (例如 "1_class_喜剧" 或 "2_type_14")
        if "_" in tid_str:
            parts = tid_str.split("_", 2)
            if len(parts) == 3:
                t = parts[0]
                if parts[1] == "type":
                    _type = f"/type/{parts[2]}"
                elif parts[1] == "class":
                    __class = f"/class/{parts[2]}"

        _by = ext.get('by', '')
        video_list = []
        h = {
            "User-Agent": self.ua,
            'referer': self.home_url,
        }
        
        try:
            # 組合出乾淨且 100% 精準的請求網址
            url = f'{self.home_url}/vod/show/id/{t}{_type}{__class}{_by}/page/{page}'
            res = requests.get(url, headers=h)
            
            aa = re.findall(r'\\"list\\":(.*?)}}}]', res.text)
            if not aa:
                return {'list': [], 'parse': 0, 'jx': 0}
            
            bb = aa[0].replace('\\"', '"')
            data_list = json.loads(bb)
            for i in data_list:
                video_list.append(
                    {
                        'vod_id': i['vodId'],
                        'vod_name': i['vodName'],
                        'vod_pic': i['vodPic'],
                        'vod_remarks': i['vodVersion'] if i['typeId1'] == 1 else i['vodRemarks']
                    }
                )
        except requests.RequestException as e:
            return {'list': [], 'msg': str(e)}
            
        return {'list': video_list, 'parse': 0, 'jx': 0}

    def detailContent(self, did):
        ids = did[0]
        video_list = []
        t = str(int(time.time() * 1000))
        data = f'id={ids}&key=cb808529bae6b6be45ecfab29a4889bc&t={t}'
        data_md5 = hashlib.md5(data.encode()).hexdigest()
        data_sha1 = hashlib.sha1(data_md5.encode()).hexdigest()
        h = {
            "User-Agent": self.ua,
            'referer': self.home_url,
            't': t, 'sign': data_sha1
        }
        try:
            res = requests.get(f'{self.home_url}/api/mw-movie/anonymous/video/detail?id={ids}', headers=h)
            data = res.json()['data']
            play_list = data['episodeList']
            vod_play_url = []
            for i in play_list:
                name = i['name']
                url = ids + '/' + str(i['nid'])
                vod_play_url.append(name + '$' + url)

            video_list.append(
                {
                    'type_name': data['typeName'],
                    'vod_id': ids,
                    'vod_name': data['vodName'],
                    'vod_remarks': data['vodRemarks'],
                    'vod_year': data['vodYear'],
                    'vod_area': data['vodArea'],
                    'vod_actor': data['vodActor'],
                    'vod_director': data['vodDirector'],
                    'vod_content': data['vodContent'],
                    'vod_play_from': '老僧酿酒',
                    'vod_play_url': '#'.join(vod_play_url)
                }
            )
        except requests.RequestException as e:
            return {'list': [], 'msg': str(e)}
        return {"list": video_list, 'parse': 0, 'jx': 0}

    def searchContent(self, key, quick, page='1'):
        wd = key
        video_list = []
        t = str(int(time.time() * 1000))
        data = f'keyword={wd}&pageNum={page}&pageSize=12&key=cb808529bae6b6be45ecfab29a4889bc&t={t}'
        data_md5 = hashlib.md5(data.encode()).hexdigest()
        data_sha1 = hashlib.sha1(data_md5.encode()).hexdigest()
        h = {
            "User-Agent": self.ua,
            'referer': self.home_url,
            't': t, 'sign': data_sha1
        }
        try:
            response = requests.get(
                f'{self.home_url}/api/mw-movie/anonymous/video/searchByWord?keyword={wd}&pageNum={page}&pageSize=12',
                headers=h,
            )
            data_list = response.json()['data']['result']['list']
            for i in data_list:
                video_list.append(
                    {
                        'vod_id': i['vodId'],
                        'vod_name': i['vodName'],
                        'vod_pic': i['vodPic'],
                        'vod_remarks': i['vodVersion'] if i['typeId1'] == 1 else i['vodRemarks']
                    }
                )
        except requests.RequestException as e:
            return {'list': [], 'msg': str(e)}
        return {'list': video_list, 'parse': 0, 'jx': 0}

    def playerContent(self, flag, pid, vipFlags):
        url = pid
        play_url = self.error_url
        data = url.split('/')
        _id = data[0]
        _nid = data[1]
        t = str(int(time.time() * 1000))
        data = f'id={_id}&nid={_nid}&key=cb808529bae6b6be45ecfab29a4889bc&t={t}'
        data_md5 = hashlib.md5(data.encode()).hexdigest()
        data_sha1 = hashlib.sha1(data_md5.encode()).hexdigest()
        h = {
            "User-Agent": self.ua,
            'referer': self.home_url,
            't': t, 'sign': data_sha1
        }
        h2 = {
            "User-Agent": self.ua,
        }
        try:
            res = requests.get(
                f'{self.home_url}/api/mw-movie/anonymous/v2/video/episode/url?id={_id}&nid={_nid}',
                headers=h)
            play_url = res.json()['data']['list'][0]['url']
        except requests.RequestException as e:
            return {"url": play_url, "header": h2, "parse": 0, "jx": 0}

        return {"url": play_url, "header": h2, "parse": 0, "jx": 0}

    def localProxy(self, params):
        pass

    def destroy(self):
        return '正在Destroy'

if __name__ == '__main__':
    pass
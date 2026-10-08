# -*- coding: utf-8 -*-
import json
import time
import random
import requests
import sys

sys.path.append('..')
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def init(self, extend=""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }

    def getName(self):
        return "冬天专享"

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def homeContent(self, filter):
        classes = [
            {"type_name": "小姐姐①", "type_id": "http://api.yujn.cn/api/zzxjj.php"},
            {"type_name": "小姐姐②", "type_id": "http://api.yujn.cn/api/xjj.php"},
            {"type_name": "女大学生", "type_id": "http://api.yujn.cn/api/nvda.php"},
            {"type_name": "黑丝", "type_id": "http://api.yujn.cn/api/heisis.php"},
            {"type_name": "Cosplay", "type_id": "http://api.yujn.cn/api/manzhan.php"},
            {"type_name": "白丝", "type_id": "http://api.yujn.cn/api/baisis.php"},
            {"type_name": "极品身材", "type_id": "http://api.yujn.cn/api/wmsc.php"},
            {"type_name": "蛇姐", "type_id": "http://api.yujn.cn/api/shejie.php"},
            {"type_name": "性感吊带", "type_id": "http://api.yujn.cn/api/diaodai.php"},
            {"type_name": "玉足", "type_id": "http://api.yujn.cn/api/jpmt.php"},
            {"type_name": "清纯", "type_id": "http://api.yujn.cn/api/qingchun.php"},
            {"type_name": "萝莉", "type_id": "http://api.yujn.cn/api/luoli.php"},
        ]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        return self.categoryContent("http://api.yujn.cn/api/zzxjj.php", "1", None, {})

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        pg_int = int(pg) if pg else 1
        
        for i in range(20):
            videos.append({
                "vod_id": f"yujn${tid}", 
                "vod_name": f"冬天专线 {pg_int}-{i+1}",
                "vod_pic": "https://t.mwm.moe/mp/", 
                "vod_remarks": "",
                "style": {"type": "rect", "ratio": 0.56},
                "vod_player": "short"
            })
            
        return {'list': videos, 'page': pg_int, 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def detailContent(self, ids):
        vod_id = ids[0]
        api_url = vod_id.split('$')[1]
        
        play_list = []
        session_id = str(int(time.time()))[-4:]
        rand_salt = str(random.randint(1000000, 9999999))
        
        for i in range(80):
            title = f"{i+1}.冬天随机 🕒{session_id}"
            full_api = f"{api_url}?type=json"
            
            play_list.append(f"{title}$yujn_play${full_api}@@{rand_salt}_{i}")
            
        vod = {
            "vod_id": f"yujn_{rand_salt}",
            "vod_name": "快活冬天",
            "vod_pic": "https://t.mwm.moe/mp/",
            "vod_play_from": "冬天引擎",
            "vod_play_url": "#".join(play_list),
            "vod_player": "short"
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('yujn_play$'):
            api_url = id.split('$')[1].split('@@')[0]
            
            try:
                r = requests.get(api_url, headers=self.headers, timeout=10).json()
                
                video_url = r.get('data') or r.get('url') or r.get('video') or r.get('msg')
                if isinstance(video_url, dict):
                    video_url = video_url.get('url') or video_url.get('video') or video_url.get('data')
                    
                if video_url and str(video_url).startswith('http'):
                    return {'parse': 0, 'url': video_url, 'vod_player': 'short', 'header': self.headers}
            except Exception:
                pass
                
            return {"parse": 0, "url": "toast://获取视频失败,请上滑重试", "header": ""}
            
        return {"parse": 0, "url": id, "header": self.headers}
        
    def searchContent(self, key, quick, pg="1"):
        return {'list': []}

    def localProxy(self, param):
        return [404, "text/plain", b""]

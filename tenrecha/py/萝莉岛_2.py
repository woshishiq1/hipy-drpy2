# -*- coding: utf-8 -*-
import sys, re, json, urllib.parse
sys.path.append('..')
try:
    from base.spider import Spider as _B
except ImportError:
    class _B: pass
try:
    import requests
except ImportError:
    requests = None

H = "https://dag29jmgma1g.site"
U = "Mozilla/5.0 (Linux; Android 12; TFY-AN00 Build/HONORTFY-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.105 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/33.0)"

class Spider(_B):
    def init(self, e=""):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": U, 
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        self.token = ""
        self._register()

    def getName(self):
        return "萝莉岛"

    def isVideoFormat(self, u):
        return ".m3u8" in u or ".mp4" in u or "preview" in u

    def manualVideoCheck(self):
        return False

    def _register(self):
        """注册/获取设备的交互 Token"""
        url = H + "/api/newreg.php"
        data = {"device": "android", "ntoken": "", "channel_code": "vbtQg9D8"}
        try:
            r = self.s.post(url, data=data, timeout=10).json()
            self.token = r.get("user", {}).get("token", "")
        except Exception as e:
            print('[REGISTER]', e)

    def homeContent(self, filter=False):
        """获取主分类及其对应的筛选条件"""
        url = H + "/api/setapp.php"
        try:
            r = self.s.get(url, timeout=10).json()
            classes = []
            filters = {}
            
            # API 将分类拆分在 vodtab 和 vodtaban (暗黑) 两个数组中，这里将其合并
            tabs = r.get("vodtab", []) + r.get("vodtaban", [])
            for tab in tabs:
                tid = tab.get("type_id")
                classes.append({
                    "type_id": tid,
                    "type_name": tab.get("type_name")
                })
                tags = tab.get("vodtags", [])
                if tags:
                    tag_values = [{"n": "全部", "v": ""}]
                    for tag in tags:
                        tag_values.append({"n": tag.get("name"), "v": tag.get("name")})
                    filters[tid] = [{"key": "class", "name": "标签", "value": tag_values}]
            
            return {"class": classes, "filters": filters if filter else {}}
        except Exception as e:
            print('[HOME]', e)
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """获取分类子列表"""
        if not extend: extend = {}
        url = H + "/api/vlist.php"
        
        # 抓包显示 num 为 0，通常代表 offset(偏移量)。结合返回结果固定30条推算，offset = (页码 - 1) * 30
        num = (int(pg) - 1) * 30
        payload = {
            "num": str(num),
            "pid": str(tid),
            "area": "全部",
            "vodclass": extend.get("class", ""),
            "vodyear": "全部",
            "sort": "1",
            "token": self.token
        }
        try:
            r = self.s.post(url, data=payload, timeout=10).json()
            videos = []
            for item in r.get("list", []):
                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": item.get("vod_pic", ""),
                    "vod_remarks": item.get("vod_class", "") or item.get("vod_remarks", "")
                })
            return {"list": videos, "page": pg}
        except Exception as e:
            print('[CATEGORY]', e)
            return {"list": []}

    def detailContent(self, ids):
        """获取视频详情及播放链接"""
        url = H + "/api/Get_vod_list.php"
        payload = {
            "id": str(ids[0]),
            "token": self.token,
            "channel": ""
        }
        try:
            r = self.s.post(url, data=payload, timeout=10).json()
            data = r.get("data", {})
            
            # API 抓包中直接包含了 TVBox 兼容格式的 vod_play_url (如："正片$https://...m3u8")
            play_url = data.get("vod_play_url", "")
            if not play_url:
                # 兼容未登录或无权限的情况，回退至试看预览链接
                play_url = "预览$" + data.get("preview_url", "")

            video = {
                "vod_id": str(data.get("vod_id", ids[0])),
                "vod_name": data.get("vod_name", ""),
                "vod_pic": data.get("vod_pic", ""),
                "vod_remarks": data.get("vod_remarks", ""),
                "vod_content": data.get("vod_blurb", "暂无简介"),
                "vod_play_from": "萝莉岛",
                "vod_play_url": play_url
            }
            return {"list": [video]}
        except Exception as e:
            print('[DETAIL]', e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        """播放器直连"""
        return {
            "parse": 0,
            "url": id,
            "header": json.dumps({"User-Agent": U})
        }

    def searchContent(self, key, quick=False, pg=1):
        """由于未提供搜索接口的抓包记录，预留空返回值避免TVBox请求报错"""
        return {"list": []}

    def localProxy(self, param):
        pass
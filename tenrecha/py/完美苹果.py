# -*- coding: utf-8 -*-
# by @嗷呜
import sys
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    host='http://s.xpgtv.net/'

    # 全局头部
    headers = {
      "User-Agent": "okhttp/3.12.11"
    }

    def homeContent(self, filter):
        data = self.fetch(f"{self.host}/api.php/v2.vod/androidtypes",headers=self.headers,).json()
        dy = {
            "classes": "类型",
            "areas": "地区",
            "years": "年份",
            "sortby": "排序",
        }
        filters = {}
        classes = []
        for item in data['data']:
            has_non_empty_field = False
            item['sortby'] = ['updatetime', 'hits', 'score']
            demos = ['时间', '人气', '评分']
            classes.append({"type_name": item["type_name"], "type_id": str(item["type_id"])})
            for key in dy:
                if key in item and len(item[key]) > 1:
                    has_non_empty_field = True
                    break
            if has_non_empty_field:
                filters[str(item["type_id"])] = []
                for dkey in item:
                    if dkey in dy and len(item[dkey]) > 1:
                        values = item[dkey]
                        value_array = [
                            {"n": demos[idx] if dkey == "sortby" else value.strip(), "v": value.strip()}
                            for idx, value in enumerate(values)
                            if value.strip() != ""
                        ]
                        filters[str(item["type_id"])].append(
                            {"key": dkey, "name": dy[dkey], "value": value_array}
                        )
        result = {}
        result["class"] = classes
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        rsp = self.fetch(f"{self.host}/api.php/v2.main/androidhome", headers=self.headers).json()
        videos = []
        for i in rsp['data']['list']:videos.extend(self.getlist(i['list']))
        return {'list':videos}

    def categoryContent(self, tid, pg, filter, extend):
        params = {
            "page": pg,
            "type": tid,
            "area":extend.get('areaes',''),
            "year":extend.get('yeares',''),
            "sortby":extend.get('sortby',''),
            "class":extend.get('classes','')
        }
        params={i:v for i,v in params.items() if v}
        rsp = self.fetch(f'{self.host}/api.php/v2.vod/androidfilter10086', headers=self.headers, params=params).json()
        result = {}
        result['list'] = self.getlist(rsp['data'])
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        rsp = self.fetch(f'{self.host}/api.php/v3.vod/androiddetail2?vod_id={ids[0]}', headers=self.headers).json()
        v = rsp['data']
        
        # 依然保留过滤逻辑，防止点击到“及时雨”广告片
        url_list = []
        if 'urls' in v:
            for i in v['urls']:
                if '及时雨' in i['key']:
                    continue
                url_list.append(f"{i['key']}${i['url']}")

        vod = {
            'vod_year':v.get('year'),
            'vod_area':v.get('area'),
            'vod_lang':v.get('lang'),
            'type_name':v.get('className'),
            'vod_actor':v.get('actor'),
            'vod_director':v.get('director'),
            'vod_content':v.get('content'),
            'vod_play_from': '小苹果',
            'vod_play_url': '#'.join(url_list)
        }
        return {'list':[vod]}

    def searchContent(self, key, quick, pg='1'):
        rsp = self.fetch(f'{self.host}/api.php/v2.vod/androidsearch10086?page={pg}&wd={key}', headers=self.headers).json()
        return {'list':self.getlist(rsp['data']),'page':pg}

    def playerContent(self, flag, id, vipFlags):
        # 核心修复：完全替换为成功日志中的 JSYBOX 配置
        header = {
            'User-Agent': 'okhttp/3.12.11',
            'user_id': 'JSYBOX',
            'token': 'XHEJzQjfigwZcU99XhK3K4ZyKqXA1jdMpaFmrn/mJf9MKEBipQN31ftE0N9EUFS+BiIyBffFa4MPMJlCZQJ4e/IuGWY/wnqwKk1McYhZES5fuT4cEFZ0kjO3wDyrb0B/w7B6VjZyQ6iNiSAaTytU7rrLN3AW+DeSyiv2Ke+ddFmVI0tfZXlXfGAIOq5vQK2RQCnAkHfewdixpG8M',
            'token2': 'Wz8tmSSTszwHXEICbw6AUodVPvH3kCouvvI4pnHLPeBhU3gcsCZ01JdT8t8=',
            'version': 'JSYBOX com.phoenix.jsy.box1.0.7',
            'timestamp': '1768114062',
            'hash': '65ad',
            'screenx': '2345',
            'screeny': '1065',
        }
        
        # 修复域名：根据日志，必须使用 s.xpgtv.net
        if 'http' not in id:
            id = f"http://s.xpgtv.net/m3u8/{id}.m3u8"
            
        return {"parse": 0, "url": id, "header": header}

    def localProxy(self, param):
        pass

    def getlist(self,data):
        videos = []
        for vod in data:
            r=f"更新至{vod.get('updateInfo')}" if vod.get('updateInfo') else ''
            videos.append({
                "vod_id": vod['id'],
                "vod_name": vod['name'],
                "vod_pic": vod['pic'],
                "vod_remarks": r or vod['score']
            })
        return videos

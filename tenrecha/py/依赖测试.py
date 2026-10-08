"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '依赖测试',
  lang: 'hipy'
})
"""

# coding=utf-8
# !/usr/bin/python
import sys
import time

sys.path.append('..')
try:
    from base.spider import BaseSpider
except ImportError:
    from t4.base.spider import BaseSpider


class Spider(BaseSpider):
    def getName(self):
        return "依赖测试"

    filterate = False

    def init(self, extend=""):
        print("============{0}============".format(extend))
        if isinstance(extend, list):
            for lib in extend:
                print(type(lib))
                if '.Spider' in str(type(lib)):
                    self.module = lib
                    break
        print('has module:',hasattr(self, 'module'))


    def getDependence(self):
#         return []
        return ['base_spider']

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        cateManual = {
            '动漫': '3',
            '动漫电影': '17',
            '综艺': '4',
            '纪录片': '5',
            '动作片': '6',
            '爱情片': '7',
            '科幻片': '8',
            '战争片': '9',
            '剧情片': '10',
            '恐怖片': '11',
            '喜剧片': '12',
            '大陆剧': '13',
            '港澳剧': '14',
            '台湾剧': '15',
            '欧美剧': '16',
            '韩剧': '18',
            '日剧': '20',
            '泰剧': '21',
            '体育': '23'
        }
        classes = []
        for k in cateManual:
            classes.append({
                'type_name': k,
                'type_id': cateManual[k]
            })
        result['class'] = classes
        if (filter):
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        result = {
            'list': []
        }
        if hasattr(self, 'module'):
            result = self.module.homeVideoContent()
        return result

    def categoryContent(self, tid, pg, filter, extend):
        print('categoryContent:',tid,pg,filter,extend)
        result = {}
        videos = []
        pagecount = 1
        limit = 20
        total = 9999
        videos = []
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = pagecount
        result['limit'] = limit
        result['total'] = total
        return result

    def detailContent(self, array):
        vod = {}
        result = {
            'list': [
                vod
            ]
        }
        return result

    def searchContent(self, key, quick, pg=1):
        videos = []
        result = {
            'list': videos
        }
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        parse = 1
        url = id
        result["parse"] = parse  # 0=直接播放、1=嗅探
        result["playUrl"] = ''
        result["url"] = url
        result['jx'] = 0  # VIP解析,0=不解析、1=解析
        result["header"] = ''
        return result

    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, params):
        return [200, "video/MP2T", ""]
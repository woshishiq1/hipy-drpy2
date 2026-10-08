# -*- coding: utf-8 -*-
# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。

import re, sys, urllib3
from base.spider import Spider
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    # 初始化请求头，使用浏览器 UA 防止被拦截
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        'Accept-Encoding': "gzip"
    }
    host = ''

    def init(self, extend=''):
        # 处理 ext 传入的地址，去除首尾空格和末尾斜杠
        if extend:
            host = extend.strip()
            if host.startswith('http'):
                self.host = host.rstrip('/')

    def homeContent(self, filter):
        # 获取分类
        url = f'{self.host}/api.php?type=getsort'
        response = self.fetch(url, headers=self.headers, verify=False).json()
        classes, filters = [], {}
        
        if 'list' in response:
            for i in response['list']:
                type_id = str(i['type_id']) # 确保 ID 是字符串
                classes.append({'type_id': type_id, 'type_name': i['type_name']})
                
                # 处理筛选条件
                if 'type_extend' in i and i['type_extend']:
                    extend = i['type_extend']
                    filter_list = []
                    
                    # 类型筛选
                    if 'class' in extend and extend['class']:
                        value_list = [{"n": "全部", "v": "全部"}]
                        for val in extend['class'].split(','):
                            if val.strip():
                                value_list.append({"n": val.strip(), "v": val.strip()})
                        filter_list.append({"key": "class", "name": "类型", "init": "全部", "value": value_list})
                    
                    # 年份筛选
                    if 'year' in extend and extend['year']:
                        value_list = [{"n": "全部", "v": "全部"}]
                        for val in extend['year'].split(','):
                            if val.strip():
                                value_list.append({"n": val.strip(), "v": val.strip()})
                        filter_list.append({"key": "year", "name": "年份", "init": "全部", "value": value_list})
                    
                    if filter_list:
                        filters[type_id] = filter_list
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        # 获取首页推荐
        url = f'{self.host}/api.php?type=getHome'
        response = self.fetch(url, headers=self.headers, verify=False).json()
        videos = []
        # 遍历 JSON 对象的所有值
        for j in response.values():
            if isinstance(j, dict) and 'list' in j:
                lis = j.get('list')
                if isinstance(lis, list):
                    videos.extend(lis)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        # 获取分类列表
        tag = extend.get('class', '全部') if extend else '全部'
        year = extend.get('year', '全部') if extend else '全部'
        
        url = f"{self.host}/api.php?type=getvod&type_id={tid}&page={pg}&tag={tag}&year={year}"
        response = self.fetch(url, headers=self.headers, verify=False).json()
        
        return {'list': response.get('list', []), 'page': int(pg), 'pagecount': response.get('pagecount', 1), 'total': response.get('total', 0)}

    def searchContent(self, key, quick, pg="1"):
        # 搜索
        url = f'{self.host}/api.php?type=getsearch&text={key}'
        response = self.fetch(url, headers=self.headers, verify=False).json()
        
        # 补充简介内容
        if 'list' in response:
            for i in response['list']:
                if not i.get('vod_content') and i.get('vod_blurb'):
                    i['vod_content'] = i['vod_blurb']
        return {'list': response.get('list', []), 'page': pg}

    def detailContent(self, ids):
        # 获取详情
        url = f'{self.host}/api.php?type=getVodinfo&id={ids[0]}'
        response = self.fetch(url, headers=self.headers, verify=False).json()
        
        show = []
        vod_play_url = []
        
        # 增加判空逻辑，防止崩溃
        if 'vod_player' in response and 'list' in response['vod_player']:
            for i in response['vod_player']['list']:
                source_name = i.get('from', '')
                source_show = i.get('ps', '')
                
                # 处理显示名称
                if source_show == source_name:
                    show.append(source_name)
                else:
                    clean_show = source_show.replace('(广告勿信)', '').strip()
                    show.append(f"{clean_show}\u2005({source_name})")
                
                # 处理播放地址，拼接 @ID 用于后续解析
                play_url = i.get('url', '')
                if play_url:
                    processed_urls = []
                    for item in play_url.split('#'):
                        if item.strip():
                            processed_urls.append(f"{item.strip()}@{ids[0]}")
                    vod_play_url.append('#'.join(processed_urls))
        
        # 如果没获取到播放源，给一个默认空值防止报错
        if not show:
            show.append('默认')
            vod_play_url.append('无数据')

        video = {
            'vod_name': response.get('vod_name', ''),
            'vod_pic': response.get('vod_pic', ''),
            'vod_id': response.get('vod_id', ''),
            'vod_class': response.get('vod_class', ''),
            'vod_actor': response.get('vod_actor', ''),
            'vod_blurb': response.get('vod_blurb', ''),
            'vod_content': response.get('vod_content', response.get('vod_blurb', '')),
            'vod_remarks': response.get('vod_remarks', ''),
            'vod_play_from': '$$$'.join(show),
            'vod_play_url': '$$$'.join(vod_play_url)
        }
        return {'list': [video]}

    def playerContent(self, flag, id, vipflags):
        # 播放解析
        jx = 0
        # 安卓原生 UA
        ua = 'Dalvik/2.1.0 (Linux; U; Android 14; Xiaomi 15 Build/SQ3A.220705.004)'
        # 电脑浏览器 UA
        ua2 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        
        url = ''
        parts = id.split('@')
        vod_url = parts[0]
        vod_id = parts[1] if len(parts) > 1 else ''
        
        # 尝试通过 API 解析
        try:
            jx_url = f'{self.host}/api.php?type=jx&vodurl={vod_url}&vodid={vod_id}'
            response = self.fetch(jx_url, headers=self.headers, verify=False).json()
            # 修复：原代码这里逻辑有误，response['url'] 赋值给了 play_url 但没给 url
            if 'url' in response and response['url']:
                play_url = response['url']
                if play_url.startswith('http'):
                    url = play_url
        except Exception:
            pass
            
        # 如果解析失败或没有解析，使用原地址
        if not url:
            url = vod_url
            # 如果是主流视频网站，开启嗅探
            if re.search(r'(?:www\.iqiyi|v\.qq|v\.youku|www\.mgtv|www\.bilibili)\.com', vod_url):
                jx = 1
                ua = ua2
                
        return {'jx': jx, 'parse': 0, 'url': url, 'header': {'User-Agent': ua}}

    # 以下方法保持空实现，满足基类要求
    def getName(self): pass
    def isVideoFormat(self, url): pass
    def manualVideoCheck(self): pass
    def destroy(self): pass
    def localProxy(self, param): pass
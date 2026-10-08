# -*- coding: utf-8 -*-
# by @嗷呜
import sys
import re

sys.path.append('..')
from base.spider import Spider


class XiaoPingGuoSpider(Spider):  # 避免类名冲突

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    host = 'http://item.xpgcom.com'

    headers = {
        "User-Agent": "okhttp/3.12.11"
    }

    def is_likely_jishiyu(self, text):
        """
        智能判断是否为“及时雨”类播放源（支持简体、繁体、拼音、变体、干扰符）
        """
        if not text:
            return False

        # 标准化：转小写，移除非字母数字和中文字符（保留用于判断）
        clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', str(text).lower())

        # 1. 中文关键词（简体/繁体/异体）
        for phrase in ['及时雨', '及時雨', '即时雨']:
            if phrase in clean:
                return True

        # 2. 提取纯字母数字部分用于拼音匹配
        alpha_num = re.sub(r'[^\w]', '', clean).lower()

        # 常见拼音核心片段（覆盖 jsy / jishiyu / jshy 等）
        core_patterns = ['jsy', 'jishy', 'jishiy', 'jshy', 'jishiyu']
        for pat in core_patterns:
            if pat in alpha_num:
                return True

        # 3. 启发式：短字符串中同时包含 j/s/y，很可能是代号
        if len(alpha_num) <= 8 and all(c in alpha_num for c in ['j', 's', 'y']):
            return True

        return False

    def homeContent(self, filter):
        data = self.fetch(f"{self.host}/api.php/v2.vod/androidtypes", headers=self.headers).json()
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
            item['sortby'] = ['updatetime', 'hits', 'score']  # 修复拼写错误
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
        result = {
            "class": classes,
            "filters": filters
        }
        return result

    def homeVideoContent(self):
        rsp = self.fetch(f"{self.host}/api.php/v2.main/androidhome", headers=self.headers).json()
        videos = []
        for i in rsp['data']['list']:
            videos.extend(self.getlist(i['list']))
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        # 修正字段名：areaes → area, yeares → year, classes → class
        params = {
            "page": pg,
            "type": tid,
            "area": extend.get('area', ''),
            "year": extend.get('year', ''),
            "sortby": extend.get('sortby', ''),
            "class": extend.get('class', '')
        }
        params = {k: v for k, v in params.items() if v}
        rsp = self.fetch(f'{self.host}/api.php/v2.vod/androidfilter10086', headers=self.headers, params=params).json()
        result = {
            'list': self.getlist(rsp['data']),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        return result

    def detailContent(self, ids):
        rsp = self.fetch(f'{self.host}/api.php/v3.vod/androiddetail2?vod_id={ids[0]}', headers=self.headers).json()
        v = rsp.get('data', {}) or {}
        urls = v.get('urls') or []
        play_items = []

        for i in urls:
            key = (i.get('key') or i.get('name') or "").strip()
            url = (i.get('url') or "").strip()
            if not key or not url:
                continue

            # 智能自动屏蔽“及时雨”及其变体
            combined_text = f"{key} {url}"
            if self.is_likely_jishiyu(combined_text):
                continue

            play_items.append(f"{key}${url}")

        play_url = "#".join(play_items)

        vod = {
            'vod_id': v.get('id'),
            'vod_name': v.get('name'),
            'vod_pic': v.get('pic'),
            'vod_year': v.get('year'),
            'vod_area': v.get('area'),
            'vod_lang': v.get('lang'),
            'type_name': v.get('className'),
            'vod_actor': v.get('actor'),
            'vod_director': v.get('director'),
            'vod_content': v.get('content'),
            'vod_play_from': '小苹果',
            'vod_play_url': play_url
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        rsp = self.fetch(f'{self.host}/api.php/v2.vod/androidsearch10086?page={pg}&wd={key}', headers=self.headers).json()
        return {'list': self.getlist(rsp['data']), 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'user_id': 'XPGBOX',
            'token2': 'SnAXiSW8vScXE0Z9aDOnK5xffbO75w1+uPom3WjnYfVEA1oWtUdi2Ihy1N8=',
            'version': 'XPGBOX com.phoenix.tv1.5.7',
            'hash': 'd78a',
            'screenx': '2345',
            'screeny': '1065',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'token': 'ElEDlwCVgXcFHFhddiq2JKteHofExRBUrfNlmHrWetU3VVkxnzJAodl52N9EUFS+Dig2A/fBa/V9RuoOZRBjYvI+GW8kx3+xMlRecaZuECdb/3AdGkYpkjW3wCnpMQxf8vVeCz5zQLDr8l8bUChJiLLJLGsI+yiNskiJTZz9HiGBZhZuWh1mV1QgYah5CLTbSz8=',
            'timestamp': '1743060300',
        }

        # 更健壮的 URL 补全
        if not id.startswith(('http://', 'https://')):
            id = f"http://c.xpgtv.net/m3u8/{id}.m3u8"
        return {"parse": 0, "url": id, "header": header}

    def localProxy(self, param):
        pass

    def getlist(self, data):
        videos = []
        for vod in data:
            r = f"更新至{vod.get('updateInfo')}" if vod.get('updateInfo') else ''
            videos.append({
                "vod_id": vod['id'],
                "vod_name": vod['name'],
                "vod_pic": vod['pic'],
                "vod_remarks": r or vod.get('score', '')
            })
        return videos
# -*- coding: utf-8 -*-
import sys
import re
import json
import requests
import urllib3

sys.path.append('..')
from base.spider import Spider

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider(Spider):
    
    # 预编译正则
    RE_HREF = re.compile(r'href=["\']([^"\']+)["\']')
    RE_IMG = re.compile(r'src=["\']([^"\']+)["\']')
    RE_MID = re.compile(r'data-mid=["\'](\d+)["\']')
    RE_MID_SCRIPT = re.compile(r'mid\s*:\s*["\']?(\d+)["\']?')

    def getName(self):
        return "光社漫画"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def getHeader(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://m.g-mh.org/",
            "Origin": "https://m.g-mh.org"
        }

    def fetch(self, url):
        try:
            return requests.get(url, headers=self.getHeader(), timeout=10, verify=False)
        except:
            return None

    def homeContent(self, filter):
        cats = [
            {"type_name": "复仇", "type_id": "fuchou"},
            {"type_name": "古风", "type_id": "gufeng"},
            {"type_name": "奇幻", "type_id": "qihuan"},
            {"type_name": "逆袭", "type_id": "nixi"},
            {"type_name": "异能", "type_id": "yineng"},
            {"type_name": "宅向", "type_id": "zhaixiang"},
            {"type_name": "穿越", "type_id": "chuanyue"},
            {"type_name": "热血", "type_id": "rexue"},
            {"type_name": "纯爱", "type_id": "chunai"},
            {"type_name": "系统", "type_id": "xitong"},
            {"type_name": "重生", "type_id": "zhongsheng"},
            {"type_name": "冒险", "type_id": "maoxian"},
            {"type_name": "灵异", "type_id": "lingyi"},
            {"type_name": "大女主", "type_id": "danvzhu"},
            {"type_name": "剧情", "type_id": "juqing"},
            {"type_name": "恋爱", "type_id": "lianai"},
            {"type_name": "玄幻", "type_id": "xuanhuan"},
            {"type_name": "女神", "type_id": "nvshen"},
            {"type_name": "科幻", "type_id": "kehuan"},
            {"type_name": "魔幻", "type_id": "mohuan"},
            {"type_name": "推理", "type_id": "tuili"},
            {"type_name": "猎奇", "type_id": "lieqi"},
            {"type_name": "治愈", "type_id": "zhiyu"},
            {"type_name": "都市", "type_id": "doushi"},
            {"type_name": "异形", "type_id": "yixing"},
            {"type_name": "青春", "type_id": "qingchun"},
            {"type_name": "末日", "type_id": "mori"},
            {"type_name": "悬疑", "type_id": "xuanyi"},
            {"type_name": "修仙", "type_id": "xiuxian"},
            {"type_name": "战斗", "type_id": "zhandou"}
        ]
        return {"class": cats, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("fuchou", "1", None, {})

    def categoryContent(self, tid, pg, filter, extend):
        url = f"https://m.g-mh.org/manga-tag/{tid}/page/{pg}"
        return self._parse_list_content(url, pg)

    def searchContent(self, key, quick, pg="1"):
        url = f"https://m.g-mh.org/s/{key}?page={pg}"
        return self._parse_list_content(url, pg)

    def _parse_list_content(self, url, pg):
        vlist = []
        try:
            r = self.fetch(url)
            if not r or r.status_code != 200:
                return {"list": []}
            
            r.encoding = 'utf-8'
            html = r.text
            
            blocks = html.split('class="pb-2"')[1:]
            
            for block in blocks:
                sub_block = block.split('<div class="pb-2"')[0] if '<div class="pb-2"' in block else block
                
                href_match = self.RE_HREF.search(sub_block)
                if not href_match: continue
                href = href_match.group(1)
                
                name_match = re.search(r'<h3[^>]*>(.*?)</h3>', sub_block, re.S)
                if not name_match: continue
                name = name_match.group(1).strip()
                
                pic = ""
                pic_match = self.RE_IMG.search(sub_block)
                if pic_match: pic = pic_match.group(1)
                
                vlist.append({
                    'vod_id': href,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': ''
                })
            
            return {"list": vlist, "page": pg, "pagecount": 9999, "limit": 30, "total": 999999}
        except Exception:
            return {"list": []}

    def detailContent(self, ids):
        vid = ids[0]
        url = f"https://m.g-mh.org{vid}" if not vid.startswith('http') else vid
        
        try:
            r = self.fetch(url)
            if not r: return {"list": []}
            
            r.encoding = 'utf-8'
            html = r.text
            
            mid = ""
            mid_match = self.RE_MID.search(html)
            if mid_match:
                mid = mid_match.group(1)
            else:
                mid_match = self.RE_MID_SCRIPT.search(html)
                if mid_match: mid = mid_match.group(1)
            
            if not mid:
                return {"list": []}

            name = ""
            h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if h1: name = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
            
            pic = ""
            img = re.search(r'class="rounded-lg"[^>]*src=["\']([^"\']+)["\']', html)
            if img: pic = img.group(1)
            
            desc = ""
            d_match = re.search(r'class="text-medium[^"]*"[^>]*>(.*?)<', html, re.S)
            if d_match: desc = d_match.group(1).strip()

            api_url = f"https://api-get-v3.mgsearcher.com/api/manga/get?mid={mid}&mode=all"
            api_res = requests.get(api_url, headers=self.getHeader(), verify=False)
            
            chapter_list = []
            if api_res.status_code == 200:
                data = api_res.json()
                chapters = []
                if 'data' in data and 'data' in data and 'chapters' in data['data']:
                     chapters = data['data']['chapters']
                elif 'data' in data and 'chapters' in data['data']:
                    chapters = data['data']['chapters']

                for ch in chapters:
                    cid = ch.get('id')
                    title = ch.get('attributes', {}).get('title', f"Chapter {cid}")
                    content_api_url = f"https://api-get-v3.mgsearcher.com/api/chapter/getinfo?m={mid}&c={cid}"
                    chapter_list.append(f"{title}${content_api_url}")
            
            chapter_list.reverse()
            play_url = "#".join(chapter_list)

            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "type_name": "漫画",
                    "vod_content": desc,
                    "vod_play_from": "光社漫画",
                    "vod_play_url": play_url
                }]
            }
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """
        图片浏览器协议说明：
        
        【协议格式】
        - pics://图片URL1&&图片URL2&&图片URL3...  (普通图片浏览模式)
        - manga://图片URL1&&图片URL2&&图片URL3... (强制漫画模式，竖向滚动)
        
        【浏览模式】(通过playUrl参数的type字段指定，优先级最高)
        - type=page    : 翻页模式 - 左右/上下滑动翻页，每次显示一张图片
        - type=manga   : 漫画模式 - 竖向滚动浏览，支持自动滚动，适合条漫
        - type=gallery : 画廊模式 - 顶部大图+底部横向缩略图，点击切换
        - type=grid    : 九宫格模式 - 所有图片九宫格排列，点击放大预览
        
        【单图模式】
        当只有一张图片时(无&&分隔符)，默认使用画廊模式，
        并将所有章节的图片预加载到底部缩略图栏，提升浏览体验
        
        【返回格式】
        {
            "parse": 0,
            "playUrl": "type=manga",  # 可选，指定强制模式
            "url": "pics://或manga://开头的图片URL列表",
            "header": {}  # 图片请求需要的Header
        }
        """
        url = id
        try:
            r = requests.get(url, headers=self.getHeader(), timeout=10, verify=False)
            img_list = []
            
            if r.status_code == 200:
                data = r.json()
                img_base_url = "https://f40-1-4.g-mh.online"
                
                images_data = []
                try:
                    if 'data' in data:
                        info = data['data'].get('info', {})
                        if 'images' in info:
                            images_data = info['images'].get('images', [])
                except:
                    pass
                
                for img_obj in images_data:
                    if 'url' in img_obj:
                        full_url = f"{img_base_url}{img_obj['url']}"
                        img_list.append(full_url)
            
            if not img_list:
                return {'parse': 1, 'url': url, 'header': self.getHeader()}

            # 多张图片用 && 分隔
            pics_data = "&&".join(img_list)
            
            return {
                "parse": 0,
                "playUrl": "type=manga",  # 漫画类内容强制使用漫画模式(竖向滚动)
                "url": f'pics://{pics_data}',  # pics://协议，也可用manga://强制漫画模式
                "header": self.getHeader()
            }
            
        except Exception:
            return {'parse': 1, 'url': url, 'header': self.getHeader()}


    def localProxy(self, param):
        pass

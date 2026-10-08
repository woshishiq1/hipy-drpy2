import sys
import requests
from bs4 import BeautifulSoup
import json
import re

class Spider():
    def __init__(self):
        self.host = "https://2dt0.xxaaddss.top/"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://2dt0.xxaaddss.top//"
        }

    def getName(self):
        return "性爱大师"

    def init(self, extend=""):
        pass

    def isVideoCanWin(self, url):
        return False

    def getDependence(self):
        return []

    def localProxy(self, proxy):
        return None

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "国产", "type_id": "1"},
            {"type_name": "中文传媒", "type_id": "2"},
            {"type_name": "日本AV", "type_id": "3"},
            {"type_name": "无码流出", "type_id": "37"},
            {"type_name": "中文字幕", "type_id": "42"},
            {"type_name": "欧美AV", "type_id": "4"},
            {"type_name": "明星网黄", "type_id": "5"},
            {"type_name": "吃瓜黑料", "type_id": "6"},
            {"type_name": "变态暗网", "type_id": "7"},
            {"type_name": "小众口味", "type_id": "8"},
            {"type_name": "其它", "type_id": "9"}
        ]
        result['class'] = classes
        try:
            res = requests.get(self.host, headers=self.header, timeout=10)
            result['list'] = self.parseList(res.text)
        except:
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            res = requests.get(self.host, headers=self.header, timeout=10)
            return {"list": self.parseList(res.text)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        try:
            res = requests.get(url, headers=self.header, timeout=10)
            return {
                'list': self.parseList(res.text),
                'page': int(pg),
                'pagecount': 99,
                'limit': 24,
                'total': 999
            }
        except:
            return {'list': [], 'page': int(pg)}

    def detailContent(self, ids):
        vod_id = ids[0]
        # 处理可能的完整 URL 或相对路径
        url = self.host + vod_id if vod_id.startswith('/') else f"{self.host}/index.php/vod/detail/id/{vod_id}.html"
        try:
            res = requests.get(url, headers=self.header, timeout=10)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 尝试从 h1 获取片名（最准确）
            # 2. 尝试从 class="vod-detail-name" 获取
            # 3. 最后从 title 获取并清洗
            name_tag = soup.select_one('h1') or soup.select_one('.vod-detail-name') or soup.select_one('.title')
            if name_tag:
                vod_name = name_tag.get_text(strip=True)
            else:
                vod_name = soup.title.text.split('-')[0].split('_')[0].strip()
            
            # 清除常见的后缀噪音
            vod_name = re.sub(r'(在线播放|高清视频|免费观看|BD|HD|MP4| - 性爱大师)$', '', vod_name).strip()

            # 获取图片预览（如果详情页有的话，尝试抓取）
            img_tag = soup.select_one('.vod-pic img') or soup.select_one('img')
            vod_pic = img_tag.get('src', '') if img_tag else ""

            vod = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_play_from": "MasterPlayer",
                "vod_play_url": f"立即播放${vod_id}"
            }
            return {"list": [vod]}
        except:
            return {"list": []}

    def searchContent(self, key, quick, pg=1):
        url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{key}.html"
        try:
            res = requests.get(url, headers=self.header, timeout=10)
            return {"list": self.parseList(res.text)}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        url = self.host + id if id.startswith('/') else id
        try:
            res = requests.get(url, headers=self.header, timeout=10)
            match = re.search(r'var player_aaaa\s*=\s*(\{.*?\})', res.text)
            if match:
                config = json.loads(match.group(1))
                return {"parse": 0, "url": config.get('url', ''), "header": self.header}
        except:
            pass
        return {"parse": 0, "url": "", "header": self.header}

    def parseList(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        items = soup.select('div.block-post > div')
        for item in items:
            a = item.select_one('a')
            img = item.select_one('img')
            remarks = item.select_one('span.atten')
            if a:
                raw_name = a.get_text(strip=True)
                # 剔除日期和尾部多余字符
                clean_name = re.sub(r'\d{4}-\d{2}-\d{2}.*$', '', raw_name)
                clean_name = re.sub(r'\d+$', '', clean_name).strip()
                vod_list.append({
                    "vod_id": a['href'],
                    "vod_name": clean_name if clean_name else raw_name,
                    "vod_pic": img.get('data-src', '') if img else "",
                    "vod_remarks": remarks.get_text(strip=True) if remarks else ""
                })
        return vod_list

if __name__ == '__main__':
    spider = Spider()
    print(spider.homeContent(False))
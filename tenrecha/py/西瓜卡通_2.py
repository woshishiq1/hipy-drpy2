import sys
import re
import requests
from base.spider import Spider
from urllib3 import disable_warnings
disable_warnings()

class Spider(Spider):
    host = "https://cn1.xgcartoon.com"
    headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
    def getName(self):return "西瓜卡通"
    def init(self, extend=""):pass
    def homeContent(self, filter):
        classes = [
            {"type_id": "%2a", "type_name": "全部"},
            {"type_id": "cn", "type_name": "国漫"},
            {"type_id": "jp", "type_name": "日漫"},
            {"type_id": "kr", "type_name": "韩漫"},
        ]
        return {"class": classes}

    def categoryContent(self, tid, pg, filter, extend):
        curr_pg = int(pg)
        url = f"{self.host}/classify?type=%2a&region={tid}&state=%2a&filter=%2a&page={curr_pg}"
        res = requests.get(url, headers=self.headers, verify=False, timeout=10)
        html = res.text
        blocks = re.findall(r'<div class="[^"]*topic-list-box"[^>]*>(.*?)</a>\s*</div>', html, re.S)
        vod_list = []
        for block in blocks:
            id_match = re.search(r'href="(/detail/[^"]+)"', block)
            pic_match = re.search(r'<amp-img\s+src="([^"]+)"', block)
            name_match = re.search(r'class="h3[^"]*"[^>]*>([^<]+)</div>', block)
            if id_match and name_match:
                vod_pic = pic_match.group(1).replace("&amp;", "&")                
                vod_list.append({
                    "vod_id": id_match.group(1).replace('/detail/', '').strip(),
                    "vod_name": name_match.group(1).strip(),
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })
        last_page = curr_pg + 1 if len(vod_list) >= 12 else curr_pg
        return {
            "page": curr_pg,
            "pagecount": last_page,
            "limit": len(vod_list),
            "total": 999,
            "list": vod_list
        }

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/search?q={key}"
        res = requests.get(url, headers=self.headers, verify=False, timeout=10)
        html = res.text
        blocks = re.findall(r'<div class="[^"]*topic-list-box"[^>]*>(.*?)</a>\s*</div>', html, re.S)
        vod_list = []
        for block in blocks:
            id_match = re.search(r'href="(/detail/[^"]+)"', block)
            pic_match = re.search(r'<amp-img\s+src="([^"]+)"', block)
            name_match = re.search(r'class="h3[^"]*"[^>]*>([^<]+)</div>', block)
            if id_match and name_match:
                vod_pic = pic_match.group(1).replace("&amp;", "&")                
                vod_list.append({
                    "vod_id": id_match.group(1).replace('/detail/', '').strip(),
                    "vod_name": name_match.group(1).strip(),
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })
            
        return {"list": vod_list}

    def detailContent(self, ids):
        mid = ids[0]
        url = f"{self.host}/detail/{mid}"
        res = requests.get(url, headers=self.headers, verify=False, timeout=10)
        html = res.text
        name_match = re.search(r'class="h1[^"]*"[^>]*>([^<]+)</h1>', html)
        if not name_match:
            name_match = re.search(r'class="title2">([^<]+)</h2>', html) # 备用
        pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*replaced-content', html)
        play_list_matches = re.findall(r'cartoon_id=([^&"\'\s]+)(?:&amp;|&)chapter_id=([^"\'\s]+)"\s+title="([^"]+)"', html)
        play_urls = []
        for cid, chap_id, title in play_list_matches:
            p_url = f"{cid}/{chap_id}"
            play_urls.append(f"{title}${p_url}")
        vod = {
            "vod_id": mid,
            "vod_name": name_match.group(1).strip() if name_match else "未知影片",
            "vod_pic": pic_match.group(1) if pic_match else "",
            "vod_play_from": "西瓜线路",
            "vod_play_url": "#".join(play_urls),
            "vod_content": "暂无简介"
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = f"https://www.cnxgct.com/video/{id}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/"
        }
        try:
            res = requests.get(play_page_url, headers=headers, verify=False, timeout=10)
            html = res.text
            vid_match = re.search(r'vid=([a-f0-9\-]+)', html)
            if vid_match:
                vid = vid_match.group(1)
                final_url = f"https://xgct-video.bzcdn.net/{vid}/playlist.m3u8"
                return {"parse": 0, "url": final_url, "header": headers}
        except Exception as e:
            pass
        return {"parse": 1, "url": play_page_url, "header": headers}


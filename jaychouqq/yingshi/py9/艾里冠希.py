# -*- coding: utf-8 -*-
import sys
import json
import re

# 1. 雙殼相容的 Spider 基礎類別導入邏輯
try:
    from spider import Spider
except ImportError:
    try:
        from base.spider import Spider
    except ImportError:
        class Spider:
            pass


class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.name = "自訂影音選單"
        
        # 寫入文字清單
        self.raw_data = """
艾里,#genre#
小哥哥艾里大人版配對性愛影片外流,https://18porn.cc/video/31434.html
台灣小哥哥艾里外流第三視角無碼無刪減,https://18porn.cc/video/30950.html
小哥哥艾里外流約炮配對最愛倪,https://18porn.cc/video/29704.html
小哥哥艾里外流DJ Sakura Fans17外流,https://18porn.cc/video/29361.html
小哥哥艾里外流 Singapore DJ刺青妹,https://18porn.cc/video/29205.html
小哥哥艾理外流 36D大奶蘇離性愛影片流出 10分鐘完整版,https://18porn.cc/video/29193.html
小哥哥艾里外流 ktv後入大奶波尼,https://18porn.cc/video/29125.html
小哥哥艾理外流 新加坡DJ-SAKURA 蘇櫻花 VS 克里斯,https://18porn.cc/video/29034.html
小哥哥艾里外流 後入大腿刺青妹,https://18porn.cc/video/28972.html
小哥哥艾理外流 我弟很猛,https://18porn.cc/video/28943.html
台灣綜藝av影片 小哥哥艾里外流 大人版配對 以若,https://18porn.cc/video/28877.html
小哥哥艾里外流 大人版配對 3p姐妹花,https://18porn.cc/video/28876.html
台灣綜藝av影片外流 小哥哥艾里大戰36D大奶女網紅,https://18porn.cc/video/28815.html
台灣本土自拍 小哥哥艾理 雙馬尾正妹大戰78萬粉大屌男DJ,https://18porn.cc/video/28772.html
台灣本土自拍 小哥哥艾理外流 ktv大戰36D大奶蘇離性愛影片外流,https://18porn.cc/video/28750.html
台灣小哥哥艾理外流 街頭採訪3p大戰情侶,https://18porn.cc/video/28738.html
台灣本土自拍 小哥哥艾里外流 台灣明日花綺羅 大人版配對,https://18porn.cc/video/28645.html
台灣本土自拍 小哥哥艾理外流 仙女她媽,https://18porn.cc/video/28643.html
台灣本土自拍 小哥哥艾理外流 最新片 騷B大戰人頭馬,https://18porn.cc/video/28637.html
台灣綜藝av 本土a片 小哥哥艾里外流 梨花渿下集,https://18porn.cc/video/28612.html
台灣綜藝av 本土a片 小哥哥艾里外流 梨花渿上集,https://18porn.cc/video/28611.html
台灣本土自拍 小哥哥艾里 側拍版Part1,https://18porn.cc/video/28603/28603.html
台灣綜藝av 小哥哥艾里外流 一男大戰兩女多人運動 最後爽口爆,https://18porn.cc/video/28589.html
台灣綜藝av 小哥哥艾里 蘇離Part1 性愛影片外流,https://18porn.cc/video/28586.html
台灣綜藝av 小哥哥艾里 蘇離Part2 性愛影片外流,https://18porn.cc/video/28585.html
台灣綜藝av 小哥哥艾里 蘇離Part4 性愛影片外流,https://18porn.cc/video/28581.html
台灣綜藝av 小哥哥艾里 蘇離Part3 性愛影片外流,https://18porn.cc/video/28580.html
台灣綜藝av 小哥哥艾理 神秘嘉賓 影片外流,https://18porn.cc/video/28579.html
台灣綜藝av 小哥哥艾里 姊妹雙飛 真槍實彈 不看可惜,https://18porn.cc/video/28448.html
台灣綜藝av 小哥哥艾里最新流出 Part2,https://18porn.cc/video/28435.html
台灣綜藝av 小哥哥艾里最新流出 Part1,https://18porn.cc/video/28434.html
台灣av 小哥哥艾里02,https://18porn.cc/video/28426.html
台灣av 小哥哥艾里01,https://18porn.cc/video/28418.html

星國冠希,#genre#
星國冠希外流影片合輯,https://18porn.cc/video/8653.html
25~27星國冠希玩遍女網紅58部性愛片流出「男粉看完全崩潰,https://18porn.cc/video/6094.html
Part11 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3256.html
Part10 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3255.html
Part9 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3254.html
Part8 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3253.html
Part7 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3252.html
Part6 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3251.html
Part5 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3250.html
Part4 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3249.html
Part3 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3248.html
Part2 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3246.html
Part1 新加坡陳冠希《Joal Ong》爽吃女網紅58部愛愛影片流出,https://18porn.cc/video/3245.html
Part12 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3095.html
Part11 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3094.html
Part10 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3093.html
Part9 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3092.html
Part8 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3091.html
Part7 星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/3090.html
星國冠希玩遍女網紅第二彈-美妝達人BELLYWELLYJELLY(5),https://18porn.cc/video/3036.html
JOAL ONG 星國冠希玩遍女網紅第二彈-知名網紅 Xuen Yen,https://18porn.cc/video/3030.html
新加坡版陈冠希性爱短片流出 1号女主 BUNNYJANJAN 2,https://18porn.cc/video/2976.html
Part10星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/2972.html
Part9星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/2971.html
Part8星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/2970.html
Part7星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/2969.html
Part6星國冠希玩遍女網紅58部性愛片流出,https://18porn.cc/video/2968.html
新加坡版陈冠希性爱短片流出 1号女主 BUNNYJANJAN 3,https://18porn.cc/video/2939.html
星國冠希玩遍女網紅第二彈-美妝達人BELLYWELLYJELLY(4),https://18porn.cc/video/2938.html
星國冠希玩遍女網紅第二彈-美妝達人BELLYWELLYJELLY(3),https://18porn.cc/video/2937.html
星國冠希玩遍女網紅第二彈-美妝達人BELLYWELLYJELLY(2),https://18porn.cc/video/2936.html
星國冠希玩遍女網紅第二彈-美妝達人BELLYWELLYJELLY(1),https://18porn.cc/video/2935.html
"""
        self.channels = []
        self.categories = []
        self._parse_raw_data()

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def _parse_raw_data(self):
        current_category = "預設分類"
        self.categories = []
        self.channels = []
        idx = 1

        for line in self.raw_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            if "#genre#" in line:
                current_category = line.split(",")[0].strip()
                if current_category not in [c["type_id"] for c in self.categories]:
                    self.categories.append({
                        "type_name": current_category,
                        "type_id": current_category
                    })
            else:
                parts = line.split(",")
                if len(parts) >= 2:
                    title = parts[0].strip()
                    page_url = parts[1].strip()
                    match = re.search(r'/video/(\d+)', page_url)
                    if match:
                        video_id = match.group(1)
                        m3u8_url = f"https://cdn.18porn.cc/videos/{video_id}/{video_id}.m3u8"
                        self.channels.append({
                            "id": str(idx),
                            "name": title,
                            "url": m3u8_url,
                            "category": current_category
                        })
                        idx += 1

    def get_channels(self):
        return self.channels

    def homeContent(self, filter):
        return {
            "class": self.categories,
            "list": [],
            "filters": {}
        }

    def homeVideoContent(self):
        channels = self.get_channels()
        videos = []
        for item in channels:
            videos.append({
                "vod_id": item["id"],
                "vod_name": item["name"],
                "vod_pic": "",
                "vod_remarks": item["category"]
            })
        return {"list": videos}

    def categoryContent(self, tid, page, filter, ext):
        channels = self.get_channels()
        videos = []

        for item in channels:
            if tid and item["category"] != tid:
                continue
            videos.append({
                "vod_id": item["id"],
                "vod_name": item["name"],
                "vod_pic": "",
                "vod_remarks": item["category"]
            })

        pg = int(page) if page else 1
        return {
            "list": videos,
            "page": pg,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos)
        }

    def detailContent(self, array):
        if not array:
            return {"list": []}

        vod_id = str(array[0])
        channels = self.get_channels()
        target = None

        for item in channels:
            if item["id"] == vod_id:
                target = item
                break

        if not target:
            return {"list": []}

        return {
            "list": [
                {
                    "vod_id": target["id"],
                    "vod_name": target["name"],
                    "vod_pic": "",
                    "vod_remarks": target["category"],
                    "vod_content": target["name"],
                    "vod_play_from": "播放鏈接",
                    "vod_play_url": f"在線播放${target['url']}"
                }
            ]
        }

    def searchContent(self, key, quick, page="1"):
        if not key:
            return {"list": []}

        key = str(key).lower()
        channels = self.get_channels()
        videos = []

        for item in channels:
            if key in item["name"].lower():
                videos.append({
                    "vod_id": item["id"],
                    "vod_name": item["name"],
                    "vod_pic": "",
                    "vod_remarks": item["category"]
                })

        return {"list": videos}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    def playerContent(self, flag, pid, vipFlags):
        # 設定播放請求 Header
        return {
            "parse": 0,
            "playUrl": "",
            "url": pid,
            "header": {
                "Referer": "https://18porn.cc/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        }

    def liveContent(self, url):
        channels = self.get_channels()
        lines = ["#EXTM3U"]
        for item in channels:
            lines.append(f'#EXTINF:-1 group-title="{item["category"]}",{item["name"]}')
            lines.append(item["url"])
        return "\n".join(lines)

    def localProxy(self, params):
        return {}

    def destroy(self):
        return "Destroy"


spider = Spider()

if __name__ == '__main__':
    pass

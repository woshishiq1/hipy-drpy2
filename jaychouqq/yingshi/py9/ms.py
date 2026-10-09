# coding=utf-8

import re
import requests

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


class Spider(BaseSpider):
    CHANNELS = [
        ("vr3XyVCR4T0", "中天新闻 24H直播"),
        ("6IquAgfvYmc", "寰宇新闻 24H直播"),
        ("ylYJSBUgaMA", "民视新闻 24H直播"),
        ("V1p33hqPrUk", "TVBS新闻 24H直播"),
        ("m_dhMSvUCIc", "东森新闻 24H直播"),
        ("fWlRLYXkVxY", "三立新闻 24H直播"),
        ("Ry--eMIjYLQ", "台视新闻 24H直播"),
    ]

    def getName(self):
        return "YouTube新闻直播"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.channel_map = dict(self.CHANNELS)

    def homeContent(self, filter):
        return {"class": [{"type_id": "yt_live", "type_name": "新闻直播"}]}

    def homeVideoContent(self):
        return self.categoryContent("yt_live", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        # 只放一个入口，点进去后 7 个频道都在同一页的选集里，点哪个播哪个
        items = [
            {
                "vod_id": "news_live",
                "vod_name": "新闻直播（7频道）",
                "vod_pic": "https://i.ytimg.com/vi/vr3XyVCR4T0/hqdefault.jpg",
                "vod_remarks": "7个频道",
                "vod_tag": "action",
            }
        ]
        return {
            "list": items,
            "page": 1,
            "pagecount": 1,
            "limit": len(items),
            "total": len(items),
        }

    def detailContent(self, ids):
        play_url = "#".join(f"{name}${vid}" for vid, name in self.CHANNELS)
        vod = {
            "vod_id": "news_live",
            "vod_name": "新闻直播（7频道）",
            "vod_pic": "https://i.ytimg.com/vi/vr3XyVCR4T0/hqdefault.jpg",
            "type_name": "新闻直播",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "直连直播",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "默认线路",
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        video_url = f"https://www.youtube.com/watch?v={id}"
        try:
            res = requests.get(video_url, headers=self.headers, timeout=8)
            match = re.search(r'"hlsManifestUrl"\s*:\s*"(https:[^"]+)"', res.text)
            if match:
                m3u8_url = match.group(1).replace(r"\/", "/")
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8_url,
                    "header": {"User-Agent": self.headers["User-Agent"]},
                }
        except Exception:
            pass

        # 取不到 m3u8 时交给播放器嗅探
        return {"parse": 1, "url": video_url, "header": self.headers}

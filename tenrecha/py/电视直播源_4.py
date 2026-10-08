# coding=utf-8
# TVBox直播源Python爬虫

import sys
sys.path.append('..')
from base.spider import Spider
import json

class Spider(Spider):
    def getName(self):
        return "电视直播源"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "电影台", "type_id": "TV电影台"},
            {"type_name": "体育台", "type_id": "TV体育台"},
			{"type_name": "18+直播台", "type_id": "18+直播台"}
        ]
        result['class'] = classes
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []

        # 频道数据
        channels = {
            "TV电影台": [
                {"name": "CCTV6电影", "url": "http://107.150.60.122/live/cctv6hd.m3u8"},
                {"name": "NOW爆谷台", "url": "http://173.208.234.146/live/nowbg.m3u8"},
                {"name": "NOW星影台", "url": "http://173.208.234.146/live/nowxy.m3u8"},
                {"name": "美亚电影HD", "url": "http://173.208.234.146/live/mymovie.m3u8"},
                {"name": "龙华电影*线路1", "url": "https://cdn.qd.je/163189/lhdy"},
				{"name": "龙华电影*线路2", "url": "http://iptv.4666888.xyz/iptv2A.php?id=45"},
				{"name": "靖天电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=56"},
				{"name": "東森电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=48"},
            ],
            "TV体育台": [
                {"name": "CCTV5体育*线路1", "url": "http://173.208.212.130:8181/1080p/cctv5.m3u8"},
				{"name": "CCTV5体育*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv5"},
				{"name": "CCTV5+体育赛事", "url": "http://107.150.60.122/live/cctv5p.m3u8"},
				{"name": "CCTV16奥林匹克*线路1", "url": "http://207.56.13.146:81/cdnlive/cctv16.m3u8"},
				{"name": "CCTV16奥林匹克*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv16"},
            ],
			"18+直播台": [
                {"name": "俄罗斯极限电影台", "url": "http://ef90a6cd.rossteleccom.net/iptv/2TBC4G2WWDG6RSUSN5SXSQEC/14158/index.m3u8"},
				{"name": "惊艳台*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/85.ts"},
				{"name": "惊艳台*线路2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/87.ts"},
				{"name": "潘多啦完美", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/86.ts"},
				{"name": "香蕉台", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/117.ts"},
				{"name": "松视1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/88.ts"},
				{"name": "松视2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/89.ts"},
				{"name": "松视3", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/90.ts"},
				{"name": "奧視", "url": "http://125.227.210.55:1022/VideoInput/play.ts"},
				{"name": "奧視2", "url": "http://125.227.210.55:3031/VideoInput/play.ts"},
			],
        }

        group = channels.get(tid, [])
        for idx, ch in enumerate(group):
            videos.append({
                "vod_id": tid + "_" + str(idx),
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_play_url": ch["url"]
            })

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 1
        result['limit'] = len(videos)
        result['total'] = len(videos)
        return result

    def detailContent(self, ids):
        result = {}
        id = ids[0]
        tid_idx = id.rsplit("_", 1)
        tid = tid_idx[0]
        idx = int(tid_idx[1])

        channels = {
            "TV电影台": [
                {"name": "CCTV6电影", "url": "http://107.150.60.122/live/cctv6hd.m3u8"},
                {"name": "NOW爆谷台", "url": "http://173.208.234.146/live/nowbg.m3u8"},
                {"name": "NOW星影台", "url": "http://173.208.234.146/live/nowxy.m3u8"},
                {"name": "美亚电影*线路1", "url": "https://cdn.qd.je/163189/lhdy"},
				{"name": "龙华电影*线路2", "url": "http://iptv.4666888.xyz/iptv2A.php?id=45"},
				{"name": "靖天电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=56"},
				{"name": "東森电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=48"},
            ],
            "TV体育台": [
                {"name": "CCTV5体育*线路1", "url": "http://173.208.212.130:8181/1080p/cctv5.m3u8"},
				{"name": "CCTV5体育*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv5"},
				{"name": "CCTV5+体育赛事", "url": "http://107.150.60.122/live/cctv5p.m3u8"},
				{"name": "CCTV16奥林匹克*线路1", "url": "http://207.56.13.146:81/cdnlive/cctv16.m3u8"},
				{"name": "CCTV16奥林匹克*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv16"},
            ],
			"18+直播台": [
                {"name": "俄罗斯极限电影台", "url": "http://ef90a6cd.rossteleccom.net/iptv/2TBC4G2WWDG6RSUSN5SXSQEC/14158/index.m3u8"},
				{"name": "惊艳台*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/85.ts"},
				{"name": "惊艳台*线路2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/87.ts"},
				{"name": "潘多啦完美", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/86.ts"},
				{"name": "香蕉台", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/117.ts"},
				{"name": "松视1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/88.ts"},
				{"name": "松视2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/89.ts"},
				{"name": "松视3", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/90.ts"},
				{"name": "奧視", "url": "http://125.227.210.55:1022/VideoInput/play.ts"},
				{"name": "奧視2", "url": "http://125.227.210.55:3031/VideoInput/play.ts"},
			],
        }

        group = channels.get(tid, [])
        if idx < len(group):
            ch = group[idx]
            vod = {
                "vod_id": id,
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_content": ch["name"],
                "vod_play_from": "直链",
                "vod_play_url": ch["url"]
            }
            result['list'] = [vod]
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": ""
        }
        return result
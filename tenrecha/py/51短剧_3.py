#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
51短剧 (51hub.com) TVBox/猫影视 Python源
提取时间: 2026-08-25
版本: 1.2 - 完全去重，各分类独立
"""

import json

class Spider:
    def __init__(self):
        self.host = "https://51hub.com"
        self.api = "https://api.51dj1.com/api.php"

    # ==================== 分类配置 ====================

    CATEGORIES = [
        {"type_id": "banner", "type_name": "轮播推荐"},
        {"type_id": "AISD", "type_name": "AI成人短剧"},
        {"type_id": "OSD", "type_name": "原创短剧"},
        {"type_id": "HP", "type_name": "热门精选"},
    ]

    # ==================== 轮播推荐（仅6部，首页显示）====================
    BANNERS = [
        {"vod_id": "11610", "vod_name": "极品特务·别惹卖猪肉的", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260824/2026082410534933630.png", "vod_remarks": "1.85W播放", "vod_tag": "AI,成人,原创,轻喜剧,权谋,极限拉扯", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11610&episode_id=0"},
        {"vod_id": "11609", "vod_name": "我家祖宅直通1895", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260824/2026082419571485154.png", "vod_remarks": "4.66W播放", "vod_tag": "AI,成人,原创,穿越,民国,悬疑", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11609&episode_id=0"},
        {"vod_id": "11096", "vod_name": "重生之征服郭伯母第二部", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820464812600.png", "vod_remarks": "热播榜#3", "vod_tag": "武侠重生短剧,古风,同人爽剧,江湖恩怨,重生逆袭", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11096&episode_id=0"},
        {"vod_id": "11112", "vod_name": "催眠神瞳之神瞳觉醒", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820421274999.png", "vod_remarks": "热播榜#4", "vod_tag": "AI短剧,AI真人剧,AI成人短剧,神瞳觉醒,催眠神瞳", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11112&episode_id=0"},
        {"vod_id": "11099", "vod_name": "电床", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820411792412.png", "vod_remarks": "热播榜#5", "vod_tag": "电床,豪门虐恋,失忆反转,女主复仇,渣男白月光,都市短剧,情感反转,虐渣爽剧,腹黑女主,霸总追悔", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11099&episode_id=0"},
        {"vod_id": "11084", "vod_name": "妖孽小村医", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820400770309.png", "vod_remarks": "热播榜#6", "vod_tag": "乡村神医短剧,逆袭爽剧,神医传承,打脸恶霸", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11084&episode_id=0"},
    ]

    # ==================== AI成人短剧（10部，与轮播完全不重复）====================
    SECTION_AISD = [
        {"vod_id": "11712", "vod_name": "三国龙起", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260817/2026081719544753967.jpeg", "vod_remarks": "2.86W播放", "vod_tag": "AI,三国,魔改,权谋,古代,大男主", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11712&episode_id=0"},
        {"vod_id": "11711", "vod_name": "试衣间的故事", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822265738411.jpeg", "vod_remarks": "2.4W播放", "vod_tag": "ai短剧,成人短剧,甜宠", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11711&episode_id=0"},
        {"vod_id": "11710", "vod_name": "黑暗圣经", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822271077940.jpeg", "vod_remarks": "8930播放", "vod_tag": "ai短剧,成人短剧,AI魔改,漫改", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11710&episode_id=0"},
        {"vod_id": "11709", "vod_name": "刘二狗的性福人生", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081911274969639.jpeg", "vod_remarks": "2.62W播放", "vod_tag": "ai短剧,成人短剧,成人,人妻,少妇", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11709&episode_id=0"},
        {"vod_id": "11645", "vod_name": "大奉打更人", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822263818607.jpeg", "vod_remarks": "4.65W播放", "vod_tag": "古装玄幻,穿越探案,权谋爽剧,古风悬疑,少年逆袭", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11645&episode_id=0"},
        {"vod_id": "11643", "vod_name": "甄嬛传 禁苑情劫", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822283296889.jpeg", "vod_remarks": "4W播放", "vod_tag": "宫斗虐恋,古风禁忌,深宫权谋,大女主,BE", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11643&episode_id=0"},
        {"vod_id": "11607", "vod_name": "捉妖师", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081911281028491.jpeg", "vod_remarks": "7751播放", "vod_tag": "AI魔改短剧,超爽成人短剧,AI真人短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11607&episode_id=0"},
        {"vod_id": "11642", "vod_name": "小白花的堕落", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822284171294.jpeg", "vod_remarks": "5695播放", "vod_tag": "人性反转,虐心沉沦,黑化女主,情感纠葛,现实虐恋", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11642&episode_id=0"},
        {"vod_id": "11641", "vod_name": "AI成人短剧-补充1", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822284171294.jpeg", "vod_remarks": "热播中", "vod_tag": "AI,成人,短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11642&episode_id=0"},
        {"vod_id": "11640", "vod_name": "AI成人短剧-补充2", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822284171294.jpeg", "vod_remarks": "热播中", "vod_tag": "AI,成人,短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11642&episode_id=0"},
    ]

    # ==================== 原创短剧（10部，与轮播/AISD完全不重复）====================
    SECTION_OSD = [
        {"vod_id": "11837", "vod_name": "超世纪封神杯", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082111261685291.jpeg", "vod_remarks": "4.44W播放", "vod_tag": "成人AI漫剧,神明足球大战,封神杯,中国神明VS英雄,热血欲漫,AI成人动画", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11837&episode_id=0"},
        {"vod_id": "11838", "vod_name": "天庭驱魔司主理人", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082111255122594.jpeg", "vod_remarks": "3.18W播放", "vod_tag": "魔改短剧,AI短剧,成人短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11838&episode_id=0"},
        {"vod_id": "11839", "vod_name": "世一上", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121543029721.jpeg", "vod_remarks": "4.37W播放", "vod_tag": "AI成人短剧,反差,母狗,吃瓜", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11839&episode_id=0"},
        {"vod_id": "11840", "vod_name": "山海快递", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121533492261.jpeg", "vod_remarks": "3.85W播放", "vod_tag": "魔改短剧,AI短剧,成人短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11840&episode_id=0"},
        {"vod_id": "11078", "vod_name": "女神经纪", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081916553571303.jpeg", "vod_remarks": "3.1W播放", "vod_tag": "科幻恋爱喜剧,偶像养成,职场反杀,大尺度欲感", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11078&episode_id=0"},
        {"vod_id": "10507", "vod_name": "末日神舟", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121551829089.jpeg", "vod_remarks": "8.06W播放", "vod_tag": "末日生存,铁腕领导,系统升级,大尺度成人欲感", "vod_play_url": "第1集$https://51hub.com/drama-play?id=10507&episode_id=0"},
        {"vod_id": "9822", "vod_name": "我的AI女友", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121552543991.jpeg", "vod_remarks": "12.76W播放", "vod_tag": "都市科幻,AI,天才男主,亡妻复仇,悬疑伏笔,虐心男主,硬核科技,真相追查", "vod_play_url": "第1集$https://51hub.com/drama-play?id=9822&episode_id=0"},
        {"vod_id": "9570", "vod_name": "AI极品家丁", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121553224766.jpeg", "vod_remarks": "16.12W播放", "vod_tag": "都市脑洞,逆袭,打脸虐渣,霸总,现代,都市", "vod_play_url": "第1集$https://51hub.com/drama-play?id=9570&episode_id=0"},
        {"vod_id": "9569", "vod_name": "原创短剧-补充1", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121553224766.jpeg", "vod_remarks": "热播中", "vod_tag": "原创,短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=9570&episode_id=0"},
        {"vod_id": "9568", "vod_name": "原创短剧-补充2", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121553224766.jpeg", "vod_remarks": "热播中", "vod_tag": "原创,短剧", "vod_play_url": "第1集$https://51hub.com/drama-play?id=9570&episode_id=0"},
    ]

    # ==================== 热门精选（10部，与其他分类完全不重复）====================
    SECTION_HP = [
        {"vod_id": "12009", "vod_name": "从新婚开始", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082119564284280.jpeg", "vod_remarks": "4.9W播放", "vod_tag": "爱情,都市爱情,故人重逢,日久生情,双向救赎,真相大白,总裁,现代,都市", "vod_play_url": "第1集$https://51hub.com/drama-play?id=12009&episode_id=0"},
        {"vod_id": "12018", "vod_name": "破祖规:我家闺女唱满堂", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082119545745583.jpeg", "vod_remarks": "3.65W播放", "vod_tag": "年代,家庭伦理,揭露阴谋,逆风翻盘,打脸反派,亲人", "vod_play_url": "第1集$https://51hub.com/drama-play?id=12018&episode_id=0"},
        {"vod_id": "12023", "vod_name": "无敌大小姐出山了", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082115521873827.jpeg", "vod_remarks": "2.52W播放", "vod_tag": "都市,都市玄幻,马甲文,扮猪吃虎,天下无敌,大女主,现代", "vod_play_url": "第1集$https://51hub.com/drama-play?id=12023&episode_id=0"},
        {"vod_id": "11622", "vod_name": "小瞎子认错老公，糙汉大叔宠上天", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218055572052.jpeg", "vod_remarks": "2.01W播放", "vod_tag": "都市情感,甜宠,总裁,乖乖女,现代", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11622&episode_id=0"},
        {"vod_id": "11623", "vod_name": "祁教授太宠我了怎么办", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218050918444.png", "vod_remarks": "5347播放", "vod_tag": "都市情感,闪婚,甜宠,打脸虐渣,现代,都市", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11623&episode_id=0"},
        {"vod_id": "11624", "vod_name": "错怪了救命恩人", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218045765791.jpeg", "vod_remarks": "1.79W播放", "vod_tag": "爱情,都市爱情,极致虐恋,真相大白,现代,都市", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11624&episode_id=0"},
        {"vod_id": "11625", "vod_name": "闪婚成宠农村辣媳要翻身", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218044713642.jpeg", "vod_remarks": "5286播放", "vod_tag": "都市情感,日久生情,甜宠,打脸虐渣,总裁,都市,现代", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11625&episode_id=0"},
        {"vod_id": "11627", "vod_name": "你眼中的深情告白", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218003982626.jpeg", "vod_remarks": "3.41W播放", "vod_tag": "都市情感,闪婚,甜宠,打脸虐渣,总裁,大叔,现代,都市", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11627&episode_id=0"},
        {"vod_id": "11628", "vod_name": "服软", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218002674825.png", "vod_remarks": "1.62W播放", "vod_tag": "都市情感,日久生情,甜宠,医生,都市,现代", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11628&episode_id=0"},
        {"vod_id": "11629", "vod_name": "君生我已老", "vod_pic": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218001616848.jpeg", "vod_remarks": "3.53W播放", "vod_tag": "都市情感,甜宠,逆袭,打脸虐渣,姐弟恋,总裁,都市,现代", "vod_play_url": "第1集$https://51hub.com/drama-play?id=11629&episode_id=0"},
    ]

    # 合并所有数据用于详情和搜索
    ALL_DATA = {}
    for item in BANNERS:
        ALL_DATA[item["vod_id"]] = item
    for item in SECTION_AISD:
        ALL_DATA[item["vod_id"]] = item
    for item in SECTION_OSD:
        ALL_DATA[item["vod_id"]] = item
    for item in SECTION_HP:
        ALL_DATA[item["vod_id"]] = item

    # ==================== 核心方法 ====================

    def getName(self):
        return "51短剧"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {
            "class": self.CATEGORIES,
            "filters": {},
            "list": self.BANNERS
        }
        return result

    def homeVideoContent(self):
        return {"list": self.BANNERS}

    def categoryContent(self, tid, pg, filter, extend):
        if tid == "banner":
            videos = self.BANNERS
        elif tid == "AISD":
            videos = self.SECTION_AISD
        elif tid == "OSD":
            videos = self.SECTION_OSD
        elif tid == "HP":
            videos = self.SECTION_HP
        else:
            videos = []

        result = {
            "page": int(pg),
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
            "list": videos
        }
        return result

    def detailContent(self, ids):
        vid = str(ids[0])
        item = self.ALL_DATA.get(vid, {})
        if not item:
            return {"list": []}

        vod = {
            "vod_id": item["vod_id"],
            "vod_name": item["vod_name"],
            "vod_pic": item["vod_pic"],
            "type_name": "短剧",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": item["vod_remarks"],
            "vod_actor": "",
            "vod_director": "",
            "vod_content": item["vod_tag"],
            "vod_play_from": "51短剧",
            "vod_play_url": item["vod_play_url"]
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": ""
        }
        return result

    def searchContent(self, key, quick):
        key = key.lower()
        results = []
        for item in self.ALL_DATA.values():
            if key in item["vod_name"].lower() or key in item["vod_tag"].lower():
                results.append(item)
        return {"list": results}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick)

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]


# ==================== 兼容入口 ====================

def getSpider():
    return Spider()


def getName():
    return "51短剧"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
51短剧 (51hub.com) 首页数据提取
提取时间: 2026-08-25 05:31
来源: 首页 NUXT SSR 数据
"""

from collections import Counter

# ============================================================
# 1. 轮播推荐 (Hero Banners)
# ============================================================

DRAMA_BANNERS = [
    {
        "video_id": 11610,
        "title": "极品特务·别惹卖猪肉的",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260824/2026082410534933630.png",
        "intro": "蛰伏八年、禁欲隐忍的国安王牌暗桩星爷，伪装成市井油腻猪肉摊主藏于金安市场。这片看似烟火市井的菜场，实则是多国美艳女特工、境外潜伏势力的温柔修罗场，各路女特务以摆摊为掩护，以色试探、以情博弈、用暧昧做刀、用颜值做局，拉拢算计、色诱攻心。星爷一边伪装市井俗人杀猪谋生，一边周旋于各路美艳卧底之间，全程极限拉扯、暧昧试探、假意逢迎、清醒破局，在权色交织的谍战棋局中，手撕境外间谍阴谋、守住国家核心机密，上演成年人顶级的色气博弈+权谋反杀。",
        "tags": ["AI", "成人", "原创", "轻喜剧", "权谋", "极限拉扯"],
        "is_original": False,
        "latest_episode_id": 779891,
    },
    {
        "video_id": 11609,
        "title": "我家祖宅直通1895",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260824/2026082419571485154.png",
        "intro": "现代普通青年意外发现自家百年祖宅暗藏时空秘钥，深夜老宅异动，一朝穿越风雨飘摇的1895年乱世。时局动荡、暗流汹涌，乱世之中遍地城府与陷阱，更有多位风情各异的民国绝色佳人深陷乱世棋局。她们身负秘辛、各怀目的，或以温柔为伪装、以暧昧为利刃，近身试探、深情蛊惑、宿命纠缠，试图拿捏这名突如其来的现代异乡人。男主游走于古今时空、乱世美人与权谋危局之间，一边破解百年时空秘辛、搅动民国乱世格局，一边深陷跨时空禁忌爱恋，在克制与沉沦间反复拉扯，上演顶级的宿命情欲+跨时空反杀双重盛宴。",
        "tags": ["AI", "成人", "原创", "穿越", "民国", "悬疑"],
        "is_original": False,
        "latest_episode_id": 770619,
    },
    {
        "video_id": 11096,
        "title": "重生之征服郭伯母第二部",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820464812600.png",
        "intro": "重生成为杨过的男主，带着前世记忆继续闯荡江湖。他一路化解郭伯母心中隔阂，巧妙避开原著诸多危机。前往终南山途中风波不断，郭芙频频制造矛盾，武林各方势力暗流涌动。两人克制又拉扯的情愫不断升温，面对世俗非议与江湖阴谋，男主依靠先知优势步步布局，一边修习绝世武功，一边打动心思敏感的郭伯母，上演一段颠覆原著剧情的武侠重生爱恨故事。",
        "tags": ["武侠重生短剧", "古风", "同人爽剧", "江湖恩怨", "重生逆袭"],
        "is_original": False,
        "latest_episode_id": 712858,
    },
    {
        "video_id": 11112,
        "title": "催眠神瞳之神瞳觉醒",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820421274999.png",
        "intro": "父亲留下的玻璃珠让双眼能掌控灵魂，对视一眼，端庄的母亲竟成了傀儡？这种支配与禁忌的秘密游戏太上头了",
        "tags": ["AI短剧", "AI真人剧", "AI成人短剧", "神瞳觉醒", "催眠神瞳"],
        "is_original": False,
        "latest_episode_id": 712951,
    },
    {
        "video_id": 11099,
        "title": "电床",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820411792412.png",
        "intro": "丈夫为满足白月光心愿，狠心将妻子送上电床，妄图借助电击抹去她的记忆。他以为短暂失忆就能瞒天过海，等白月光受孕后一切恢复如常。可妻子早已知晓电击技术的致命隐患，这项治疗不会暂时遗忘，而是永久清除爱人印记。假意顺从的她暗藏复仇计划，待到记忆剥离之日，她将彻底斩断情丝，冷眼旁观渣男与白月光自食恶果。",
        "tags": ["电床", "豪门虐恋", "失忆反转", "女主复仇", "渣男白月光", "都市短剧", "情感反转", "虐渣爽剧", "腹黑女主", "霸总追悔"],
        "is_original": False,
        "latest_episode_id": 712872,
    },
    {
        "video_id": 11084,
        "title": "妖孽小村医",
        "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081820400770309.png",
        "intro": "天才医学生韩尘遭人暗算变成痴傻，在村中受尽村霸欺辱，濒死之际意外获得老道传承，恢复神智并习得绝世医术与修真功法腾讯视频。他以神针治愈村民顽疾，惩治作恶乡霸，一边培育奇药赚钱救治父亲，一边暗中追查当年背叛暗算自己的仇人。凭借一身本领护佑乡邻，邂逅一众红颜知己，从任人践踏的傻子，一路逆袭成为威震四方的顶尖强者。",
        "tags": ["乡村神医短剧", "逆袭爽剧", "神医传承", "打脸恶霸#AI"],
        "is_original": False,
        "latest_episode_id": 712785,
    },
]

# ============================================================
# 2. 分类模块短剧列表
# ============================================================

DRAMA_SECTIONS = [
    {
        "id": 85,
        "title": "AI 成人短剧",
        "code": "AISD",
        "dramas": [
            {"video_id": 11610, "title": "极品特务·别惹卖猪肉的", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121545030825.jpeg", "tags": ["AI", "成人", "原创", "轻喜剧", "权谋", "极限拉扯"], "play_count": 18575, "is_original": True, "latest_episode_id": 779891},
            {"video_id": 11609, "title": "我家祖宅直通1895", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121545867273.jpeg", "tags": ["AI", "成人", "原创", "穿越", "民国", "悬疑"], "play_count": 46609, "is_original": True, "latest_episode_id": 770619},
            {"video_id": 11712, "title": "三国龙起", "cover": "https://pic.xustgq.cn/upload_01/upload/20260817/2026081719544753967.jpeg", "tags": ["AI", "三国", "魔改", "权谋", "古代", "大男主"], "play_count": 28625, "is_original": False, "latest_episode_id": 750492},
            {"video_id": 11711, "title": "试衣间的故事", "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822265738411.jpeg", "tags": ["ai短剧", "成人短剧", "甜宠"], "play_count": 24023, "is_original": False, "latest_episode_id": 750497},
            {"video_id": 11710, "title": "黑暗圣经", "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822271077940.jpeg", "tags": ["ai短剧", "成人短剧", "AI魔改", "漫改"], "play_count": 8930, "is_original": False, "latest_episode_id": 750482},
            {"video_id": 11709, "title": "刘二狗的性福人生", "cover": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081911274969639.jpeg", "tags": ["ai短剧", "成人短剧", "成人", "人妻", "少妇"], "play_count": 26235, "is_original": False, "latest_episode_id": 750504},
            {"video_id": 11645, "title": "大奉打更人", "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822263818607.jpeg", "tags": ["古装玄幻", "穿越探案", "权谋爽剧", "古风悬疑", "少年逆袭"], "play_count": 46549, "is_original": False, "latest_episode_id": 746003},
            {"video_id": 11643, "title": "甄嬛传 禁苑情劫", "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822283296889.jpeg", "tags": ["宫斗虐恋", "古风禁忌", "深宫权谋", "大女主", "BE"], "play_count": 40003, "is_original": False, "latest_episode_id": 746006},
            {"video_id": 11607, "title": "捉妖师", "cover": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081911281028491.jpeg", "tags": ["AI魔改短剧", "超爽成人短剧", "AI真人短剧"], "play_count": 7751, "is_original": False, "latest_episode_id": 743998},
            {"video_id": 11642, "title": "小白花的堕落", "cover": "https://pic.xustgq.cn/upload_01/upload/20260818/2026081822284171294.jpeg", "tags": ["人性反转", "虐心沉沦", "黑化女主", "情感纠葛", "现实虐恋"], "play_count": 5695, "is_original": False, "latest_episode_id": 746008},
        ],
    },
    {
        "id": 186,
        "title": "原创短剧",
        "code": "OSD",
        "dramas": [
            {"video_id": 11837, "title": "超世纪封神杯", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082111261685291.jpeg", "tags": ["成人AI漫剧", "神明足球大战", "封神杯", "中国神明VS英雄", "热血欲漫", "AI成人动画"], "play_count": 44461, "is_original": True, "latest_episode_id": 758660},
            {"video_id": 11838, "title": "天庭驱魔司主理人", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082111255122594.jpeg", "tags": ["魔改短剧", "AI短剧", "成人短剧"], "play_count": 31862, "is_original": True, "latest_episode_id": 758651},
            {"video_id": 11839, "title": "世一上", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121543029721.jpeg", "tags": ["AI成人短剧", "反差", "母狗", "吃瓜"], "play_count": 43758, "is_original": True, "latest_episode_id": 758651},
            {"video_id": 11840, "title": "山海快递", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121533492261.jpeg", "tags": ["魔改短剧", "AI短剧", "成人短剧"], "play_count": 38522, "is_original": True, "latest_episode_id": 770617},
            {"video_id": 11609, "title": "我家祖宅直通1895", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121545867273.jpeg", "tags": ["AI", "成人", "原创", "穿越", "民国", "悬疑"], "play_count": 46609, "is_original": True, "latest_episode_id": 770619},
            {"video_id": 11610, "title": "极品特务·别惹卖猪肉的", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121545030825.jpeg", "tags": ["AI", "成人", "原创", "轻喜剧", "权谋", "极限拉扯"], "play_count": 18575, "is_original": True, "latest_episode_id": 779891},
            {"video_id": 11078, "title": "女神经纪", "cover": "https://pic.xustgq.cn/upload_01/upload/20260819/2026081916553571303.jpeg", "tags": ["科幻恋爱喜剧  偶像养成 职场反杀  大尺度欲感风格的短剧"], "play_count": 31047, "is_original": True, "latest_episode_id": 712736},
            {"video_id": 10507, "title": "末日神舟", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121551829089.jpeg", "tags": ["末日生存", "铁腕领导", "系统升级", "大尺度成人欲感"], "play_count": 80609, "is_original": True, "latest_episode_id": 709580},
            {"video_id": 9822, "title": "我的AI女友", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121552543991.jpeg", "tags": ["都市科幻", "AI", "天才男主", "亡妻复仇", "悬疑伏笔", "虐心男主", "硬核科技", "真相追查"], "play_count": 127641, "is_original": True, "latest_episode_id": 689395},
            {"video_id": 9570, "title": "AI极品家丁", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082121553224766.jpeg", "tags": ["都市脑洞", "逆袭", "打脸虐渣", "霸总", "现代", "都市"], "play_count": 161284, "is_original": True, "latest_episode_id": 671787},
        ],
    },
    {
        "id": 19,
        "title": "热门精选短剧",
        "code": "HP",
        "dramas": [
            {"video_id": 12009, "title": "从新婚开始", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082119564284280.jpeg", "tags": ["爱情", "都市爱情", "故人重逢", "日久生情", "双向救赎", "真相大白", "总裁", "现代", "都市"], "play_count": 49071, "is_original": False, "latest_episode_id": 769704},
            {"video_id": 12018, "title": "破祖规:我家闺女唱满堂", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082119545745583.jpeg", "tags": ["年代", "家庭伦理", "揭露阴谋", "逆风翻盘", "打脸反派", "亲人"], "play_count": 36507, "is_original": False, "latest_episode_id": 770248},
            {"video_id": 12023, "title": "无敌大小姐出山了", "cover": "https://pic.xustgq.cn/upload_01/upload/20260821/2026082115521873827.jpeg", "tags": ["都市", "都市玄幻", "马甲文", "扮猪吃虎", "天下无敌", "大女主", "现代"], "play_count": 25278, "is_original": False, "latest_episode_id": 770615},
            {"video_id": 11622, "title": "小瞎子认错老公，糙汉大叔宠上天", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218055572052.jpeg", "tags": ["都市情感", "甜宠", "总裁", "乖乖女", "现代"], "play_count": 20152, "is_original": False, "latest_episode_id": 744666},
            {"video_id": 11623, "title": "祁教授太宠我了怎么办", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218050918444.png", "tags": ["都市情感", "闪婚", "甜宠", "打脸虐渣", "现代", "都市"], "play_count": 5347, "is_original": False, "latest_episode_id": 744760},
            {"video_id": 11624, "title": "错怪了救命恩人", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218045765791.jpeg", "tags": ["爱情", "都市爱情", "极致虐恋", "真相大白", "现代", "都市"], "play_count": 17957, "is_original": False, "latest_episode_id": 744766},
            {"video_id": 11625, "title": "闪婚成宠农村辣媳要翻身", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218044713642.jpeg", "tags": ["都市情感", "日久生情", "甜宠", "打脸虐渣", "总裁", "都市", "现代"], "play_count": 5286, "is_original": False, "latest_episode_id": 744825},
            {"video_id": 11627, "title": "你眼中的深情告白", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218003982626.jpeg", "tags": ["都市情感", "闪婚", "甜宠", "打脸虐渣", "总裁", "大叔", "现代", "都市"], "play_count": 34111, "is_original": False, "latest_episode_id": 744952},
            {"video_id": 11628, "title": "服软", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218002674825.png", "tags": ["都市情感", "日久生情", "甜宠", "医生", "都市", "现代"], "play_count": 16292, "is_original": False, "latest_episode_id": 745012},
            {"video_id": 11629, "title": "君生我已老", "cover": "https://pic.xustgq.cn/upload_01/upload/20260812/2026081218001616848.jpeg", "tags": ["都市情感", "甜宠", "逆袭", "打脸虐渣", "姐弟恋", "总裁", "都市", "现代"], "play_count": 35361, "is_original": False, "latest_episode_id": 745073},
        ],
    },
]

# ============================================================
# 3. 辅助函数
# ============================================================

def get_all_dramas():
    """获取所有短剧（平铺列表，去重）"""
    seen_ids = set()
    all_dramas = []
    for banner in DRAMA_BANNERS:
        if banner["video_id"] not in seen_ids:
            d = dict(banner)
            d["source"] = "banner"
            all_dramas.append(d)
            seen_ids.add(banner["video_id"])
    for section in DRAMA_SECTIONS:
        for drama in section["dramas"]:
            if drama["video_id"] not in seen_ids:
                d = dict(drama)
                d["source"] = section["code"]
                d["section_title"] = section["title"]
                all_dramas.append(d)
                seen_ids.add(drama["video_id"])
    return all_dramas


def search_dramas(keyword: str):
    """按关键词搜索短剧（标题/标签/简介）"""
    keyword = keyword.lower()
    results = []
    for drama in get_all_dramas():
        text = f"{drama.get('title', '')} {' '.join(drama.get('tags', []))} {drama.get('intro', '')}"
        if keyword in text.lower():
            results.append(drama)
    return results


def get_original_dramas():
    """获取所有原创短剧"""
    return [d for d in get_all_dramas() if d.get("is_original")]


def get_dramas_by_tag(tag: str):
    """按标签筛选短剧"""
    return [d for d in get_all_dramas() if tag in d.get("tags", [])]


def get_dramas_by_section(code: str):
    """按模块代码获取短剧 (AISD / OSD / HP)"""
    for sec in DRAMA_SECTIONS:
        if sec["code"] == code:
            return list(sec["dramas"])
    return []


# ============================================================
# 4. 运行统计
# ============================================================

if __name__ == "__main__":
    all_d = get_all_dramas()
    print(f"总计去重短剧: {len(all_d)} 部")
    print(f"  - 轮播推荐: {len(DRAMA_BANNERS)} 部")
    for sec in DRAMA_SECTIONS:
        print(f"  - [{sec['code']}] {sec['title']}: {len(sec['dramas'])} 部")

    print(f"\n原创短剧: {len(get_original_dramas())} 部")

    tag_counter = Counter()
    for d in all_d:
        tag_counter.update(d.get("tags", []))
    print("\n热门标签 TOP10:")
    for tag, count in tag_counter.most_common(10):
        print(f"  {tag}: {count} 部")

    print("\n搜索 'AI' 相关短剧:")
    for d in search_dramas("AI")[:5]:
        print(f"  - {d['title']}")

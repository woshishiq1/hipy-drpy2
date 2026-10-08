# -*- coding: utf-8 -*-
import json
import re
import random
import time
from urllib.parse import urljoin, quote, unquote
from urllib.request import Request, urlopen

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

from base.spider import Spider


class Spider(Spider):
    name = "仙缘秘录阁"

    _nm_h_hex = ["68", "74", "74", "70", "73", "3a", "2f", "2f"]
    _nm_d_hex = ["38", "37", "32", "38", "2e", "6d", "72", "73", "76", "6a", "2e", "63", "6f", "6d"]
    _nm_api_d_hex = ["34", "67", "66", "35", "36", "34", "36", "35", "66", "67", "31", "31", "32", "2e",
                     "68", "6f", "6e", "67", "6a", "69", "75", "63", "68", "61", "6e", "67", "2e", "63", "6f", "6d"]
    page_size = 24

    _tc_h_hex = ["68", "74", "74", "70", "73", "3a", "2f", "2f"]
    _tc_d_hex = ["77", "68", "6f", "73", "2e", "74", "76"]

    _xx_map = {
        "风月影阁": "仙缘录", "新出春宫": "新出秘典", "热片金榜": "热修金榜",
        "东瀛花谱": "东瀛仙谱", "当红头牌": "当红仙子", "花魁金榜": "仙魁金榜",
        "热播剧": "热播仙剧", "新剧": "新剧秘典", "VIP专享": "VIP仙缘",
        "午夜全部": "午夜秘录", "午夜剧场": "午夜秘录",
        "中文字幕": "天书秘译", "无码": "无遮秘录", "有码": "有遮秘录",
        "国产": "华夏秘录", "日本": "东瀛秘录", "欧美": "西域秘录",
        "动漫": "幻梦秘录", "制服": "霓裳秘录", "人妻": "人妻秘录",
        "熟女": "熟女秘录", "萝莉": "萝莉秘录", "巨乳": "巨乳秘录",
        "肛交": "后庭秘录", "群交": "群修秘录", "口交": "口修秘录",
        "手淫": "自修秘录", "强奸": "强修秘录", "乱伦": "乱修秘录",
        "偷拍": "偷修秘录", "女优": "仙子谱", "明星": "星宿谱",
        "主播": "主播谱", "自拍": "自拍谱", "伦理": "伦修谱",
        "三级": "三级谱", "其他": "杂修谱", "全部": "全部",
        "全部视频": "全部秘录", "标签": "印记",
        "最新发布": " newest 仙谕", "最高热度": " hottest 仙焰", "最高收藏": " most 仙藏",
        "排序": "仙序", "进入": "遁入", "打开": "启封",
    }

    @staticmethod
    def _decode_hex(hex_arr):
        return "".join(chr(int(c, 16)) for c in hex_arr)

    def __init__(self):
        self.nm_host = self._decode_hex(self._nm_h_hex) + self._decode_hex(self._nm_d_hex)
        self.nm_api_host = self._decode_hex(self._nm_h_hex) + self._decode_hex(self._nm_api_d_hex)
        self.nm_api = self.nm_api_host + "/api/web/v1"
        self.nm_video_host = ""
        self.nm_static_host = ""
        self.nm_night_video_host = ""
        self.nm_night_static_host = ""
        self.nm_night_categories = []
        self.nm_tag_map = {}
        self.nm_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
            "Origin": self.nm_host,
            "Referer": self.nm_host + "/h5/",
            "Content-Type": "application/json",
        }
        self.nm_session = requests.Session() if requests else None
        if self.nm_session:
            self.nm_session.headers.update(self.nm_headers)

        self.tc_host = self._decode_hex(self._tc_h_hex) + self._decode_hex(self._tc_d_hex)
        self.tc_header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": self.tc_host + "/"
        }

    def getName(self):
        return self.name

    def init(self, extend=""):
        if isinstance(extend, dict):
            data = extend
        else:
            try:
                data = json.loads(extend) if extend else {}
            except Exception:
                data = {}
        if isinstance(data, dict):
            if data.get("nm_api_host"):
                self.nm_api_host = str(data.get("nm_api_host")).rstrip("/")
                self.nm_api = self.nm_api_host + "/api/web/v1"
            if data.get("nm_video_host"):
                self.nm_video_host = str(data.get("nm_video_host")).rstrip("/")
            if data.get("nm_static_host"):
                self.nm_static_host = str(data.get("nm_static_host")).rstrip("/")
            if data.get("nm_night_video_host"):
                self.nm_night_video_host = str(data.get("nm_night_video_host")).rstrip("/")
            if data.get("nm_night_static_host"):
                self.nm_night_static_host = str(data.get("nm_night_static_host")).rstrip("/")

    @staticmethod
    def _page(pg):
        try:
            return max(1, int(pg))
        except Exception:
            return 1

    @staticmethod
    def _rsp_text(response):
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if isinstance(response, bytes):
            return response.decode("utf-8", "ignore")
        if isinstance(response, dict):
            for key in ("body", "text", "content", "data"):
                value = response.get(key)
                if isinstance(value, bytes):
                    return value.decode("utf-8", "ignore")
                if isinstance(value, str):
                    return value
            return json.dumps(response, ensure_ascii=True)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content.decode("utf-8", "ignore")
        return ""

    def _xx(self, name):
        if not name:
            return "未知秘录"
        if name in self._xx_map:
            return self._xx_map[name]
        for k, v in self._xx_map.items():
            if k in name:
                return name.replace(k, v)
        return name if any(name.endswith(x) for x in ("秘录", "谱", "录", "阁", "典")) else name + "秘录"

    # ═══════════════════════════════════════════════════════════════
    #  玄天 · API通信
    # ═══════════════════════════════════════════════════════════════
    def _nm_post(self, path, data=None):
        url = self.nm_api + path
        payload = json.dumps(data or {}, ensure_ascii=True).encode("utf-8")
        responses = []
        if self.nm_session:
            try:
                responses.append(self.nm_session.post(url, data=payload, timeout=15))
            except Exception:
                pass
        post_fn = getattr(self, "post", None)
        if callable(post_fn):
            try:
                responses.append(post_fn(url, data=payload, headers=self.nm_headers))
            except Exception:
                pass
        try:
            responses.append(self.fetch(url, headers=self.nm_headers, data=payload, method="POST"))
        except Exception:
            pass
        if not responses:
            try:
                request = Request(url, data=payload, headers=self.nm_headers, method="POST")
                responses.append(urlopen(request, timeout=15).read())
            except Exception:
                pass
        for response in responses:
            try:
                obj = json.loads(self._rsp_text(response) or "{}")
                if isinstance(obj, dict) and obj.get("code") == 10000:
                    return obj.get("data") or {}
            except Exception:
                continue
        return {}

    def _nm_load_config(self):
        data = self._nm_post("/config/load")
        config = data.get("config") or {}
        self.nm_video_host = str(config.get("video_domain") or self.nm_video_host).rstrip("/")
        self.nm_static_host = str(config.get("static_domain") or self.nm_static_host or self.nm_api_host).rstrip("/")
        self.nm_night_video_host = str(config.get("wy_video_domain") or self.nm_night_video_host).rstrip("/")
        self.nm_night_static_host = str(config.get("wy_static_domain") or self.nm_night_static_host).rstrip("/")
        tags = config.get("tags") or []
        self.nm_tag_map = {str(x.get("id")): str(x.get("t") or "") for x in tags if x.get("id") is not None}
        return config

    def _nm_pic(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        if value.startswith("http"):
            return value
        if not self.nm_static_host:
            self._nm_load_config()
        return urljoin((self.nm_static_host or self.nm_api_host) + "/", value)

    def _nm_night_pic(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        if value.startswith("http"):
            return value
        if not self.nm_night_static_host:
            self._nm_load_config()
        base = (self.nm_night_static_host or self.nm_static_host or self.nm_api_host).rstrip("/")
        return base + "/" + value.lstrip("/")

    def _nm_load_night_cates(self):
        data = self._nm_post("/night/topic/category")
        self.nm_night_categories = data.get("list") or []
        return self.nm_night_categories

    def _nm_night_cate(self, cate):
        for item in self.nm_night_categories or self._nm_load_night_cates():
            if str(item.get("i") or "") == str(cate):
                return item
        return {}

    def _nm_night_tag_folders(self, cate, pg, order="0"):
        item = self._nm_night_cate(cate)
        tags = [{"i": 0, "n": "全部视频"}] + list(item.get("t") or [])
        start = (pg - 1) * self.page_size
        current = tags[start:start + self.page_size]
        logo = self._nm_night_pic("h5/logo.png")
        videos = []
        for tag in current:
            tag_id = str(tag.get("i") if tag.get("i") is not None else "0")
            videos.append({
                "vod_id": "folder_nighttag_{}_{}_{}".format(cate, tag_id, order),
                "vod_name": self._xx(str(tag.get("n") or "标签")),
                "vod_pic": logo,
                "vod_remarks": "进入印记",
                "vod_tag": "folder",
            })
        total = len(tags)
        pagecount = max(1, (total + self.page_size - 1) // self.page_size)
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": self.page_size, "total": total, "filters": {}}

    def _nm_list_result(self, data, pg, night=False):
        videos = []
        for item in data.get("list") or []:
            videos.append({
                "vod_id": ("night_" if night else "") + str(item.get("id") or ""),
                "vod_name": str(item.get("title") or ""),
                "vod_pic": self._nm_night_pic(item.get("pic")) if night else self._nm_pic(item.get("cover") or item.get("pic")),
                "vod_remarks": "全{}集".format(item.get("sets")) if item.get("sets") else str(item.get("times") or ""),
            })
        total = int(data.get("total") or 0)
        size = int(data.get("pageSize") or self.page_size)
        pagecount = max(pg, (total + size - 1) // size) if total else pg + (1 if data.get("hasMore") else 0)
        return {"list": videos, "page": pg, "pagecount": max(1, pagecount), "limit": size, "total": total}

    # ═══════════════════════════════════════════════════════════════
    #  昆仑 · Web爬虫核心
    # ═══════════════════════════════════════════════════════════════
    def _tc_fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.tc_host + url
        return url

    def _tc_decode_cover(self, encoded):
        if not encoded:
            return ""
        try:
            key_hex = encoded[-2:]
            key = int(key_hex, 16)
            data_hex = encoded[:-2]
            chars = []
            for i in range(0, len(data_hex), 2):
                byte_val = int(data_hex[i:i+2], 16)
                chars.append(chr(byte_val ^ key))
            return ''.join(chars)
        except Exception:
            return ""

    def _tc_convert_name(self, name):
        if not name:
            return "无名仙子"
        titles = [
            '圣母', '元君', '天尊', '帝君', '天妃', '玄女', '素女', '玉女',
            '仙子', '神女', '圣女', '妖姬', '花魁', '天女', '魔女', '嫦娥',
            '贵妃', '昭仪', '婕妤', '才人', '贵人', '嫔妃', '姬妾', '侍妾'
        ]
        name_hash = sum(ord(c) for c in name) + len(name) * 31
        title = titles[name_hash % len(titles)]
        name = name.strip()
        if len(name) >= 4:
            core = name[1:3]
        elif len(name) == 3:
            core = name[1:]
        else:
            core = name
        vulgar = ['野', '多', '田', '山', '川', '木', '石', '土']
        if any(v in core for v in vulgar):
            return f"小{core[0]}{title}"
        return f"{core}{title}"

    def _tc_clean_title(self, title):
        if not title:
            return ""
        title = re.sub(r'\s*[-–—]\s*[^\s]*(?:tv|com|net|org|xyz|cc)[^\s]*', '', title, flags=re.I)
        title = re.sub(r'https?://\S+', '', title, flags=re.I)
        trash = [
            '作品资料', '精彩画面', '高清在线播放', '在线观看', '免费观看',
            '高清完整版', '中文字幕', '无码', '有码', '下载', '磁力', '迅雷',
            '福利', '资源', '合集', '全集', '在线', '播放', '视频', '电影',
            '高清', '完整版', '字幕', '版', '免费', '观看', '资料', '画面'
        ]
        for t in trash:
            title = title.replace(t, '')
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[\s\-–—]+|[\s\-–—]+$', '', title)
        return title

    def _tc_gen_story(self, title, actors, tags):
        actor = self._tc_convert_name(actors.split(',')[0]) if actors else "神秘女修"
        tag = tags.split(',')[0] if tags else "双修"
        code = self.regStr(title, r'([A-Z0-9]+-[0-9]+)') or "秘卷"
        stories = [
            f"太古洪荒之际，{actor}与{tag}师姐并称绝代双骄，二人容颜绝世倾城，修为通天彻地。然天劫骤至，师姐为护{actor}周全，以肉身硬抗九霄神雷，魂飞魄散。{actor}悲痛欲绝，不惜燃烧万年修为撕裂虚空，横渡无尽混沌追寻师姐残魂，终在末法时代的红尘俗世寻得其一缕转世真灵。为助师姐重聚三魂七魄、恢复上古大能之实力，{actor}只得隐于都市霓虹之中，以采阴补阳之术汲取纯阳精气，此番号「{code}」便是她于现代尘缘中双修采补、以情入道的珍贵实录。",
            f"上古{tag}仙宫之中，{actor}身为宫主独女，天生九阴玄体，貌若天仙，与圣女师姐并称仙界双璧。一场域外天魔入侵，仙宫覆灭，{actor}与师姐双双陨落，仅余一缕神魂遁入轮回井。千年之后，二人于现代都市转世重生，却失了前世修为与记忆。{actor}率先觉醒，忆起往昔峥嵘，方知师姐转世之身阳气亏虚、命不久矣。为救师姐性命、助其重登仙途，{actor}毅然踏入红尘，以绝世姿容为饵，采补都市男子元阳反哺师姐，此番「{code}」记载了她于摩天楼中设下双修大阵、一夜汲取百人精元的惊世手笔。",
            f"传闻{actor}乃是上古{tag}宗开派祖师与太上长老之女，自幼与掌门师姐青梅竹马，二人同修阴阳合欢诀，姿容绝世、功法通玄，被尊为\"玄门双骄\"。因宗门至宝\"混沌阴阳镜\"现世，引来八方觊觎，一场血战之后，二人肉身尽毁，仅余元神逃入时空裂缝，魂穿至二十一世纪的繁华都市。末法时代灵气稀薄，{actor}为护师姐元神不散，不得不以肉身布施，于灯红酒绿间采阴补阳、汲取精气炼化真元，此番号「{code}」完整呈现了她从清冷仙子到都市魅影的蜕变，每一帧皆是上古大能屈尊降贵、以情入道的辛酸写照。",
            f"远古{tag}神殿深处，{actor}与神殿圣女并称\"绝代双姝\"，二人冰肌玉骨、倾国倾城，修为已至大罗金仙之境。因触犯天条私授凡人长生秘法，被天帝降下诛仙令，二人肉身被毁、神魂贬入凡尘，历经百世轮回。这一世，{actor}于繁华都市中觉醒前世记忆，却发现师姐转世之身沦为寻常女子，阳气衰弱、寿元将尽。为逆转天命、助师姐重踏修仙之路，{actor}不惜自降身份，化身都市名媛，以双修采补之术汲取男子元阳，炼化为精纯灵气渡给师姐，此番「{code}」正是她于总统套房中施展上古媚术、与商界巨子颠鸾倒凤的私密影像。",
            f"{actor}本是上古{tag}洞天的大师姐，与师妹并称\"玄天双骄\"，二人容貌绝世、修为高深，已臻半步圣人境界。因探寻上古遗迹时触动了\"时空逆乱大阵\"，二人被卷入虚空乱流，横渡亿万光年，最终肉身崩解、神魂穿越至现代世界。末法时代大道不显，{actor}为保师妹神魂不灭，只得寄居都市女子肉身，以采阴补阳之法汲取红尘男子精气，炼化为混沌真元滋养师妹残魂，此番号「{code}」记录了她于现代夜店中施展上古惑心术、一夜连御七位都市精英的惊世场面，每一幕皆是上古大能屈尊纡贵、为爱堕尘的悲壮史诗。",
            f"洪荒年间，{tag}祖地有一株并蒂仙莲，化形为{actor}与师姐，二人同根同源、心意相通，姿容绝世、气质倾城，被万族尊为\"造化双骄\"。因仙魔大战波及，祖地被毁，二人元神受损，不得不舍弃仙躯，以秘法转世重生。{actor}率先于现代都市觉醒，却发现师姐转世之身先天阳气不足、体弱多病。为助师姐重塑仙根、恢复上古修为，{actor}毅然踏入红尘风月场，以绝世容颜为刃，采补都市男子纯阳精气，此番「{code}」便是她于高级会所中施展上古双修秘术、与政商名流共参阴阳大道的珍贵实录，观之可知上古大能即便堕凡，依旧风华绝代、颠倒众生。",
            f"{actor}与{tag}圣女乃是上古昆仑墟的\"绝代双璧\"，二人容貌倾城、修为通天，已臻准圣之境。因争夺\"鸿蒙紫气\"与域外邪神激战，二人肉身湮灭、神魂破碎，仅存一缕真灵遁入轮回。千年之后，{actor}于现代都市苏醒，忆起往昔，却发现圣女转世之身阳气枯竭、命悬一线。为救故友、重聚上古荣光，{actor}不惜自污仙名，化身都市丽人，以采阴补阳之术汲取男子元阳炼化真元，渡给圣女续命，此番号「{code}」完整记录了她于私人别墅中施展上古媚功、与豪门公子双修采补的全过程，从欲拒还迎到主动索取，尽显上古大能的风骨与无奈。",
            f"上古{tag}禁地之中，{actor}与守禁圣女并称\"幽冥双骄\"，二人肌肤胜雪、眉目如画，修为已至混元大罗金仙。因私放被囚的洪荒凶兽以救苍生，触犯天规，被天帝打入\"九幽轮回井\"，神魂历经万劫转世于末法时代。{actor}在现代都市中率先觉醒前世记忆，却发现圣女转世之身被阴气侵蚀、阳气衰败。为逆转乾坤、助圣女重登仙途，{actor}只得隐于红尘，以肉身布施，采补都市男子纯阳精气炼化为混沌元力，此番「{code}」正是她于海景豪宅中施展上古合欢秘术、与金融巨鳄颠鸾倒凤的私密影像，每一帧皆是上古大能为爱牺牲、屈尊降贵的血泪见证。",
            f"{actor}乃上古{tag}神朝长公主，与神朝女战神并称\"天骄双姝\"，二人容颜绝世、战功赫赫，曾联手镇压十方动乱。因神朝内乱，奸臣篡位，二人被诬陷谋反，遭\"斩仙台\"处决，神魂不灭、遁入时空裂缝，魂穿至现代都市。末法时代灵气匮乏，{actor}为保女战神转世之身神魂不散，不得不以凡人之躯修炼采补邪术，于都市霓虹中汲取男子元阳炼化真元，此番号「{code}」记载了她于顶级酒店中施展上古惑心术、与国际名流共赴巫山的惊世场面，从端庄公主到魅惑女王，尽显上古大能在末法时代的挣扎与坚韧。",
            f"远古{tag}仙山之巅，{actor}与山主之女并称\"仙山双璧\"，二人天资绝世、容貌倾城，同修\"太上忘情诀\"已至大成。因山主渡劫失败、仙山崩塌，二人以肉身护佑山门弟子，最终身死道消、仅余元神。{actor}元神不灭，横渡虚空追寻师姐残魂，终在末法时代的都市中寻得其转世之身，却发现师姐先天阳气不足、难以修行。为助师姐重聚三魂七魄、恢复上古修为，{actor}化身都市名媛，以采阴补阳之术汲取红尘男子精气，炼化为纯阳真元渡给师姐，此番「{code}」便是她于私人游艇上施展上古双修大法、与世家子弟翻云覆雨的珍贵实录，观之令人唏嘘上古大能的痴情与执着。",
            f"{actor}与{tag}宗圣女乃是上古蓬莱仙岛的\"海上双骄\"，二人肤若凝脂、气质出尘，修为已至真仙境。因探寻海底遗迹时触动了上古封印，释放出灭世凶兽，二人以生命为代价重新封印凶兽，神魂破碎、遁入轮回。千年之后，{actor}于现代都市觉醒，却发现圣女转世之身阳气衰弱、寿元无多。为救故友、重续仙缘，{actor}不惜堕入红尘，以绝世姿容为饵，采补都市男子元阳炼化混沌灵气，此番号「{code}」完整呈现了她于摩天大楼顶层施展上古媚术、与权贵名流颠鸾倒凤的全过程，从清冷仙子到热情如火，每一幕皆是上古大能为爱牺牲的真实写照。",
            f"上古{tag}魔宗之中，{actor}与宗主千金并称\"魔道双姝\"，二人容貌妖冶、修为高深，已臻魔尊之境。因正魔大战，魔宗被灭，二人肉身被毁、元神逃入时空乱流，横渡虚空来到末法时代的现代世界。{actor}率先觉醒，却发现师姐转世之身被正道封印所伤、阳气枯竭。为破除封印、助师姐恢复魔尊修为，{actor}只得隐于都市暗处，以采阴补阳之术汲取男子纯阳精气，炼化为魔元反哺师姐，此番「{code}」正是她于地下会所中施展上古魔门双修秘术、与黑道枭雄共参阴阳大道的私密影像，观之可知即便是上古魔尊，亦有柔情似水的一面。",
            f"{actor}本是上古{tag}天庭的瑶池圣女，与织女并称\"天界双璧\"，二人容貌绝世、手巧心灵，受万仙敬仰。因私动凡心、触犯天条，被王母娘娘打入\"红尘炼狱\"，神魂历经百世轮回。这一世，{actor}于现代都市中觉醒前世记忆，却发现织女转世之身阳气亏虚、神魂不稳。为助织女重登天界、恢复仙籍，{actor}不惜自降身份，化身都市白领，以采阴补阳之术汲取男子元阳炼化仙灵之气，此番号「{code}」记录了她于商务酒店中施展上古仙媚之术、与商界精英翻云覆雨的惊世场面，从圣洁圣女到红尘尤物，尽显上古大能的无奈与决绝。",
            f"洪荒{tag}古战场遗址中，{actor}与战魂公主并称\"铁血双骄\"，二人英姿飒爽、容貌倾城，修为已至武神之境。因古战场封印松动、邪灵出世，二人以肉身重铸封印，最终魂飞魄散、仅余一丝战意不灭。{actor}战意化形，横渡无尽虚空追寻公主残魂，终在现代都市寻得其转世之身，却发现公主阳气衰弱、被邪灵阴气侵蚀。为驱除邪灵、助公主重塑武神之躯，{actor}只得寄居都市女子肉身，以采阴补阳之术汲取男子纯阳精气炼化战魂元力，此番「{code}」便是她于格斗俱乐部中施展上古战媚之术、与格斗冠军颠鸾倒凤的珍贵实录，每一帧皆是上古武神为爱而战的热血见证。",
            f"{actor}与{tag}龙宫公主并称\"四海双姝\"，二人龙姿凤章、绝世倾城，修为已至龙神之境。因海眼暴动、四海倾覆，二人以龙躯镇压海眼，最终肉身崩解、龙魂遁入轮回井。千年之后，{actor}于现代都市觉醒龙魂记忆，却发现公主转世之身阳气不足、难以觉醒龙族血脉。为助公主重聚龙魂、恢复龙神实力，{actor}化身都市名媛，以采阴补阳之术汲取男子元阳炼化龙元，此番号「{code}」完整记录了她于海滨别墅中施展上古龙族双修秘术、与 maritime tycoon 翻云覆雨的全过程，从高贵龙女到魅惑人间，尽显上古大能的痴情与担当。",
            f"上古{tag}佛国之中，{actor}与观音座下龙女并称\"佛门双璧\"，二人宝相庄严、容貌绝世，已修成菩萨果位。因悲悯苍生、私传凡人佛法，触犯佛规，被佛祖打入\"轮回苦海\"，历经万劫。{actor}于现代都市中率先觉醒，却发现龙女转世之身阳气枯竭、佛光黯淡。为助龙女重聚佛元、恢复菩萨修为，{actor}不惜破戒入世，以肉身布施，采补都市男子精气炼化佛力，此番「{code}」正是她于禅意酒店中施展上古佛媚之术、与慈善家共参欢喜禅的私密影像，观之令人感慨即便是上古菩萨，为救故友亦可放下身段、堕入红尘。",
            f"{actor}乃上古{tag}妖庭的九尾天狐，与青丘女帝并称\"妖界双骄\"，二人倾国倾城、魅惑众生，修为已至妖圣之境。因天庭围剿妖庭，二人以妖躯抵挡十万天兵，最终肉身湮灭、妖魂破碎。{actor}妖魂不灭，横渡虚空追寻女帝残魂，终在末法都市寻得其转世之身，却发现女帝阳气衰弱、妖魂难聚。为助女帝重凝妖魂、恢复妖圣实力，{actor}化身都市网红，以采阴补阳之术汲取男子元阳炼化妖元，此番号「{code}」记载了她于直播镜头后施展上古狐媚之术、与粉丝大佬颠鸾倒凤的惊世场面，从妖界至尊到网络女神，每一幕皆是上古大能屈尊降贵的辛酸写照。",
            f"远古{tag}剑冢之中，{actor}与剑灵圣女并称\"剑道双璧\"，二人冷艳绝世、剑气纵横，已臻剑仙之境。因剑冢封印的上古邪剑出世，二人以本命剑胎镇压邪剑，最终剑胎碎裂、神魂遁入轮回。{actor}剑意不灭，魂穿至现代都市寻得圣女转世之身，却发现圣女阳气亏虚、剑骨难成。为助圣女重铸剑骨、恢复剑仙修为，{actor}只得隐于红尘，以采阴补阳之术汲取男子精气炼化剑元，此番「{code}」便是她于剑道主题酒店中施展上古剑媚之术、与剑道爱好者双修采补的珍贵实录，从无情剑仙到多情女子，尽显上古大能的柔情与执念。",
            f"{actor}与{tag}丹宗圣女并称\"丹道双骄\"，二人容貌绝世、丹术通神，已臻丹圣之境。因炼制\"九转还魂丹\"引来丹劫，二人以肉身抗劫、护佑丹炉，最终肉身焚毁、神魂破碎。{actor}神魂不灭，横渡虚空追寻圣女残魂，终在现代都市寻得其转世之身，却发现圣女阳气衰弱、丹火难燃。为助圣女重聚丹火、恢复丹圣实力，{actor}化身都市药师，以采阴补阳之术汲取男子元阳炼化丹元，此番号「{code}」完整呈现了她于药膳会所中施展上古丹媚之术、与养生名流共参阴阳大道的私密影像，每一帧皆是上古丹圣为爱炼丹、屈尊纡贵的感人篇章。",
            f"上古{tag}音宗之中，{actor}与琴瑟仙子并称\"音律双璧\"，二人姿容绝世、琴技通神，一曲可动天地。因演奏\"灭世魔音\"封印域外天魔，二人琴弦断裂、神魂受损，遁入轮回井历经万劫。{actor}于现代都市中觉醒，却发现仙子转世之身阳气不足、琴心难聚。为助仙子重凝琴心、恢复音宗修为，{actor}化身都市歌手，以采阴补阳之术汲取男子精气炼化音元，此番「{code}」正是她于录音棚休息室中施展上古音媚之术、与音乐制作人颠鸾倒凤的惊世实录，从音宗至尊到流行天后，尽显上古大能为爱发声、不惜一切的决绝与勇气。",
        ]
        seed = sum(ord(c) for c in (code + actor)) % len(stories)
        return stories[seed]

    def _tc_shuffle(self, videos, period, limit):
        if not videos:
            return []
        seed = int(time.time()) // (3600 if period == "hour" else 86400)
        r = random.Random(seed)
        vlist = list(videos)
        r.shuffle(vlist)
        return vlist[:limit]

    def _tc_fetch_list(self, tid, pg):
        if not BeautifulSoup:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        original_tid = tid
        # === 印记：完整映射所有分类id ===
        if tid in ("tc_actresses_hot", "tc_actresses_rank"):
            tid = "/actresses"
        elif tid == "tc_videos_latest":
            tid = "/videos?sort=latest"
        elif tid == "tc_videos_popular":
            tid = "/videos?sort=popular"
        elif tid == "tc_videos":
            tid = "/videos"
        elif tid == "tc_actresses":
            tid = "/actresses"
        elif tid.startswith("tc_"):
            tid = tid[3:]  # 仙子个人页 tc_/actresses/xxx -> /actresses/xxx

        url = self.tc_host + tid
        if int(pg) > 1:
            if "?" in url:
                url += "&page=" + str(pg)
            else:
                url += "/page-" + str(pg)
        try:
            rsp = self.fetch(url, headers=self.tc_header)
            soup = BeautifulSoup(rsp.text, 'html.parser')
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

        videos = []
        seen = set()

        # 仙子名录页（东瀛仙谱、当红仙子、仙魁金榜）
        if tid == "/actresses" or original_tid in ("tc_actresses_hot", "tc_actresses_rank"):
            items = soup.find_all('a', href=re.compile(r'^/actresses/.'))
            for item in items:
                try:
                    img = item.find('img')
                    if not img:
                        continue
                    raw_name = img.get('alt', '').strip()
                    name = self._tc_convert_name(raw_name)
                    href = item.get('href')
                    if not raw_name or not href or href == "/actresses" or "page-" in href:
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    pic_url = self._tc_fix_url(img.get('src', ''))
                    count_text = ""
                    icon_span = item.find('span', class_=re.compile(r'icon-\[lucide--film\]'))
                    if icon_span:
                        parent_flex = icon_span.find_parent('span', class_='flex')
                        if parent_flex:
                            count_text = parent_flex.get_text(strip=True) + "部仙籍"
                    videos.append({
                        "vod_id": "tc_" + href,
                        "vod_name": name,
                        "vod_pic": pic_url,
                        "vod_remarks": count_text if count_text else "仙籍集",
                        "vod_tag": "folder"
                    })
                except Exception:
                    continue

            # 轮播分类多页聚合（当红仙子、仙魁金榜）
            if original_tid in ("tc_actresses_hot", "tc_actresses_rank", "tc_videos_latest", "tc_videos_popular"):
                max_target = 100 if original_tid in ("tc_actresses_hot", "tc_videos_latest") else 50
                for extra_pg in range(2, 4):
                    if len(videos) >= max_target:
                        break
                    extra_url = self.tc_host + tid
                    if "?" in extra_url:
                        extra_url += "&page=" + str(extra_pg)
                    else:
                        extra_url += "/page-" + str(extra_pg)
                    try:
                        extra_rsp = self.fetch(extra_url, headers=self.tc_header)
                        extra_soup = BeautifulSoup(extra_rsp.text, 'html.parser')
                        extra_items = extra_soup.find_all('a', href=re.compile(r'^/actresses/.'))
                        for item in extra_items:
                            try:
                                img = item.find('img')
                                if not img:
                                    continue
                                raw_name = img.get('alt', '').strip()
                                name = self._tc_convert_name(raw_name)
                                href = item.get('href')
                                if not raw_name or not href or href == "/actresses" or "page-" in href:
                                    continue
                                if href in seen:
                                    continue
                                seen.add(href)
                                pic_url = self._tc_fix_url(img.get('src', ''))
                                count_text = ""
                                icon_span = item.find('span', class_=re.compile(r'icon-\[lucide--film\]'))
                                if icon_span:
                                    parent_flex = icon_span.find_parent('span', class_='flex')
                                    if parent_flex:
                                        count_text = parent_flex.get_text(strip=True) + "部仙籍"
                                videos.append({
                                    "vod_id": "tc_" + href,
                                    "vod_name": name,
                                    "vod_pic": pic_url,
                                    "vod_remarks": count_text if count_text else "仙籍集",
                                    "vod_tag": "folder"
                                })
                            except Exception:
                                continue
                    except Exception:
                        break
                if original_tid in ("tc_actresses_hot", "tc_videos_latest"):
                    videos = self._tc_shuffle(videos, "hour", 100)
                elif original_tid in ("tc_actresses_rank", "tc_videos_popular"):
                    videos = self._tc_shuffle(videos, "day", 50)
        else:
            # 影片列表（风月影阁、新出秘典、热修金榜、仙子个人页）
            items = soup.find_all('a', href=re.compile(r'^/videos/.'))
            for item in items:
                try:
                    h3 = item.find('h3')
                    v_name = h3.get_text(strip=True) if h3 else item.get('alt', '')
                    if not v_name:
                        continue
                    href = item.get('href')
                    if not href:
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    div_cover = item.find('div', attrs={'data-cover-src': True})
                    real_pic = ""
                    if div_cover:
                        encoded = div_cover.get('data-cover-src')
                        real_pic = self._tc_decode_cover(encoded)
                    real_pic = self._tc_fix_url(real_pic)
                    remarks = self.regStr(v_name, r'([A-Z0-9]+-[0-9]+)')
                    videos.append({
                        "vod_id": "tc_" + href,
                        "vod_name": v_name,
                        "vod_pic": real_pic,
                        "vod_remarks": remarks if remarks else ""
                    })
                except Exception:
                    continue

        # === 印记：统一构建返回结果，确保 pagecount/total 始终有值 ===
        result = {}
        if original_tid in ("tc_actresses_hot", "tc_actresses_rank", "tc_videos_latest", "tc_videos_popular"):
            result['pagecount'] = 1
            result['total'] = len(videos)
            result['limit'] = len(videos)
        else:
            result['pagecount'] = 999
            result['limit'] = len(videos)
            result['total'] = 9999
        result['list'] = videos
        result['page'] = pg
        # 仙子个人页提取仙子名
        if tid.startswith("/actresses/"):
            h1_tag = soup.find('h1')
            if h1_tag:
                result['type_name'] = h1_tag.get_text(strip=True)
        return result

    def _tc_detail(self, vod_id):
        if not BeautifulSoup:
            return None
        real_id = vod_id[3:] if vod_id.startswith("tc_") else vod_id
        if real_id.startswith("/actresses/"):
            # 仙子个人页，直接返回仙籍列表
            return self._tc_fetch_list(vod_id, 1)

        url = self.tc_host + real_id
        try:
            rsp = self.fetch(url, headers=self.tc_header)
            soup = BeautifulSoup(rsp.text, 'html.parser')
        except Exception:
            return None

        title = ""
        title_meta = soup.find('meta', property="og:title")
        if title_meta:
            title = title_meta.get('content', '')
        if not title:
            h1_tag = soup.find('h1')
            if h1_tag:
                title = h1_tag.get_text(strip=True)
        clean_title = self._tc_clean_title(title)

        pic = ""
        pic_meta = soup.find('meta', property="og:image")
        if pic_meta:
            pic = pic_meta.get('content', '')
        if not pic:
            video_tag = soup.find('video', poster=True)
            if video_tag:
                pic = video_tag.get('poster', '')
        pic = self._tc_fix_url(pic)

        play_url = ""
        source = soup.find('source', type="application/x-mpegURL")
        if source:
            play_url = source.get('src', '')
        if not play_url:
            video_tag = soup.find('video')
            if video_tag:
                play_url = video_tag.get('src', '')
        if not play_url:
            html = rsp.text
            js_patterns = [
                "var\\s+now\\s*=\\s*['\"]([^'\"]+\\.m3u8[^'\"]*)['\"]",
                "var\\s+playurl\\s*=\\s*['\"]([^'\"]+\\.m3u8[^'\"]*)['\"]",
                "var\\s+play_url\\s*=\\s*['\"]([^'\"]+\\.m3u8[^'\"]*)['\"]",
                "var\\s+player_data\\s*=\\s*['\"]([^'\"]+\\.m3u8[^'\"]*)['\"]",
                "['\"]([^'\"]+\\.m3u8[^'\"]*)['\"]",
                "['\"]([^'\"]+\\.mp4[^'\"]*)['\"]"
            ]
            for pat in js_patterns:
                m = re.search(pat, html)
                if m:
                    play_url = m.group(1)
                    break
        if not play_url:
            iframe = soup.find('iframe')
            if iframe:
                play_url = iframe.get('src', '')
        play_url = self._tc_fix_url(play_url)

        actor_tags = soup.select('a[href^="/actresses/"]')
        raw_actors = [a.get_text(strip=True) for a in actor_tags if a.get_text(strip=True)]
        actors = ",".join([self._tc_convert_name(a) for a in raw_actors])

        tag_tags = soup.select('a[href^="/tags/"] span.truncate')
        tags = ",".join([t.get_text(strip=True) for t in tag_tags])

        story = self._tc_gen_story(clean_title, ",".join(raw_actors), tags)

        return {
            "vod_id": vod_id,
            "vod_name": clean_title if clean_title else title,
            "vod_pic": pic,
            "type_name": tags,
            "vod_actor": actors,
            "vod_content": story,
            "vod_play_from": "昆仑道",
            "vod_play_url": "全高清$" + play_url if play_url else "",
            "vod_remarks": self.regStr(clean_title, r'([A-Z0-9]+-[0-9]+)') or ""
        }

    def _tc_search(self, key, pg=1):
        if not BeautifulSoup:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        url = self.tc_host + "/result?serach=" + quote(str(key))
        try:
            rsp = self.fetch(url, headers=self.tc_header)
            soup = BeautifulSoup(rsp.text, 'html.parser')
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

        videos = []
        seen = set()
        items = soup.find_all('a', href=re.compile(r'^/videos/.'))
        for item in items:
            try:
                h3 = item.find('h3')
                if not h3:
                    continue
                v_name = h3.get_text(strip=True)
                href = item.get('href')
                if not href:
                    continue
                if href in seen:
                    continue
                seen.add(href)
                div_cover = item.find('div', attrs={'data-cover-src': True})
                real_pic = ""
                if div_cover:
                    encoded = div_cover.get('data-cover-src')
                    real_pic = self._tc_decode_cover(encoded)
                real_pic = self._tc_fix_url(real_pic)
                remarks = self.regStr(v_name, r'([A-Z0-9]+-[0-9]+)')
                videos.append({
                    "vod_id": "tc_" + href,
                    "vod_name": v_name,
                    "vod_pic": real_pic,
                    "vod_remarks": remarks if remarks else ""
                })
            except Exception:
                continue
        return {"list": videos, "page": pg, "pagecount": 1, "limit": len(videos), "total": len(videos)}

    # ═══════════════════════════════════════════════════════════════
    #  首页 · 分类总览
    # ═══════════════════════════════════════════════════════════════
    def homeContent(self, filter=False):
        if not self.nm_tag_map:
            self._nm_load_config()

        tag_items = [{"n": self._xx(name), "v": tag_id} for tag_id, name in list(self.nm_tag_map.items())[:72] if name]
        tag_groups = [{
            "key": "tag",
            "name": "标签",
            "value": [{"n": "全部", "v": ""}] + tag_items,
        }]
        classes = [
            {"type_id": "hot", "type_name": self._xx("热播剧")},
            {"type_id": "new", "type_name": self._xx("新剧")},
            {"type_id": "vip", "type_name": self._xx("VIP专享")},
            {"type_id": "night", "type_name": self._xx("午夜全部")},
        ]
        filters = {key: tag_groups for key in ("hot", "new", "vip")}
        order_filter = {"key": "order", "name": "排序", "value": [
            {"n": "最新发布", "v": "0"},
            {"n": "最高热度", "v": "hot"},
            {"n": "最高收藏", "v": "collect"},
        ]}
        filters["night"] = [order_filter]

        night_categories = self.nm_night_categories or self._nm_load_night_cates()
        for item in night_categories:
            cate = str(item.get("i") or "")
            name = str(item.get("n") or "")
            if not cate or not name:
                continue
            tid = "nightcate_" + cate
            classes.append({"type_id": tid, "type_name": self._xx(name)})
            current = []
            tags = item.get("t") or []
            if 0 < len(tags) <= 15:
                current.append({
                    "key": "night_tag",
                    "name": "标签",
                    "value": [{"n": "全部", "v": "0"}] + [
                        {"n": self._xx(str(tag.get("n") or "")), "v": str(tag.get("i") or "")}
                        for tag in tags if tag.get("i") is not None and tag.get("n")
                    ],
                })
            elif len(tags) > 15:
                current.append({
                    "key": "night_tag",
                    "name": "标签",
                    "value": [{"n": "全部视频", "v": "0"}],
                })
            current.append(order_filter)
            filters[tid] = current

        classes.extend([
            {"type_id": "tc_videos", "type_name": self._xx("风月影阁")},
            {"type_id": "tc_videos_latest", "type_name": self._xx("新出春宫")},
            {"type_id": "tc_videos_popular", "type_name": self._xx("热片金榜")},
            {"type_id": "tc_actresses", "type_name": self._xx("东瀛花谱")},
            {"type_id": "tc_actresses_hot", "type_name": self._xx("当红头牌")},
            {"type_id": "tc_actresses_rank", "type_name": self._xx("花魁金榜")},
        ])

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        data = self._nm_post("/video/list", {"pageNum": 1, "pageSize": self.page_size})
        return {"list": self._nm_list_result(data, 1)["list"]}

    # ═══════════════════════════════════════════════════════════════
    #  分类 · 路由分发
    # ═══════════════════════════════════════════════════════════════
    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._page(pg)
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        tid = str(tid or "")

        if tid.startswith("tc_"):
            return self._tc_fetch_list(tid, page)

        if tid.startswith("folder_nighttag_"):
            parts = tid.split("_")
            if len(parts) >= 5:
                cate, tag, order = parts[2], parts[3], parts[4]
                data = self._nm_post("/night/video/video-list", {
                    "pageNum": page,
                    "pageSize": self.page_size,
                    "cate": cate,
                    "tag": tag,
                    "order": order,
                })
                result = self._nm_list_result(data, page, night=True)
                result["filters"] = {}
                return result

        if tid == "night" or tid.startswith("nightcate_"):
            cate = tid.replace("nightcate_", "") if tid.startswith("nightcate_") else "0"
            order = str(extend.get("order") or "0")
            cate_info = self._nm_night_cate(cate) if cate != "0" else {}
            tags = cate_info.get("t") or []
            if cate != "0" and len(tags) > 15:
                return self._nm_night_tag_folders(cate, page, order)
            payload = {
                "pageNum": page,
                "pageSize": self.page_size,
                "cate": cate,
                "tag": str(extend.get("night_tag") or "0"),
                "order": order,
            }
            data = self._nm_post("/night/video/video-list", payload)
            return self._nm_list_result(data, page, night=True)

        tag = str(extend.get("tag") or "")
        if tag:
            data = self._nm_post("/tags/video", {"tag": int(tag), "pageNum": page, "pageSize": self.page_size})
        else:
            payload = {"pageNum": page, "pageSize": self.page_size}
            if tid in ("new", "vip"):
                payload["type"] = tid
            data = self._nm_post("/video/list", payload)
        return self._nm_list_result(data, page)

    # ═══════════════════════════════════════════════════════════════
    #  详情 · 双源映照
    # ═══════════════════════════════════════════════════════════════
    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) and ids else ids
        if not vod_id:
            return {"list": []}
        vod_id = str(vod_id)

        # ── 昆仑详情 ──
        if vod_id.startswith("tc_"):
            real_id = vod_id[3:]
            if real_id.startswith("/actresses/"):
                # 仙子个人页，直接返回仙籍列表
                return self._tc_fetch_list(vod_id, 1)
            detail = self._tc_detail(vod_id)
            if not detail:
                return {"list": []}
            # 尝试匹配玄天线路
            try:
                code = detail.get("vod_remarks", "")
                if code:
                    nm_search = self._nm_post("/search/list", {"text": code, "pageNum": 1, "pageSize": 5})
                    nm_list = nm_search.get("list") or []
                    if nm_list:
                        nm_id = str(nm_list[0].get("id") or "")
                        if nm_id:
                            nm_data = self._nm_post("/video/play-info", {"id": nm_id, "setIndex": 0})
                            nm_info = nm_data.get("info") or {}
                            nm_eps = []
                            for item in nm_info.get("setList") or []:
                                idx = item.get("i")
                                if idx is not None:
                                    nm_eps.append("第{}集${}|{}".format(idx, nm_id, idx))
                            if nm_eps:
                                detail["vod_play_from"] = "昆仑道$$$玄天仙缘"
                                detail["vod_play_url"] = detail.get("vod_play_url", "") + "$$$" + "#".join(nm_eps)
            except Exception:
                pass
            return {"list": [detail]}

        # ── 玄天标签文件夹 ──
        if vod_id.startswith("folder_nighttag_"):
            parts = vod_id.split("_")
            if len(parts) >= 5:
                cate, tag, order = parts[2], parts[3], parts[4]
                cate_info = self._nm_night_cate(cate)
                tag_name = "全部视频" if tag == "0" else next((str(t.get("n") or "") for t in cate_info.get("t") or [] if str(t.get("i")) == tag), "标签")
                vod = {
                    "vod_id": vod_id,
                    "vod_name": "{} - {}".format(self._xx(str(cate_info.get("n") or "午夜秘录")), self._xx(tag_name)),
                    "vod_pic": self._nm_night_pic("h5/logo.png"),
                    "vod_remarks": "印记目录",
                    "vod_content": "印记入口，点击播放进入影像总览",
                    "vod_play_from": "目录",
                    "vod_play_url": "打开$" + vod_id,
                }
                return {"list": [vod]}

        # ── 玄天午夜视频 ──
        if vod_id.startswith("night_"):
            real_id = vod_id[6:]
            data = self._nm_post("/night/video/info", {"id": int(real_id)})
            info = data.get("info") or {}
            if not info:
                return {"list": []}
            title = str(info.get("title") or "")
            story = self._tc_gen_story(title, "", "")
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._nm_night_pic(info.get("pic")),
                "vod_remarks": str(info.get("times") or ""),
                "vod_content": story,
                "vod_play_from": "午夜秘录",
                "vod_play_url": "播放$nightplay_{}".format(real_id),
            }
            # 尝试匹配昆仑线路
            try:
                code = self.regStr(title, r'([A-Z0-9]+-[0-9]+)')
                if code:
                    tc_search = self._tc_search(code)
                    tc_list = tc_search.get("list") or []
                    if tc_list:
                        tc_vod_id = tc_list[0]["vod_id"]
                        tc_detail = self._tc_detail(tc_vod_id)
                        if tc_detail and tc_detail.get("vod_play_url"):
                            vod["vod_play_from"] = "玄天秘录$$$昆仑道"
                            vod["vod_play_url"] = vod["vod_play_url"] + "$$$" + tc_detail["vod_play_url"]
                            if tc_detail.get("vod_content"):
                                vod["vod_content"] = tc_detail["vod_content"]
            except Exception:
                pass
            return {"list": [vod]}

        # ── 玄天普通视频 ──
        data = self._nm_post("/video/play-info", {"id": vod_id, "setIndex": 0})
        info = data.get("info") or {}
        if not info:
            return {"list": []}
        episodes = []
        for item in info.get("setList") or []:
            index = item.get("i")
            if index is not None:
                episodes.append("第{}集${}|{}".format(index, vod_id, index))
        tags = []
        if not self.nm_tag_map:
            self._nm_load_config()
        for tag_id in str(info.get("tags") or "").split(","):
            if self.nm_tag_map.get(tag_id):
                tags.append(self._xx(self.nm_tag_map[tag_id]))
        title = str(info.get("title") or "")
        story = self._tc_gen_story(title, "", ",".join(tags))
        vod = {
            "vod_id": str(vod_id),
            "vod_name": title,
            "vod_pic": self._nm_pic(info.get("cover")),
            "vod_remarks": "全{}集".format(info.get("sets") or len(episodes)),
            "vod_content": story,
            "vod_type": ",".join(tags),
            "vod_play_from": "玄天仙缘",
            "vod_play_url": "#".join(episodes),
        }
        # 尝试匹配昆仑线路
        try:
            code = self.regStr(title, r'([A-Z0-9]+-[0-9]+)')
            if not code and len(title) >= 5:
                code = title[:10]
            if code:
                tc_search = self._tc_search(code)
                tc_list = tc_search.get("list") or []
                if tc_list:
                    tc_vod_id = tc_list[0]["vod_id"]
                    tc_detail = self._tc_detail(tc_vod_id)
                    if tc_detail and tc_detail.get("vod_play_url"):
                        vod["vod_play_from"] = "玄天仙缘$$$昆仑道"
                        vod["vod_play_url"] = vod["vod_play_url"] + "$$$" + tc_detail["vod_play_url"]
                        if tc_detail.get("vod_content"):
                            vod["vod_content"] = tc_detail["vod_content"]
        except Exception:
            pass
        return {"list": [vod]}

    # ═══════════════════════════════════════════════════════════════
    #  搜索 · 双源映照
    # ═══════════════════════════════════════════════════════════════
    def searchContent(self, key, quick=False, pg=1):
        page = self._page(pg)
        if not key:
            return {"list": [], "page": page, "pagecount": 1, "limit": self.page_size, "total": 0}

        all_videos = []
        seen_names = set()

        try:
            data = self._nm_post("/search/list", {"text": str(key), "pageNum": page, "pageSize": self.page_size})
            nm_result = self._nm_list_result(data, page)
            for v in nm_result.get("list") or []:
                name = v.get("vod_name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    all_videos.append(v)
        except Exception:
            pass

        try:
            tc_result = self._tc_search(key, page)
            for v in tc_result.get("list") or []:
                name = v.get("vod_name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    all_videos.append(v)
        except Exception:
            pass

        return {"list": all_videos, "page": page, "pagecount": 1, "limit": self.page_size, "total": len(all_videos)}

    # ═══════════════════════════════════════════════════════════════
    #  播放 · 路由分发
    # ═══════════════════════════════════════════════════════════════
    def playerContent(self, flag, id, vipFlags=None):
        text = str(id or "")

        # ── 昆仑播放 ──
        if "昆仑道" in str(flag or ""):
            if self.isVideoFormat(text):
                return {
                    "parse": 0,
                    "url": text,
                    "header": {
                        "User-Agent": self.tc_header["User-Agent"],
                        "Referer": self.tc_host + "/",
                        "Origin": self.tc_host
                    }
                }
            return {
                "parse": 0,
                "url": text,
                "header": {
                    "User-Agent": self.tc_header["User-Agent"],
                    "Referer": self.tc_host + "/",
                    "Origin": self.tc_host
                }
            }

        # ── 玄天标签文件夹 ──
        if text.startswith("folder_nighttag_"):
            return {"parse": 1, "url": text, "header": {}}

        # ── 玄天午夜播放 ──
        if text.startswith("nightplay_"):
            real_id = text[10:]
            data = self._nm_post("/night/video/info", {"id": int(real_id)})
            info = data.get("info") or {}
            path = str(info.get("url_m3u8") or "").strip()
            if not path:
                return {"parse": 0, "url": "", "header": {}}
            if not self.nm_night_video_host:
                self._nm_load_config()
            base = (self.nm_night_video_host or self.nm_video_host).rstrip("/")
            url = path if path.startswith("http") else base + "/" + path.lstrip("/")
            return {
                "parse": 0,
                "url": url,
                "header": {
                    "User-Agent": self.nm_headers["User-Agent"],
                    "Referer": self.nm_host + "/h5/",
                    "Origin": self.nm_host
                }
            }

        # ── 玄天普通播放 ──
        if "|" not in text:
            return {"parse": 0, "url": "", "header": {}}
        vod_id, set_no = text.rsplit("|", 1)
        data = self._nm_post("/video/set-info", {"id": vod_id, "set": self._page(set_no)})
        info = data.get("info") or {}
        path = str(info.get("url_m3u8") or "").strip()
        if not path:
            return {"parse": 0, "url": "", "header": {}}
        if not self.nm_video_host:
            self._nm_load_config()
        url = path if path.startswith("http") else urljoin((self.nm_video_host or self.nm_api_host) + "/", path)
        return {
            "parse": 0,
            "url": url,
            "header": {
                "User-Agent": self.nm_headers["User-Agent"],
                "Referer": self.nm_host + "/h5/",
                "Origin": self.nm_host
            }
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        exts = ['.m3u8', '.mp4', '.avi', '.flv', '.mkv', '.ts']
        return any(url.lower().endswith(ext) for ext in exts) or 'm3u8' in url.lower()

    def localProxy(self, param):
        return [404, "text/plain", ""]

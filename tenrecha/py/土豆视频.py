import json
import base64
from requests import Session
from urllib.parse import quote, unquote
import sys
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    host_base = "https://x0j1b8o6e9l2b3.com/jbapi"
    xor_key = b"2019ysapp7527"

    def getName(self):
        return "土豆视频"

    def _decrypt_api_data(self, enc_data):
        try:
            enc_data = str(enc_data).replace('\n', '').replace('\r', '').replace(' ', '')
            enc_data += "=" * ((4 - len(enc_data) % 4) % 4)
            step1 = base64.b64decode(enc_data).decode('utf-8')[::-1]
            step1 = step1.replace('\n', '').replace('\r', '').replace(' ', '')
            step1 += "=" * ((4 - len(step1) % 4) % 4)
            return json.loads(base64.b64decode(step1).decode('utf-8'))
        except:
            return {}

    def init(self, extend=""):
        self.session = Session()
        self.token = ""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/147.0.7727.137 Mobile Safari/537.36"}
            res = self.session.get(f"{self.host_base}/user/autoUser/null/td/null", headers=headers, verify=False, timeout=10).json()
            data = self._decrypt_api_data(res.get("data", "")) if res.get("enc") else res.get("data", {})
            self.token = data.get("token", "") if isinstance(data, dict) else self._decrypt_api_data(data).get("token", "")
        except:
            pass

    def get_headers(self):
        return {
            "token": self.token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/147.0.7727.137 Mobile Safari/537.36"
        }

    def _post(self, path, payload=None):
        if not path.endswith('.ojbk'): path = path.rstrip('/') + '/hjm.ojbk'
        url = f"{self.host_base}/{path}"
        try:
            res = self.session.post(url, headers=self.get_headers(), json=payload, verify=False, timeout=10).json() if payload else self.session.get(url, headers=self.get_headers(), verify=False, timeout=10).json()
            return self._decrypt_api_data(res.get("data", "")) if res.get("enc") else res.get("data", {})
        except:
            return {}

    def _live_get(self, path):
        try:
            res = self.session.get(f"{self.host_base}/{path.lstrip('/')}", headers=self.get_headers(), verify=False, timeout=10).json()
            data = res.get("data", {})
            return self._decrypt_api_data(data) if isinstance(data, str) else (data if isinstance(data, dict) else {})
        except:
            return {}

    def get_subs_dict(self):
        return {
            "9": [{"n": "🌟每日「星」推荐", "v": "zhuti_10661"}, {"n": "精彩推荐-让生活多一点「色」彩", "v": "zhuti_10662"}, {"n": "SM用户喜爱合集", "v": "zhuti_27117"}, {"n": "🌟独家-女优VLOG", "v": "zhuti_10667"}, {"n": "原创投稿-VLOG百万博主计划", "v": "zhuti_24941"}, {"n": "黑料不打烊-重磅泄密", "v": "zhuti_10666"}, {"n": "SM会员福利", "v": "zhuti_10664"}, {"n": "SM乱伦-经典演绎", "v": "zhuti_17503"}, {"n": "最新大作-不容错过", "v": "zhuti_10663"}, {"n": "SM丝足天花板", "v": "zhuti_17501"}, {"n": "SM半次元-Cosplay", "v": "zhuti_17504"}, {"n": "SM-官方严选", "v": "zhuti_10668"}, {"n": "全网探花集中营", "v": "zhuti_27109"}, {"n": "校园霸凌-校园不是乌托邦...", "v": "zhuti_27132"}],
            "12": [{"n": "菠萝啤", "v": "user_25111"}, {"n": "桥本香菜", "v": "user_13856"}, {"n": "饼干姐姐", "v": "user_11022"}, {"n": "情深叉喔", "v": "user_13859"}, {"n": "白菜妹妹", "v": "user_19192"}, {"n": "亦可姐姐", "v": "user_28811"}, {"n": "狐不妖", "v": "user_19051"}, {"n": "捅主任", "v": "user_13858"}, {"n": "黑椒盖饭", "v": "user_13853"}, {"n": "鸡教练", "v": "user_10921"}, {"n": "懒懒猪", "v": "user_13854"}, {"n": "糖糖", "v": "user_18851"}, {"n": "中南半島工作室", "v": "user_30891"}, {"n": "小奶茉", "v": "user_30890"}, {"n": "樱桃空空", "v": "user_30880"}, {"n": "花匠探花", "v": "user_30874"}, {"n": "SM-baby", "v": "user_30873"}, {"n": "辛尤里", "v": "user_19191"}, {"n": "香艳职场", "v": "user_30284"}, {"n": "阿朱", "v": "user_30437"}, {"n": "星十三", "v": "user_29174"}, {"n": "韦小宝", "v": "user_26076"}, {"n": "奶气草莓", "v": "user_26077"}, {"n": "老万", "v": "user_18852"}, {"n": "喜之郎", "v": "user_26073"}, {"n": "Pao泡糖", "v": "user_18715"}],
            "15": [{"n": "玩偶姐姐", "v": "user_24711"}, {"n": "COLA酱", "v": "user_25235"}, {"n": "小水水", "v": "user_26075"}, {"n": "妮可NicoLove", "v": "user_19132"}, {"n": "多乙", "v": "user_26155"}, {"n": "米菲兔", "v": "user_24652"}, {"n": "小敏儿", "v": "user_26154"}, {"n": "柚子猫yuzukitty", "v": "user_19131"}, {"n": "冉冉学姐", "v": "user_25234"}, {"n": "粉红兔 Pinkriabbit", "v": "user_29171"}, {"n": "pinkloving", "v": "user_14273"}, {"n": "Reislin", "v": "user_14272"}, {"n": "樱空桃桃", "v": "user_24653"}, {"n": "辛尤里", "v": "user_19191"}, {"n": "淫妻小鑫", "v": "user_26153"}, {"n": "ai美乳", "v": "user_26151"}],
            "25": [{"n": "奶气草莓", "v": "user_26077"}, {"n": "爱吃雪糕", "v": "user_29032"}, {"n": "老渣男", "v": "user_29031"}, {"n": "糖糖", "v": "user_18851"}, {"n": "喜之郎", "v": "user_26073"}, {"n": "芒果", "v": "user_29371"}, {"n": "我的姐姐会喷水", "v": "user_25991"}, {"n": "同城约炮", "v": "user_30451"}, {"n": "老六探花", "v": "user_30889"}, {"n": "Milk喵姐", "v": "user_30857"}, {"n": "浪味小仙女", "v": "user_30846"}, {"n": "魅狐姐姐", "v": "user_30848"}, {"n": "婉婉的性爱日记", "v": "user_30850"}, {"n": "小羊MM", "v": "user_30851"}, {"n": "熊猫可乐", "v": "user_30852"}, {"n": "意淫自己妹妹", "v": "user_30853"}, {"n": "真实小猫咪", "v": "user_30854"}, {"n": "小宝儿", "v": "user_30861"}, {"n": "辣妈榨精日记", "v": "user_30887"}, {"n": "ok先生", "v": "user_30888"}, {"n": "深情小吕布", "v": "user_30091"}, {"n": "好色星球", "v": "user_25232"}],
            "70": [{"n": "每日最新-抢先一步看🍵", "v": "zhuti_27116"}, {"n": "🔥AI消碼", "v": "zhuti_27058"}, {"n": "素人數人", "v": "zhuti_27056"}, {"n": "明里紬", "v": "zhuti_27084"}, {"n": "miru", "v": "zhuti_27074"}, {"n": "翼舞", "v": "zhuti_27072"}, {"n": "森沢佳奈", "v": "zhuti_27071"}, {"n": "河北彩伽", "v": "zhuti_27063"}, {"n": "仁藤さや香", "v": "zhuti_27059"}, {"n": "香水純", "v": "zhuti_27089"}, {"n": "水卜櫻", "v": "zhuti_27091"}, {"n": "七嶋舞", "v": "zhuti_27086"}, {"n": "楓花戀", "v": "zhuti_27055"}, {"n": "山岸逢花", "v": "zhuti_27061"}, {"n": "星乃夏月", "v": "zhuti_27098"}, {"n": "竹内有紀", "v": "zhuti_27096"}, {"n": "小宵虎南", "v": "zhuti_27094"}, {"n": "君島美緒", "v": "zhuti_27092"}, {"n": "小仓七海", "v": "zhuti_27090"}, {"n": "蜜美杏", "v": "zhuti_27057"}, {"n": "波多野結衣", "v": "zhuti_27060"}, {"n": "櫻井麻美", "v": "zhuti_27062"}, {"n": "三上悠亜", "v": "zhuti_27064"}, {"n": "神木丽", "v": "zhuti_27065"}, {"n": "夏木凛", "v": "zhuti_27066"}, {"n": "藍芽水月", "v": "zhuti_27067"}, {"n": "新井里真", "v": "zhuti_27068"}, {"n": "楪可憐", "v": "zhuti_27069"}, {"n": "深田詠美", "v": "zhuti_27070"}, {"n": "石川澪", "v": "zhuti_27073"}, {"n": "川上奈奈美", "v": "zhuti_27075"}, {"n": "天使萌", "v": "zhuti_27076"}, {"n": "愛弓涼", "v": "zhuti_27077"}, {"n": "青空光", "v": "zhuti_27078"}, {"n": "新有菜", "v": "zhuti_27079"}, {"n": "小倉由菜", "v": "zhuti_27080"}, {"n": "藤井一夜", "v": "zhuti_27081"}, {"n": "栗山莉緒", "v": "zhuti_27082"}, {"n": "涼森怜夢", "v": "zhuti_27083"}, {"n": "安齋拉拉", "v": "zhuti_27085"}],
            "21": [{"n": "热门推荐", "v": "cm_11241"}, {"n": "乱伦禁地", "v": "cm_11242"}, {"n": "极品尤物", "v": "cm_11244"}, {"n": "崇洋媚黑", "v": "cm_11544"}, {"n": "约炮偷腥", "v": "cm_11245"}, {"n": "熟女人妻", "v": "cm_29096"}, {"n": "丝足美腿", "v": "cm_28851"}, {"n": "白虎粉穴", "v": "cm_29097"}, {"n": "直播精选", "v": "cm_11543"}, {"n": "会所按摩", "v": "cm_29094"}, {"n": "Cosplay", "v": "cm_28111"}, {"n": "窥探性癖", "v": "cm_11545"}, {"n": "麻豆探花", "v": "cm_13601"}, {"n": "暗网解密", "v": "cm_11546"}, {"n": "三级片", "v": "cm_29101"}, {"n": "反差百科", "v": "cm_29100"}, {"n": "明星淫梦", "v": "cm_29099"}],
            "18": [{"n": "皇家华人", "v": "cm_11559"}, {"n": "蜜桃影像", "v": "cm_11547"}, {"n": "色控", "v": "cm_25781"}, {"n": "麻麻传媒", "v": "cm_28892"}, {"n": "爱豆团队", "v": "cm_28894"}, {"n": "绝对领域", "v": "cm_11552"}, {"n": "爱神传媒", "v": "cm_25790"}, {"n": "红斯灯影像", "v": "cm_11558"}, {"n": "辣椒原创", "v": "cm_11555"}, {"n": "星空传媒", "v": "cm_11587"}, {"n": "天美传媒", "v": "cm_11548"}, {"n": "精东影业", "v": "cm_11549"}, {"n": "果冻传媒", "v": "cm_11550"}, {"n": "长治传媒", "v": "cm_11551"}, {"n": "肉肉传媒", "v": "cm_11583"}, {"n": "蝌蚪传媒", "v": "cm_11586"}, {"n": "豚豚創媒", "v": "cm_11592"}, {"n": "兔子先生", "v": "cm_29102"}, {"n": "性世界", "v": "cm_29103"}, {"n": "扣扣传媒", "v": "cm_11584"}],
            "72": [{"n": "麻豆传媒", "v": "cm_28891"}, {"n": "吴梦梦", "v": "cm_28895"}, {"n": "MSD系列", "v": "cm_28896"}, {"n": "MDX系列", "v": "cm_29122"}, {"n": "MCY系列", "v": "cm_29123"}, {"n": "MKY全系列", "v": "cm_29124"}, {"n": "放浪传媒", "v": "cm_11556"}, {"n": "冠希传媒", "v": "cm_11557"}, {"n": "渡边传媒", "v": "cm_11582"}, {"n": "O-star", "v": "cm_11585"}, {"n": "AV帝王", "v": "cm_11588"}, {"n": "涩会", "v": "cm_11590"}, {"n": "叮叮映畫", "v": "cm_11591"}],
            "22": [{"n": "禁漫精选", "v": "cm_26413"}, {"n": "3D精选", "v": "cm_26314"}, {"n": "VAM同人", "v": "cm_26412"}, {"n": "原神", "v": "cm_26313"}, {"n": "斗罗大陆", "v": "cm_26316"}, {"n": "完美世界", "v": "cm_26312"}, {"n": "斗破苍穹", "v": "cm_26315"}],
            "23": [{"n": "欧美推荐", "v": "cm_25782"}, {"n": "黑白配", "v": "cm_25787"}, {"n": "街头搭讪", "v": "cm_25783"}, {"n": "欧美中字", "v": "cm_25784"}, {"n": "麻豆US", "v": "cm_25785"}, {"n": "欧美经典", "v": "cm_25786"}],
            "19": [{"n": "突袭女优家", "v": "cm_11611"}, {"n": "AV头条大事件", "v": "cm_11620"}, {"n": "鲍鱼的胜利", "v": "cm_11616"}, {"n": "小葛格東遊記Season2", "v": "cm_11613"}, {"n": "欲不可纵", "v": "cm_25789"}, {"n": "情趣K歌房", "v": "cm_11621"}, {"n": "经典节目-狼人插🐺", "v": "cm_11615"}, {"n": "大人学", "v": "cm_26512"}, {"n": "我是畅畅子", "v": "cm_26511"}, {"n": "性爱自修室", "v": "cm_12021"}, {"n": "男女优生死斗", "v": "cm_11625"}, {"n": "男优练习生-极乐天堂爭霸战", "v": "cm_11624"}, {"n": "AV没台词-开学荒淫健康检查", "v": "cm_11623"}, {"n": "Kiss糖果屋", "v": "cm_11622"}, {"n": "禁慾小屋", "v": "cm_11619"}, {"n": "心动的性号", "v": "cm_11618"}, {"n": "性爱自修室第二季", "v": "cm_11617"}, {"n": "野外露初-说走就走的约会露淫趣", "v": "cm_11614"}, {"n": "城市猎人-渣男极限约炮企划", "v": "cm_11612"}, {"n": "小葛格东游记Season3", "v": "cm_11593"}],
            "24": [{"n": "吃瓜黑料", "v": "cm_10666"}, {"n": "十八禁", "v": "cm_11541"}, {"n": "绿帽淫妻", "v": "cm_11542"}, {"n": "巨乳肥臀", "v": "cm_29093"}, {"n": "国产偷拍", "v": "cm_11243"}],
            "71": [{"n": "性虐SM", "v": "cm_29105"}, {"n": "菊门探秘", "v": "cm_29106"}, {"n": "虐阴", "v": "cm_29107"}, {"n": "女奴", "v": "cm_29108"}, {"n": "男奴", "v": "cm_29109"}, {"n": "重口猎奇", "v": "cm_29111"}, {"n": "孕妇", "v": "cm_29112"}, {"n": "醉酒捡尸", "v": "cm_29113"}, {"n": "强奸", "v": "cm_29114"}, {"n": "迷奸", "v": "cm_29115"}, {"n": "轮奸", "v": "cm_29116"}, {"n": "调教天堂", "v": "cm_29117"}, {"n": "户外系列", "v": "cm_29118"}, {"n": "人妖伪娘", "v": "cm_29119"}, {"n": "多P群交", "v": "cm_29098"}, {"n": "情色主播任你玩", "v": "cm_29120"}, {"n": "女同百合", "v": "cm_29121"}],
            "73": [{"n": "粉穴白虎一线天", "v": "zhuti_27134"}, {"n": "按摩会所-淫乱妓师", "v": "zhuti_27139"}, {"n": "美味小姨子", "v": "zhuti_27136"}, {"n": "偷情出轨", "v": "zhuti_27140"}, {"n": "约炮达人-金先生", "v": "zhuti_27133"}, {"n": "崇洋媚黑婊♠️", "v": "zhuti_27141"}, {"n": "不伦乱伦", "v": "zhuti_27158"}, {"n": "饥渴人妻", "v": "zhuti_27157"}, {"n": "母子春情", "v": "zhuti_27156"}, {"n": "丰韵熟女", "v": "zhuti_27155"}, {"n": "丝足美腿", "v": "zhuti_27154"}, {"n": "淫乱KTV", "v": "zhuti_27152"}, {"n": "探穴系列-小宝探花", "v": "zhuti_27151"}, {"n": "探花偷拍", "v": "zhuti_27150"}, {"n": "迷人御姐", "v": "zhuti_27149"}, {"n": "媚黑淫妻", "v": "zhuti_27148"}, {"n": "荒淫鬼父", "v": "zhuti_27147"}, {"n": "换妻群P", "v": "zhuti_27146"}, {"n": "好吃不过嫂子", "v": "zhuti_27145"}, {"n": "辣手摧花男技师", "v": "zhuti_27153"}, {"n": "富人圈-纸醉金迷", "v": "zhuti_27143"}, {"n": "顶级萝莉少女", "v": "zhuti_27142"}, {"n": "夫妻一家亲", "v": "zhuti_27135"}, {"n": "兄弟姐妹", "v": "zhuti_27138"}, {"n": "忘年师生恋", "v": "zhuti_27137"}],
            "104": [{"n": "变态家族", "v": "zhuti_27414"}, {"n": "地窖性奴", "v": "zhuti_27413"}, {"n": "人间炼狱", "v": "zhuti_27412"}, {"n": "灵异玄幻", "v": "zhuti_27411"}],
            "105": [{"n": "圣水", "v": "zhuti_27419"}, {"n": "羞辱", "v": "zhuti_27418"}, {"n": "耳光", "v": "zhuti_27417"}, {"n": "黄金", "v": "zhuti_27416"}, {"n": "拳交", "v": "zhuti_27415"}],
            "106": [{"n": "触手系列", "v": "zhuti_27426"}, {"n": "踩踏虐鸡", "v": "zhuti_27425"}, {"n": "窒息", "v": "zhuti_27424"}, {"n": "虐阴", "v": "zhuti_27423"}, {"n": "3D重口", "v": "zhuti_27422"}, {"n": "奇趣性爱", "v": "zhuti_27421"}, {"n": "重口调教", "v": "zhuti_27420"}],
            "107": [{"n": "粗暴强奸", "v": "zhuti_27431"}, {"n": "孕妇也疯狂", "v": "zhuti_27430"}, {"n": "摄像破解～监控偷拍", "v": "zhuti_27429"}, {"n": "换妻性爱", "v": "zhuti_27428"}]
        }

    def homeContent(self, filter):
        base_classes = [
            {"n": "推荐", "v": "9"}, {"n": "最新", "v": "20"}, {"n": "色点", "v": "73"},
            {"n": "热点", "v": "21"}, {"n": "原创", "v": "12"}, {"n": "大神投稿", "v": "25"},
            {"n": "华语", "v": "18"}, {"n": "日本", "v": "70"}, {"n": "网黄", "v": "15"},
            {"n": "广场", "v": "72"}, {"n": "动漫", "v": "22"}, {"n": "欧美", "v": "23"},
            {"n": "综艺", "v": "19"}, {"n": "热门推荐", "v": "24"}, {"n": "性癖猎奇", "v": "71"},
            {"n": "萝莉吃瓜", "v": "103"}, {"n": "外网禁片", "v": "104"},
            {"n": "凌辱调教", "v": "105"}, {"n": "变态另类", "v": "106"},
            {"n": "猎奇性爱", "v": "107"}
        ]
        classes = [{"type_name": c["n"], "type_id": f"movie_{c['v']}"} for c in base_classes] + [{"type_name": "短视频", "type_id": "tik_001"}, {"type_name": "直播", "type_id": "live_001"}]
        subs_dict, filters = self.get_subs_dict(), {}
        for c in base_classes:
            cid, t_id = c["v"], f"movie_{c['v']}"
            cls_f = [{"key": "sub_cid", "name": "标签", "value": subs_dict[cid]}] if cid in subs_dict else []
            cls_f.append({"key": "sort", "name": "排序", "value": [{"n": "最新", "v": "zx"}, {"n": "推荐", "v": "tj"}, {"n": "随机", "v": "rand"}]})
            filters[t_id] = cls_f
        filters["tik_001"] = [{"key": "sub_cid", "name": "模式", "value": [{"n": "最新短片", "v": "zuixin"}, {"n": "热门推荐", "v": "rand"}]}]
        filters["live_001"] = [{"key": "sub_cid", "name": "频道", "value": [{"n": "推荐", "v": "10041"}, {"n": "最热", "v": "10105"}, {"n": "新主播", "v": "10103"}, {"n": "中国", "v": "10042"}, {"n": "日本", "v": "10106"}, {"n": "乌克兰", "v": "10102"}]}]
        return {'class': classes, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        result, sub_cid = {'list': [], 'page': int(pg), 'pagecount': 99}, extend.get('sub_cid', '')
        if tid == "live_001":
            items = self._live_get(f"local_live/fldata/{sub_cid or '10041'}/{pg}/20").get("list", [])
            for v in (items if isinstance(items, list) else []):
                if not isinstance(v, dict) or not v.get('id'): continue
                vod_name, pic_url, stream, viewers = str(v.get('username') or v.get('nickname') or '主播'), v.get('snapshot') or v.get('avatarUrl') or "", v.get('stream') or "", v.get('viewersCount', 0)
                pic_proxy = self.getProxyUrl() + "&url=" + quote(pic_url) if pic_url else ""
                result['list'].append({'vod_id': f"live@@{v['id']}@@{quote(stream)}@@{quote(vod_name)}@@{quote(pic_proxy)}@@{quote(f'👁️ 在线人数: {viewers}')}", 'vod_name': vod_name, 'vod_pic': pic_proxy, 'vod_remarks': f"👁️ {viewers}人在线"})
            return result
        if tid == "tik_001":
            data = self._post(f"tik/zuixin/{pg}/15/time") if (sub_cid or "zuixin") == "zuixin" else self._post("tik/rand/15")
            items = (data.get("records") if (sub_cid or "zuixin") == "zuixin" else data.get("tik")) or []
            for item in (items if isinstance(items, list) else []):
                if not isinstance(item, dict): continue
                v = item.get("dataTik") or item.get("movie") or item
                if not isinstance(v, dict) or not v.get('id') or "未知" in str(v.get('id')): continue
                pic_url, movie_url, vod_name = v.get("imgurl") or v.get("pic") or "", v.get('movieurl') or v.get("play_url") or "", str(v.get('title') or v.get('name') or '短视频')
                pic_proxy = self.getProxyUrl() + "&url=" + quote(pic_url) if pic_url else ""
                result['list'].append({'vod_id': f"movie@@{v['id']}@@{movie_url}@@{quote(vod_name)}@@{quote(pic_proxy)}@@{quote(str(v.get('miaoshu', '')))}", 'vod_name': vod_name, 'vod_pic': pic_proxy, 'vod_remarks': "短视频"})
            return result

        cid, sort_by = tid.split('_')[1], extend.get('sort', 'zx')
        subs_dict = self.get_subs_dict()
        if not sub_cid and cid in subs_dict: sub_cid = subs_dict[cid][0]["v"]
        
        if sub_cid:
            if sub_cid.startswith('cm_'): data = self._post(f"movie/cmdata/{sub_cid[3:]}/{pg}/15/{sort_by}")
            elif sub_cid.startswith('zhuti_'): data = self._post(f"movie/moredata/{sub_cid[6:]}/{pg}/15/{sort_by}")
            elif sub_cid.startswith('user_'): data = self._post(f"movieUser/moredata/{sub_cid[5:]}/{pg}/15/{sort_by}")
            else: data = {}
            data_list = data.get("list") or data.get("records") or [] if isinstance(data, dict) else []
        else:
            data = self._post(f"movie/fengleidataShow/{cid}/{pg}/15/{sort_by}")
            data_list = data.get("movieList") or data.get("list") or data.get("records") or [] if isinstance(data, dict) else []

        for item in data_list:
            if not isinstance(item, dict): continue
            v = item.get("movie") or item
            if not isinstance(v, dict) or not v.get('id') or "未知" in str(v.get('id')): continue
            pic_url, movie_url, vod_name = v.get("imgurl") or v.get("pic") or "", v.get('movieurl') or v.get("play_url") or "", str(v.get('title') or v.get('name') or '未知')
            pic_proxy = self.getProxyUrl() + "&url=" + quote(pic_url) if pic_url else ""
            result['list'].append({'vod_id': f"movie@@{v['id']}@@{movie_url}@@{quote(vod_name)}@@{quote(pic_proxy)}@@{quote(str(v.get('miaoshu', '')))}", 'vod_name': vod_name, 'vod_pic': pic_proxy, 'vod_remarks': f"{v.get('creatTime', '')[:10]} | {v.get('duration', '')}"})
        return result

    def detailContent(self, ids):
        if str(ids[0]).startswith("http"): return {'list': [{'vod_id': ids[0], 'vod_name': '详情', 'vod_play_from': '土豆直连', 'vod_play_url': f"点击播放${ids[0]}"}]}
        p = ids[0].split("@@")
        prefix, movie_url, vod_name, vod_pic, miaoshu = p[0] if p else "movie", unquote(p[2]) if len(p) > 2 else "", unquote(p[3]) if len(p) > 3 else "详情", unquote(p[4]) if len(p) > 4 else "", unquote(p[5]) if len(p) > 5 else ""
        is_live = (prefix == "live")
        vod_content = miaoshu if miaoshu else ("直播直连播放" if is_live else "土豆视频，点击直连播放！") if movie_url else "⚠️ 暂无可用流地址，请稍后重试。"
        return {'list': [{'vod_id': ids[0], 'vod_name': vod_name, 'vod_pic': vod_pic, 'vod_play_from': "直播专线" if is_live else "土豆专线", 'vod_content': vod_content, 'vod_play_url': f"直接播放${movie_url}" if movie_url else f"暂无流$about:blank"}]}

    def searchContent(self, key, quick, pg="1"):
        result = {'list': [], 'page': int(pg)}
        try:
            res = self.session.post(f"{self.host_base}/movie/searchv2/{pg}/15/time", headers=self.get_headers(), json={"name": base64.b64encode(key.encode('utf-8')).decode('utf-8')}, verify=False, timeout=10).json()
            data = self._decrypt_api_data(res.get("data", "")) if res.get("enc") else res.get("data", {})
            for item in (data.get("records") if isinstance(data, dict) else []):
                movie = item.get("movie", {})
                if not movie or not movie.get('id'): continue
                pic_url, vod_name = movie.get("imgurl", ""), str(movie.get("title", "未知"))
                pic_proxy = self.getProxyUrl() + "&url=" + quote(pic_url) if pic_url else ""
                result['list'].append({'vod_id': f"movie@@{movie['id']}@@{movie.get('movieurl', '')}@@{quote(vod_name)}@@{quote(pic_proxy)}@@{quote(str(movie.get('miaoshu', '')))}", 'vod_name': vod_name, 'vod_pic': pic_proxy, 'vod_remarks': movie.get('duration', '点击查看')})
        except:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        if str(id).startswith("http"): return {'parse': 0, 'url': id, 'header': ''}
        p = str(id).split("@@")
        if len(p) > 2 and unquote(p[2]).startswith("http"): return {'parse': 0, 'url': unquote(p[2]), 'header': ''}
        return {'parse': 0, 'url': id, 'header': ''}

    def localProxy(self, param):
        url = unquote(param.get('url', ''))
        if not url: return [404, "text/plain", b""]
        try:
            content = self.session.get(url, verify=False, headers=self.get_headers(), timeout=8).content
            if not content: return [404, "text/plain", b""]
            if '.html' in url:
                try: content = base64.b64decode(content)
                except: pass
            else:
                try:
                    if not content.startswith((b'\xff\xd8', b'\x89PNG', b'GIF8', b'BM')) and b'WEBP' not in content[:20]:
                        out, limit = bytearray(content), min(100, len(content))
                        for i in range(limit): out[i] ^= self.xor_key[i % len(self.xor_key)]
                        content = bytes(out)
                except: pass
            return [200, "image/png" if content.startswith(b'\x89PNG') else "image/jpeg", content]
        except Exception as e:
            return [500, "text/plain", str(e).encode('utf-8')]

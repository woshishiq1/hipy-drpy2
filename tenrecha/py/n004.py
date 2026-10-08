import json, base64, re, time
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class Spider:
    API_BASE = "https://0lyjne.941ct.cc/api"
    HOST = "https://0lyjne.941ct.cc"
    AES_KEY = b"a9yX32LpQvUt7wBc"
    AES_IV = b"N7cPk2Bv38hWqFzM"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    MINOR_IDS = {"2219", "2218", "2185", "2805"}
    CLASSICAL_MAP = {
        "成人": "风月", "色情": "春宫", "性爱": "云雨", "淫": "风月", "黄色": "春宫",
        "淫秽": "猥亵", "激情": "云雨", "做爱": "云雨", "性交": "交欢", "性行为": "云雨",
        "欲": "情思", "高潮": "云端", "偷拍": "窥帘", "偷窥": "窥帘",
        "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱", "迷奸": "迷占",
        "无码": "素纱", "有码": "遮面", "熟女": "徐娘", "萝莉": "豆蔻",
        "幼女": "玉蕊", "少女": "碧玉", "学生": "书生", "人妻": "罗敷",
        "少妇": "艳妇", "御姐": "玉人", "护士": "药女", "教师": "先生",
        "医生": "郎中", "警察": "捕快", "军人": "军爷", "秘书": "掌印",
        "老板": "东家", "丈夫": "夫君", "妻子": "拙荆", "情人": "相好",
        "小三": "外遇", "二奶": "外室", "出轨": "翻墙", "偷情": "私会",
        "通奸": "私通", "嫖娼": "寻花", "卖淫": "卖身", "妓女": "花娘",
        "性骚扰": "轻薄", "猥亵": "猥亵", "露阴": "曝玉", "咸猪手": "禄山爪",
        "丝袜": "丝履", "网袜": "网履", "内衣": "亵衣", "内裤": "亵裤",
        "情趣": "风月", "春药": "催情", "巨乳": "丰盈", "爆乳": "丰盈",
        "胸": "酥胸", "乳": "玉兔", "美乳": "玉兔", "臀": "玉臀",
        "屁股": "玉臀", "脚": "莲步", "玉足": "莲步", "腿": "玉腿",
        "裸体": "玉体", "全裸": "玉体", "半裸": "半褪", "走光": "泄春",
        "露点": "泄玉", "自慰": "弄玉", "口交": "含朱", "口活": "含朱",
        "肛交": "后庭", "屁眼": "后庭", "肛门": "后庭", "群交": "合卺",
        "乳交": "玉兔", "足交": "莲步", "车震": "车行", "野战": "郊合",
        "精液": "元阳", "精子": "元阳", "阴道": "幽处", "阴户": "幽处",
        "阴茎": "玉茎", "阳具": "玉茎", "SM": "调教", "制服": "官衣",
        "OL": "衙内", "空姐": "行云", "继母": "继室", "姐妹": "同根",
        "同学": "同窗", "邻居": "东邻", "处女": "处子", "初夜": "破瓜",
        "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥", "赌博": "孤注",
        "毒品": "药石", "枪支": "火器", "刀具": "利刃", "国产": "华夏",
        "日韩": "东瀛", "欧美": "西洋", "港台": "香江", "动漫": "丹青",
        "综艺": "百戏", "电视剧": "传奇", "电影": "光影", "约炮": "私会",
        "裸聊": "玉聊", "露出": "泄春", "盗摄": "盗摄", "换脸": "换脸",
        "多P": "多P", "母狗": "母狗", "绿帽": "绿帽", "会所": "会所",
        "技师": "技师", "厂牌": "厂牌", "传媒": "传媒", "剧情": "剧情",
        "主播": "主播", "网红": "网红", "诱惑": "诱惑", "吃瓜": "吃瓜",
        "黑料": "黑料", "网曝": "网曝", "社区": "社区", "头条": "头条",
        "原创": "原创", "精品": "精品", "推荐": "推荐", "超清": "超清",
        "自拍": "自拍", "短片": "短片", "探花": "探花", "国内": "华夏",
        "华语": "华语", "皇家": "皇家", "华人": "华人", "星空": "星空",
        "焦点": "焦点", "海角": "海角", "乌鸦": "乌鸦", "兔子": "兔子",
        "先生": "先生", "杏吧": "杏吧", "玩偶": "玩偶", "姐姐": "姐姐",
        "大象": "大象", "开心鬼": "开心鬼", "糖心": "糖心", "性视界": "风月视界",
        "小学生": "稚子", "学妹": "书生", "粉穴": "粉穴",
    }
    _cache = {}
    _cache_ttl = 60

    def getDependence(self):
        return ""

    def init(self, extend):
        self.extend = extend or {}
        if isinstance(extend, str):
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        self._session = self._make_session()
        self._warmup()

    def _make_session(self):
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": self.HOST + "/",
        })
        return s

    def _warmup(self):
        try:
            self._fetch("/config")
        except Exception:
            pass

    def _decrypt(self, cipher_b64):
        raw = base64.b64decode(cipher_b64)
        cipher = AES.new(self.AES_KEY, AES.MODE_CBC, self.AES_IV)
        dec = unpad(cipher.decrypt(raw), 16)
        return json.loads(dec.decode("utf-8"))

    def _fetch(self, path, params=None):
        url = self.API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        cache_key = url
        now = time.time()
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["t"] < self._cache_ttl:
                return entry["d"]
        r = self._session.get(url, timeout=15)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and "cipher" in j:
            d = self._decrypt(j["cipher"])
            data = d.get("data", d)
        elif isinstance(j, dict) and "code" in j and "data" in j:
            if j["code"] != 0:
                raise Exception(f"API error {j['code']}: {j.get('msg','')}")
            data = j["data"]
        else:
            data = j
        self._cache[cache_key] = {"t": now, "d": data}
        if len(self._cache) > 24:
            oldest = min(self._cache, key=lambda k: self._cache[k]["t"])
            del self._cache[oldest]
        return data

    def desensitize(self, text):
        if not text or not isinstance(text, str):
            return text
        result = text
        for k, v in self.CLASSICAL_MAP.items():
            if k in result:
                result = result.replace(k, v)
        return result

    def _is_minor(self, text):
        if not text:
            return False
        minor_words = ["萝莉", "幼女", "少女", "学生", "小学生", "学妹", "童",
                       "teen", "loli", "schoolgirl", "豆蔻", "玉蕊", "碧玉", "书生", "稚子"]
        text_lower = text.lower()
        return any(w in text_lower for w in minor_words)

    def _vod_from_item(self, item):
        title = self.desensitize(item.get("title", ""))
        if self._is_minor(title):
            return None
        cat = self.desensitize(item.get("category", ""))
        if self._is_minor(cat):
            return None
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": title,
            "vod_pic": item.get("cover_url", ""),
            "vod_remarks": cat,
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
        }

    def homeContent(self, filter=False):
        cats_data = self._fetch("/categories", {"limit": 100})
        class_list = []
        filters = {}
        for c in cats_data.get("list", []):
            if c.get("module") != "video":
                continue
            cid = str(c.get("id", ""))
            if cid in self.MINOR_IDS:
                continue
            cname = self.desensitize(c.get("name", ""))
            if self._is_minor(cname):
                continue
            class_list.append({"type_id": cid, "type_name": cname})
            filters[cid] = [
                {"key": "sort", "name": "排序", "init": "", "value": [
                    {"n": "最新", "v": "new"},
                    {"n": "最热", "v": "hot"},
                ]}
            ]
        rec_data = self._fetch("/videos", {"page": 1, "limit": 20})
        vod_list = []
        for item in rec_data.get("list", []):
            v = self._vod_from_item(item)
            if v:
                vod_list.append(v)
        return {"class": class_list, "filters": filters, "list": vod_list}

    def homeVideoContent(self):
        data = self._fetch("/videos", {"page": 1, "limit": 20})
        vod_list = []
        for item in data.get("list", []):
            v = self._vod_from_item(item)
            if v:
                vod_list.append(v)
        total = data.get("total", 0)
        pages = data.get("pages", 1)
        return {"page": 1, "pagecount": pages, "limit": 20, "total": total, "list": vod_list}

    def categoryContent(self, tid, pg, filter, extend):
        params = {"category_id": tid, "page": pg, "limit": 20}
        if extend and isinstance(extend, dict):
            sort = extend.get("sort", "")
            if sort == "hot":
                params["sort"] = "hits"
        data = self._fetch("/videos", params)
        vod_list = []
        for item in data.get("list", []):
            v = self._vod_from_item(item)
            if v:
                vod_list.append(v)
        page = data.get("page", pg)
        pages = data.get("pages", 1)
        total = data.get("total", 0)
        return {"page": page, "pagecount": pages, "limit": 20, "total": total, "list": vod_list}

    def detailContent(self, ids):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        results = []
        for vid in ids:
            vid = str(vid)
            try:
                data = self._fetch("/movie", {"id": vid})
            except Exception:
                continue
            info = data.get("info", {})
            title = self.desensitize(info.get("title", ""))
            if self._is_minor(title):
                continue
            cat = self.desensitize(info.get("category", ""))
            play_url = info.get("play_url", "")
            play_from = info.get("play_from", "m3u8") or "m3u8"
            if not play_url:
                continue
            vod = {
                "vod_id": str(info.get("id", "")),
                "vod_name": title,
                "vod_pic": info.get("cover_url", ""),
                "vod_remarks": cat,
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": title,
                "vod_play_from": play_from,
                "vod_play_url": "正片$" + play_url,
            }
            results.append(vod)
        return {"list": results}

    def searchContent(self, key, quick=False):
        params = {"kw": key, "page": 1, "limit": 20}
        data = self._fetch("/videos", params)
        vod_list = []
        for item in data.get("list", []):
            v = self._vod_from_item(item)
            if v:
                vod_list.append(v)
        total = data.get("total", 0)
        pages = data.get("pages", 1)
        return {"page": 1, "pagecount": pages, "limit": 20, "total": total, "list": vod_list}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            },
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        try:
            if param.startswith("http"):
                url = param
            elif param.startswith("cover/"):
                url = "https://" + param[len("cover/"):]
            else:
                url = param
            r = self._session.get(url, timeout=10)
            if r.status_code == 200:
                ctype = r.headers.get("Content-Type", "image/jpeg")
                return {"code": 200, "content": r.content, "headers": {"Content-Type": ctype}}
        except Exception:
            pass
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or url.endswith(".mp4") or ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        try:
            self._session.close()
        except Exception:
            pass

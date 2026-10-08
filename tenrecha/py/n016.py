# -*- coding: utf-8 -*-
"""
弟大勿勃 - 四壳通用Python Spider
站点类型: 苹果CMS v10 (maccms)
协议: TVBox/影视仓/OK影视/PickTV 四壳通用
"""

import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup


class Spider:
    """四壳通用Spider - 独立类不继承base.spider"""

    # 古典映射脱敏字典 (铁律11)
    CLASSICAL_MAP = {
        "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫",
        "淫秽": "猥亵", "激情": "云雨", "做爱": "云雨", "性交": "交欢",
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
        "毒品": "药石", "枪支": "火器", "刀具": "利刃",
        "国产": "华夏", "日韩": "东瀛", "欧美": "西洋", "港台": "香江",
        "动漫": "丹青", "综艺": "百戏", "电视剧": "传奇", "电影": "光影",
        "情色": "风月", "自淫": "弄玉", "捆绑": "束缚",
    }

    # 未成年相关关键词 (铁律13 - 脱敏后跳过)
    MINOR_KEYWORDS = ["豆蔻", "玉蕊", "碧玉", "书生", "稚子", "未成年", "teen", "loli", "schoolgirl", "学生妹", "少女", "萝莉", "幼女", "童"]

    def __init__(self):
        self.siteName = "弟大勿勃"
        self.baseUrl = "https://iiv.ddwb8.best/cn/home/web"
        self.rawSite = "https://iiv.ddwb8.best"
        self.session = requests.Session()
        self.session.trust_env = False  # 禁用环境变量代理，直连目标
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.proxy = None
        self.siteUrl = self.baseUrl

    def desensitize(self, text):
        """古典映射脱敏 (铁律11)"""
        if not text:
            return text
        result = str(text)
        for key, value in self.CLASSICAL_MAP.items():
            result = result.replace(key, value)
        return result

    def is_minor_content(self, text):
        """检测是否含未成年相关内容 (铁律13)"""
        if not text:
            return False
        text_lower = str(text).lower()
        for kw in self.MINOR_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def _get(self, url, timeout=15):
        """HTTP GET请求"""
        try:
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = self.session.get(url, timeout=timeout, proxies=proxies, verify=False)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            return ""

    def _parse_list(self, html):
        """解析视频列表"""
        vod_list = []
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".fed-list-item")
        for item in items:
            try:
                link_tag = item.select_one(".fed-list-pics")
                title_tag = item.select_one(".fed-list-title")
                if not link_tag or not title_tag:
                    continue
                href = link_tag.get("href", "")
                vod_id_match = re.search(r"/id/(\d+)", href)
                if not vod_id_match:
                    continue
                vod_id = vod_id_match.group(1)
                vod_name = title_tag.get_text(strip=True)
                # 未成年内容跳过 (铁律13)
                if self.is_minor_content(vod_name):
                    continue
                vod_pic = link_tag.get("data-original", "")
                if not vod_pic:
                    img = link_tag.find("img")
                    if img:
                        vod_pic = img.get("src", "")
                desc_tag = item.select_one(".fed-list-desc")
                vod_remarks = desc_tag.get_text(strip=True) if desc_tag else ""
                score_tag = item.select_one(".fed-list-score")
                if score_tag:
                    vod_remarks = (vod_remarks + " " + score_tag.get_text(strip=True)).strip()
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": self.desensitize(vod_name),
                    "vod_pic": vod_pic,
                    "vod_remarks": self.desensitize(vod_remarks),
                })
            except Exception:
                continue
        return vod_list

    def _parse_pagination(self, html):
        """解析分页信息"""
        page = 1
        pagecount = 1
        limit = 24
        total = 0
        soup = BeautifulSoup(html, "html.parser")
        # 查找最后一页链接
        last_links = soup.select('a[href*="/page/"]')
        max_page = 1
        for link in last_links:
            href = link.get("href", "")
            page_match = re.search(r"/page/(\d+)", href)
            if page_match:
                p = int(page_match.group(1))
                if p > max_page:
                    max_page = p
        pagecount = max_page
        total = pagecount * limit
        return page, pagecount, limit, total

    # ==================== 四壳协议13接口 ====================

    def init(self, extend):
        """初始化接口"""
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if isinstance(extend, dict):
                if extend.get("proxy"):
                    self.proxy = extend["proxy"]
                if extend.get("siteUrl"):
                    self.siteUrl = extend["siteUrl"]
                    self.baseUrl = extend["siteUrl"]
                if extend.get("direct"):
                    self.proxy = None
        return None

    def homeContent(self, filter=False):
        """首页内容 - 返回class + filters"""
        result = {}
        classes = [
            {"type_id": "20", "type_name": self.desensitize("美女写真")},
            {"type_id": "21", "type_name": self.desensitize("国产精品")},
            {"type_id": "22", "type_name": self.desensitize("无码专区")},
            {"type_id": "23", "type_name": self.desensitize("中文字幕")},
            {"type_id": "24", "type_name": self.desensitize("强奸乱伦")},
            {"type_id": "25", "type_name": self.desensitize("人妻熟女")},
            {"type_id": "26", "type_name": self.desensitize("亚洲情色")},
            {"type_id": "27", "type_name": self.desensitize("制服丝袜")},
            {"type_id": "28", "type_name": self.desensitize("SM捆绑")},
            {"type_id": "29", "type_name": self.desensitize("自淫系列")},
            {"type_id": "30", "type_name": self.desensitize("三级伦理")},
        ]
        result["class"] = classes

        # filters为dict (铁律8)
        filters = {}
        for cls in classes:
            filters[cls["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        result["filters"] = filters

        # 首页最近更新列表
        html = self._get(self.baseUrl + "/")
        if html:
            result["list"] = self._parse_list(html)
        else:
            result["list"] = []

        return result

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容 - 返回五键"""
        if not pg or pg == "0":
            pg = "1"
        url = f"{self.baseUrl}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._get(url)
        vod_list = self._parse_list(html) if html else []
        page, pagecount, limit, total = self._parse_pagination(html) if html else (int(pg), 1, 24, 0)
        return {
            "page": int(pg),
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
            "list": vod_list,
        }

    def detailContent(self, ids):
        """详情内容 - 必须遍历ids (铁律8)"""
        result = {"list": []}
        if not ids:
            return result
        # ids是list/tuple必须遍历
        if isinstance(ids, (list, tuple)):
            id_list = list(ids)
        else:
            id_list = [str(ids)]

        for vod_id in id_list:
            try:
                vod_id = str(vod_id).strip()
                if not vod_id:
                    continue
                # 访问播放页获取播放地址
                play_url = f"{self.baseUrl}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
                html = self._get(play_url)
                if not html:
                    continue

                # 提取player_data
                player_match = re.search(r'var\s+player_data\s*=\s*(\{.*?\})', html, re.DOTALL)
                play_url_final = ""
                if player_match:
                    try:
                        player_data = json.loads(player_match.group(1))
                        play_url_final = player_data.get("url", "")
                    except Exception:
                        url_match = re.search(r'"url"\s*:\s*"([^"]+)"', player_match.group(1))
                        if url_match:
                            play_url_final = url_match.group(1).replace("\\/", "/")

                # 解析详情信息
                soup = BeautifulSoup(html, "html.parser")
                vod_name = ""
                title_tag = soup.select_one(".fed-play-text")
                if title_tag:
                    vod_name = title_tag.get_text(strip=True)
                if not vod_name:
                    h3_tag = soup.select_one(".fed-deta-content h3 a")
                    if h3_tag:
                        vod_name = h3_tag.get_text(strip=True)

                # 未成年内容跳过 (铁律13)
                if self.is_minor_content(vod_name):
                    continue

                vod_pic = ""
                pic_tag = soup.select_one(".fed-deta-images .fed-list-pics")
                if pic_tag:
                    vod_pic = pic_tag.get("data-original", "")

                # 解析详情字段
                vod_actor = "未知"
                vod_director = "未知"
                vod_content = ""
                vod_year = ""
                vod_area = ""
                type_name = ""

                detail_items = soup.select(".fed-deta-content li")
                for item in detail_items:
                    text = item.get_text(strip=True)
                    if "主演" in text:
                        vod_actor = text.replace("主演：", "").strip()
                    elif "导演" in text:
                        vod_director = text.replace("导演：", "").strip()
                    elif "分类" in text:
                        type_tag = item.find("a")
                        if type_tag:
                            type_name = type_tag.get_text(strip=True)
                    elif "地区" in text:
                        vod_area = text.replace("地区：", "").strip()
                    elif "年份" in text:
                        year_tag = item.find("a")
                        if year_tag:
                            vod_year = year_tag.get_text(strip=True)

                # 简介
                content_tag = soup.select_one(".fed-conv-text")
                if content_tag:
                    vod_content = content_tag.get_text(strip=True)

                # 播放线路 - 单线路单集
                vod_play_from = "ckplayer"
                if play_url_final:
                    vod_play_url = f"第1集${play_url_final}"
                else:
                    vod_play_url = ""

                detail = {
                    "vod_id": vod_id,
                    "vod_name": self.desensitize(vod_name),
                    "vod_pic": vod_pic,
                    "type_name": self.desensitize(type_name),
                    "vod_year": vod_year,
                    "vod_area": vod_area,
                    "vod_actor": self.desensitize(vod_actor),
                    "vod_director": self.desensitize(vod_director),
                    "vod_content": self.desensitize(vod_content),
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                    "vod_remarks": "",
                }
                result["list"].append(detail)
            except Exception:
                continue

        return result

    def searchContent(self, key, quick=False):
        """搜索内容"""
        encoded_key = urllib.parse.quote(key)
        url = f"{self.baseUrl}/index.php/vod/search/wd/{encoded_key}.html"
        html = self._get(url)
        vod_list = self._parse_list(html) if html else []
        page, pagecount, limit, total = self._parse_pagination(html) if html else (1, 1, 24, len(vod_list))
        return {
            "page": 1,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
            "list": vod_list,
        }

    def playerContent(self, flag, id, vipFlags):
        """播放内容 - parse=0/jx=0/url/header"""
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {
                "User-Agent": self.session.headers["User-Agent"],
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
        }

    def getDependence(self):
        """依赖声明"""
        return "requests,beautifulsoup4"

    def localProxy(self, param):
        """本地代理 - m3u8广告清洗 (铁律8建议项)"""
        try:
            if not param or not param.get("url"):
                return [404, "text/plain", ""]
            url = param["url"]
            # 简单透传，运行时auto智能清洗
            resp = self.session.get(url, timeout=15, headers={
                "User-Agent": self.session.headers["User-Agent"],
                "Referer": self.rawSite + "/",
            })
            content = resp.text
            content_type = resp.headers.get("Content-Type", "application/vnd.apple.mpegurl")
            return [200, content_type, content]
        except Exception:
            return [404, "text/plain", ""]

    def destroy(self):
        """销毁"""
        try:
            self.session.close()
        except Exception:
            pass
        return None

    def isVideoFormat(self, url):
        """判断是否视频格式"""
        if not url:
            return False
        video_exts = [".m3u8", ".mp4", ".ts", ".flv", ".mkv", ".avi", ".mov", ".wmv"]
        url_lower = url.lower()
        for ext in video_exts:
            if ext in url_lower:
                return True
        return False

    def getProxyUrl(self, url):
        """获取代理URL"""
        return url

    def getName(self):
        """获取站点名称"""
        return self.siteName

    def getApp(self):
        """获取APP标识"""
        return "tvbox"


# ==================== 本地测试入口 ====================
if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sp = Spider()
    print("=== 站点名称 ===")
    print(sp.getName())

    print("\n=== 首页分类 ===")
    home = sp.homeContent()
    for c in home.get("class", []):
        print(f"  {c['type_id']}: {c['type_name']}")
    print(f"  首页列表数: {len(home.get('list', []))}")

    print("\n=== 分类页测试 (id=21, page=1) ===")
    cat = sp.categoryContent("21", "1", False, {})
    print(f"  page={cat['page']}, pagecount={cat['pagecount']}, total={cat['total']}")
    print(f"  列表数: {len(cat['list'])}")
    if cat["list"]:
        print(f"  第一条: {cat['list'][0]['vod_name']} (id={cat['list'][0]['vod_id']})")

    print("\n=== 详情页测试 ===")
    if cat["list"]:
        test_id = cat["list"][0]["vod_id"]
        detail = sp.detailContent([test_id])
        if detail["list"]:
            d = detail["list"][0]
            print(f"  标题: {d['vod_name']}")
            print(f"  分类: {d['type_name']}")
            print(f"  播放源: {d['vod_play_from']}")
            print(f"  播放地址: {d['vod_play_url'][:80]}..." if len(d['vod_play_url']) > 80 else f"  播放地址: {d['vod_play_url']}")

    print("\n=== 搜索测试 ===")
    search = sp.searchContent("人妻")
    print(f"  搜索结果数: {len(search['list'])}")
    if search["list"]:
        print(f"  第一条: {search['list'][0]['vod_name']}")

    print("\n=== 脱敏测试 ===")
    test_texts = ["无码专区", "强奸乱伦", "人妻熟女", "制服丝袜", "SM捆绑", "自淫系列"]
    for t in test_texts:
        print(f"  {t} -> {sp.desensitize(t)}")

    print("\n=== 全部测试完成 ===")

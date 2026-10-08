# -*- coding: utf-8 -*-
"""
集芳阁 TVBox 四壳通用 Python Spider
站点: https://dna.jfg4.quest/vod/
类型: 自定义CMS影视站（HTML直出，DPlayer+HLS）
广告预检: has_ads=True, score=72, confidence=高, 命中特征: 前4段未加密(METHOD=NONE)+路径异于正片+DISCONTINUITY后AES-128加密正片+短时长贴片(约14秒)
Cloudflare: 站点位于CF后，内容路径(/vod/、/vodtype/、/s/、详情页)使用移动端UA可直连，/jfg/入口路径被CF 403封禁；默认直连，失败自动回退反代
"""

import re
import json
import urllib.parse
import urllib.request
import gzip
import io
import ssl
import os
import sys

class Spider:
    """集芳阁 四壳通用 Spider（独立类，不继承 base.spider）"""

    # ========== 古典映射脱敏表（铁律11，类内置） ==========
    CLASSICAL_MAP = {
        "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
        "激情": "云雨", "做爱": "云雨", "性交": "交欢", "欲": "情思", "高潮": "云端",
        "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱",
        "迷奸": "迷占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘", "萝莉": "豆蔻",
        "幼女": "玉蕊", "少女": "碧玉", "学生": "书生", "人妻": "罗敷", "少妇": "艳妇",
        "御姐": "玉人", "护士": "药女", "教师": "先生", "医生": "郎中", "警察": "捕快",
        "军人": "军爷", "秘书": "掌印", "老板": "东家", "丈夫": "夫君", "妻子": "拙荆",
        "情人": "相好", "小三": "外遇", "二奶": "外室", "出轨": "翻墙", "偷情": "私会",
        "通奸": "私通", "嫖娼": "寻花", "卖淫": "卖身", "妓女": "花娘", "性骚扰": "轻薄",
        "猥亵": "猥亵", "露阴": "曝玉", "咸猪手": "禄山爪", "丝袜": "丝履", "网袜": "网履",
        "内衣": "亵衣", "内裤": "亵裤", "情趣": "风月", "春药": "催情", "巨乳": "丰盈",
        "爆乳": "丰盈", "胸": "酥胸", "乳": "玉兔", "美乳": "玉兔", "臀": "玉臀",
        "屁股": "玉臀", "脚": "莲步", "玉足": "莲步", "腿": "玉腿", "裸体": "玉体",
        "全裸": "玉体", "半裸": "半褪", "走光": "泄春", "露点": "泄玉", "自慰": "弄玉",
        "口交": "含朱", "口活": "含朱", "肛交": "后庭", "屁眼": "后庭", "肛门": "后庭",
        "群交": "合卺", "乳交": "玉兔", "足交": "莲步", "车震": "车行", "野战": "郊合",
        "精液": "元阳", "精子": "元阳", "阴道": "幽处", "阴户": "幽处", "阴茎": "玉茎",
        "阳具": "玉茎", "SM": "调教", "制服": "官衣", "OL": "衙内", "空姐": "行云",
        "继母": "继室", "姐妹": "同根", "同学": "同窗", "邻居": "东邻", "处女": "处子",
        "初夜": "破瓜", "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥", "赌博": "孤注",
        "毒品": "药石", "枪支": "火器", "刀具": "利刃", "国产": "华夏", "日韩": "东瀛",
        "欧美": "西洋", "港台": "香江", "动漫": "丹青", "综艺": "百戏", "电视剧": "传奇",
        "电影": "光影", "变态": "幽冥", "三级": "情色", "师生": "书生",
    }

    # 未成年相关词（铁律13，脱敏后仍命中则跳过不展示）
    MINOR_KEYWORDS = {"豆蔻", "玉蕊", "碧玉", "书生", "稚子", "未成年", "teen", "loli", "schoolgirl", "萝莉", "幼女", "少女", "学生", "童", "15岁", "14岁", "13岁", "12岁", "11岁", "10岁", "9岁", "8岁", "7岁", "6岁", "5岁", "4岁", "3岁", "2岁", "1岁", "0岁"}

    # ========== 站点配置 ==========
    rawSite = "https://dna.jfg4.quest"
    siteUrl = "https://dna.jfg4.quest"
    HOST = siteUrl
    DEFAULT_PROXY = "https://xsz-shared-proxy.97471201.workers.dev"

    UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 "
                  "Mobile/15E148 Safari/604.1")

    # 分类表（铁律7：父子层级完整；铁律13：跳过含未成年词的分类"制服师生"）
    CATEGORIES = [
        {"type_id": "20", "type_name": "素纱视频"},
        {"type_id": "21", "type_name": "强占禁脔"},
        {"type_id": "22", "type_name": "罗敷丰盈"},
        {"type_id": "23", "type_name": "华夏视频"},
        {"type_id": "25", "type_name": "遮面视频"},
        {"type_id": "26", "type_name": "调教幽冥"},
        {"type_id": "27", "type_name": "翻墙窥帘"},
        {"type_id": "28", "type_name": "伦理传奇"},
    ]

    # ========== 初始化 ==========
    def __init__(self):
        self.use_proxy = False
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        # 尝试导入 m3u8_cleaner 模块（铁律8广告处理）
        self._m3u8_cleaner = None
        try:
            cleaner_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", ".user_skills", "tvbox-dev", "scripts"
            )
            if cleaner_path not in sys.path:
                sys.path.insert(0, cleaner_path)
            import m3u8_cleaner
            self._m3u8_cleaner = m3u8_cleaner
        except Exception:
            pass

    # ========== 脱敏方法（铁律11，正则单次扫描防级联） ==========
    def desensitize(self, text):
        """古典映射脱敏，未成年相关词返回空字符串（铁律13跳过）"""
        if not text:
            return text
        # 构建正则：按长度降序，单次扫描替换，防止级联替换（如玉臀→玉玉臀）
        if not hasattr(self, "_desens_pattern"):
            sorted_keys = sorted(self.CLASSICAL_MAP.keys(), key=len, reverse=True)
            self._desens_pattern = re.compile(
                "|".join(re.escape(k) for k in sorted_keys)
            )
            self._desens_map = self.CLASSICAL_MAP
        result = self._desens_pattern.sub(
            lambda m: self._desens_map[m.group(0)], text
        )
        # 铁律13：检测未成年相关词，命中则返回空（跳过不展示）
        for kw in self.MINOR_KEYWORDS:
            if kw in result:
                return ""
        return result

    def _is_minor_content(self, text):
        """检测文本是否含未成年相关内容（铁律13）"""
        if not text:
            return False
        for kw in self.MINOR_KEYWORDS:
            if kw in text:
                return True
        return False

    # ========== HTTP 请求（直连+反代回退，铁律15） ==========
    def _http_get(self, url, referer=None, timeout=15):
        """HTTP GET，直连失败自动回退反代"""
        headers = {
            "User-Agent": self.UA_MOBILE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if referer:
            headers["Referer"] = referer
        # 直连
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
            html = data.decode("utf-8", errors="ignore")
            if "Sorry, you have been blocked" in html or "Attention Required" in html:
                raise Exception("CF blocked")
            return html
        except Exception:
            pass
        # 回退反代（铁律15）
        if self.rawSite in url:
            proxy_url = url.replace(self.rawSite, self.DEFAULT_PROXY, 1)
            try:
                req = urllib.request.Request(proxy_url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
                data = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
                return data.decode("utf-8", errors="ignore")
            except Exception:
                pass
        return ""

    def _http_get_raw(self, url, referer=None, timeout=15):
        """HTTP GET 返回原始字节（用于m3u8/图片代理）"""
        headers = {
            "User-Agent": self.UA_MOBILE,
            "Accept": "*/*",
        }
        if referer:
            headers["Referer"] = referer
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
        except Exception:
            return b"", "text/plain"

    # ========== 13接口之1: init ==========
    def init(self, extend):
        """初始化，支持 ext.proxy/ext.siteUrl 覆盖，ext.direct=true 直连"""
        try:
            ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
        except Exception:
            ext = {}
        if ext.get("direct"):
            self.siteUrl = self.rawSite
        elif ext.get("siteUrl"):
            self.siteUrl = ext["siteUrl"]
        elif ext.get("proxy"):
            self.siteUrl = ext["proxy"]
        self.HOST = self.siteUrl
        return "ok"

    # ========== 13接口之2: homeContent ==========
    def homeContent(self, filter):
        """首页分类+filters（铁律7分类层级完整，filters为dict）"""
        classes = []
        filters = {}
        for cat in self.CATEGORIES:
            desensitized_name = self.desensitize(cat["type_name"])
            if not desensitized_name:
                continue  # 铁律13跳过未成年分类
            classes.append({
                "type_id": cat["type_id"],
                "type_name": desensitized_name,
            })
            # 每个分类的筛选（按排序维度）
            filters[cat["type_id"]] = [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最新", "v": "new"},
                    {"n": "最热", "v": "hot"},
                ]}
            ]
        return {"class": classes, "filters": filters}

    # ========== 13接口之3: categoryContent ==========
    def categoryContent(self, tid, pg, filter, extend):
        """分类分页列表（五键：page/pagecount/limit/total/list）"""
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        # 分页URL：第1页 /vodtype/{id}.html，第2页起 /vodtype/{id}-{page}.html
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._http_get(url, referer=f"{self.siteUrl}/vod/")
        vod_list = []
        pagecount = 1
        total = 0
        limit = 90
        if html:
            # 提取视频条目：href="/{id}.html" + title + img
            # 使用正则匹配 postbox 区块
            item_pattern = re.compile(
                r'<a[^>]*href="/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?'
                r'<img[^>]*src="([^"]*)"',
                re.DOTALL
            )
            seen_ids = set()
            for match in item_pattern.finditer(html):
                vod_id = match.group(1)
                vod_name = match.group(2).strip()
                vod_pic = match.group(3).strip()
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                # 铁律11脱敏
                desensitized_name = self.desensitize(vod_name)
                # 铁律13跳过未成年条目
                if not desensitized_name or self._is_minor_content(vod_name):
                    continue
                if not vod_pic.startswith("http"):
                    vod_pic = self.siteUrl + vod_pic
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": desensitized_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
            # 提取总页数
            page_match = re.search(r'vodtype/' + re.escape(tid) + r'-(\d+)\.html[^>]*>尾页', html)
            if page_match:
                pagecount = int(page_match.group(1))
            else:
                # 尝试从所有分页链接中找最大
                all_pages = re.findall(r'vodtype/' + re.escape(tid) + r'-(\d+)\.html', html)
                if all_pages:
                    pagecount = max(int(p) for p in all_pages)
            total = pagecount * limit
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
            "list": vod_list,
        }

    # ========== 13接口之4: detailContent ==========
    def detailContent(self, ids):
        """详情页（ids是list/tuple必须遍历，铁律8）"""
        if not ids:
            return {"list": []}
        vod_list = []
        for vod_id in ids:
            vod_id = str(vod_id).strip()
            if not vod_id:
                continue
            url = f"{self.siteUrl}/{vod_id}.html"
            html = self._http_get(url, referer=f"{self.siteUrl}/vod/")
            if not html:
                continue
            # 提取标题
            title_match = re.search(r'<title>([^<]*)</title>', html)
            vod_name = title_match.group(1).split(" - ")[0].strip() if title_match else vod_id
            # 提取封面
            pic_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', html)
            if not pic_match:
                pic_match = re.search(r'<img[^>]*class="imgPlay"[^>]*src="([^"]*)"', html)
            vod_pic = pic_match.group(1).strip() if pic_match else ""
            if vod_pic and not vod_pic.startswith("http"):
                vod_pic = self.siteUrl + vod_pic
            # 提取播放地址 m3u8（铁律：从 const rawUrl = '...' 提取）
            play_url = ""
            raw_match = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
            if raw_match:
                play_url = raw_match.group(1).strip()
            else:
                # 兜底：直接匹配 m3u8 URL
                m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?', html)
                if m3u8_match:
                    play_url = m3u8_match.group(0)
            # 铁律11脱敏
            desensitized_name = self.desensitize(vod_name)
            # 铁律13跳过未成年条目
            if not desensitized_name or self._is_minor_content(vod_name):
                continue
            # 播放线路（单线路，m3u8直链）
            # 铁律：TVBox标准格式 集名$地址，集之间#分隔，缺一不可
            vod_play_from = "集芳阁"
            vod_play_url = f"第1集${play_url}" if play_url else ""
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": desensitized_name,
                "vod_pic": vod_pic,
                "type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": desensitized_name,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            })
        return {"list": vod_list}

    # ========== 13接口之5: playerContent（已移除广告处理，master playlist自动解析子流绝对路径） ==========
    def playerContent(self, flag, id, vipFlags):
        """播放地址：parse=0/jx=0，自动解析master多码率播放列表的子流绝对路径，防盗链双Header"""
        url = id
        # 兜底：若id被污染（含集名前缀等非纯URL），强制提取m3u8地址
        if url and not url.startswith("http"):
            m = re.search(r'https?://[^\s"\'<>$#]+\.m3u8(?:\?[^\s"\'<>$#]*)?', url)
            if m:
                url = m.group(0)
        # 核心修复：master playlist子流相对路径解析
        # 此站master m3u8内容为：#EXT-X-STREAM-INF... \n 2348kb/hls/index.m3u8（相对路径）
        # 壳播放器无法解析相对路径子流导致全不能播，此处下载master后提取子流转绝对路径返回
        if url and ".m3u8" in url:
            try:
                m3u8_bytes, _ = self._http_get_raw(url, referer=self.rawSite + "/")
                if m3u8_bytes:
                    text = m3u8_bytes.decode("utf-8", errors="ignore")
                    if "#EXT-X-STREAM-INF" in text:
                        # 是master playlist，遍历找第一个子流URL
                        for line in text.split("\n"):
                            stripped = line.strip()
                            if stripped and not stripped.startswith("#") and ".m3u8" in stripped:
                                if stripped.startswith("http"):
                                    url = stripped
                                else:
                                    url = urllib.parse.urljoin(url, stripped)
                                break
            except Exception:
                pass  # 解析失败则用原URL，不崩溃
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self.UA_MOBILE,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
        }

    # ========== 13接口之6: searchContent ==========
    def searchContent(self, key, pg):
        """搜索（五键齐全）"""
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.siteUrl}/s/{encoded_key}.html"
        html = self._http_get(url, referer=f"{self.siteUrl}/vod/")
        vod_list = []
        if html:
            item_pattern = re.compile(
                r'<a[^>]*href="/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?'
                r'<img[^>]*src="([^"]*)"',
                re.DOTALL
            )
            seen_ids = set()
            for match in item_pattern.finditer(html):
                vod_id = match.group(1)
                vod_name = match.group(2).strip()
                vod_pic = match.group(3).strip()
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                desensitized_name = self.desensitize(vod_name)
                if not desensitized_name or self._is_minor_content(vod_name):
                    continue
                if not vod_pic.startswith("http"):
                    vod_pic = self.siteUrl + vod_pic
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": desensitized_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
        return {
            "page": page,
            "pagecount": 1,
            "limit": 90,
            "total": len(vod_list),
            "list": vod_list,
        }

    # ========== 13接口之7: localProxy（铁律8 m3u8广告清洗，非空壳） ==========
    def localProxy(self, params):
        """本地代理：接收壳的m3u8代理请求→下载→清洗→返回干净m3u8
        兼容params为dict或字符串；清洗失败自动回退原始m3u8保播放"""
        # 兼容多种params格式
        url = ""
        if isinstance(params, dict):
            url = params.get("url", "") or params.get("u", "") or ""
        elif isinstance(params, str):
            url = params
        # 从 local://proxy?url=xxx 中提取
        if not url and isinstance(params, str) and "url=" in params:
            m = re.search(r'[?&]url=([^&]+)', params)
            if m:
                url = m.group(1)
        if not url:
            return [404, "text/plain", ""]
        # 去掉协议前缀
        if url.startswith("proxy://") or url.startswith("local://"):
            url = url.replace("proxy://", "").replace("local://", "")
            if "?" in url:
                url = url.split("?", 1)[1]
                if url.startswith("url="):
                    url = url[4:]
        # URL解码
        try:
            url = urllib.parse.unquote(url)
        except Exception:
            pass
        # 二次兜底：若解码后仍非纯http，强制提取m3u8
        if not url.startswith("http"):
            m = re.search(r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?', url)
            if m:
                url = m.group(0)
        if not url or not url.startswith("http"):
            return [404, "text/plain", ""]
        # 下载 m3u8（带防盗链Referer）
        m3u8_content, content_type = self._http_get_raw(
            url, referer=self.rawSite + "/"
        )
        if not m3u8_content:
            return [404, "text/plain", ""]
        original_text = m3u8_content.decode("utf-8", errors="ignore")
        # 清洗广告（铁律8），失败则回退原始内容保播放
        try:
            cleaned = self._clean_m3u8(original_text, url)
            if not cleaned or "#EXTM3U" not in cleaned:
                cleaned = original_text
        except Exception:
            cleaned = original_text
        return [200, "application/vnd.apple.mpegurl", cleaned]

    # ========== m3u8 广告清洗核心（铁律8，重写版·加密流安全） ==========
    def _clean_m3u8(self, m3u8_text, base_url):
        """解析m3u8→剔除广告贴片→相对路径转绝对→保留加密KEY→多码率递归
        此站特征：前N段明文(METHOD=NONE)为广告贴片，#EXT-X-DISCONTINUITY后
        出现#EXT-X-KEY:METHOD=AES-128即为正片开始。精准切除贴片前所有分片。"""
        if not m3u8_text or "#EXTM3U" not in m3u8_text:
            return m3u8_text
        lines = m3u8_text.split("\n")

        # ---- master playlist（多码率）：子流递归走代理 ----
        if "#EXT-X-STREAM-INF" in m3u8_text:
            result = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and ".m3u8" in stripped:
                    sub_url = stripped if stripped.startswith("http") else urllib.parse.urljoin(base_url, stripped)
                    result.append(self._proxy_m3u8_url(sub_url))
                else:
                    result.append(line)
            return "\n".join(result)

        # ---- 媒体流：精准切除明文广告贴片 ----
        # 第一步：定位第一个 AES-128 KEY 标签的行号（正片起点）
        aes_key_idx = -1
        for idx, line in enumerate(lines):
            if "#EXT-X-KEY" in line and "AES-128" in line:
                aes_key_idx = idx
                break

        result = []
        i = 0
        ad_removed = 0

        if aes_key_idx > 0:
            # 有AES加密：正片从aes_key_idx行开始，之前的全是广告贴片
            # 先保留头部标签（#EXTM3U, #EXT-X-VERSION, #EXT-X-TARGETDURATION等）
            while i < aes_key_idx:
                line = lines[i]
                stripped = line.strip()
                # 跳过广告段的EXTINF和分片URL，以及广告段前的DISCONTINUITY
                if stripped.startswith("#EXTINF:"):
                    ad_removed += 1
                    i += 2  # 跳过 EXTINF + 分片URL
                    continue
                if stripped.startswith("#EXT-X-DISCONTINUITY"):
                    i += 1
                    continue
                if stripped.startswith("#EXT-X-KEY") and "METHOD=NONE" in stripped:
                    i += 1
                    continue
                # 保留头部元信息
                if stripped.startswith("#") or stripped == "":
                    result.append(line)
                i += 1
            # 从AES KEY行开始，正片内容全部保留（相对路径转绝对）
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                # KEY标签的URI转绝对
                if "#EXT-X-KEY" in stripped and "URI=" in stripped:
                    line = self._absolutize_key_uri(line, base_url)
                # 分片URL转绝对
                elif stripped and not stripped.startswith("#") and stripped:
                    if not stripped.startswith("http"):
                        line = urllib.parse.urljoin(base_url, stripped)
                result.append(line)
                i += 1
        else:
            # 无AES加密（全明文流）：用通用五重识别保守清洗
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped.startswith("#EXTINF:"):
                    duration_match = re.search(r"#EXTINF:([\d.]+)", stripped)
                    duration = float(duration_match.group(1)) if duration_match else 0
                    seg_url = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if self._is_ad_segment(stripped, seg_url, duration, lines, i):
                        ad_removed += 1
                        i += 2
                        if i < len(lines) and lines[i].strip().startswith("#EXT-X-DISCONTINUITY"):
                            i += 1
                        continue
                # 分片URL转绝对
                if stripped and not stripped.startswith("#") and not stripped.startswith("http") and stripped:
                    line = urllib.parse.urljoin(base_url, stripped)
                result.append(line)
                i += 1

        # 重写 MEDIA-SEQUENCE 从0开始（切除了前置广告段）
        cleaned = "\n".join(result)
        if ad_removed > 0:
            cleaned = re.sub(r'#EXT-X-MEDIA-SEQUENCE:\d+', '#EXT-X-MEDIA-SEQUENCE:0', cleaned)
        return cleaned

    def _absolutize_key_uri(self, key_line, base_url):
        """将#EXT-X-KEY中的相对URI转为绝对路径"""
        m = re.search(r'URI="([^"]+)"', key_line)
        if m:
            uri = m.group(1)
            if not uri.startswith("http"):
                abs_uri = urllib.parse.urljoin(base_url, uri)
                key_line = key_line.replace(f'URI="{uri}"', f'URI="{abs_uri}"')
        return key_line

    # ========== 广告段判断（铁律8 五重识别+前置贴片切除） ==========
    def _is_ad_segment(self, extinf_line, seg_url, duration, all_lines, current_idx):
        """五重识别广告段：关键词+短时长+路径标记+加密特征+主CDN统计"""
        if not seg_url:
            return False
        # 第一重：关键词识别
        ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告", "insert", "promo", "sponsor"]
        seg_lower = seg_url.lower()
        for kw in ad_keywords:
            if kw in seg_lower:
                return True
        # 第二重：短时长识别（≤1.2s 极可能是广告）
        if duration <= 1.2:
            return True
        # 第三重：路径标记不匹配（正片CDN vs 广告CDN）
        # 集芳阁特征：广告段为相对路径 /20260906/xxx/seg_XXXXX.jpg 且 METHOD=NONE
        # 正片段为 https://fqts5.top/xxx.jpg 且 AES-128
        if seg_url.startswith("/") and "seg_" in seg_url:
            return True
        # 第四重：加密特征 METHOD=NONE（广告段通常不加密）
        # 向前查找最近的 KEY 标签
        for j in range(current_idx, max(0, current_idx - 20), -1):
            if "METHOD=NONE" in all_lines[j]:
                return True
            if "METHOD=AES" in all_lines[j]:
                break
        # 第五重：前置贴片切除兜底（前3段且未加密）
        if current_idx < 10:
            for j in range(current_idx, max(0, current_idx - 10), -1):
                if "METHOD=NONE" in all_lines[j]:
                    return True
        return False

    # ========== m3u8 代理URL生成（铁律8） ==========
    def _proxy_m3u8_url(self, url):
        """生成走本地代理清洗的m3u8 URL"""
        if not url:
            return url
        # 壳支持 getProxyUrl 时自动生效，不支持时降级直连
        # local:// 协议由壳的 localProxy 接口处理
        encoded = urllib.parse.quote(url, safe="")
        return f"local://proxy?url={encoded}"

    # ========== 13接口之8: getDependence ==========
    def getDependence(self):
        return ""

    # ========== 13接口之9: getName ==========
    def getName(self):
        return "集芳阁"

    # ========== 13接口之10: getApp（可空） ==========
    def getApp(self):
        return ""

    # ========== 13接口之11: getJar（可空） ==========
    def getJar(self):
        return ""

    # ========== 13接口之12: destroy ==========
    def destroy(self):
        pass

    # ========== 13接口之13: check ==========
    def check(self, flags):
        return True

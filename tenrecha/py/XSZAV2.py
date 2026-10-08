# -*- coding: utf-8 -*-
"""
XSZAV2 四壳通用 Python Spider
适配 TVBox / 影视仓 / OK影视 / PickTV
站点: https://tw.xszav2.com
类型: Laravel Livewire 服务端渲染风月宝穴
"""

import re
import json
import urllib.parse
import urllib.request
import urllib.error
import ssl
import time
import subprocess
import shutil


class Spider:
    """独立类，不继承 base.spider，四壳通用"""

    # ========== 站点配置 ==========
    HOST = "https://tw.xszav2.com"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/131.0.0.0 Safari/537.36")
    TIMEOUT = 15

    # ========== 古典映射脱敏表（铁律11） ==========
    CLASSICAL_MAP = {
        "成人": "风月", "色情": "风月", "淫": "风月", "黄色": "春宫",
        "淫秽": "猥亵", "激情": "云雨", "做爱": "云雨", "性交": "交欢",
        "欲": "情思", "高潮": "云端", "偷拍": "窥帘", "偷窥": "窥帘",
        "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱", "迷奸": "迷占",
        "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
        "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
        "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人",
        "护士": "药女", "教师": "先生", "医生": "郎中", "警察": "捕快",
        "军人": "军爷", "秘书": "掌印", "老板": "东家",
        "丈夫": "夫君", "妻子": "拙荆", "情人": "相好", "小三": "外遇",
        "二奶": "外室", "出轨": "翻墙", "偷情": "私会", "通奸": "私通",
        "嫖娼": "寻花", "卖淫": "卖身", "妓女": "花娘",
        "性骚扰": "轻薄", "猥亵": "猥亵", "露阴": "曝玉", "咸猪手": "禄山爪",
        "丝袜": "丝履", "网袜": "网履", "内衣": "亵衣", "内裤": "亵裤",
        "情趣": "风月", "春药": "催情",
        "巨乳": "丰盈", "爆乳": "丰盈", "胸": "酥胸", "乳": "玉兔",
        "美乳": "玉兔", "臀": "玉臀", "屁股": "玉臀", "脚": "莲步",
        "玉足": "莲步", "腿": "玉腿",
        "裸体": "玉体", "全裸": "玉体", "半裸": "半褪", "走光": "泄春",
        "露点": "泄玉",
        "自慰": "弄玉", "口交": "含朱", "口活": "含朱", "肛交": "后庭",
        "屁眼": "后庭", "肛门": "后庭", "群交": "合卺",
        "车震": "车行", "野战": "郊合", "精液": "元阳", "精子": "元阳",
        "阴道": "幽处", "阴户": "幽处", "阴茎": "玉茎", "阳具": "玉茎",
        "SM": "调教", "制服": "官衣", "OL": "衙内", "空姐": "行云",
        "继母": "继室", "姐妹": "同根", "同学": "同窗", "邻居": "东邻",
        "处女": "处子", "初夜": "破瓜",
        "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥",
        "赌博": "孤注", "毒品": "药石", "枪支": "火器", "刀具": "利刃",
        "国产": "华夏", "日韩": "东瀛", "欧美": "西洋", "港台": "香江",
        "动漫": "丹青", "综艺": "百戏", "电视剧": "传奇", "电影": "光影",
        "AV": "风月", "av": "风月", "JAV": "东瀛风月", "jav": "东瀛风月",
        "日本AV": "东瀛风月", "日本av": "东瀛风月",
        "女子校生": "豆蔻书生", "学生服": "书生官衣", "美少女": "碧玉",
        "校生": "书生", "校園": "书院", "校园": "书院",
    }

    # 未成年相关词（铁律13，脱敏后仍命中则跳过）
    MINOR_KEYWORDS = [
        "豆蔻", "玉蕊", "碧玉", "书生", "稚子", "未成年", "teen", "loli",
        "schoolgirl", "school girl", "student", "18岁以下", "十八禁",
        "女子校生", "学生服", "美少女", "少女", "萝莉", "幼女", "学生",
        "童", "小女", "初美", "姬", "学园", "校园", "校生",
    ]

    def __init__(self):
        self._session = None
        self._extend = {}
        self._cache = {}
        self._cache_ttl = 300  # 5分钟短TTL缓存

    # ========== 工具方法 ==========
    def _get_ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    def _build_headers(self, referer=None):
        """构建浏览器导航头"""
        headers = {
            "User-Agent": self.UA,
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-User": "?1",
        }
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"
        return headers

    def _request(self, url, referer=None):
        """HTTP GET 请求（多通道降级：curl_cffi → requests → curl命令 → urllib）"""
        headers = self._build_headers(referer)

        # 通道1: curl_cffi（TLS指纹最像浏览器，绕过Cloudflare最佳）
        try:
            from curl_cffi import requests as cffi_requests
            resp = cffi_requests.get(url, headers=headers, timeout=self.TIMEOUT,
                                      impersonate="chrome131")
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception:
            pass

        # 通道2: requests库（TVBox/Android环境通常有）
        try:
            import requests as req_lib
            session = req_lib.Session()
            resp = session.get(url, headers=headers, timeout=self.TIMEOUT, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception:
            pass

        # 通道3: curl命令
        curl_path = shutil.which("curl")
        if curl_path:
            cmd = [
                curl_path, "-sL", "--compressed",
                "-A", self.UA,
                "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.6",
                "-H", "Upgrade-Insecure-Requests: 1",
                "-H", "Sec-Fetch-Mode: navigate",
                "-H", "Sec-Fetch-Dest: document",
                "-H", "Sec-Fetch-User: ?1",
                "--max-time", str(self.TIMEOUT),
                url,
            ]
            if referer:
                cmd.extend(["-H", f"Referer: {referer}", "-H", "Sec-Fetch-Site: same-origin"])
            else:
                cmd.extend(["-H", "Sec-Fetch-Site: none"])
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=self.TIMEOUT + 5)
                if result.returncode == 0 and result.stdout:
                    return result.stdout.decode("utf-8", errors="ignore")
            except Exception:
                pass

        # 通道4: urllib兜底
        return self._request_urllib(url, referer)

    def _request_urllib(self, url, referer=None):
        """urllib兜底请求"""
        headers = self._build_headers(referer)
        req = urllib.request.Request(url, headers=headers)
        try:
            ctx = self._get_ssl_context()
            resp = urllib.request.urlopen(req, timeout=self.TIMEOUT, context=ctx)
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                data = gzip.decompress(data)
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _cache_get(self, key):
        item = self._cache.get(key)
        if item and (time.time() - item["t"]) < self._cache_ttl:
            return item["v"]
        return None

    def _cache_set(self, key, value):
        self._cache[key] = {"v": value, "t": time.time()}

    def desensitize(self, text):
        """古典映射脱敏（铁律11）"""
        if not text:
            return text
        result = text
        # 按长度降序排列，避免短词先替换
        for word in sorted(self.CLASSICAL_MAP.keys(), key=len, reverse=True):
            if word in result:
                result = result.replace(word, self.CLASSICAL_MAP[word])
        return result

    def is_minor_content(self, text):
        """检测是否含未成年相关内容（铁律13）"""
        if not text:
            return False
        text_lower = text.lower()
        for kw in self.MINOR_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def _filter_minor(self, vod_list):
        """从列表中剔除未成年相关条目（铁律13）"""
        result = []
        for vod in vod_list:
            title = vod.get("vod_name", "")
            if self.is_minor_content(title):
                continue
            result.append(vod)
        return result

    def _parse_video_list(self, html):
        """从列表页HTML解析视频卡片（分块提取法）"""
        vod_list = []
        # 按thumbnail分割成块
        blocks = re.split(r'class="thumbnail"', html)
        for block in blocks[1:]:  # 跳过第一个（第一个thumbnail之前的内容）
            # 提取video id
            vid_match = re.search(r'https://tw\.xszav2\.com/video/(\d+)', block)
            if not vid_match:
                continue
            vid = vid_match.group(1)

            # 提取封面img的data-src（跳过video标签的data-src，找img标签）
            pic = ""
            # 先找img标签块
            img_match = re.search(r'<img[^>]*data-src="([^"]+)"[^>]*>', block, re.DOTALL)
            if img_match:
                pic = img_match.group(1).strip()
            else:
                # 兜底：找所有data-src，取第二个（第一个是video预览）
                srcs = re.findall(r'data-src="([^"]+)"', block)
                if len(srcs) >= 2:
                    pic = srcs[1]
                elif srcs:
                    pic = srcs[0]

            # 提取标题（img的alt属性）
            title = ""
            alt_match = re.search(r'<img[^>]*alt="([^"]*)"', block, re.DOTALL)
            if alt_match:
                title = alt_match.group(1).strip()
            if not title:
                # 兜底：从下方a标签文本提取
                title_match = re.search(r'<a[^>]*href="https://tw\.xszav2\.com/video/' + vid + r'"[^>]*>([^<]+)</a>', block)
                if title_match:
                    title = title_match.group(1).strip()

            # 提取时长
            duration = ""
            dur_match = re.search(r'class="[^"]*absolute[^"]*bottom[^"]*"[^>]*>([^<]+)</span>', block)
            if dur_match:
                duration = dur_match.group(1).strip()
            if not duration:
                dur_match2 = re.search(r'>(\d+:\d{2}(?::\d{2})?)<', block)
                if dur_match2:
                    duration = dur_match2.group(1)

            if not title:
                title = f"影片_{vid}"

            # 脱敏
            title = self.desensitize(title)
            # 未成年跳过（铁律13）
            if self.is_minor_content(title):
                continue

            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic if pic.startswith("http") else self.HOST + pic,
                "vod_remarks": duration,
            })
        return vod_list

    def _parse_total_pages(self, html):
        """从分页HTML解析总页数"""
        # 匹配最后一页链接，如 page=2000
        m = re.findall(r'\?page=(\d+)', html)
        if m:
            pages = [int(x) for x in m]
            return max(pages)
        return 1

    def _parse_detail(self, html, vod_id):
        """从详情页HTML解析视频详情和m3u8"""
        # 提取m3u8 hash
        hash_match = re.search(r'v_([a-f0-9]+)\.m3u8', html)
        m3u8_hash = hash_match.group(1) if hash_match else ""

        # 标题
        title = ""
        og_title = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if og_title:
            title = og_title.group(1).strip()
        if not title:
            title_match = re.search(r'<title>([^<]*)</title>', html)
            if title_match:
                title = title_match.group(1).replace("| XSZAV2", "").strip()

        # 封面
        pic = ""
        og_image = re.search(r'<meta property="og:image" content="([^"]*)"', html)
        if og_image:
            pic = og_image.group(1).strip()

        # 描述 - 尝试提取详情区域
        content = ""
        desc_match = re.search(
            r'<div[^>]*class="[^"]*(?:description|desc|content|detail)[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            content = content[:500]

        # 时长
        duration = ""
        dur_match = re.search(r'(\d+:\d{2}(?::\d{2})?)', html)
        if dur_match:
            duration = dur_match.group(1)

        # 脱敏
        title = self.desensitize(title)
        content = self.desensitize(content)

        # 构建播放地址
        play_url = ""
        if m3u8_hash:
            play_url = f"{self.HOST}/media/videos/v_{m3u8_hash}.m3u8"

        return {
            "vod_id": vod_id,
            "vod_name": title or f"影片_{vod_id}",
            "vod_pic": pic,
            "vod_content": content,
            "vod_remarks": duration,
            "vod_play_from": "XSZAV2",
            "vod_play_url": f"正片${play_url}" if play_url else "",
        }

    def _build_category_url(self, tid, page, filter_params=None):
        """根据分类ID构建URL
        tid格式:
          c:<slug>:<sort>  → 分类页 + 排序
          c:<slug>         → 分类页
          t:<tag>          → 标签页
        """
        parts = tid.split(":")
        page = max(1, int(page))
        if parts[0] == "c":
            slug = parts[1]
            sort = parts[2] if len(parts) > 2 else ""
            url = f"{self.HOST}/c/{slug}?page={page}"
            if sort:
                url += f"&o={sort}"
            return url
        elif parts[0] == "t":
            tag = parts[1]
            return f"{self.HOST}/tags/{tag}?page={page}"
        return f"{self.HOST}/?page={page}"

    # ========== 13个标准接口 ==========

    def getDependence(self):
        return ""

    def init(self, extend):
        """初始化，解析配置"""
        if isinstance(extend, str):
            try:
                self._extend = json.loads(extend)
            except Exception:
                try:
                    import ast
                    self._extend = ast.literal_eval(extend)
                except Exception:
                    self._extend = {}
        elif isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, list):
            self._extend = {"list": extend}
        else:
            self._extend = {}

        # 覆盖HOST
        if "url" in self._extend:
            self.HOST = self._extend["url"].rstrip("/")
        elif "host" in self._extend:
            self.HOST = self._extend["host"].rstrip("/")

        # 预热：发起一次请求完成TLS握手
        try:
            self._request(self.HOST + "/")
        except Exception:
            pass
        return True

    def homeContent(self):
        """首页分类 + filters"""
        # 分类列表（父子层级完整，铁律7）
        classes = [
            # 父分类
            {"type_id": "c:japanese", "type_name": "东瀛风月"},
            # 子分类（排序维度）
            {"type_id": "c:japanese:bw", "type_name": "东瀛风月-最新"},
            {"type_id": "c:japanese:mv", "type_name": "东瀛风月-最多观看"},
            {"type_id": "c:japanese:tf", "type_name": "东瀛风月-最高评分"},
            {"type_id": "c:japanese:lg", "type_name": "东瀛风月-最长"},
            # 父分类
            {"type_id": "c:amateur", "type_name": "素人云雨"},
            # 子分类（标签维度）
            {"type_id": "c:amateur:bw", "type_name": "素人云雨-最新"},
            {"type_id": "t:siro", "type_name": "素人云雨-siro"},
            {"type_id": "t:luxu", "type_name": "素人云雨-luxu"},
            {"type_id": "t:gana", "type_name": "素人云雨-gana"},
            {"type_id": "t:prestigepremium", "type_name": "素人云雨-prestigepremium"},
            {"type_id": "t:s-cute", "type_name": "素人云雨-s-cute"},
            # 父分类
            {"type_id": "c:uncensored", "type_name": "素纱秘境"},
            # 子分类
            {"type_id": "c:uncensored:bw", "type_name": "素纱秘境-最新"},
            {"type_id": "c:uncensored-leak", "type_name": "素纱秘境-素纱流出"},
            {"type_id": "t:fc2ppv", "type_name": "素纱秘境-fc2ppv"},
            {"type_id": "t:heyzo", "type_name": "素纱秘境-heyzo"},
            {"type_id": "t:1pondo", "type_name": "素纱秘境-1pondo"},
            {"type_id": "t:caribbeancom", "type_name": "素纱秘境-caribbeancom"},
            {"type_id": "t:caribbeancompr", "type_name": "素纱秘境-caribbeancompr"},
            {"type_id": "t:10musume", "type_name": "素纱秘境-10musume"},
            {"type_id": "t:pacopacomama", "type_name": "素纱秘境-pacopacomama"},
        ]

        # filters（dict，铁律8）
        filters = {}
        sort_filter = [
            {"key": "sort", "name": "排序", "init": "bw",
             "value": [
                 {"n": "最新", "v": "bw"},
                 {"n": "最多观看", "v": "mv"},
                 {"n": "最高评分", "v": "tf"},
                 {"n": "最长", "v": "lg"},
             ]}
        ]
        for cls in classes:
            filters[cls["type_id"]] = sort_filter

        # 首页推荐列表
        vod_list = []
        try:
            cache_key = "home_list"
            cached = self._cache_get(cache_key)
            if cached:
                vod_list = cached
            else:
                html = self._request(self.HOST + "/")
                vod_list = self._parse_video_list(html)
                self._cache_set(cache_key, vod_list)
        except Exception:
            pass

        return {
            "class": classes,
            "filters": filters,
            "list": vod_list[:24],
        }

    def homeVideoContent(self):
        """首页视频（五键齐全）"""
        vod_list = []
        try:
            html = self._request(self.HOST + "/")
            vod_list = self._parse_video_list(html)
        except Exception:
            pass
        return {
            "page": 1,
            "pagecount": 1,
            "limit": 24,
            "total": len(vod_list),
            "list": vod_list[:24],
        }

    def categoryContent(self, tid, page, filter_params=None, extend=None):
        """分类分页（五键齐全）"""
        page = int(page) if page else 1
        # 处理filter_params中的排序
        sort = ""
        if filter_params and isinstance(filter_params, dict):
            sort = filter_params.get("sort", "")
        elif filter_params and isinstance(filter_params, str):
            sort = filter_params

        # 如果tid本身带排序，filter_params不覆盖
        url = self._build_category_url(tid, page)
        if sort and ":" not in tid.split(":")[-1] if ":" in tid else True:
            # 追加排序参数
            sep = "&" if "?" in url else "?"
            url += f"{sep}o={sort}"

        vod_list = []
        total_pages = 1
        try:
            cache_key = f"cat_{tid}_{page}_{sort}"
            cached = self._cache_get(cache_key)
            if cached:
                vod_list, total_pages = cached
            else:
                html = self._request(url)
                vod_list = self._parse_video_list(html)
                total_pages = self._parse_total_pages(html)
                self._cache_set(cache_key, (vod_list, total_pages))
        except Exception:
            pass

        return {
            "page": page,
            "pagecount": total_pages,
            "limit": len(vod_list) if vod_list else 24,
            "total": total_pages * 24,
            "list": vod_list,
        }

    def detailContent(self, ids):
        """详情页（遍历ids，铁律8）"""
        if not ids:
            return {"list": []}
        # ids是list/tuple，必须遍历
        if isinstance(ids, (str, int)):
            ids = [str(ids)]

        result_list = []
        for vod_id in ids:
            vod_id = str(vod_id).strip()
            if not vod_id:
                continue
            try:
                cache_key = f"detail_{vod_id}"
                cached = self._cache_get(cache_key)
                if cached:
                    detail = cached
                else:
                    url = f"{self.HOST}/video/{vod_id}"
                    html = self._request(url, referer=self.HOST + "/")
                    detail = self._parse_detail(html, vod_id)
                    self._cache_set(cache_key, detail)

                # 未成年跳过
                if self.is_minor_content(detail.get("vod_name", "")):
                    continue
                result_list.append(detail)
            except Exception:
                continue

        return {"list": result_list}

    def searchContent(self, wd, page, extend=None):
        """搜索（五键齐全）"""
        page = int(page) if page else 1
        wd = str(wd).strip()
        if not wd:
            return {"page": 1, "pagecount": 0, "limit": 0, "total": 0, "list": []}

        # 未成年关键词直接返回空（铁律13）
        if self.is_minor_content(wd):
            return {"page": 1, "pagecount": 0, "limit": 0, "total": 0, "list": []}

        # 脱敏搜索词
        wd_desens = self.desensitize(wd)

        encoded = urllib.parse.quote(wd)
        url = f"{self.HOST}/search/videos/{encoded}?page={page}"

        vod_list = []
        total_pages = 1
        try:
            cache_key = f"search_{encoded}_{page}"
            cached = self._cache_get(cache_key)
            if cached:
                vod_list, total_pages = cached
            else:
                html = self._request(url)
                vod_list = self._parse_video_list(html)
                total_pages = self._parse_total_pages(html)
                self._cache_set(cache_key, (vod_list, total_pages))
        except Exception:
            pass

        return {
            "page": page,
            "pagecount": total_pages,
            "limit": len(vod_list) if vod_list else 24,
            "total": total_pages * 24,
            "list": vod_list,
        }

    def playerContent(self, flag, id, vipFlags=None, extend=None):
        """播放地址（parse=0/jx=0/header为dict）"""
        # id可能是m3u8完整URL或vod_id
        url = str(id).strip()
        if not url.startswith("http"):
            # 尝试从详情页获取
            try:
                detail_url = f"{self.HOST}/video/{url}"
                html = self._request(detail_url, referer=self.HOST + "/")
                hash_match = re.search(r'v_([a-f0-9]+)\.m3u8', html)
                if hash_match:
                    url = f"{self.HOST}/media/videos/v_{hash_match.group(1)}.m3u8"
            except Exception:
                pass

        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            },
            "format": "application/x-mpegURL",
        }

    def localProxy(self, url, header=None):
        """本地代理（兼容dict和三元组）"""
        try:
            if not url:
                return [404, "text/plain", ""]
            # 封面图代理
            if "img.xszav2.com" in url or "xszcdn" in url:
                headers = {"User-Agent": self.UA, "Referer": self.HOST + "/"}
                if header:
                    headers.update(header)
                req = urllib.request.Request(url, headers=headers)
                ctx = self._get_ssl_context()
                resp = urllib.request.urlopen(req, timeout=self.TIMEOUT, context=ctx)
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                return [200, content_type, data]
            return [404, "text/plain", ""]
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        return url.endswith(".m3u8") or ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def action(self, action, extend=None):
        return ""

    def destroy(self):
        self._cache.clear()
        return True

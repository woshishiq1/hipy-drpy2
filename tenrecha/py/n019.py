# -*- coding: utf-8 -*-
"""
四壳通用Python Spider - 海天盛筵
站点类型：苹果CMS v10 (maccms) youku_pc模板
基础URL：https://hpp.htsy7.fit/cn/home/web/
播放方式：播放页 player_data.url 中的 m3u8 直链
协议兼容：TVBox / 影视仓 / OK影视 / PickTV / PyramidStore
"""

import re
import json
import base64
import urllib.parse
import traceback

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass


# ==================== 常量配置 ====================

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

NAV_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
}

# 未成年相关关键词（命中即剔除，凌驾所有铁律）
JUVENILE_KEYWORDS = [
    "萝莉", "幼女", "少女", "童", "未成年", "teen", "loli", "schoolgirl",
    "小女", "女童", "幼童", "稚女", "少女", "teenie", "young girl",
    "小学生", "初中生", "中学生", "小学", "初中",
]

# 分类列表（实际从导航提取，此处为兜底）
DEFAULT_CLASSES = [
    {"type_id": "20", "type_name": "无码视频"},
    {"type_id": "21", "type_name": "强奸乱伦"},
    {"type_id": "22", "type_name": "人妻巨乳"},
    {"type_id": "23", "type_name": "国产视频"},
    {"type_id": "24", "type_name": "制服师生"},
    {"type_id": "25", "type_name": "有码视频"},
    {"type_id": "26", "type_name": "调教变态"},
    {"type_id": "27", "type_name": "出轨偷拍"},
    {"type_id": "28", "type_name": "三级伦理"},
]


# ==================== 工具函数 ====================

def _is_juvenile(text):
    """检测文本是否含未成年相关关键词，命中返回True（需剔除）"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in JUVENILE_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


def _filter_juvenile(vod_list):
    """从视频列表中剔除未成年相关条目"""
    if not vod_list:
        return []
    result = []
    for item in vod_list:
        name = item.get("vod_name", "") or ""
        remarks = item.get("vod_remarks", "") or ""
        content = item.get("vod_content", "") or ""
        if _is_juvenile(name) or _is_juvenile(remarks) or _is_juvenile(content):
            continue
        result.append(item)
    return result


def _extract_vod_id_from_url(url):
    """从播放页/详情页URL中提取vod_id"""
    if not url:
        return ""
    m = re.search(r"/(?:play|detail)/id/(\d+)", url)
    if m:
        return m.group(1)
    return ""


def _clean_text(text):
    """清理文本中的多余空白"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# ==================== Spider 主类 ====================

class Spider(_BaseSpider):
    """海天盛筵 - 四壳通用Python Spider"""

    # 类属性（四壳协议要求）
    header = {"User-Agent": UA}

    def __init__(self):
        super().__init__()
        self.rawSite = "https://hpp.htsy7.fit"
        self.basePath = "/cn/home/web"
        self.siteUrl = self.rawSite + self.basePath
        self.HOST = self.siteUrl
        self.extend = ""
        self._classes = None
        self._session = None
        self._proxy_url = None
        self._direct = False

    # ---------- 依赖声明 ----------
    def getDependence(self):
        return ""

    # ---------- 初始化 ----------
    def init(self, extend=""):
        """初始化，解析扩展配置"""
        self.extend = extend or ""
        # 兼容 dict / list / JSON字符串 / ast.literal_eval
        ext_dict = {}
        if isinstance(extend, dict):
            ext_dict = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                ext_dict = json.loads(extend)
            except Exception:
                try:
                    import ast
                    ext_dict = ast.literal_eval(extend)
                except Exception:
                    pass
        elif isinstance(extend, list):
            for item in extend:
                if isinstance(item, dict):
                    ext_dict.update(item)

        # 支持 ext.proxy / ext.siteUrl 覆盖，ext.direct 直连
        if ext_dict.get("direct") is True:
            self._direct = True
        if ext_dict.get("proxy"):
            self._proxy_url = ext_dict["proxy"]
            self.siteUrl = self._proxy_url + self.basePath
            self.HOST = self.siteUrl
        elif ext_dict.get("siteUrl"):
            self.siteUrl = ext_dict["siteUrl"].rstrip("/")
            self.HOST = self.siteUrl

        # 预热：建立session
        self._get_session()

    # ---------- HTTP 请求封装 ----------
    def _get_session(self):
        """获取requests session，带重试和cookie"""
        if self._session is not None:
            return self._session
        try:
            import requests
            from requests.adapters import HTTPAdapter
            try:
                from urllib3.util.retry import Retry
            except ImportError:
                Retry = None

            s = requests.Session()
            if Retry is not None:
                retry = Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504],
                )
                adapter = HTTPAdapter(max_retries=retry)
                s.mount("http://", adapter)
                s.mount("https://", adapter)
            s.headers.update(NAV_HEADERS)
            self._session = s
            return s
        except ImportError:
            self._session = None
            return None

    def _http_get(self, url, timeout=15):
        """GET请求，返回文本或None"""
        s = self._get_session()
        if s is None:
            # fallback: urllib
            try:
                import urllib.request
                req = urllib.request.Request(url, headers=NAV_HEADERS)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    # 尝试解码
                    for enc in ["utf-8", "gbk", "gb2312"]:
                        try:
                            return data.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return data.decode("utf-8", errors="replace")
            except Exception:
                return None
        try:
            resp = s.get(url, timeout=timeout, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception:
            return None

    def _http_post(self, url, data, timeout=15):
        """POST请求，返回文本或None"""
        s = self._get_session()
        if s is None:
            try:
                import urllib.request
                import urllib.parse
                post_data = urllib.parse.urlencode(data).encode("utf-8")
                req = urllib.request.Request(url, data=post_data, headers=NAV_HEADERS)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    for enc in ["utf-8", "gbk", "gb2312"]:
                        try:
                            return raw.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return raw.decode("utf-8", errors="replace")
            except Exception:
                return None
        try:
            resp = s.post(url, data=data, timeout=timeout, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception:
            return None

    # ---------- 分类提取 ----------
    def _fetch_classes(self):
        """从首页导航提取分类列表"""
        if self._classes is not None:
            return self._classes
        html = self._http_get(self.siteUrl + "/")
        classes = []
        if html:
            # 匹配导航链接：/cn/home/web/index.php/vod/type/id/XX.html
            pattern = r'href="[^"]*vod/type/id/(\d+)\.html"[^>]*>([^<]+)</a>'
            seen = set()
            for m in re.finditer(pattern, html):
                tid = m.group(1)
                tname = _clean_text(m.group(2))
                if tid and tname and tid not in seen:
                    # 未成年分类直接跳过（铁律13）
                    if _is_juvenile(tname):
                        continue
                    seen.add(tid)
                    classes.append({"type_id": tid, "type_name": tname})
        if not classes:
            # 兜底：使用默认分类
            classes = [c for c in DEFAULT_CLASSES if not _is_juvenile(c["type_name"])]
        self._classes = classes
        return classes

    # ---------- 列表解析 ----------
    def _parse_list_html(self, html):
        """解析列表页HTML，返回视频列表"""
        vod_list = []
        if not html:
            return vod_list
        # 匹配每个 yk-pack 条目
        # 结构：<li class="yk-pack"> ... <a href="...play/id/XXX..." title="TITLE"> ... <img ... src="PIC" ...> ... <li class="title"><a ...>TITLE</a></li>
        pattern = re.compile(
            r'<li class="yk-pack">(.*?)</li>\s*</li>',
            re.DOTALL
        )
        # 更宽松的匹配：按 yk-pack 分块
        blocks = re.split(r'<li class="yk-pack">', html)
        for block in blocks[1:]:
            # 提取播放页链接中的vod_id
            id_match = re.search(r'/(?:play|detail)/id/(\d+)', block)
            vod_id = id_match.group(1) if id_match else ""
            if not vod_id:
                continue

            # 提取标题（优先title属性，其次a标签文本）
            title = ""
            title_match = re.search(r'title="([^"]+)"', block)
            if title_match:
                title = _clean_text(title_match.group(1))
            if not title:
                a_match = re.search(r'class="title"><a[^>]*>([^<]+)</a>', block)
                if a_match:
                    title = _clean_text(a_match.group(1))

            # 提取封面图（优先data-original，其次src）
            pic = ""
            pic_match = re.search(r'data-original="([^"]+)"', block)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<img[^>]*src="([^"]+)"', block)
                if pic_match:
                    pic = pic_match.group(1)

            # 提取备注/日期
            remarks = ""
            rem_match = re.search(r'<li><span>([^<]+)</span></li>', block)
            if rem_match:
                remarks = _clean_text(rem_match.group(1))

            if title:
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": self._proxy_image_url(pic),
                    "vod_remarks": remarks,
                })
        return _filter_juvenile(vod_list)

    # ---------- 分页信息提取 ----------
    def _parse_pagination(self, html, current_page):
        """从分页HTML中提取总页数"""
        if not html:
            return current_page
        # 匹配尾页链接：page/XXX.html
        tail_match = re.search(r'page/(\d+)\.html"[^>]*title="尾页"', html)
        if tail_match:
            return int(tail_match.group(1))
        # 匹配最大页码
        pages = re.findall(r'page/(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        return current_page

    # ---------- 图片本地代理URL生成 ----------
    def _proxy_image_url(self, img_url):
        """将图片URL转为本地代理URL，带Referer破防盗链；壳不支持代理时兜底直连"""
        if not img_url:
            return ""
        try:
            if hasattr(self, "getProxyUrl"):
                proxy = self.getProxyUrl()
                if proxy:
                    encoded = base64.b64encode(img_url.encode("utf-8")).decode("utf-8")
                    return f"{proxy}?do=img&url={encoded}"
        except Exception:
            pass
        return img_url

    # ---------- 首页内容 ----------
    def homeContent(self, *args):
        """首页：分类 + filters + 推荐列表"""
        try:
            classes = self._fetch_classes()
            # filters 必须为 dict
            filters = {}
            for c in classes:
                filters[c["type_id"]] = []

            # 抓取首页推荐列表
            html = self._http_get(self.siteUrl + "/")
            vod_list = self._parse_list_html(html) if html else []

            return {
                "class": classes,
                "filters": filters,
                "list": vod_list,
            }
        except Exception as e:
            traceback.print_exc()
            return {"class": [], "filters": {}, "list": []}

    # ---------- 首页视频内容（部分壳调用） ----------
    def homeVideoContent(self, *args):
        """首页视频列表"""
        try:
            html = self._http_get(self.siteUrl + "/")
            vod_list = self._parse_list_html(html) if html else []
            return {
                "page": 1,
                "pagecount": 1,
                "limit": len(vod_list),
                "total": len(vod_list),
                "list": vod_list,
            }
        except Exception:
            traceback.print_exc()
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    # ---------- 分类内容 ----------
    def categoryContent(self, *args):
        """分类页：支持 (tid, page, pg, filter, extend) 多种签名"""
        tid = ""
        page = 1
        # 解析参数
        if len(args) >= 1:
            tid = str(args[0]) if args[0] else ""
        if len(args) >= 2:
            try:
                page = int(args[1])
            except (ValueError, TypeError):
                page = 1
        # 兼容 pg 参数（PyramidStore）
        for i, arg in enumerate(args):
            if isinstance(arg, dict) and "pg" in arg:
                try:
                    page = int(arg["pg"])
                except (ValueError, TypeError):
                    pass

        if not tid:
            return {"page": page, "pagecount": 0, "limit": 20, "total": 0, "list": []}

        try:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._http_get(url)
            vod_list = self._parse_list_html(html) if html else []
            pagecount = self._parse_pagination(html, page) if html else page
            total = pagecount * 20

            return {
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
                "list": vod_list,
            }
        except Exception:
            traceback.print_exc()
            return {"page": page, "pagecount": 0, "limit": 20, "total": 0, "list": []}

    # ---------- 详情内容 ----------
    def detailContent(self, *args):
        """详情页：ids 是 list/tuple，必须遍历"""
        ids = []
        if len(args) >= 1:
            arg = args[0]
            if isinstance(arg, (list, tuple)):
                ids = [str(x) for x in arg]
            elif isinstance(arg, str):
                ids = [arg]
            elif arg is not None:
                ids = [str(arg)]

        if not ids:
            return {"list": []}

        vod_list = []
        for vod_id in ids:
            try:
                vod = self._fetch_detail(vod_id)
                if vod:
                    # 未成年过滤
                    if _is_juvenile(vod.get("vod_name", "")) or _is_juvenile(vod.get("vod_content", "")):
                        continue
                    vod_list.append(vod)
            except Exception:
                traceback.print_exc()
                continue

        return {"list": vod_list}

    def _fetch_detail(self, vod_id):
        """抓取单个视频详情"""
        url = f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html"
        html = self._http_get(url)
        if not html:
            return None

        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_year": "",
            "vod_area": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 标题
        title_match = re.search(r'<h1>([^<]+)</h1>', html)
        if title_match:
            vod["vod_name"] = _clean_text(title_match.group(1))

        # 封面
        pic_match = re.search(r'class="s-cover[^"]*"[^>]*>.*?<img[^>]*data-original="([^"]+)"', html, re.DOTALL)
        if not pic_match:
            pic_match = re.search(r'class="s-cover[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
        if pic_match:
            vod["vod_pic"] = self._proxy_image_url(pic_match.group(1))

        # 年代
        year_match = re.search(r'年代：</span>\s*([^<\s]+)', html)
        if year_match:
            vod["vod_year"] = _clean_text(year_match.group(1))

        # 类型
        type_match = re.search(r'类型：</span>\s*([^<]+)', html)
        if type_match:
            vod["vod_remarks"] = _clean_text(type_match.group(1))

        # 导演
        dir_match = re.search(r'导演：</span>\s*([^<]+)', html)
        if dir_match:
            vod["vod_director"] = _clean_text(dir_match.group(1))

        # 演员
        actor_match = re.search(r'演员：</span>\s*([^<]+)', html)
        if actor_match:
            vod["vod_actor"] = _clean_text(actor_match.group(1))

        # 简介
        desc_match = re.search(r'简介：</span><span[^>]*>(.*?)</span>', html, re.DOTALL)
        if desc_match:
            vod["vod_content"] = _clean_text(re.sub(r'<[^>]+>', '', desc_match.group(1)))

        # 播放来源（线路名）
        play_from = []
        from_matches = re.findall(r'class="ea-site[^"]*"[^>]*>([^<]+)</span>', html)
        for fm in from_matches:
            fm_clean = _clean_text(fm)
            if fm_clean and fm_clean not in play_from:
                play_from.append(fm_clean)
        if not play_from:
            # 从播放页链接推断
            play_from = ["CkPlayer-H5播放器"]

        # 剧集列表（精确定位 num-tab 区域，避免匹配到封面/立即播放等重复链接）
        episodes = []
        ep_section = ""
        # 优先提取 "全部剧集" 后的 num-tab 区域
        sec_match = re.search(
            r'全部剧集.*?(<div class="num-tab[^"]*".*?)(?:<div class="d-play-side"|<!--|$)',
            html, re.DOTALL
        )
        if sec_match:
            ep_section = sec_match.group(1)
        else:
            # 兜底：提取所有 num-tab 区域
            sec_match2 = re.search(r'<div class="num-tab[^"]*".*?(?=<div class="d-play-side"|$)', html, re.DOTALL)
            if sec_match2:
                ep_section = sec_match2.group(0)

        if ep_section:
            ep_pattern = re.compile(
                r'<a[^>]*href="[^"]*play/id/' + re.escape(vod_id) + r'/sid/(\d+)/nid/(\d+)\.html"[^>]*>([^<]+)</a>',
                re.DOTALL
            )
            seen_nids = set()
            for m in ep_pattern.finditer(ep_section):
                sid = m.group(1)
                nid = m.group(2)
                if nid in seen_nids:
                    continue
                seen_nids.add(nid)
                ep_name = _clean_text(m.group(3))
                if not ep_name:
                    ep_name = f"第{nid}集"
                play_url = f"{self.siteUrl}/index.php/vod/play/id/{vod_id}/sid/{sid}/nid/{nid}.html"
                episodes.append(f"{ep_name}${play_url}")

        if not episodes:
            # 兜底：只有一集
            play_url = f"{self.siteUrl}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            episodes.append(f"正片${play_url}")

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "#".join(episodes)

        return vod

    # ---------- 搜索内容 ----------
    def searchContent(self, *args):
        """搜索：支持 (wd, page) / (key, quick) / (key, quick, pg) 多种签名"""
        wd = ""
        page = 1
        if len(args) >= 1:
            wd = str(args[0]) if args[0] else ""
        if len(args) >= 2:
            try:
                page = int(args[1])
            except (ValueError, TypeError):
                page = 1
        # 兼容 pg
        for i, arg in enumerate(args):
            if isinstance(arg, dict) and "pg" in arg:
                try:
                    page = int(arg["pg"])
                except (ValueError, TypeError):
                    pass

        if not wd:
            return {"page": page, "pagecount": 0, "limit": 20, "total": 0, "list": []}

        # 未成年搜索词直接返回空（铁律13）
        if _is_juvenile(wd):
            return {"page": page, "pagecount": 0, "limit": 20, "total": 0, "list": []}

        try:
            url = f"{self.siteUrl}/index.php/vod/search.html"
            data = {"wd": wd}
            html = self._http_post(url, data)
            vod_list = self._parse_list_html(html) if html else []
            pagecount = self._parse_pagination(html, page) if html else page
            total = pagecount * 20

            return {
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
                "list": vod_list,
            }
        except Exception:
            traceback.print_exc()
            return {"page": page, "pagecount": 0, "limit": 20, "total": 0, "list": []}

    # ---------- 播放内容 ----------
    def playerContent(self, *args):
        """播放解析：从播放页提取 m3u8 直链"""
        flag = ""
        id_url = ""
        vipFlags = []
        if len(args) >= 1:
            flag = str(args[0]) if args[0] else ""
        if len(args) >= 2:
            id_url = str(args[1]) if args[1] else ""
        if len(args) >= 3:
            if isinstance(args[2], (list, tuple)):
                vipFlags = list(args[2])
            elif args[2]:
                vipFlags = [str(args[2])]

        if not id_url:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

        try:
            # id_url 是播放页URL，抓取并解析 player_data
            html = self._http_get(id_url)
            real_url = ""
            if html:
                # 匹配 player_data 变量
                pd_match = re.search(r'var player_data\s*=\s*(\{.*?\})', html, re.DOTALL)
                if pd_match:
                    pd_str = pd_match.group(1)
                    # 提取 url 字段
                    url_match = re.search(r'"url"\s*:\s*"([^"]+)"', pd_str)
                    if url_match:
                        real_url = url_match.group(1).replace("\\/", "/")

                # 兜底：直接匹配 m3u8 URL
                if not real_url:
                    m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                    if m3u8_match:
                        real_url = m3u8_match.group(1)

            return {
                "parse": 0,
                "jx": 0,
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": id_url if id_url else (self.rawSite + "/"),
                    "Origin": self.rawSite,
                },
                "format": "application/x-mpegURL",
            }
        except Exception:
            traceback.print_exc()
            return {"parse": 0, "jx": 0, "url": id_url, "header": {"User-Agent": UA}}

    # ---------- 本地代理（图片防盗链代理） ----------
    def localProxy(self, *args):
        """
        本地代理：处理图片防盗链请求（do=img），带Referer+UA下载后返回
        返回 [code, content_type, content_bytes] 三元组
        """
        # 兼容 dict 和 字符串 两种参数格式
        params = {}
        if len(args) >= 1:
            arg = args[0]
            if isinstance(arg, dict):
                params = arg
            elif isinstance(arg, str):
                # 解析query string
                if "?" in arg:
                    qs = arg.split("?", 1)[1]
                    params = urllib.parse.parse_qs(qs)
                    # parse_qs返回list，取第一个
                    params = {k: v[0] for k, v in params.items()}

        do = params.get("do", "")
        if do != "img":
            return [404, "text/plain", ""]

        # 解码图片URL（base64编码）
        img_url = ""
        encoded = params.get("url", "")
        if encoded:
            try:
                img_url = base64.b64decode(encoded).decode("utf-8")
            except Exception:
                # 兜底：可能是urlencode的
                try:
                    img_url = urllib.parse.unquote(encoded)
                except Exception:
                    img_url = encoded

        if not img_url:
            return [404, "text/plain", ""]

        try:
            # 带Referer+UA下载图片，破防盗链
            s = self._get_session()
            if s is None:
                return [404, "text/plain", ""]
            headers = {
                "User-Agent": UA,
                "Referer": self.rawSite + "/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            resp = s.get(img_url, headers=headers, timeout=15, stream=True)
            if resp.status_code != 200:
                return [resp.status_code, "text/plain", ""]
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            content = resp.content
            return [200, content_type, content]
        except Exception:
            traceback.print_exc()
            return [404, "text/plain", ""]

    # ---------- 视频格式判断 ----------
    def isVideoFormat(self, *args):
        """判断是否为视频格式"""
        url = ""
        if len(args) >= 1:
            url = str(args[0]) if args[0] else ""
        if not url:
            return False
        return url.endswith(".m3u8") or ".m3u8" in url

    # ---------- 手动视频检查 ----------
    def manualVideoCheck(self, *args):
        """是否需要手动检查视频"""
        return False

    # ---------- 扩展动作 ----------
    def action(self, *args):
        """扩展动作接口"""
        return ""

    # ---------- 销毁 ----------
    def destroy(self, *args):
        """销毁清理"""
        self._session = None
        self._classes = None


# ==================== 本地测试入口 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("海天盛筵 Spider 本地测试")
    print("=" * 60)

    sp = Spider()
    sp.init()

    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']}: {c['type_name']}")
    print(f"  filters类型: {type(home.get('filters')).__name__}")
    print(f"  推荐列表数: {len(home.get('list', []))}")

    print("\n[2] categoryContent (id=20, page=1):")
    cat = sp.categoryContent("20", 1)
    print(f"  page: {cat['page']}, pagecount: {cat['pagecount']}, total: {cat['total']}")
    print(f"  列表数: {len(cat['list'])}")
    if cat["list"]:
        first = cat["list"][0]
        print(f"  首个: id={first['vod_id']}, name={first['vod_name'][:30]}...")

    print("\n[3] detailContent:")
    if cat["list"]:
        test_id = cat["list"][0]["vod_id"]
        detail = sp.detailContent([test_id])
        print(f"  详情数: {len(detail['list'])}")
        if detail["list"]:
            d = detail["list"][0]
            print(f"  标题: {d['vod_name'][:40]}")
            print(f"  线路: {d['vod_play_from']}")
            print(f"  集数: {len(d['vod_play_url'].split('#'))}")

    print("\n[4] searchContent (wd=人妻):")
    search = sp.searchContent("人妻", 1)
    print(f"  page: {search['page']}, pagecount: {search['pagecount']}")
    print(f"  结果数: {len(search['list'])}")

    print("\n[5] playerContent:")
    if cat["list"] and detail["list"]:
        # 从详情中取第一个播放地址
        play_url = detail["list"][0]["vod_play_url"].split("#")[0].split("$")[-1]
        player = sp.playerContent("ckplayer", play_url, [])
        print(f"  parse: {player['parse']}, jx: {player['jx']}")
        print(f"  url: {player.get('url', '')[:80]}...")
        print(f"  header keys: {list(player.get('header', {}).keys())}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

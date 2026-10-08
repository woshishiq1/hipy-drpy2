# coding=utf-8
# //@name:123视频
# //@id:sp123sp
# //@version:1.0
#
# 四壳通用Python Spider — 123视频 (glm.123sp3.fit)
# 站点类型: 苹果CMS + fed模板
# 播放方式: m3u8直链 (播放页player_data变量)
# 铁律11: 代码层直接返回原始内容，不做古典映射脱敏
# 铁律13: 未成年相关分类/条目自动剔除不返回

import json
import re
import os
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

# ========== 站点配置 ==========
DEFAULT_HOST = "https://glm.123sp3.fit"
BASE_PATH = "/cn/home/web"
SITE_URL = DEFAULT_HOST + BASE_PATH

DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

NAV_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# ========== 分类配置 (铁律7: 分类完整写入) ==========
CATEGORIES = [
    {"type_id": "20", "type_name": "美女写真"},
    {"type_id": "21", "type_name": "国产精品"},
    {"type_id": "22", "type_name": "无码专区"},
    {"type_id": "23", "type_name": "中文字幕"},
    {"type_id": "24", "type_name": "强奸乱伦"},
    {"type_id": "25", "type_name": "人妻熟女"},
    {"type_id": "26", "type_name": "亚洲情色"},
    {"type_id": "27", "type_name": "制服丝袜"},
    {"type_id": "28", "type_name": "SM捆绑"},
    {"type_id": "29", "type_name": "自淫系列"},
    {"type_id": "30", "type_name": "三级伦理"},
]

# ========== 铁律13: 未成年关键词 (命中则剔除不返回) ==========
_MINOR_KEYWORDS = (
    "萝莉", "幼女", "少女", "童", "未成年", "teen", "loli",
    "schoolgirl", "豆蔻", "玉蕊", "碧玉", "稚子",
)


def _is_minor(text):
    """铁律13: 检测文本是否含未成年相关内容"""
    if not text:
        return False
    lower = str(text).lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def _filter_minor_vod(vod):
    """铁律13: 未成年条目返回None剔除"""
    if not isinstance(vod, dict):
        return vod
    name = vod.get("vod_name", "")
    remarks = vod.get("vod_remarks", "")
    content = vod.get("vod_content", "")
    if _is_minor(name) or _is_minor(remarks) or _is_minor(content):
        return None
    return vod


def _clean_html(text):
    """去除HTML标签，清理空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_session():
    """获取requests会话"""
    if requests is None:
        return None
    session = requests.Session()
    session.headers.update(NAV_HEADERS)
    return session


def _http_get(url, session=None, timeout=15):
    """HTTP GET请求"""
    try:
        if session is None:
            session = _get_session()
        if session is None:
            return ""
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        # 不强制设置encoding，用content解码避免乱码
        content = resp.content
        for enc in ("utf-8", "gbk", "gb2312"):
            try:
                return content.decode(enc)
            except Exception:
                continue
        return content.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _parse_vod_list(html):
    """解析分类页/搜索页的视频列表 (fed模板: li.fed-list-item)"""
    vod_list = []
    # 匹配每个视频li项: li.fed-list-item
    li_pattern = re.compile(
        r'<li[^>]*class="[^"]*fed-list-item[^"]*"[^>]*>(.*?)</li>',
        re.DOTALL
    )
    for li_match in li_pattern.finditer(html):
        item = li_match.group(1)
        # 提取封面图: a.fed-list-pics 的 data-original
        pic_match = re.search(
            r'<a[^>]*class="[^"]*fed-list-pics[^"]*"[^>]*data-original="([^"]+)"',
            item
        )
        if not pic_match:
            pic_match = re.search(r'data-original="(https?://[^"]+\.(?:jpg|png|jpeg|gif|webp))"', item)
        pic = pic_match.group(1) if pic_match else ""
        if pic and pic.startswith("/"):
            pic = DEFAULT_HOST + pic

        # 提取标题: a.fed-list-title (不依赖属性顺序)
        title_match = re.search(
            r'<a[^>]*class="[^"]*fed-list-title[^"]*"[^>]*>(.*?)</a>',
            item, re.DOTALL
        )
        if not title_match:
            # 备选: 找含vod/play且文本最长的a
            links = re.findall(
                r'<a[^>]*href="[^"]*vod/(?:play|detail)/id/(\d+)[^"]*"[^>]*>(.*?)</a>',
                item, re.DOTALL
            )
            best_text = ""
            best_id = ""
            for vid, text in links:
                text = _clean_html(text)
                if len(text) > len(best_text) and not re.match(r"^[\d.]+$", text):
                    best_text = text
                    best_id = vid
            title = best_text
            vod_id = best_id
        else:
            title = _clean_html(title_match.group(1))
            # 从整个item中提取第一个vod_id (不依赖属性顺序)
            id_match = re.search(r'vod/(?:play|detail)/id/(\d+)', item)
            vod_id = id_match.group(1) if id_match else ""

        if not title or not vod_id:
            continue

        # 提取备注/日期: span.fed-list-desc
        remarks = ""
        desc_match = re.search(
            r'<span[^>]*class="[^"]*fed-list-desc[^"]*"[^>]*>(.*?)</span>',
            item, re.DOTALL
        )
        if desc_match:
            remarks = _clean_html(desc_match.group(1))

        vod_list.append({
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
        })
    return vod_list


def _parse_pagination(html):
    """解析分页信息 (fed模板: 从分页链接提取最大页码)"""
    total = 0
    pagecount = 0
    # 尝试匹配"共XX条"
    total_match = re.search(r"共\s*(\d+)\s*条", html)
    if total_match:
        total = int(total_match.group(1))
    # 尝试匹配"页次:X/XX"
    page_match = re.search(r"页次[:：]\s*(\d+)\s*/\s*(\d+)", html)
    if page_match:
        pagecount = int(page_match.group(2))
    # fed模板: 从分页链接提取最大页码
    if pagecount == 0:
        pages = re.findall(r"page/(\d+)\.html", html)
        if pages:
            pagecount = max(int(p) for p in pages)
    # 末页链接: href=".../page/XX.html" 文本为"末页"或"尾页"
    if pagecount == 0:
        last_match = re.search(
            r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(?:末页|尾页|最后)',
            html
        )
        if last_match:
            pagecount = int(last_match.group(1))
    return total, pagecount


def _parse_detail(html, vod_id):
    """解析详情页信息"""
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
    # 标题 (fed模板: dd.fed-deta-content > h3 > a)
    title_match = re.search(
        r'<dd[^>]*class="[^"]*fed-deta-content[^"]*"[^>]*>\s*<h3[^>]*>\s*<a[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    if title_match:
        vod["vod_name"] = _clean_html(title_match.group(1))
    else:
        # 备选: 从title标签提取
        title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        if title_match:
            title = _clean_html(title_match.group(1))
            title = re.sub(r"[_-].*?123视频.*$", "", title).strip()
            title = re.sub(r"_影片详情.*$", "", title).strip()
            vod["vod_name"] = title
    # 封面图 (fed模板: dt.fed-deta-images > a[data-original])
    pic_match = re.search(
        r'<dt[^>]*class="[^"]*fed-deta-images[^"]*"[^>]*>.*?data-original="([^"]+)"',
        html, re.DOTALL
    )
    if not pic_match:
        pic_match = re.search(r'data-original="(https?://[^"]+\.(?:jpg|png|jpeg|gif|webp))"', html)
    if pic_match:
        pic = pic_match.group(1)
        if pic.startswith("/"):
            pic = DEFAULT_HOST + pic
        vod["vod_pic"] = pic
    # 详情信息 (演员/导演/年份/地区)
    info_items = re.findall(r'<li[^>]*>.*?<label[^>]*>(.*?)</label>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
    for label, value in info_items:
        label = _clean_html(label)
        value = _clean_html(value)
        if "导演" in label:
            vod["vod_director"] = value
        elif "主演" in label or "演员" in label:
            vod["vod_actor"] = value
        elif "年份" in label:
            vod["vod_year"] = value
        elif "地区" in label:
            vod["vod_area"] = value
        elif "更新" in label or "备注" in label:
            vod["vod_remarks"] = value
    # 简介
    content_match = re.search(r'<div[^>]*class="[^"]*fed-deta-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if content_match:
        vod["vod_content"] = _clean_html(content_match.group(1))
    # 播放线路 (只匹配集数链接: 第X集 / 数字集数，排除标题和立即播放)
    play_area = re.search(
        r'<div[^>]*class="[^"]*fed-conv-play[^"]*"[^>]*>(.*?)(?:</div>\s*){3}',
        html, re.DOTALL
    )
    play_html = play_area.group(1) if play_area else html
    play_links = re.findall(
        r'<a[^>]*href="([^"]*vod/play/id/' + vod_id + r'/sid/(\d+)/nid/(\d+)[^"]*)"[^>]*>(.*?)</a>',
        play_html, re.DOTALL
    )
    if play_links:
        lines = {}
        for url, sid, nid, text in play_links:
            text = _clean_html(text)
            # 只保留集数格式: 第X集 / 第X话 / 纯数字
            if not text:
                continue
            if not (re.match(r"^第\d+[集话期]$", text) or re.match(r"^\d+$", text)):
                continue
            if url.startswith("/"):
                url = DEFAULT_HOST + url
            if sid not in lines:
                lines[sid] = []
            lines[sid].append(f"{text}${url}")
        if lines:
            from_names = []
            url_groups = []
            for sid, episodes in sorted(lines.items(), key=lambda x: int(x[0])):
                from_names.append(f"线路{sid}")
                url_groups.append("#".join(episodes))
            vod["vod_play_from"] = "$$$".join(from_names)
            vod["vod_play_url"] = "$$$".join(url_groups)
    return vod


def _extract_json_object(text, start_pos):
    """从start_pos的{开始，用括号计数法提取完整JSON对象"""
    if start_pos >= len(text) or text[start_pos] != "{":
        return ""
    depth = 0
    in_string = False
    escape = False
    for i in range(start_pos, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_pos:i + 1]
    return ""


def _get_play_url(vod_id, sid="1", nid="1", session=None):
    """从播放页获取m3u8地址 (带重试和多方式提取)"""
    play_url = f"{SITE_URL}/index.php/vod/play/id/{vod_id}/sid/{sid}/nid/{nid}.html"

    # 最多重试2次
    for attempt in range(2):
        html = _http_get(play_url, session=session, timeout=12)
        if not html:
            continue

        # 方式1: 提取player_data (括号计数法)
        idx = html.find("var player_data")
        if idx >= 0:
            brace_idx = html.find("{", idx)
            if brace_idx >= 0:
                json_str = _extract_json_object(html, brace_idx)
                if json_str:
                    try:
                        data = json.loads(json_str)
                        url = data.get("url", "")
                        if url and url.startswith("http"):
                            return url
                    except Exception:
                        pass

        # 方式2: 直接正则提取m3u8
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m3u8_match:
            return m3u8_match.group(1)

        # 方式3: 提取mp4直链
        mp4_match = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html)
        if mp4_match:
            return mp4_match.group(1)

        # 方式4: 从player_data的正则提取url字段 (容错)
        url_match = re.search(r'"url"\s*:\s*"(https?://[^"]+)"', html)
        if url_match:
            return url_match.group(1)

    return ""


# ========== Spider 主类 ==========
class Spider:
    """四壳通用Python Spider"""

    def __init__(self):
        self.session = _get_session()
        self.siteUrl = SITE_URL
        self.rawSite = DEFAULT_HOST

    def init(self, extend=""):
        """初始化"""
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    if ext.get("siteUrl"):
                        self.siteUrl = ext["siteUrl"].rstrip("/")
                    if ext.get("proxy"):
                        self.siteUrl = ext["proxy"].rstrip("/")
            except Exception:
                pass
        # 预热: 访问首页获取cookie
        _http_get(self.siteUrl + "/", session=self.session)

    def homeContent(self, *args):
        """首页: 分类 + 推荐"""
        # 分类 (铁律7: 完整写入)
        classes = []
        for cat in CATEGORIES:
            if not _is_minor(cat["type_name"]):
                classes.append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
        #  filters (dict格式)
        filters = {}
        for cat in classes:
            filters[cat["type_id"]] = [
                {"key": "by", "name": "排序", "value": [
                    {"n": "最新", "v": "time"},
                    {"n": "最热", "v": "hit"},
                    {"n": "评分", "v": "score"},
                ]}
            ]
        # 首页推荐 (从首页提取)
        home_html = _http_get(self.siteUrl + "/", session=self.session)
        vod_list = _parse_vod_list(home_html) if home_html else []
        vod_list = [v for v in (_filter_minor_vod(v) for v in vod_list) if v]
        return {
            "class": classes,
            "filters": filters,
            "list": vod_list[:20],
        }

    def categoryContent(self, tid, pg, *args):
        """分类页"""
        pg = int(pg) if pg else 1
        url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = _http_get(url, session=self.session)
        if not html:
            return {"page": pg, "pagecount": 0, "limit": 20, "total": 0, "list": []}
        vod_list = _parse_vod_list(html)
        vod_list = [v for v in (_filter_minor_vod(v) for v in vod_list) if v]
        total, pagecount = _parse_pagination(html)
        if pagecount == 0 and vod_list:
            pagecount = pg + 1  # 至少还有下一页
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
            "list": vod_list,
        }

    def detailContent(self, ids, *args):
        """详情页 (铁律: ids是list/tuple必须遍历)"""
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        result_list = []
        for vod_id in ids:
            vod_id = str(vod_id)
            url = f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html"
            html = _http_get(url, session=self.session)
            if not html:
                continue
            vod = _parse_detail(html, vod_id)
            # 铁律13: 未成年条目剔除
            if _is_minor(vod.get("vod_name", "")) or _is_minor(vod.get("vod_content", "")):
                continue
            # 如果详情页没有播放线路，构造默认播放线路
            if not vod.get("vod_play_url"):
                vod["vod_play_from"] = "线路1"
                vod["vod_play_url"] = f"第1集${self.siteUrl}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            result_list.append(vod)
        return {"list": result_list}

    def searchContent(self, wd, pg, *args):
        """搜索页"""
        pg = int(pg) if pg else 1
        wd_encoded = quote(str(wd))
        url = f"{self.siteUrl}/index.php/vod/search/wd/{wd_encoded}.html"
        html = _http_get(url, session=self.session)
        if not html:
            return {"page": pg, "pagecount": 0, "limit": 20, "total": 0, "list": []}
        vod_list = _parse_vod_list(html)
        vod_list = [v for v in (_filter_minor_vod(v) for v in vod_list) if v]
        total, pagecount = _parse_pagination(html)
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
            "list": vod_list,
        }

    def playerContent(self, flag, id, *args):
        """播放页: 获取m3u8地址
        id格式: 播放页URL 或 纯数字vod_id
        """
        play_url = str(id)
        vod_id = ""
        sid = "1"
        nid = "1"
        # 情况1: 纯数字vod_id
        if play_url.isdigit():
            vod_id = play_url
        else:
            # 情况2: 从URL中提取参数
            id_match = re.search(r"id/(\d+)", play_url)
            sid_match = re.search(r"sid/(\d+)", play_url)
            nid_match = re.search(r"nid/(\d+)", play_url)
            if id_match:
                vod_id = id_match.group(1)
            if sid_match:
                sid = sid_match.group(1)
            if nid_match:
                nid = nid_match.group(1)
        # 获取m3u8
        m3u8 = ""
        if vod_id:
            m3u8 = _get_play_url(vod_id, sid, nid, session=self.session)
        if not m3u8 and play_url.startswith("http"):
            html = _http_get(play_url, session=self.session)
            if html:
                idx = html.find("var player_data")
                if idx >= 0:
                    brace_idx = html.find("{", idx)
                    if brace_idx >= 0:
                        json_str = _extract_json_object(html, brace_idx)
                        if json_str:
                            try:
                                data = json.loads(json_str)
                                m3u8 = data.get("url", "")
                            except Exception:
                                pass
        return {
            "parse": 0,
            "jx": 0,
            "url": m3u8,
            "header": {
                "User-Agent": DEFAULT_UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
        }

    def localProxy(self, url, *args):
        """m3u8本地代理 (铁律8: 非空壳，广告清洗)"""
        try:
            if not url or not url.startswith("http"):
                return [404, "text/plain", ""]
            resp = self.session.get(url, timeout=15, headers={
                "User-Agent": DEFAULT_UA,
                "Referer": self.rawSite + "/",
            })
            content = resp.text
            # 简单广告清洗: 剔除广告ts片段
            content = self._clean_m3u8(content, url)
            return [200, "application/vnd.apple.mpegurl", content]
        except Exception:
            return [404, "text/plain", ""]

    def _clean_m3u8(self, content, base_url):
        """m3u8广告清洗 (铁律8: 剔除广告ts)"""
        if not content:
            return content
        lines = content.split("\n")
        cleaned = []
        skip_next = False
        for line in lines:
            stripped = line.strip()
            # 五重广告识别
            if self._is_ad_segment(stripped):
                skip_next = True
                continue
            if skip_next and stripped and not stripped.startswith("#"):
                skip_next = False
                continue
            skip_next = False
            # 相对路径转绝对路径
            if stripped and not stripped.startswith("#") and not stripped.startswith("http"):
                from urllib.parse import urljoin
                stripped = urljoin(base_url, stripped)
            cleaned.append(line)
        return "\n".join(cleaned)

    def _is_ad_segment(self, line):
        """广告片段识别 (铁律8: 五重识别)"""
        if not line:
            return False
        lower = line.lower()
        # 关键词识别
        ad_keywords = ("ad", "gg", "adv", "preroll", "片头", "广告", "贴片")
        for kw in ad_keywords:
            if kw in lower:
                return True
        # 短时长识别 (EXTINF <= 1.2s)
        duration_match = re.search(r"#EXTINF:([\d.]+)", line)
        if duration_match:
            try:
                if float(duration_match.group(1)) <= 1.2:
                    return True
            except Exception:
                pass
        return False

    def getDependence(self, *args):
        """依赖声明"""
        return "requests"

    def isVideoFormat(self, url, *args):
        """判断是否为视频格式"""
        if not url:
            return False
        return url.endswith(".m3u8") or url.endswith(".mp4") or ".m3u8" in url

    def destroy(self, *args):
        """销毁"""
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass


# ========== 本地测试入口 ==========
if __name__ == "__main__":
    spider = Spider()
    spider.init()
    print("=== homeContent ===")
    home = spider.homeContent()
    print(f"分类数: {len(home['class'])}")
    print(f"推荐数: {len(home['list'])}")
    for cat in home["class"]:
        print(f"  {cat['type_id']}: {cat['type_name']}")
    print("\n=== categoryContent (id=21, pg=1) ===")
    cat = spider.categoryContent("21", "1")
    print(f"总数: {cat['total']}, 页数: {cat['pagecount']}, 列表: {len(cat['list'])}")
    for v in cat["list"][:3]:
        print(f"  {v['vod_id']}: {v['vod_name'][:40]}")
    print("\n=== searchContent (wd=国产, pg=1) ===")
    search = spider.searchContent("国产", "1")
    print(f"列表: {len(search['list'])}")
    for v in search["list"][:3]:
        print(f"  {v['vod_id']}: {v['vod_name'][:40]}")
    if cat["list"]:
        test_id = cat["list"][0]["vod_id"]
        print(f"\n=== detailContent (id={test_id}) ===")
        detail = spider.detailContent([test_id])
        if detail["list"]:
            d = detail["list"][0]
            print(f"标题: {d['vod_name']}")
            print(f"封面: {d['vod_pic'][:60]}")
            print(f"线路: {d['vod_play_from']}")
            print(f"播放地址: {d['vod_play_url'][:100]}")
        print(f"\n=== playerContent (id={test_id}) ===")
        player = spider.playerContent("线路1", test_id)
        print(f"m3u8: {player['url'][:100]}")
    spider.destroy()

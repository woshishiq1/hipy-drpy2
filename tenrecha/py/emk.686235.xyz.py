#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox Python 爬虫 - emk.686235.xyz
站点: https://emk.686235.xyz/
特点: 全站 JS 混淆（base64 反转 -> atob -> escape -> decodeURIComponent -> document.write）
      页面加载 JS 模板文件定义变量 h，替换 {@json_code} 占位符后写入 j_b64 JSON 数据
"""

import sys
sys.path.append("..")

import re
import json
import base64
import urllib.parse

# ============================================================
# 沙箱兼容层：base.spider 不存在时用 requests 兜底
# ============================================================
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            pass

        def fetch(self, url, headers=None, **kwargs):
            import requests
            r = requests.get(url, headers=headers or {}, timeout=15, verify=False)
            return r

        def post(self, url, data=None, headers=None, **kwargs):
            import requests
            r = requests.post(url, data=data, headers=headers or {}, timeout=15, verify=False)
            return r


class Spider(Spider):  # type: ignore[no-redef]
    pass


# ============================================================
# 站点配置
# ============================================================
SITE_URL = "https://emk.686235.xyz"

# 分类列表 (cid, name)
CATEGORIES = [
    ("41604214", "传媒作品"),
    ("41614214", "网黄女神"),
    ("41624214", "外围探花"),
    ("41634214", "直播大秀"),
    ("41644214", "绿帽淫妻"),
    ("41654214", "夫妻交换"),
    ("41664214", "亚洲媚黑"),
    ("41674214", "良家人妻"),
    ("41594245", "国产磁力"),
    ("41604245", "日本磁力"),
]

# 页面请求头（保留原始配置，内容获取需要）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": SITE_URL + "/",
}


# ============================================================
# 核心解码工具
# ============================================================
def _b64_decode_str(b64_str):
    """JS atob + escape + decodeURIComponent 等价：base64 解码为 bytes 再 UTF-8 解码"""
    decoded_bytes = base64.b64decode(b64_str)
    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError:
        percent_str = "".join(
            chr(b) if b < 128 else "%%%02X" % b for b in decoded_bytes
        )
        return urllib.parse.unquote(percent_str, encoding="utf-8")


def _decode_page(html_text):
    """
    解码全站通用的 JS 混淆页面。
    页面结构: function Xxx(x){...atob...escape...decodeURIComponent...} var p = Xxx('reversed_b64'.split('').reverse().join(''))
    解码后得到中间 HTML，其中通过 loadScript 加载 JS 模板并替换 {@json_code} 后 document.write 最终页面。
    返回: 解码后的中间 HTML（含 j_b64 JSON 数据）
    """
    # 匹配任意函数名的混淆模式
    match = re.search(
        r"function\s+\w+\(\w+\)\s*\{"
        r".*?window\.atob\(\w+\).*?"
        r"decodeURIComponent\(escape\(\w+\)\).*?"
        r"return\s+\w+;\s*\}"
        r'\s*var\s+\w+\s*=\s*\w+\(\'(.*?)\'\s*\.\s*split',
        html_text,
        re.DOTALL,
    )
    if not match:
        return None

    raw_reversed = match.group(1)
    # 反转字符串 (JS: .split('').reverse().join(''))
    b64_str = raw_reversed[::-1]
    decoded_bytes = base64.b64decode(b64_str)
    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError:
        percent_str = "".join(
            chr(b) if b < 128 else "%%%02X" % b for b in decoded_bytes
        )
        return urllib.parse.unquote(percent_str, encoding="utf-8")


def _extract_j_b64(text):
    """从解码后的中间 HTML 中提取 j_b64 并解析为 JSON dict"""
    match = re.search(r"j_b64\s*=\s*'([^']+)'", text)
    if not match:
        return None
    b64_str = match.group(1)
    try:
        json_str = base64.b64decode(b64_str).decode("utf-8")
        return json.loads(json_str)
    except Exception:
        return None


def _fetch_and_decode(self, url):
    """获取页面并解码，返回 j_b64 JSON dict 或 None"""
    try:
        r = self.fetch(url, headers=HEADERS)
        html = r.text if hasattr(r, "text") else r.content.decode("utf-8")
    except Exception:
        return None

    decoded = _decode_page(html)
    if not decoded:
        return None

    return _extract_j_b64(decoded)


# ============================================================
# 爬虫主体
# ============================================================
class Spider(Spider):  # type: ignore[no-redef]

    def init(self, ext=""):
        """框架要求的初始化方法"""
        pass

    def destroy(self):
        """框架要求的销毁方法"""
        pass

    def getName(self):
        return "emk.686235.xyz"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    @staticmethod
    def _fix_m3u8_url(url):
        """补全 m3u8 URL 的 md5 参数。
        部分 CDN 节点要求同时传 dir= 和 md=（值相同），缺少 md5 时
        返回 'file lost' 但 HTTP 200 + Content-Type 正确，
        导致 TVBox 误判拿到有效 m3u8 后转圈黑屏。"""
        if "play.m3u8" in url and "dir=" in url and "md5=" not in url:
            m = re.search(r'dir=([a-f0-9]+)', url)
            if m:
                url += "&md5=" + m.group(1)
        return url

    # ----------------------------------------------------------
    # 首页：分类列表 + 推荐
    # ----------------------------------------------------------
    def homeContent(self, filter=False):
        result = {"class": [], "filters": {}}

        # 分类列表
        for cid, name in CATEGORIES:
            result["class"].append({"type_id": cid, "type_name": name})

        # 推荐视频（从首页 j_b64 获取）
        try:
            data = _fetch_and_decode(self, SITE_URL + "/")
            if data and "l" in data:
                videos = []
                for section_key, section_list in data["l"].items():
                    for item in section_list:
                        url = item.get("url", "")
                        if not url:
                            continue
                        vod_id = url.strip("/")
                        videos.append({
                            "vod_id": vod_id,
                            "vod_name": item.get("title", ""),
                            "vod_pic": item.get("pic", ""),
                            "vod_remarks": "磁力" if "torrent" in url else "在线",
                        })
                # 去重
                seen = set()
                unique = []
                for v in videos:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        unique.append(v)
                result["list"] = unique
        except Exception:
            result["list"] = []

        return result

    def homeVideoContent(self):
        result = {"list": []}
        try:
            data = _fetch_and_decode(self, SITE_URL + "/")
            if data and "l" in data:
                seen = set()
                for section_list in data["l"].values():
                    for item in section_list:
                        url = item.get("url", "")
                        if not url:
                            continue
                        vod_id = url.strip("/")
                        if vod_id in seen:
                            continue
                        seen.add(vod_id)
                        result["list"].append({
                            "vod_id": vod_id,
                            "vod_name": item.get("title", ""),
                            "vod_pic": item.get("pic", ""),
                            "vod_remarks": "磁力" if "torrent" in url else "在线",
                        })
        except Exception:
            pass
        return result

    # ----------------------------------------------------------
    # 分类内容：列表页
    # ----------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        try:
            page = int(pg) if pg else 1
            url = f"{SITE_URL}/list/{tid}-{page}.html"
            data = _fetch_and_decode(self, url)

            if not data:
                return result

            # 视频列表
            video_list = []
            if "l" in data:
                for section_list in data["l"].values():
                    for item in section_list:
                        url_path = item.get("url", "")
                        if not url_path:
                            continue
                        vod_id = url_path.strip("/")
                        video_list.append({
                            "vod_id": vod_id,
                            "vod_name": item.get("title", ""),
                            "vod_pic": item.get("pic", ""),
                            "vod_remarks": "磁力" if "torrent" in url_path else "在线",
                        })

            # 去重
            seen = set()
            unique = []
            for v in video_list:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    unique.append(v)

            result["list"] = unique

            # 分页信息
            if "p" in data:
                p = data["p"]
                result["page"] = p.get("c", page)
                result["pagecount"] = p.get("t", 1)
                result["total"] = p.get("s", len(unique))
            else:
                result["page"] = page
                result["pagecount"] = page
                result["total"] = len(unique)

        except Exception:
            pass

        return result

    # ----------------------------------------------------------
    # 详情页：视频详情 / 种子详情
    # ----------------------------------------------------------
    def detailContent(self, ids):
        result = {"list": []}
        vod_id = ids[0] if isinstance(ids, list) else ids

        try:
            # 判断是视频还是种子
            if "torrent" in vod_id:
                url = f"{SITE_URL}/{vod_id}"
                data = _fetch_and_decode(self, url)
                if not data:
                    return result

                title = data.get("name", "")
                magnet = data.get("tm", "")
                torrent_url = data.get("tt", "")
                cover = ""
                # 从 tc 字段提取第一张封面图
                tc = data.get("tc", "")
                if tc:
                    img_match = re.search(r'<img\s+src="([^"]+)"', tc)
                    if img_match:
                        cover = img_match.group(1)

                # 播放源：磁力链 + torrent 下载
                play_parts = []
                if magnet:
                    play_parts.append(f"磁力播放${magnet}")
                if torrent_url:
                    play_parts.append(f"种子下载$torrent:{torrent_url}")

                vod_play_url = "#".join(play_parts) if play_parts else ""

                result["list"] = [{
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": cover,
                    "vod_play_from": "emk",
                    "vod_play_url": vod_play_url,
                    "vod_content": f"文件大小: {data.get('ts', '未知')} | 分辨率: {data.get('tr', '未知')}",
                }]

            else:
                # 视频详情
                url = f"{SITE_URL}/{vod_id}"
                data = _fetch_and_decode(self, url)
                if not data:
                    return result

                title = data.get("name", "")
                m3u8_url = data.get("m3", "")
                cover = data.get("co", "")
                cn = data.get("cn", "")

                # 分类名可能是 base64 编码（搜索结果页）
                try:
                    decoded_cn = base64.b64decode(cn).decode("utf-8")
                    if decoded_cn:
                        cn = decoded_cn
                except Exception:
                    pass

                # 修复：多源格式，每个线路独立成源，用 $$$ 分隔
                play_from_list = []
                play_url_list = []

                if m3u8_url:
                    play_from_list.append("emk")
                    play_url_list.append(f"正片${m3u8_url}")

                # CDN 备用线路
                cdn_list = data.get("cdn", [])
                for i, cdn in enumerate(cdn_list):
                    cdn_url = cdn.get("url", "")
                    cdn_name = cdn.get("name", f"线路{i+1}")
                    if cdn_url:
                        play_from_list.append(cdn_name)
                        play_url_list.append(f"正片${cdn_url}")

                vod_play_from = "$$$".join(play_from_list) if play_from_list else ""
                vod_play_url = "$$$".join(play_url_list) if play_url_list else ""

                result["list"] = [{
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": cover,
                    "vod_year": "",
                    "vod_area": "",
                    "type_name": cn,
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                    "vod_content": "",
                }]

        except Exception:
            pass

        return result

    # ----------------------------------------------------------
    # 搜索
    # ----------------------------------------------------------
    def searchContent(self, key, quick, pg=1):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        try:
            page = int(pg) if pg else 1
            content_b64 = base64.b64encode(key.encode("utf-8")).decode("utf-8")

            # 第一页走搜索接口，后续页用搜索结果的 ci 走 list 接口翻页
            if page <= 1:
                url = f"{SITE_URL}/search.php?content={content_b64}&type=1"
            else:
                # 先取第一页拿到 ci，再请求对应页
                first_url = f"{SITE_URL}/search.php?content={content_b64}&type=1"
                first_data = _fetch_and_decode(self, first_url)
                if not first_data:
                    return result
                ci = first_data.get("ci", "")
                if not ci:
                    return result
                url = f"{SITE_URL}/list/{ci}-{page}.html"

            data = _fetch_and_decode(self, url)
            if not data:
                return result

            video_list = []
            if "l" in data:
                for section_list in data["l"].values():
                    for item in section_list:
                        url_path = item.get("url", "")
                        if not url_path:
                            continue
                        vod_id = url_path.strip("/")
                        video_list.append({
                            "vod_id": vod_id,
                            "vod_name": item.get("title", ""),
                            "vod_pic": item.get("pic", ""),
                            "vod_remarks": "磁力" if "torrent" in url_path else "在线",
                        })

            seen = set()
            unique = []
            for v in video_list:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    unique.append(v)

            result["list"] = unique

            if "p" in data:
                p = data["p"]
                result["page"] = p.get("c", page)
                result["pagecount"] = p.get("t", 1)
                result["total"] = p.get("s", len(unique))

        except Exception:
            pass

        return result

    # ----------------------------------------------------------
    # 播放解析
    # ----------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        # 修复：header 必须是合法 JSON 字符串，绝不能用 ""
        result = {"parse": 0, "header": "{}", "url": "", "playUrl": ""}

        try:
            if not id:
                return result

            # 修复：播放专用头，不带 Accept-Encoding，避免 gzip 导致播放器无法解析
            play_headers = {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": SITE_URL + "/",
            }

            # torrent: 开头的种子下载链接 -> 返回直链
            if id.startswith("torrent:"):
                real_url = id[len("torrent:"):]
                result["url"] = real_url
                result["parse"] = 0
                result["header"] = json.dumps(play_headers)
                return result

            # magnet: 开头的磁力链接 -> 返回磁力链
            if id.startswith("magnet:"):
                result["url"] = id
                result["parse"] = 0
                result["header"] = json.dumps(play_headers)
                return result

            # m3u8 直链
            if ".m3u8" in id:
                result["url"] = self._fix_m3u8_url(id)
                result["parse"] = 0
                result["header"] = json.dumps(play_headers)
                result["playUrl"] = ""
                return result

            # CDN API URL -> 需要进一步请求获取 m3u8
            # 修复：必须用 play_headers（不含 Accept-Encoding）
            if "api.php" in id:
                try:
                    r = self.fetch(id, headers=play_headers)
                    resp_text = r.text if hasattr(r, "text") else r.content.decode("utf-8")
                    # CDN API 返回 JSON: {"m3u8Url": "...", "testFile": "..."}
                    try:
                        resp_json = json.loads(resp_text)
                        m3u8 = resp_json.get("m3u8Url") or resp_json.get("url") or resp_json.get("m3u8") or resp_json.get("play", "")
                        if m3u8:
                            result["url"] = self._fix_m3u8_url(m3u8)
                            result["parse"] = 0
                            result["header"] = json.dumps(play_headers)
                            return result
                    except json.JSONDecodeError:
                        pass
                    # 如果响应本身就是 URL
                    if resp_text.strip().startswith("http"):
                        result["url"] = self._fix_m3u8_url(resp_text.strip())
                        result["parse"] = 0
                        result["header"] = json.dumps(play_headers)
                        return result
                except Exception:
                    pass
                # 修复：API 解析失败时返回原始 URL 让播放器尝试，不要 parse=1 进 WebView 黑屏
                result["url"] = id
                result["parse"] = 0
                result["header"] = json.dumps(play_headers)
                return result

            # 其他直链
            result["url"] = id
            result["parse"] = 0
            result["header"] = json.dumps(play_headers)

        except Exception:
            result["url"] = id
            result["parse"] = 0
            result["header"] = json.dumps({"User-Agent": HEADERS["User-Agent"]})

        return result


# ============================================================
# 沙箱测试入口
# ============================================================
if __name__ == "__main__":
    spider = Spider()
    spider.init()

    print("=" * 60)
    print("1. 测试 homeContent (首页分类 + 推荐)")
    print("=" * 60)
    home = spider.homeContent()
    print(f"分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"  {c['type_name']} -> {c['type_id']}")
    print(f"推荐数: {len(home.get('list', []))}")
    if home.get("list"):
        v = home["list"][0]
        print(f"  [0] {v['vod_name'][:30]}... | {v['vod_id']}")

    print("\n" + "=" * 60)
    print("2. 测试 categoryContent (分类列表)")
    print("=" * 60)
    cat = spider.categoryContent("41604214", "1")
    print(f"当前页: {cat.get('page')}, 总页: {cat.get('pagecount')}, 总数: {cat.get('total')}")
    print(f"列表数: {len(cat.get('list', []))}")
    if cat.get("list"):
        v = cat["list"][0]
        print(f"  [0] {v['vod_name'][:30]}... | {v['vod_id']}")

    print("\n" + "=" * 60)
    print("3. 测试 detailContent (视频详情)")
    print("=" * 60)
    if cat.get("list"):
        first_id = cat["list"][0]["vod_id"]
        print(f"获取详情: {first_id}")
        detail = spider.detailContent([first_id])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d.get('vod_name', '')[:40]}")
            print(f"  封面: {d.get('vod_pic', '')}")
            print(f"  播放源: {d.get('vod_play_from', '')}")
            print(f"  播放URL: {d.get('vod_play_url', '')[:80]}")

    print("\n" + "=" * 60)
    print("4. 测试 searchContent (搜索)")
    print("=" * 60)
    search = spider.searchContent("国产", False)
    print(f"搜索结果数: {len(search.get('list', []))}")
    print(f"总页: {search.get('pagecount')}, 总数: {search.get('total')}")
    if search.get("list"):
        v = search["list"][0]
        print(f"  [0] {v['vod_name'][:30]}... | {v['vod_id']}")

    print("\n" + "=" * 60)
    print("5. 测试 playerContent (播放解析)")
    print("=" * 60)
    if "detail" in dir() and detail.get("list"):
        play_url = detail["list"][0].get("vod_play_url", "")
        if play_url:
            first_play = play_url.split("#")[0]
            flag = first_play.split("$")[0]
            url = first_play.split("$", 1)[1] if "$" in first_play else ""
            print(f"  flag={flag}, url={url[:80]}")
            player = spider.playerContent(flag, url, "")
            print(f"  解析结果: parse={player.get('parse')}, url={player.get('url', '')[:80]}")
            print(f"  header={player.get('header', '')[:60]}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

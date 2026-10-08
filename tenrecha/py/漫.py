# -*- coding: utf-8 -*-
"""
漫小肆韓漫 (ccrip.com) 爬虫 / TVBox 四壳通用 Spider
=====================================================
站点结构：
  首页        /                     最近更新
  分类列表    /booklist?tag=&area=&end=
  漫画详情    /book/{book_id}
  章节阅读    /chapter/{chapter_id}   图片 data-original，CDN 域名 jjmhw8.top
  搜索        /search?keyword=

依赖：仅标准库 + requests（TVBox 环境默认自带；无 requests 时自动降级 urllib）
用法：
  独立运行：  python3 漫小肆.py
  TVBox 加载：本文件为独立 class Spider，不继承 base.spider，13 接口齐全
"""

import re
import json
import time
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from html import unescape

# ============================================================
# 基础配置
# ============================================================
BASE_URL = "shturl.cc/14tjjUzd2b3"
IMG_CDN = "shturl.cc/xFk90HvODmH5"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
TIMEOUT = 15
RETRY = 3

# 分类配置（题材 / 地区 / 进度）
TAGS = ["全部", "青春", "性感", "长腿", "多人", "御姐", "巨乳", "新婚", "媳妇",
        "暧昧", "清纯", "调教", "少妇", "风骚", "同居", "淫乱", "好友", "女神",
        "诱惑", "偷情", "出轨", "正妹", "家教"]
AREAS = {"全部": "-1", "韩国": "1", "日本": "2", "台湾": "3"}
ENDS = {"全部": "-1", "连载": "0", "完结": "1"}

# ============================================================
# 敏感词古典映射脱敏（展示文本用，思考与输出全流程）
# ============================================================
CLASSICAL_MAP = {
    "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
    "激情": "云雨", "做爱": "云雨", "性交": "交欢", "欲": "情思", "高潮": "云端",
    "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱",
    "迷奸": "迷占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
    "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
    "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人", "护士": "药女",
    "教师": "先生", "医生": "郎中", "警察": "捕快", "军人": "军爷",
    "秘书": "掌印", "老板": "东家", "丈夫": "夫君", "妻子": "拙荆",
    "情人": "相好", "小三": "外遇", "二奶": "外室", "出轨": "翻墙",
    "偷情": "私会", "通奸": "私通", "嫖娼": "寻花", "卖淫": "卖身",
    "妓女": "花娘", "性骚扰": "轻薄", "猥亵": "猥亵", "露阴": "曝玉",
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
    "H漫": "春宫图", "h漫": "春宫图", "A漫": "风月图", "a漫": "风月图",
    "无遮": "素纱", "无遮挡": "素纱", "肉番": "云雨番", "里番": "禁苑番",
}

# 未成年关键词（命中则跳过该条目，凌驾所有规则）
JUVENILE_KEYWORDS = ["萝莉", "幼女", "少女", "童", "teen", "loli", "schoolgirl",
                      "豆蔻", "玉蕊", "碧玉", "稚子", "未成年", "underage", "小學生",
                      "小学生", "中学生", "初中生", "高中生"]


def desensitize(text):
    """敏感词古典映射脱敏；命中未成年关键词返回空字符串（调用方需跳过）"""
    if not text:
        return text
    lower = text.lower()
    for kw in JUVENILE_KEYWORDS:
        if kw.lower() in lower:
            return ""
    for k in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if k in text:
            text = text.replace(k, CLASSICAL_MAP[k])
    return text


def _clean_text(s):
    """去除 HTML 标签 + 反转义 + 压缩空白"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ============================================================
# HTTP 层（优先 requests，降级 urllib）
# ============================================================
try:
    import requests as _requests
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False


class HttpClient:
    def __init__(self):
        self.session = None
        if _HAS_REQUESTS:
            self.session = _requests.Session()
            self.session.headers.update({
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })

    def get(self, url, referer=None, timeout=TIMEOUT):
        headers = {}
        if referer:
            headers["Referer"] = referer
        for i in range(RETRY):
            try:
                if self.session:
                    r = self.session.get(url, headers=headers, timeout=timeout, verify=False)
                    r.encoding = r.apparent_encoding or "utf-8"
                    return r.text
                else:
                    import ssl as _ssl
                    ctx = _ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = _ssl.CERT_NONE
                    req = urllib.request.Request(url, headers={
                        "User-Agent": UA,
                        "Referer": referer or BASE_URL + "/",
                    })
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                        raw = resp.read()
                        return raw.decode("utf-8", errors="ignore")
            except Exception as e:
                if i == RETRY - 1:
                    return ""
                time.sleep(1 + i)
        return ""

    def get_image(self, url, referer=None):
        """下载图片二进制，用于本地代理"""
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        try:
            if self.session:
                r = self.session.get(url, headers=headers, timeout=TIMEOUT, verify=False)
                return r.content, r.headers.get("Content-Type", "image/jpeg")
            else:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                    return resp.read(), resp.headers.get("Content-Type", "image/jpeg")
        except Exception:
            return None, None


_http = HttpClient()

if _HAS_REQUESTS:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


# ============================================================
# 解析器（纯正则，零第三方依赖）
# ============================================================
def parse_manga_list(html):
    results = []
    li_blocks = re.split(r'(?=<li\b)', html)
    for block in li_blocks:
        if 'mh-item' not in block and '/book/' not in block:
            continue
        m_id = re.search(r'href="/book/(\d+)"', block)
        if not m_id:
            continue
        vid = m_id.group(1)
        pic = ""
        m_pic = re.search(r'<img[^>]*(?:data-original|src)="([^"]+)"', block)
        if m_pic:
            pic = m_pic.group(1)
        else:
            m_bg = re.search(r'background-image\s*:\s*url\(["\']?([^"\')]+)["\']?\)', block)
            if m_bg:
                pic = m_bg.group(1)
        name = ""
        m_name = re.search(r'<h2 class="title">\s*<a[^>]*>\s*(.*?)\s*</a>', block, re.DOTALL)
        if m_name:
            name = _clean_text(m_name.group(1))
        else:
            m_title = re.search(r'<a[^>]*title="([^"]+)"[^>]*>\s*<p class="mh-cover', block)
            if m_title:
                name = _clean_text(m_title.group(1))
        if not name:
            continue
        remarks = ""
        m_rem = re.search(r'<p class="chapter">\s*<span>[^<]*</span>\s*(.*?)\s*</p>', block, re.DOTALL)
        if m_rem:
            remarks = _clean_text(m_rem.group(1))
        if name and desensitize(name) == "":
            continue
        if remarks and desensitize(remarks) == "":
            continue
        if pic.startswith("//"):
            pic = "https:" + pic
        results.append({
            "vod_id": vid,
            "vod_name": desensitize(name),
            "vod_pic": pic,
            "vod_remarks": desensitize(remarks)[:80],
        })
    return results


def parse_pagination(html):
    page = 1
    pagecount = 1
    total_match = re.search(r'共\s*(\d+)\s*条', html)
    total = int(total_match.group(1)) if total_match else 0
    cur_match = re.search(r'class="[^"]*active[^"]*"[^>]*>\s*(\d+)\s*<', html)
    if cur_match:
        page = int(cur_match.group(1))
    last_match = re.search(r'href="[^"]*page=(\d+)"[^>]*>\s*末页', html)
    if last_match:
        pagecount = int(last_match.group(1))
    elif total > 0:
        pagecount = max(1, (total + 35) // 36)
    limit = 36
    return page, pagecount, limit, total


def parse_detail(html):
    info = {"vod_name": "", "vod_pic": "", "vod_content": "", "vod_remarks": "",
            "vod_author": "", "vod_area": "", "vod_year": ""}
    m = re.search(r'<h1>\s*(.*?)\s*</h1>', html, re.DOTALL)
    if m:
        info["vod_name"] = desensitize(_clean_text(m.group(1)))
    m = re.search(r'<div class="cover">\s*<img[^>]*src="([^"]+)"', html)
    if m:
        pic = m.group(1)
        if pic.startswith("//"):
            pic = "https:" + pic
        info["vod_pic"] = pic
    m = re.search(r'作者[：:]\s*(.*?)\s*</p>', html)
    if m:
        info["vod_author"] = _clean_text(m.group(1))
    m = re.search(r'状态[：:]\s*<span>\s*(.*?)\s*</span>', html)
    if m:
        info["vod_remarks"] = _clean_text(m.group(1))
    m = re.search(r'地区[：:].*?<a[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)
    if m:
        info["vod_area"] = _clean_text(m.group(1))
    m = re.search(r'更新时间[：:]\s*([\d\-]+)', html)
    if m:
        info["vod_year"] = m.group(1)[:4]
    tags = re.findall(r'<a href="/booklist/\?tag=[^"]+"[^>]*>\s*(.*?)\s*</a>', html)
    if tags:
        info["vod_remarks"] = (info["vod_remarks"] + " " + " ".join(tags)).strip()
    m = re.search(r'<p class="content"[^>]*>\s*(.*?)\s*</p>', html, re.DOTALL)
    if m:
        info["vod_content"] = desensitize(_clean_text(m.group(1)))

    chapters = []
    chap_pattern = re.compile(r'<a[^>]*href="/chapter/(\d+)"[^>]*>(.*?)</a>', re.DOTALL)
    seen = set()
    for m in chap_pattern.finditer(html):
        cid = m.group(1)
        cname = _clean_text(m.group(2))
        if not cname or cid in seen:
            continue
        if cname in ("开始阅读", "立即阅读", "阅读"):
            continue
        seen.add(cid)
        chapters.append({"chapter_id": cid, "chapter_name": desensitize(cname)})

    if desensitize(info["vod_name"]) == "":
        info["vod_name"] = ""
    return info, chapters


def parse_chapter_images(html):
    images = []
    pattern = re.compile(r'<img[^>]*(?:data-original|src)="([^"]+\.(?:jpg|jpeg|png|webp|gif))"', re.I)
    skip_keywords = ['wxqrcode', 'qrcode', 'logo', 'icon', 'banner', 'ad_', 'advert',
                     'header-img', 'footer', 'avatar', 'loading', 'spinner', 'placeholder',
                     '/static/images/']
    for m in pattern.finditer(html):
        url = m.group(1)
        if url.startswith("//"):
            url = "https:" + url
        lower = url.lower()
        if any(kw in lower for kw in skip_keywords):
            continue
        if '/static/upload/' not in url and 'jjmhw8' not in url and 'ccrip' not in url:
            continue
        if url not in images:
            images.append(url)
    return images


def parse_search(html):
    return parse_manga_list(html)


# ============================================================
# Spider 主类
# ============================================================
class Spider:
    """漫小肆韓漫 Spider — TVBox/影视仓/OK影视/PickTV 四壳通用"""

    def getDependence(self):
        return ""

    def init(self, extend=""):
        self.base_url = BASE_URL
        self.img_cdn = IMG_CDN
        self.proxy = None
        self.direct = False
        if extend:
            try:
                if isinstance(extend, str):
                    cfg = json.loads(extend)
                elif isinstance(extend, dict):
                    cfg = extend
                else:
                    cfg = {}
                if cfg.get("siteUrl"):
                    self.base_url = cfg["siteUrl"].rstrip("/")
                if cfg.get("imgCdn"):
                    self.img_cdn = cfg["imgCdn"].rstrip("/")
                if cfg.get("proxy"):
                    self.proxy = cfg["proxy"].rstrip("/")
                if cfg.get("direct"):
                    self.direct = True
            except Exception:
                pass
        self.raw_site = self.base_url
        if self.proxy and not self.direct:
            self.site_url = self.proxy
        else:
            self.site_url = self.base_url
        self.HOST = self.site_url
        self._cache = {}

    def homeContent(self, filter=False):
        classes = []
        filters = {}
        for i, tag in enumerate(TAGS):
            tid = f"tag_{i}"
            classes.append({"type_id": tid, "type_name": desensitize(tag) or tag})
            filters[tid] = [
                {"key": "area", "name": "地区", "init": "-1",
                 "value": [{"n": k, "v": v} for k, v in AREAS.items()]},
                {"key": "end", "name": "进度", "init": "-1",
                 "value": [{"n": k, "v": v} for k, v in ENDS.items()]},
            ]
        html = _http.get(self.site_url + "/", referer=self.raw_site + "/")
        list_data = parse_manga_list(html)
        return {"class": classes, "filters": filters, "list": list_data}

    def homeVideoContent(self):
        html = _http.get(self.site_url + "/", referer=self.raw_site + "/")
        list_data = parse_manga_list(html)
        return {"page": 1, "pagecount": 1, "limit": len(list_data),
                "total": len(list_data), "list": list_data}

    def categoryContent(self, tid, pg, filter=None, extend=None):
        if tid.startswith("tag_"):
            raw = tid[4:]
            if raw.isdigit():
                idx = int(raw)
                tag = TAGS[idx] if 0 <= idx < len(TAGS) else "全部"
            else:
                tag = raw
        else:
            tag = "全部"
        area_val = "-1"
        end_val = "-1"
        if extend and isinstance(extend, dict):
            raw_area = str(extend.get("area", "-1"))
            raw_end = str(extend.get("end", "-1"))
            if raw_area in AREAS.values():
                area_val = raw_area
            else:
                area_val = AREAS.get(raw_area, "-1")
            if raw_end in ENDS.values():
                end_val = raw_end
            else:
                end_val = ENDS.get(raw_end, "-1")
        params = {"tag": tag, "area": area_val, "end": end_val}
        if pg and str(pg).isdigit() and int(pg) > 1:
            params["page"] = pg
        url = self.site_url + "/booklist?" + urllib.parse.urlencode(params)
        html = _http.get(url, referer=self.raw_site + "/booklist")
        list_data = parse_manga_list(html)
        page, pagecount, limit, total = parse_pagination(html)
        return {"page": page, "pagecount": pagecount, "limit": limit,
                "total": total, "list": list_data}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        results = []
        for vid in ids:
            cache_key = f"detail_{vid}"
            if cache_key in self._cache:
                results.append(self._cache[cache_key])
                continue
            url = self.site_url + f"/book/{vid}"
            html = _http.get(url, referer=self.raw_site + "/")
            info, chapters = parse_detail(html)
            if not info["vod_name"]:
                continue
            vod_play_from = "默认"
            vod_play_url = "#".join(
                f"{c['chapter_name']}${c['chapter_id']}" for c in chapters
            )
            item = {
                "vod_id": str(vid),
                "vod_name": info["vod_name"],
                "vod_pic": info["vod_pic"],
                "vod_content": info["vod_content"],
                "vod_remarks": info["vod_remarks"],
                "vod_author": info["vod_author"],
                "vod_area": info["vod_area"],
                "vod_year": info["vod_year"],
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            }
            self._cache[cache_key] = item
            results.append(item)
        return {"list": results}

    def searchContent(self, key, quick=False, pg="1"):
        params = {"keyword": key}
        if pg and int(pg) > 1:
            params["page"] = pg
        url = self.site_url + "/search?" + urllib.parse.urlencode(params)
        html = _http.get(url, referer=self.raw_site + "/")
        list_data = parse_search(html)
        page, pagecount, limit, total = parse_pagination(html)
        return {"page": page, "pagecount": pagecount, "limit": limit,
                "total": total, "list": list_data}

    def playerContent(self, flag, id, vipFlags=None):
        cache_key = f"chapter_{id}"
        if cache_key in self._cache:
            images = self._cache[cache_key]
        else:
            url = self.site_url + f"/chapter/{id}"
            html = _http.get(url, referer=self.raw_site + "/")
            images = parse_chapter_images(html)
            self._cache[cache_key] = images
        if not images:
            return {"parse": 0, "jx": 0, "url": "", "header": {}, "format": "image/*"}
        header = {
            "User-Agent": UA,
            "Referer": self.raw_site + "/",
            "Origin": self.raw_site,
        }
        images_json = json.dumps(images, ensure_ascii=False)
        return {
            "parse": 0, "jx": 0, "url": images[0], "header": header,
            "format": "application/x-mpegURL",
            "images": images, "images_json": images_json,
        }

    def localProxy(self, params):
        if isinstance(params, dict):
            img_url = params.get("url", "")
        else:
            img_url = str(params)
        if not img_url:
            return [404, "text/plain", ""]
        content, ctype = _http.get_image(img_url, referer=self.raw_site + "/")
        if content is None:
            return [404, "text/plain", ""]
        return [200, ctype or "image/jpeg", content]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def action(self, action, params):
        if action == "getImages":
            cid = params.get("id", "") if isinstance(params, dict) else str(params)
            return self.playerContent("", cid).get("images_json", "[]")
        return ""

    def destroy(self):
        self._cache.clear()

    # 独立爬虫 API
    def get_categories(self):
        return {"tags": TAGS, "areas": AREAS, "ends": ENDS}

    def get_recommend(self, page=1):
        return self.homeVideoContent()

    def get_category_list(self, tag="全部", area="全部", end="全部", page=1):
        if isinstance(tag, int) or (isinstance(tag, str) and tag.isdigit()):
            tid = f"tag_{tag}"
        else:
            idx = TAGS.index(tag) if tag in TAGS else 0
            tid = f"tag_{idx}"
        area_val = area if area in AREAS.values() else AREAS.get(area, "-1")
        end_val = end if end in ENDS.values() else ENDS.get(end, "-1")
        return self.categoryContent(tid, page, extend={"area": area_val, "end": end_val})

    def get_manga_detail(self, book_id):
        result = self.detailContent([str(book_id)])
        return result["list"][0] if result["list"] else None

    def get_chapter_images(self, chapter_id):
        result = self.playerContent("", str(chapter_id))
        return result.get("images", [])

    def search_manga(self, keyword, page=1):
        return self.searchContent(keyword, pg=str(page))

    def download_chapter(self, chapter_id, save_dir="./download"):
        import os
        images = self.get_chapter_images(chapter_id)
        if not images:
            return 0
        os.makedirs(save_dir, exist_ok=True)
        count = 0
        for i, img_url in enumerate(images, 1):
            content, ctype = _http.get_image(img_url, referer=self.raw_site + "/")
            if content:
                ext = ".jpg"
                if "png" in (ctype or "").lower():
                    ext = ".png"
                elif "webp" in (ctype or "").lower():
                    ext = ".webp"
                fname = os.path.join(save_dir, f"{i:03d}{ext}")
                with open(fname, "wb") as f:
                    f.write(content)
                count += 1
                time.sleep(0.3)
        return count


if __name__ == "__main__":
    spider = Spider()
    spider.init()
    print("=" * 50)
    print("  漫小肆韓漫 Spider 自检模式")
    print("=" * 50)
    home = spider.homeContent()
    print(f"分类: {len(home['class'])}  推荐: {len(home['list'])}")
    cat = spider.categoryContent("tag_3", 1)
    print(f"分类(长腿): {len(cat['list'])} 条")
    sr = spider.searchContent("秘密")
    print(f"搜索: {len(sr['list'])} 条")
    if home["list"]:
        vid = home["list"][0]["vod_id"]
        det = spider.detailContent([vid])
        if det["list"]:
            d = det["list"][0]
            chaps = d["vod_play_url"].split("#") if d["vod_play_url"] else []
            print(f"详情: {d['vod_name']}  章节: {len(chaps)}")
            if chaps:
                cid = chaps[0].split("$")[1]
                imgs = spider.get_chapter_images(cid)
                print(f"章节图片: {len(imgs)} 张")
    print("=" * 50)
    print("  自检完成")
    print("=" * 50)
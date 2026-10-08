# -*- coding: utf-8 -*-
"""
OK影视 Spider - IFN影视 (cn1.ifn.watch)
网站结构分析（实际抓包确认）：
  - Next.js SSR + Supabase认证
  - 登录: POST {supabase}/auth/v1/token?grant_type=password  (apikey头)
  - 分类页: /category/{id}
  - 详情页: /detail/{base64_id}
  - 详情数据嵌在HTML中: "mediaId":"49825_0,1,4,128","episodes":[{"id":1594402,"title":"01"}]
  - 播放token: POST /api/play/token  body={mediaId:"完整字符串",episodeId:"数字ID",title}
  - 播放地址: /api/play/{token}.m3u8?ts=true&reslo=false  (reslo: false=1080P, true=4K)
  - TS分片代理: /api/ts?url={encoded}
  - 鉴权: Authorization: Bearer {access_token}
  - 作者：堂主
"""
import re
import json
import base64
import time
import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        pass

# ==================== 配置 ====================
HOST = "https://cn1.ifn.watch"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
LOGIN_EMAIL = "你的邮箱"
LOGIN_PASSWORD = "你的密码"

# Supabase配置（从网站JS中提取）
SUPABASE_URL = "https://rvcrrwdtggvbomvzvpev.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ2Y3Jyd2R0Z2d2Ym9tdnp2cGV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ5MzEwNjUsImV4cCI6MjA2MDUwNzA2NX0.eiNtiUxJxXZzYn1uFRtKaPAXim64vP6brgRWxgMcmyE"

# 分类ID映射 (从网站nav提取)
CATEGORIES = [
    {"type_id": "3", "type_name": "电影"},
    {"type_id": "4", "type_name": "剧集"},
    {"type_id": "5", "type_name": "综艺"},
    {"type_id": "6", "type_name": "动漫"},
    {"type_id": "8", "type_name": "短剧"},
    {"type_id": "7", "type_name": "纪录片"},
    {"type_id": "40", "type_name": "4K"},
]

# ==================== 正则 ====================
_RE_CARD_BLOCK = re.compile(
    r'href="(/detail/[A-Za-z0-9_-]+)"[^>]*>(.*?)</a>', re.S)
_RE_IMG_ALT = re.compile(r'alt="([^"]+)"', re.S)
_RE_IMG_SRC = re.compile(r'(?:data-src|src)="([^"]+)"', re.S)
_RE_RATING = re.compile(r'(\d+\.?\d*)\s*分', re.S)
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S)
_RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
_RE_DESC_TEXT = re.compile(r'>([^<]{15,300})<', re.S)
_RE_YEAR = re.compile(r'发行[:：]\s*</[^>]+>\s*(\d{4})', re.S)

# 详情页嵌入数据正则（Next.js SSR数据，HTML中为转义JSON）
_RE_DETAIL_MEDIA_ID = re.compile(r'\\"mediaId\\":\\"([^"\\]+)\\"')
_RE_DETAIL_EPISODES = re.compile(r'\\"episodes\\":(\[.*?\])')
_RE_DETAIL_EPISODE_ITEM = re.compile(r'\\"id\\":(\d+),\\"title\\":\\"([^"\\]*)\\"')
_RE_DETAIL_TITLE = re.compile(r'\\"title\\":\\"([^"\\]{1,100})\\"')
_RE_DETAIL_DESC = re.compile(r'\\"description\\":\\"([^"\\]*)\\"')
_RE_DETAIL_ACTOR = re.compile(r'\\"actor\\":\\"([^"\\]*)\\"')
_RE_DETAIL_DIRECTOR = re.compile(r'\\"director\\":\\"([^"\\]*)\\"')
_RE_DETAIL_TYPE = re.compile(r'\\"cidMapper\\":\\"([^"\\]*)\\"')
_RE_DETAIL_AREA = re.compile(r'\\"regional\\":\\"([^"\\]*)\\"')
_RE_DETAIL_SCORE = re.compile(r'\\"score\\":\\"([^"\\]*)\\"')
_RE_DETAIL_LANG = re.compile(r'\\"lang\\":\\"([^"\\]*)\\"')
_RE_DETAIL_UPDATE = re.compile(r'\\"updateStatus\\":\\"([^"\\]*)\\"')
_RE_DETAIL_DATE = re.compile(r'\\"date\\":\\"(\d{4})')


def _strip(t):
    return re.sub(r'<[^>]+>', '', t or '').strip()


def _b64_decode(s):
    try:
        return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', errors='replace')
    except Exception:
        return ""


# ==================== Spider类 ====================
class Spider(BaseSpider):
    def __init__(self):
        self._session = None
        self._access_token = None
        self._token_expire = 0

    def _get_session(self):
        if self._session is None:
            self._session = requests.Session()
            retry = Retry(total=2, backoff_factor=0.3,
                          status_forcelist=[500, 502, 503, 504])
            adapter = HTTPAdapter(pool_connections=5,
                                  pool_maxsize=5, max_retries=retry)
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            self._session.headers.update({
                "User-Agent": UA,
                "Referer": HOST + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
        return self._session

    def _auth_headers(self):
        h = {"Content-Type": "application/json"}
        if self._access_token:
            h["Authorization"] = "Bearer " + self._access_token
        return h

    def _ensure_login(self):
        """确保已登录，token过期则重新登录"""
        if self._access_token and time.time() < self._token_expire:
            return True
        return self._do_login()

    def _do_login(self):
        """通过Supabase Auth登录，获取access_token"""
        s = self._get_session()
        try:
            r = s.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
                json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                token = data.get("access_token")
                if token:
                    self._access_token = token
                    # Supabase token有效期3600秒，提前5分钟刷新
                    expires_in = data.get("expires_in", 3600)
                    self._token_expire = time.time() + expires_in - 300
                    return True
        except Exception:
            pass
        return False

    def _get(self, url, timeout=15):
        s = self._get_session()
        try:
            r = s.get(url, timeout=timeout)
            r.encoding = 'utf-8'
            return r.text
        except Exception:
            return ""

    def _get_json(self, url, timeout=10):
        s = self._get_session()
        try:
            r = s.get(url, timeout=timeout, headers=self._auth_headers())
            return r.json()
        except Exception:
            return {}

    def _post_json(self, url, data, timeout=10):
        s = self._get_session()
        try:
            r = s.post(url, json=data, timeout=timeout,
                       headers=self._auth_headers())
            return r.json()
        except Exception:
            return {}

    # ==================== HTML解析 ====================
    def _parse_videos(self, html):
        """从HTML中解析视频卡片列表"""
        videos = []
        seen = set()
        for m in _RE_CARD_BLOCK.finditer(html):
            link = m.group(1)
            block = m.group(2)
            detail_id = link.replace("/detail/", "")
            if detail_id in seen:
                continue
            seen.add(detail_id)
            # 标题
            alt = _RE_IMG_ALT.search(block)
            title = alt.group(1).strip() if alt else ""
            if not title:
                text = _strip(block)
                title = text[:30] if text else "未知"
            # 海报
            src = _RE_IMG_SRC.search(block)
            pic = src.group(1) if src else ""
            if pic and pic.startswith("/"):
                pic = HOST + pic
            # 评分
            rating = _RE_RATING.search(block)
            remark = rating.group(1) + "分" if rating else ""
            if title:
                videos.append({
                    "vod_id": detail_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
        return videos

    def _parse_detail(self, html, detail_id):
        """解析详情页信息（从Next.js嵌入的JSON数据中提取）"""
        result = {
            "vod_id": detail_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_year": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # --- 从嵌入JSON提取核心数据 ---
        # mediaId完整字符串，如 "49825_0,1,4,128"
        m_media = _RE_DETAIL_MEDIA_ID.search(html)
        full_media_id = m_media.group(1) if m_media else ""

        # 标题
        m_title = _RE_DETAIL_TITLE.search(html)
        if m_title:
            result["vod_name"] = m_title.group(1)
        if not result["vod_name"]:
            h1 = _RE_H1.search(html)
            if h1:
                result["vod_name"] = _strip(h1.group(1))
        if not result["vod_name"]:
            t = _RE_TITLE_TAG.search(html)
            if t:
                result["vod_name"] = t.group(1).split("|")[0].split("-")[0].strip()

        # 海报
        imgs = _RE_IMG_SRC.findall(html)
        for img in imgs:
            if "/api/image/" in img:
                result["vod_pic"] = HOST + img if img.startswith("/") else img
                break

        # 简介
        m_desc = _RE_DETAIL_DESC.search(html)
        if m_desc:
            result["vod_content"] = m_desc.group(1)
        if not result["vod_content"]:
            for m in _RE_DESC_TEXT.finditer(html):
                text = m.group(1).strip()
                if any(kw in text for kw in ['故事', '讲述', '简介', '发生', '改编', '影片']):
                    result["vod_content"] = text
                    break

        # 年份
        m_date = _RE_DETAIL_DATE.search(html)
        if m_date:
            result["vod_year"] = m_date.group(1)
        else:
            yr = _RE_YEAR.search(html)
            if yr:
                result["vod_year"] = yr.group(1)

        # 演员
        m_actor = _RE_DETAIL_ACTOR.search(html)
        if m_actor:
            result["vod_actor"] = m_actor.group(1)

        # 导演
        m_dir = _RE_DETAIL_DIRECTOR.search(html)
        if m_dir:
            result["vod_director"] = m_dir.group(1)

        # 类型/地区
        m_type = _RE_DETAIL_TYPE.search(html)
        if m_type:
            result["vod_area"] = m_type.group(1)
        m_area = _RE_DETAIL_AREA.search(html)
        if m_area and m_area.group(1):
            result["vod_area"] = (result["vod_area"] + " " + m_area.group(1)).strip()

        # 评分/更新状态
        m_score = _RE_DETAIL_SCORE.search(html)
        m_update = _RE_DETAIL_UPDATE.search(html)
        remarks = []
        if m_score and m_score.group(1):
            remarks.append(m_score.group(1) + "分")
        if m_update and m_update.group(1):
            remarks.append(m_update.group(1))
        result["vod_remarks"] = " ".join(remarks)

        # --- 解析剧集列表 ---
        episodes = self._parse_episodes_from_data(html)
        if episodes and full_media_id:
            result["vod_play_from"] = "IFN线路"
            # vod_play_url格式: 集名$fullMediaId|episodeId
            result["vod_play_url"] = "#".join(
                f"{ep['title']}${full_media_id}|{ep['id']}" for ep in episodes)
        elif full_media_id:
            # 没有剧集列表，尝试用默认episodeId
            m_epid = re.search(r'\\"episodeId\\":(\d+)', html)
            ep_id = m_epid.group(1) if m_epid else "0"
            result["vod_play_from"] = "IFN线路"
            result["vod_play_url"] = f"正片${full_media_id}|{ep_id}"
        else:
            # 兜底：从base64 detail_id解析
            decoded = _b64_decode(detail_id)
            result["vod_play_from"] = "IFN线路"
            result["vod_play_url"] = f"播放${decoded}|0"

        return result

    def _parse_episodes_from_data(self, html):
        """从Next.js嵌入数据中解析剧集列表"""
        episodes = []
        # 先找episodes数组
        m_eps = _RE_DETAIL_EPISODES.search(html)
        if m_eps:
            eps_str = m_eps.group(1)
            for m in _RE_DETAIL_EPISODE_ITEM.finditer(eps_str):
                episodes.append({"id": m.group(1), "title": m.group(2)})
        return episodes

    # ==================== OK影视标准接口 ====================
    def init(self, extend=""):
        try:
            self._get_session().get(HOST, timeout=8)
        except Exception:
            pass

    def getName(self):
        return "IFN影视"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        pass

    def destroy(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass

    def homeContent(self, filter=False):
        html = self._get(HOST)
        videos = self._parse_videos(html)[:60]
        return {"class": CATEGORIES, "list": videos}

    def homeVideoContent(self):
        html = self._get(HOST)
        videos = self._parse_videos(html)[:40]
        return {"list": videos}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1
        url = f"{HOST}/category/{tid}"
        if pn > 1:
            url += f"?page={pn}"
        html = self._get(url)
        videos = self._parse_videos(html)
        return {
            "list": videos,
            "page": pn,
            "pagecount": pn + 10 if len(videos) >= 20 else pn,
            "limit": 24,
            "total": 0,
        }

    def detailContent(self, ids):
        try:
            detail_id = str(ids[0])
            url = f"{HOST}/detail/{detail_id}"
            html = self._get(url)
            if not html:
                return {"list": []}
            info = self._parse_detail(html, detail_id)
            return {"list": [info]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        """
        获取播放地址
        id格式: 集名$fullMediaId|episodeId
        例如: 01$49825_0,1,4,128|1594402
        """
        try:
            raw = str(id)
            # 解析id: title$mediaId|episodeId
            if "$" in raw:
                raw = raw.split("$", 1)[1]
            if "|" in raw:
                media_id, episode_id = raw.split("|", 1)
            elif "_" in raw:
                parts = raw.split("_", 1)
                media_id = parts[0]
                episode_id = parts[1] if len(parts) > 1 else "0"
            else:
                media_id = raw
                episode_id = "0"

            # 确保登录
            if not self._ensure_login():
                return {"parse": 0, "url": "", "msg": "登录失败，请检查账号"}

            # 先GET检查是否已有有效token（不扣积分）
            check_url = f"{HOST}/api/play/token?mediaId={quote(media_id)}&episodeId={episode_id}"
            check_data = self._get_json(check_url)
            token = ""
            if check_data.get("success") and check_data.get("token"):
                token = check_data["token"]
            else:
                # POST请求新token（会消耗积分）
                post_data = self._post_json(
                    f"{HOST}/api/play/token",
                    {"mediaId": media_id, "episodeId": episode_id, "title": "播放"}
                )
                if post_data.get("success") and post_data.get("token"):
                    token = post_data["token"]
                else:
                    msg = post_data.get("message", "获取播放令牌失败")
                    return {"parse": 0, "url": "", "msg": msg}

            if not token:
                return {"parse": 0, "url": "", "msg": "获取播放令牌失败"}

            # 构造播放地址 (reslo: false=1080P, true=4K)
            play_url = f"{HOST}/api/play/{token}.m3u8?ts=true&reslo=false"
            return {"parse": 0, "url": play_url, "header": ""}
        except Exception as e:
            return {"parse": 0, "url": "", "msg": str(e)[:100]}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pn = max(int(str(pg)), 1)
            url = f"{HOST}/search?q={quote(key)}"
            if pn > 1:
                url += f"&page={pn}"
            html = self._get(url)
            videos = self._parse_videos(html)
            return {"list": videos, "page": pn}
        except Exception:
            return {"list": [], "page": 1}

    def localProxy(self, param):
        pass


# ==================== 独立运行测试 ====================
if __name__ == "__main__":
    spider = Spider()
    print("=" * 50)
    print("IFN影视 Spider 测试")
    print("=" * 50)

    # 测试登录
    print("\n[0] 测试Supabase登录...")
    if spider._ensure_login():
        print("  登录成功! token:", spider._access_token[:40] + "...")
    else:
        print("  登录失败!")

    # 测试首页
    print("\n[1] 测试首页...")
    home = spider.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    print(f"  视频数: {len(home.get('list', []))}")
    if home.get("list"):
        v = home["list"][0]
        print(f"  第一个: {v['vod_name']} (id={v['vod_id'][:25]}...)")

    # 测试分类
    print("\n[2] 测试电影分类...")
    cat = spider.categoryContent("3", 1)
    print(f"  视频数: {len(cat.get('list', []))}")

    # 测试详情
    if home.get("list"):
        vid = home["list"][0]["vod_id"]
        print(f"\n[3] 测试详情 (id={vid[:25]}...)...")
        detail = spider.detailContent([vid])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d['vod_name']}")
            print(f"  年份: {d['vod_year']}")
            print(f"  演员: {d['vod_actor'][:40]}")
            print(f"  类型: {d['vod_area']}")
            print(f"  评分: {d['vod_remarks']}")
            print(f"  播放源: {d['vod_play_from']}")
            eps = d['vod_play_url'].split('#') if d['vod_play_url'] else []
            print(f"  剧集数: {len(eps)}")
            if eps:
                print(f"  第一集: {eps[0][:60]}")

    # 测试搜索
    print("\n[4] 测试搜索...")
    search = spider.searchContent("金色")
    print(f"  结果数: {len(search.get('list', []))}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
# coding=utf-8
# !/usr/bin/python
#发送任何内容到【hdys.top@gmail.com】获取最新地址。
"""

作者 丢丢喵 🚓 内容均从互联网收集而来 仅供交流学习使用 版权归原创者所有 如侵犯了您的权益 请通知作者 将及时删除侵权内容
                   ====================Diudiumiao====================

"""

from Crypto.Util.Padding import unpad
from Crypto.Util.Padding import pad
from urllib.parse import unquote
from Crypto.Cipher import ARC4
from urllib.parse import quote
from base.spider import Spider
from Crypto.Cipher import AES
from datetime import datetime
from bs4 import BeautifulSoup
from base64 import b64decode
import urllib.request
import urllib.parse
import datetime
import binascii
import requests
import random
import base64
import html
import json
import time
import sys
import re
import os

sys.path.append('..')

# ==================== 多域名配置区域 ====================
# 发布页地址（用于自动获取最新可用域名）
pub_urls = [
   "https://abc.hdfby.com",
   "https://b.hdfby.com",
   "https://b.hdfby.net",
   "https://b.hdfby.org",
]

# 备用视频站域名（当发布页不可用时依次尝试）
domain_list = [
   "https://hd28.huadutx.com/",
   "https://rb.huaduys.org/",
]
# =======================================================

headerz = {
   'sec-ch-ua': '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
   'sec-ch-ua-mobile': '?0',
   'sec-ch-ua-platform': '"Windows"',
   'Upgrade-Insecure-Requests': '1',
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
   'Sec-Fetch-Site': 'none',
   'Sec-Fetch-Mode': 'navigate',
   'Sec-Fetch-User': '?1',
   'Sec-Fetch-Dest': 'document',
   'Accept-Language': 'zh-CN,zh;q=0.9',
   'Accept-Encoding': 'gzip, deflate'
         }

xurl = domain_list[0]
headerx = None


def check_domain(url):
   """检测域名是否可用"""
   try:
       test_url = url if url.endswith('/') else url + '/'
       resp = requests.get(test_url, headers=headerz, timeout=8, allow_redirects=True)
       if resp.status_code == 200 and ('花都' in resp.text or 'huadu' in resp.text or 'vodtype' in resp.text or 'voddetail' in resp.text):
           return True
   except Exception:
       pass
   return False


def get_working_domain():
   """从发布页获取最新可用域名，失败则使用备用域名"""
   global xurl
   # 1. 尝试从发布页获取
   for pub in pub_urls:
       try:
           resp = requests.get(pub, headers=headerz, timeout=10, allow_redirects=True)
           resp.encoding = 'utf-8'
           text = resp.text
           # 提取发布页中指向视频站的链接
           candidates = re.findall(r'https?://[a-zA-Z0-9\-\.]+\.(?:com|net|org|top|cc|vip)/?', text)
           seen = set()
           for cand in candidates:
               cand = cand if cand.endswith('/') else cand + '/'
               if cand in seen:
                   continue
               seen.add(cand)
               if check_domain(cand):
                   xurl = cand
                   return xurl
       except Exception:
           continue

   # 2. 发布页全部失败，尝试备用域名
   for dm in domain_list:
       if check_domain(dm):
           xurl = dm
           return xurl

   # 3. 全部失败，使用默认第一个
   xurl = domain_list[0]
   return xurl


def build_headerx(target_url=None):
   """根据当前可用域名构建请求头"""
   global xurl, headerx
   if target_url is None:
       target_url = xurl

   domain = target_url.replace("https://", "").replace("http://", "").split('/')[0]

   # 获取Cookie
   try:
       response = requests.get(target_url, headers=headerz, timeout=10)
       cookie_dict = {}
       for cookie in response.cookies:
           cookie_dict[cookie.name] = cookie.value
       first_cookie_key = None
       first_cookie_value = None
       server_session_value = cookie_dict.get('server_name_session')
       for key, value in cookie_dict.items():
           if key != 'server_name_session':
               first_cookie_key = key
               first_cookie_value = value
               break
   except Exception:
       first_cookie_key = ""
       first_cookie_value = ""
       server_session_value = ""

   cookie_str = ""
   if first_cookie_key and first_cookie_value:
       cookie_str += f"{first_cookie_key}={first_cookie_value}; "
   if server_session_value:
       cookie_str += f"server_name_session={server_session_value}"

   headerx = {
       "Host": domain,
       "Connection": "keep-alive",
       "sec-ch-ua": '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
       "sec-ch-ua-mobile": "?0",
       "sec-ch-ua-platform": '"Windows"',
       "Upgrade-Insecure-Requests": "1",
       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
       "Sec-Fetch-Site": "same-origin",
       "Sec-Fetch-Mode": "navigate",
       "Sec-Fetch-Dest": "document",
       "Referer": target_url,
       "Accept-Language": "zh-CN,zh;q=0.9",
       "Cookie": cookie_str,
       "Accept-Encoding": "gzip, deflate"
   }
   return headerx


headers = {
   'User-Agent': 'Linux; Android 12; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.101 Mobile Safari/537.36'
         }


class Spider(Spider):
   global xurl
   global headerx
   global headers

   # 分类排序偏好(按名称), 未提及的分类保持页面原顺序
   _CLASS_ORDER = [
       "中字无码", "国产", "AI短剧", "欧美中字", "欧美",
       "国产精品", "国产传媒", "糖心Vlog", "步兵无码", "中文字幕",
       "无字幕", "动漫", "中字有码", "骑兵有码", "中字里番", "3D动漫",
   ]

   def _sort_classes(self, classes):
        """按 _CLASS_ORDER 名称顺序重排分类, 未提及的分类保持原相对顺序"""
        order = {name: i for i, name in enumerate(self._CLASS_ORDER)}
        ordered = [c for c in classes if c["type_name"] in order]
        rest = [c for c in classes if c["type_name"] not in order]
        ordered.sort(key=lambda c: order[c["type_name"]])
        return ordered + rest

   def getName(self):
       return "首页"

   def init(self, extend):
       # 初始化时自动获取可用域名并构建Header
       get_working_domain()
       build_headerx()

   def isVideoFormat(self, url):
       pass

   def manualVideoCheck(self):
       pass

   def extract_middle_text(self, text, start_str, end_str, pl, start_index1: str = '', end_index2: str = ''):
       if pl == 3:
           plx = []
           while True:
               start_index = text.find(start_str)
               if start_index == -1:
                   break
               end_index = text.find(end_str, start_index + len(start_str))
               if end_index == -1:
                   break
               middle_text = text[start_index + len(start_str):end_index]
               plx.append(middle_text)
               text = text.replace(start_str + middle_text + end_str, '')
           if len(plx) > 0:
               purl = ''
               for i in range(len(plx)):
                   matches = re.findall(start_index1, plx[i])
                   output = ""
                   for match in matches:
                       match3 = re.search(r'(?:^|[^0-9])(\d+)(?:[^0-9]|$)', match[1])
                       if match3:
                           number = match3.group(1)
                       else:
                           number = 0
                       if 'http' not in match[0]:
                           output += f"#{match[1]}${number}{xurl}{match[0]}"
                       else:
                           output += f"#{match[1]}${number}{match[0]}"
                   output = output[1:]
                   purl = purl + output + "$$$"
               purl = purl[:-3]
               return purl
           else:
               return ""
       else:
           start_index = text.find(start_str)
           if start_index == -1:
               return ""
           end_index = text.find(end_str, start_index + len(start_str))
           if end_index == -1:
               return ""

       if pl == 0:
           middle_text = text[start_index + len(start_str):end_index]
           return middle_text.replace("\\", "")

       if pl == 1:
           middle_text = text[start_index + len(start_str):end_index]
           matches = re.findall(start_index1, middle_text)
           if matches:
               jg = ' '.join(matches)
               return jg

       if pl == 2:
           middle_text = text[start_index + len(start_str):end_index]
           matches = re.findall(start_index1, middle_text)
           if matches:
               new_list = [f'{item}' for item in matches]
               jg = '$$$'.join(new_list)
               return jg

   def parse_videos_from_doc(self, doc, xurl):
       videos = []

       skip_names = ["广告点赞"]

       soups = doc.find_all('ul', class_="stui-vodlist clearfix")

       for soup in soups:
           vods = soup.find_all('li')

           for vod in vods:

               remarks = vod.find('a', class_="stui-vodlist__thumb picture w-thumb img-shadow")
               remark = remarks.text.strip() + "点赞"
               if remark in skip_names:
                   continue

               names = vod.find('h4', class_="title text-overflow")
               name = names.text.strip()

               id = names.find('a')['href']

               pic = vod.find('img')['data-original']
               if 'http' not in pic:
                   pic = xurl + pic

               video = {
                   "vod_id": id,
                   "vod_name": name,
                   "vod_pic": pic,
                   "vod_remarks": '集多▶️' + remark
                       }
               videos.append(video)

       return videos

   def homeContent(self, filter):
       result = {"class": []}
       seen_ids = set()

       detail = requests.get(url=xurl, headers=headerx)
       detail.encoding = "utf-8"
       res = detail.text
       doc = BeautifulSoup(res, "lxml")

       # 1. 提取主导航栏分类（一级分类：中文字幕、无字幕、国产、动漫、欧美）
       soups = doc.find_all('ul', class_="stui-header__menu type-slide")
       for soup in soups:
           vods = soup.find_all('li')
           for vod in vods:
               name = vod.text.strip()
               # 跳过首页、发布页、VPN下载
               skip_names = ["首页", "发布页", "VPN下载"]
               if name in skip_names:
                   continue
               a_tag = vod.find('a')
               if not a_tag:
                   continue
               id1 = a_tag.get('href', '')
               if not id1:
                   continue
               fenge = id1.split(".html")
               id = f"{fenge[0]}-----------.html"
               id = id.replace('vodtype', 'vodshow')
               if id not in seen_ids:
                    seen_ids.add(id)
                    result["class"].append({"type_id": id, "type_name": name})

       # 2. 提取页面中的所有子分类链接（二级分类）
       # 中字无码、中字有码、步兵无码、骑兵有码、国产精品、国产传媒、糖心Vlog、欧美中字、中字里番、3D动漫、AI短剧
       sub_links = doc.find_all('a', href=re.compile(r'/vodshow/\d+-----------\.html'))
       for link in sub_links:
           href = link.get('href', '')
           name = link.text.strip()
           if not name or not href:
               continue
           # 排除已添加的一级分类（1-5）避免重复
           match = re.search(r'/vodshow/(\d+)-----------\.html', href)
           if match:
               cid_num = match.group(1)
               if cid_num in ['1', '2', '3', '4', '5']:
                   continue
           if href not in seen_ids:
                seen_ids.add(href)
                result["class"].append({"type_id": href, "type_name": name})

       # 按排序偏好(_CLASS_ORDER)重排分类
       result["class"] = self._sort_classes(result["class"])
       return result

   def homeVideoContent(self):
       videos = []

       detail = requests.get(url=xurl, headers=headerx)
       detail.encoding = "utf-8"
       res = detail.text
       doc = BeautifulSoup(res, "lxml")
       videos = self.parse_videos_from_doc(doc, xurl)

       result = {'list': videos}
       return result

   def categoryContent(self, cid, pg, filter, ext):
       result = {}
       videos = []

       if pg:
           page = int(pg)
       else:
           page = 1

       fenge = cid.split("---.html")
       url = f'{xurl}{fenge[0]}{str(page)}---.html'
       detail = requests.get(url=url, headers=headerx)
       detail.encoding = "utf-8"
       res = detail.text
       doc = BeautifulSoup(res, "lxml")
       videos = self.parse_videos_from_doc(doc, xurl)

       result = {'list': videos}
       result['page'] = pg
       result['pagecount'] = 9999
       result['limit'] = 90
       result['total'] = 999999
       return result

   def detailContent(self, ids):
       did = ids[0]
       result = {}
       videos = []
       xianlu = ''
       bofang = ''

       if 'http' not in did:
           did = xurl + did

       res = requests.get(url=did, headers=headerx)
       res.encoding = "utf-8"
       res = res.text
       res = html.unescape(res)

       url = 'http://rihou.cc:88/je.json'
       response = requests.get(url)
       response.encoding = 'utf-8'
       code = response.text
       name = self.extract_middle_text(code, "s1='", "'", 0)
       Jumps = self.extract_middle_text(code, "s2='", "'", 0)

       content = '集多🎉为您介绍剧情📢' + self.extract_middle_text(res, '标题：', '</span>', 1, 'alt="(.*?)">')

       director = self.extract_middle_text(res, '分类：', '</p>', 1, 'target=".*?">(.*?)</a>')

       actor = self.extract_middle_text(res, '演员：', '</span>', 1, 'target=".*?">(.*?)</a>')

       remarks = self.extract_middle_text(res, '类别：', '</li>', 1, 'target=".*?">(.*?)</a>')

       year = self.extract_middle_text(res, '日期：', 'p>', 1, '</strong>(.*?)<')

       area = self.extract_middle_text(res, '时长：', 'p>', 1, '</strong>(.*?)<')

       if name not in content:
           bofang = Jumps
           xianlu = '1'
       else:
           id = self.extract_middle_text(res, 'class="btn btn-primary" href="', '"', 0)
           if 'http' not in id:
               id = xurl + id

           name = "集多请您欣赏"

           bofang = name + '$' + id

           xianlu = '花都专线'

       videos.append({
           "vod_id": did,
           "vod_director": director,
           "vod_actor": actor,
           "vod_remarks": remarks,
           "vod_year": year,
           "vod_area": area,
           "vod_content": content,
           "vod_play_from": xianlu,
           "vod_play_url": bofang
                    })

       result['list'] = videos
       return result

   def playerContent(self, flag, id, vipFlags):

       detail = requests.get(url=id, headers=headerx)
       detail.encoding = "utf-8"
       res = detail.text

       url = self.extract_middle_text(res, '"","url":"', '"', 0).replace('\\', '')
       base64_decoded_bytes = base64.b64decode(url)
       base64_decoded_string = base64_decoded_bytes.decode('utf-8')
       url = unquote(base64_decoded_string)

       result = {}
       result["parse"] = 0
       result["playUrl"] = ''
       result["url"] = url
       result["header"] = headers
       return result

   def searchContentPage(self, key, quick, pg):
       result = {}
       videos = []

       url = f'{xurl}/vodsearch/-------------.html?wd={key}'
       detail = requests.get(url=url, headers=headerx)
       detail.encoding = "utf-8"
       res = detail.text
       doc = BeautifulSoup(res, "lxml")
       videos = self.parse_videos_from_doc(doc, xurl)

       result['list'] = videos
       result['page'] = pg
       result['pagecount'] = 9999
       result['limit'] = 90
       result['total'] = 999999
       return result

   def searchContent(self, key, quick, pg="1"):
       return self.searchContentPage(key, quick, '1')

   def localProxy(self, params):
       if params['type'] == "m3u8":
           return self.proxyM3u8(params)
       elif params['type'] == "media":
           return self.proxyMedia(params)
       elif params['type'] == "ts":
           return self.proxyTs(params)
       return None

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====

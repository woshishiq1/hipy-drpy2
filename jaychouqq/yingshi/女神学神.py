# -*- coding: utf-8 -*-
# xts.mtyx4.beer — TvBox Python 源
# 基于 PyramidStore (CatVod) Spider 接口
# 站点类型：苹果CMS (MacCMS) v10 + qyu5_pc 模板
# 特征：详情页不存在(error)，播放页承载标题+播放器数据，单集单视频无播放列表
# URL 路由：/cn/home/web/index.php/vod/{type|play|search}/...@猪猪

import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
from urllib.parse import quote, unquote

try:
    from Crypto.Cipher import AES
    import base64
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


def _log(msg):
    try:
        sys.stderr.write("[MTYX] " + str(msg) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


class Spider(Spider):

    HOST = "https://xts.mtyx4.beer"
    PREFIX = "/cn/home/web"
    BASE = HOST + PREFIX + "/index.php/vod"

    # ── 分类（从站点实际 HTML 提取的真实 ID） ──
    CATE = {
        "女神学生": "21",
        "美女直播": "22",
        "人妻系列": "23",
        "强奸乱伦": "24",
        "自拍偷拍": "25",
        "制服诱惑": "26",
        "巨乳系列": "27",
        "自慰系列": "28",
        "国产视频": "29",
        "无码视频": "30",
        "有码31": "31",
        "中文字幕": "32",
        "日韩精品": "33",
        "欧美精品": "34",
        "动漫精品": "35",
        "三级伦理": "36",
    }

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    # ── 预编译正则 ──

    # 列表项（qyu5_pc 模板结构）：
    # <li id="video-XXX"><div class="video">
    #   <a href="...vod/play/id/XXX/sid/1/nid/1.html" title="标题" class="thumbnail">
    #     <div class="video-thumb"><img src="..." alt="..."></div>
    #     <span class="video-rating ...">9.0%</span>
    #     <span class="video-title">标题</span>
    #     <div class="video-details"><span>日期</span><span>播放次数</span></div>
    #   </a>
    # </div></li>
    RE_LIST_ITEM = re.compile(
        r'<li\s+id="video-(\d+)">\s*<div\s+class="video">\s*'
        r'<a\s+href="[^"]*vod/play/id/\1/sid/(\d+)/nid/(\d+)\.html"[^>]*'
        r'\s+title="([^"]*)"[^>]*>\s*'
        r'<div\s+class="video-thumb">\s*'
        r'<img[^>]*\bsrc="([^"]*)"[^>]*>.*?'
        r'<span\s+class="video-title">(.*?)</span>.*?'
        r'</a>\s*</div>\s*</li>',
        re.S | re.I
    )
    # 备用：宽松匹配
    RE_LIST_LOOSE = re.compile(
        r'<li\s+id="video-(\d+)">.*?'
        r'href="[^"]*vod/play/id/\1/sid/(\d+)/nid/(\d+)\.html"[^>]*'
        r'\s+title="([^"]*)"[^>]*>.*?'
        r'<img[^>]*\bsrc="([^"]*)"',
        re.S | re.I
    )
    RE_IMG_SRC = re.compile(r'<img[^>]*\bsrc="([^"]*)"', re.S | re.I)
    RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
    RE_ALT_ATTR = re.compile(r'alt="([^"]*)"', re.I)
    RE_VIDEO_DETAILS = re.compile(r'<div\s+class="video-details">(.*?)</div>', re.S | re.I)
    RE_REM_TAG = re.compile(r'<[^>]+>')

    # 分页：<ul class="pagination ..."> 中提取最大页码
    RE_PAGINATION = re.compile(r'<ul\s+class="pagination[^"]*"[^>]*>(.*?)</ul>', re.S | re.I)
    RE_PAGE_NUM = re.compile(r'/vod/type/id/\d+/page/(\d+)\.html', re.I)

    # 播放页标题：<h2>标题</h2>（在 #video 区域内）
    RE_PLAY_TITLE = re.compile(r'<div\s+id="video"[^>]*>\s*<h2>(.*?)</h2>', re.S | re.I)
    # 播放页封面：video-thumb 中的 img src
    RE_PLAY_POSTER = re.compile(
        r'<div\s+class="video-thumb">\s*<img[^>]*\bsrc="([^"]*)"',
        re.S | re.I
    )
    # og 标签
    RE_OG_IMAGE = re.compile(r'<meta[^>]*og:image[^>]*content="([^"]+)"', re.I)
    RE_OG_TITLE = re.compile(r'<meta[^>]*og:title[^>]*content="([^"]+)"', re.I)

    # 播放器数据：player_data = {...}
    RE_PLAYER_DATA = re.compile(r'player_data\s*=\s*(\{)', re.S)
    RE_PLAYER_AAAA = re.compile(r'player_aaaa\s*=\s*(\{)', re.S)

    # 媒体直链
    RE_MEDIA_M3U8 = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.I)
    RE_MEDIA_MP4 = re.compile(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', re.I)

    # AES
    RE_AES_KEY = re.compile(r'key\s*[:=]\s*["\']([A-Za-z0-9]{16})["\']')

    def __init__(self):
        pass

    def getName(self):
        return "MTYX影视"

    def init(self, extend=""):
        pass

    # ════════════ 请求 ════════════

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + self.PREFIX + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _play_header(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + self.PREFIX + "/",
            "Origin": self.HOST,
        }

    def _fetch_html(self, url):
        try:
            rsp = self.fetch(url, headers=self._headers(), timeout=10)
            try:
                ct = rsp.headers.get('Content-Type', '').lower()
                if 'charset' not in ct:
                    rsp.encoding = 'utf-8'
            except Exception:
                pass
            return rsp.text
        except Exception as e:
            _log("请求失败(" + url + "): " + str(e))
            return ""

    # ════════════ 首页 ════════════

    def homeContent(self, filter):
        result = {}
        classes = [{'type_name': n, 'type_id': self.CATE[n]} for n in self.CATE]
        result['class'] = classes
        if filter:
            result['filters'] = {cid: [] for cid in self.CATE.values()}
        return result

    def homeVideoContent(self):
        result = {'list': []}
        try:
            html = self._fetch_html(self.HOST + self.PREFIX + "/")
            if not html:
                return result
            videos = self._parse_list_html(html)
            _log("首页解析到 " + str(len(videos)) + " 条")
            result = {'list': videos[:30]}
        except Exception as e:
            _log("首页异常: " + str(e))
        return result

    # ════════════ 分类列表 ════════════

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        result = {'list': [], 'page': page, 'pagecount': 1, 'limit': 30, 'total': 0}

        if page <= 1:
            url = self.BASE + "/type/id/{0}.html".format(tid)
        else:
            url = self.BASE + "/type/id/{0}/page/{1}.html".format(tid, page)

        _log("分类URL: " + url)
        html = self._fetch_html(url)
        if not html or len(html) < 500:
            _log("分类页HTML为空或过短")
            return result

        videos = self._parse_list_html(html)
        _log("分类 " + str(tid) + " 第 " + str(page) + " 页解析到 " + str(len(videos)) + " 条")
        result['list'] = videos

        pagecount = self._parse_pagecount(html)
        result['pagecount'] = pagecount if pagecount else 9999
        result['total'] = 999999
        return result

    # ════════════ 详情 ════════════

    def detailContent(self, array):
        try:
            return self._detail_inner(array)
        except Exception as e:
            _log("详情异常: " + str(e))
            vod_id = str(array[0]) if array else ""
            return {
                'list': [{
                    "vod_id": vod_id, "vod_name": "解析异常", "vod_pic": "",
                    "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "",
                    "vod_actor": "", "vod_director": "", "vod_content": str(e)[:200],
                    "vod_play_from": "默认线路",
                    "vod_play_url": "播放$" + vod_id + "___1___1"
                }]
            }

    def _detail_inner(self, array):
        vod_id = str(array[0])
        # 详情页不存在(error)，直接请求播放页
        url = self.BASE + "/play/id/{0}/sid/1/nid/1.html".format(vod_id)
        html = self._fetch_html(url)
        if not html or len(html) < 200:
            raise Exception("播放页获取失败")

        # 标题
        title = self._m(self.RE_PLAY_TITLE, html)
        if not title:
            title = self._m(self.RE_OG_TITLE, html)
        title = self.RE_REM_TAG.sub('', title).strip() if title else "未知"

        # 封面图
        pic = self._m(self.RE_PLAY_POSTER, html)
        if not pic:
            pic = self._m(self.RE_OG_IMAGE, html)
        pic = self._fix_url(pic)

        vod = {
            "vod_id": vod_id, "vod_name": title, "vod_pic": pic,
            "type_name": "", "vod_year": "", "vod_area": "",
            "vod_remarks": "", "vod_actor": "", "vod_director": "",
            "vod_content": "",
        }

        # 该站点无播放列表，单集单视频
        play_from = "默认线路"
        play_url = "播放$" + vod_id + "___1___1"

        vod["vod_play_from"] = play_from
        vod["vod_play_url"] = play_url
        _log("详情完成: " + title)
        return {'list': [vod]}

    # ════════════ 搜索 ════════════

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        result = {'list': []}
        try:
            encoded_key = quote(key)
            if page <= 1:
                url = self.BASE + "/search.html?wd={0}".format(encoded_key)
            else:
                url = self.BASE + "/search/page/{0}/wd/{1}.html".format(page, encoded_key)

            _log("搜索URL: " + url)
            html = self._fetch_html(url)
            if not html or len(html) < 500:
                return result
            videos = self._parse_list_html(html)
            _log('搜索 "' + key + '" 第 ' + str(page) + ' 页解析到 ' + str(len(videos)) + ' 条')
            result = {'list': videos}
        except Exception as e:
            _log("搜索异常: " + str(e))
        return result

    # ════════════ 播放解析 ════════════

    def playerContent(self, flag, id, vipFlags):
        parts = id.split("___")
        if len(parts) < 3:
            return {"parse": 0, "url": id, "header": ""}

        vod_id, sid, nid = parts[0], parts[1], parts[2]
        play_url = self.BASE + "/play/id/{0}/sid/{1}/nid/{2}.html".format(vod_id, sid, nid)

        try:
            _log("播放URL: " + play_url)
            html = self._fetch_html(play_url)
            if not html:
                return {"parse": 1, "url": play_url, "header": ""}

            # 解析 player_data / player_aaaa JSON
            player_json = self._extract_player_data(html)
            if player_json:
                real_url = player_json.get('url', '')
                if real_url:
                    encrypt = player_json.get('encrypt', 0)
                    if encrypt == 1:
                        real_url = unquote(real_url)
                    elif encrypt == 2 and _HAS_CRYPTO:
                        real_url = self._aes_decrypt(real_url, html)
                    elif encrypt == 2 and not _HAS_CRYPTO:
                        try:
                            real_url = unquote(real_url)
                        except Exception:
                            pass

                    _log("播放器解析成功, encrypt=" + str(encrypt) + ", url=" + real_url[:80])
                    return {
                        "parse": 0, "playUrl": "", "url": real_url,
                        "header": json.dumps(self._play_header())
                    }

            # 直接搜索媒体直链
            media_url = self._extract_media_url(html)
            if media_url:
                _log("媒体直链: " + media_url[:80])
                return {
                    "parse": 0, "url": media_url,
                    "header": json.dumps(self._play_header())
                }

            _log("未找到播放链接，fallback到网页解析")
        except Exception as e:
            _log("播放异常: " + str(e))

        return {"parse": 1, "url": play_url, "header": ""}

    # ════════════ 辅助：列表解析 ════════════

    def _parse_list_html(self, html):
        """
        解析列表页 HTML（首页 + 分类页 + 搜索页通用）。
        qyu5_pc 模板结构：
        <li id="video-XXX"><div class="video">
          <a href="...vod/play/id/XXX/sid/1/nid/1.html" title="标题" class="thumbnail">
            <div class="video-thumb"><img src="..." alt="..."></div>
            <span class="video-rating">9.0%</span>
            <span class="video-title">标题</span>
            <div class="video-details"><span>日期</span><span>次数</span></div>
          </a>
        </div></li>
        """
        videos = []
        seen = set()

        # 策略1：完整匹配
        for m in self.RE_LIST_ITEM.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            sid = m.group(2)
            nid = m.group(3)
            name = m.group(4).strip()
            img = m.group(5).strip()
            # video-title span 内容（可能含 HTML）
            vtitle = self.RE_REM_TAG.sub('', m.group(6)).strip()

            # 标题优先用 title 属性
            if not name:
                name = vtitle

            pic = self._fix_url(img)

            # 提取备注（日期 + 播放次数）
            remarks = ""
            details_m = self.RE_VIDEO_DETAILS.search(m.group(0))
            if details_m:
                details = self.RE_REM_TAG.sub(' ', details_m.group(1)).strip()
                details = re.sub(r'\s+', ' ', details)
                if details:
                    remarks = details[:50]

            if not name:
                continue
            seen.add(vid)
            videos.append({
                "vod_id": str(vid), "vod_name": name,
                "vod_pic": pic, "vod_remarks": remarks
            })

        # 策略2：宽松匹配
        if not videos:
            _log("策略1未匹配，尝试宽松匹配")
            for m in self.RE_LIST_LOOSE.finditer(html):
                vid = m.group(1)
                if vid in seen:
                    continue
                sid = m.group(2)
                nid = m.group(3)
                name = m.group(4).strip()
                img = m.group(5).strip()

                if not name:
                    continue
                pic = self._fix_url(img)

                # 尝试从后续 HTML 提取 video-details
                rest = html[m.end():m.end() + 500]
                remarks = ""
                details_m = self.RE_VIDEO_DETAILS.search(rest)
                if details_m:
                    details = self.RE_REM_TAG.sub(' ', details_m.group(1)).strip()
                    details = re.sub(r'\s+', ' ', details)
                    if details:
                        remarks = details[:50]

                seen.add(vid)
                videos.append({
                    "vod_id": str(vid), "vod_name": name,
                    "vod_pic": pic, "vod_remarks": remarks
                })

        if not videos:
            _log("列表解析: 所有策略均未匹配到视频")
        return videos

    # ════════════ 辅助：分页 ════════════

    def _parse_pagecount(self, html):
        m = self.RE_PAGINATION.search(html)
        if m:
            pag_html = m.group(1)
            nums = self.RE_PAGE_NUM.findall(pag_html)
            if nums:
                try:
                    return max(int(n) for n in nums if n.isdigit())
                except Exception:
                    pass
        nums = self.RE_PAGE_NUM.findall(html)
        if nums:
            try:
                return max(int(n) for n in nums if n.isdigit())
            except Exception:
                pass
        return 0

    # ════════════ 辅助：播放器 JSON 提取 ════════════

    def _extract_player_data(self, html):
        """提取 player_data / player_aaaa JSON 对象（平衡括号匹配）"""
        for pattern in (self.RE_PLAYER_DATA, self.RE_PLAYER_AAAA):
            m = pattern.search(html)
            if m:
                start = m.end() - 1
                obj = self._extract_json(html, start)
                if obj:
                    _log("Player JSON keys: " + str(list(obj.keys())))
                    return obj

        for name in ('player_data', 'player_aaaa', 'player_config', 'MacPlayer'):
            pat = re.compile(name + r'\s*=\s*(\{[^}]+\})', re.S)
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
        return {}

    def _extract_json(self, text, start):
        """从 start 位置（花括号）开始提取平衡的 JSON 对象"""
        if start >= len(text) or text[start] != '{':
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        return None
        return None

    def _extract_media_url(self, html):
        m = self.RE_MEDIA_M3U8.search(html)
        if not m:
            m = self.RE_MEDIA_MP4.search(html)
        return m.group(1) if m else ""

    def _aes_decrypt(self, encrypted, html):
        try:
            key_match = self.RE_AES_KEY.search(html)
            key = key_match.group(1) if key_match else "28fd7d0f7dac4156"
            cipher = AES.new(key.encode(), AES.MODE_ECB)
            decrypted = cipher.decrypt(base64.b64decode(encrypted))
            pad = decrypted[-1]
            return decrypted[:-pad].decode('utf-8', errors='ignore')
        except Exception:
            return encrypted

    # ════════════ 通用 ════════════

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.HOST + url
        return url

    def _m(self, regex, text):
        m = regex.search(text)
        return m.group(1) if m else ""

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

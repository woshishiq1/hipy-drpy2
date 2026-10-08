# -*- coding: utf-8 -*-
# 高清福利社 TVBox 爬虫 v3
# 站点: https://hdhi151.life
# MacCMS v10 模板站 - 特殊列表结构
# 列表项: <ul><a title="标题" href="/play/id/xxx"><li class="image"><img img="封面"></li><li class="title">标题</li></a></ul>
# 封面使用自定义 img 属性懒加载
#
# v3 修复内容:
#   1. playerContent header 字段从 json.dumps(string) 改为 dict (符合 TVBox/FongMi API 规范)
#   2. contentType 字段改名为 format, 值改为 application/x-mpegURL
#   3. isVideoFormat 增加 url 参数, 正确判断视频格式
#   4. 新增 manualVideoCheck 方法
#   5. _parse_player 修复回退逻辑, 增加 HTML 实体解码和 encrypt 字段处理
#   6. detailContent 增加 encrypt 解密支持

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
import urllib.parse


class Spider(Spider):
    # 类属性: TVBox 不调用 __init__, 所有常量必须定义在类级别
    siteUrl = "https://hdhi151.life"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://hdhi151.life/"
    }

    def getName(self):
        return "高清福利社"

    def init(self, extend=""):
        self.extend = extend

    def isVideoFormat(self, url):
        """判断URL是否为可直接播放的视频格式"""
        if not url:
            return False
        url_lower = str(url).lower()
        video_exts = ['.m3u8', '.mp4', '.flv', '.mkv', '.avi', '.webm', '.ts', '.mov']
        for ext in video_exts:
            if ext in url_lower:
                return True
        return False

    def manualVideoCheck(self):
        """不需要手动 WebView 拦截检查"""
        return False

    def _text(self, rsp):
        """安全获取响应文本, 兼容 TVBox 非标准 Response / bytes / str"""
        try:
            return rsp.text
        except Exception:
            pass
        try:
            data = rsp.content
            if isinstance(data, bytes):
                return data.decode('utf-8', errors='ignore')
            return str(data)
        except Exception:
            pass
        if isinstance(rsp, bytes):
            return rsp.decode('utf-8', errors='ignore')
        return str(rsp)

    def _fetch(self, url):
        """发起GET请求并返回文本"""
        try:
            rsp = self.fetch(url, headers=self.header, timeout=15, verify=False)
            return self._text(rsp)
        except:
            return ""

    def _parse_list(self, html):
        """解析列表页HTML - 特殊结构<ul><a>...</a></ul>"""
        videos = []
        pattern = re.compile(
            r'<a\s+title="([^"]*)"\s+href="/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html">'
            r'.*?<li\s+class="image">'
            r'.*?<img\s+[^>]*img="([^"]*)"'
            r'.*?<li\s+class="title">([^<]*)</li>',
            re.DOTALL
        )
        items = pattern.findall(html)
        seen = set()
        for title, vid, sid, nid, pic, title2 in items:
            if vid in seen:
                continue
            seen.add(vid)
            # 过滤广告图(slabcde.icu), 只保留真实封面
            if 'slabcde.icu' in pic:
                pic = ''
            videos.append({
                "vod_id": vid,
                "vod_name": title or title2,
                "vod_pic": pic,
                "vod_remarks": ''
            })
        return videos

    def _decode_url(self, url, encrypt):
        """根据 encrypt 类型解密 URL
        encrypt=0: 明文, 不需处理
        encrypt=1: URL编码(unescape)
        encrypt=2: base64解码后再URL编码(unescape)
        """
        if not url:
            return ''
        if encrypt == 1:
            try:
                return urllib.parse.unquote(url)
            except:
                return url
        elif encrypt == 2:
            try:
                import base64
                decoded = base64.b64decode(url).decode('utf-8', errors='ignore')
                return urllib.parse.unquote(decoded)
            except:
                return url
        return url

    def _parse_player(self, html):
        """从播放页HTML提取 player_aaaa 中的播放地址
        支持 encrypt 字段: 0=明文, 1=URL编码, 2=base64+URL编码
        """
        match = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;?</script>', html, re.DOTALL)
        if not match:
            # 备选: 宽松匹配, 不要求 </script>
            match = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.DOTALL)
        if not match:
            return {}

        raw = match.group(1)

        # 尝试直接解析
        try:
            return json.loads(raw)
        except:
            pass

        # 清理 HTML 实体后重试
        try:
            cleaned = raw.replace('&quot;', '"').replace('&#34;', '"')
            cleaned = cleaned.replace('&#39;', "'").replace('&amp;', '&')
            return json.loads(cleaned)
        except:
            pass

        # 尝试将单引号替换为双引号后重试
        try:
            cleaned = raw.replace("'", '"')
            return json.loads(cleaned)
        except:
            pass

        # 提取关键字段的手动解析兜底
        result = {}
        try:
            url_m = re.search(r'"url"\s*:\s*"([^"]*)"', raw)
            if url_m:
                result['url'] = url_m.group(1).replace('\\/', '/')
            from_m = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
            if from_m:
                result['from'] = from_m.group(1)
            enc_m = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
            if enc_m:
                result['encrypt'] = int(enc_m.group(1))
            if result.get('url'):
                return result
        except:
            pass

        return {}

    def _get_pagecount(self, html):
        """从分页HTML提取总页数"""
        m = re.search(r'data-total="(\d+)"', html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'href="[^"]*/page/(\d+)\.html"', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _get_nav_types(self, html):
        """从首页HTML提取分类导航"""
        classes = []
        navs = re.findall(r'href="/index\.php/vod/type/id/(\d+)\.html"[^>]*>([^<]+)', html)
        seen = set()
        for tid, name in navs:
            if tid in seen:
                continue
            seen.add(tid)
            classes.append({"type_id": tid, "type_name": name.strip()})
        return classes

    # ==================== TVBox 接口 ====================

    def homeContent(self, filter):
        """首页 - 分类 + 最新内容"""
        result = {}
        html = self._fetch(self.siteUrl + "/")
        classes = self._get_nav_types(html)
        result["class"] = classes
        result["filters"] = {}
        result["list"] = self._parse_list(html)
        return result

    def homeVideoContent(self):
        """首页视频(备用)"""
        html = self._fetch(self.siteUrl + "/")
        return self._parse_list(html)

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{pg}.html"

        html = self._fetch(url)
        videos = self._parse_list(html)
        pagecount = self._get_pagecount(html)

        return {
            "list": videos,
            "page": str(pg),
            "pagecount": pagecount,
            "limit": 18,
            "total": pagecount * 18
        }

    def detailContent(self, ids):
        """详情页 - 直接走播放页提取信息"""
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        if not vid:
            return {"list": []}

        # 详情页返回 JS 重定向到播放页, 直接访问播放页
        play_url_path = f"/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        play_url = self.siteUrl + play_url_path
        html = self._fetch(play_url)

        if not html or len(html) < 200:
            return {"list": []}

        # 提取标题
        title = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 提取封面 - 优先 tukaka.space 的真实封面
        pic = ""
        all_imgs = re.findall(r'<img[^>]*\bimg="([^"]*)"[^>]*>', html)
        for p in all_imgs:
            if 'tukaka.space' in p:
                pic = p
                break
        # 备选: 从 src 提取 tukaka 封面
        if not pic:
            all_srcs = re.findall(r'<img[^>]*src="(https?://[^"]*tukaka[^"]*)"', html)
            if all_srcs:
                pic = all_srcs[0]

        # 提取简介
        desc = ""
        m_desc = re.search(r'<div[^>]*class="[^"]*text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if m_desc:
            desc = re.sub(r'<[^>]+>', '', m_desc.group(1)).strip()
        if not desc:
            desc = title

        # 从播放页提取 player_aaaa
        player_data = self._parse_player(html)
        play_url_str = ""
        play_from = ""

        if player_data:
            m3u8_url = player_data.get('url', '')
            from_src = player_data.get('from', '')
            encrypt = player_data.get('encrypt', 0)

            # 处理加密URL
            if m3u8_url and encrypt:
                m3u8_url = self._decode_url(m3u8_url, encrypt)

            # 清理转义字符
            if m3u8_url:
                m3u8_url = m3u8_url.replace('\\/', '/').replace('\\u0026', '&')

            if m3u8_url:
                play_url_str = f"第1集${m3u8_url}"
                play_from = from_src or "m3u8"

        # 如果播放页没提取到, 尝试从页面其他位置找 m3u8
        if not play_url_str:
            m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m3u8_match:
                play_url_str = f"第1集${m3u8_match.group(1)}"
                play_from = "m3u8"

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": play_from,
            "vod_play_url": play_url_str
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg='1'):
        """搜索"""
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page == 1:
            url = f"{self.siteUrl}/index.php/vod/search.html?wd={kw}"
        else:
            url = f"{self.siteUrl}/index.php/vod/search/page/{page}.html?wd={kw}"

        html = self._fetch(url)
        videos = self._parse_list(html)
        pagecount = self._get_pagecount(html)

        return {
            "list": videos,
            "page": str(page),
            "pagecount": pagecount,
            "limit": 18,
            "total": pagecount * 18
        }

    def playerContent(self, flag, id, vipFlags=None):
        """播放解析
        关键修复: header 字段必须返回 dict 对象(不是 json.dumps 字符串)
                  contentType 字段改名为 format, 值为 application/x-mpegURL
        """
        raw = str(id or '').strip()
        if '$' in raw:
            raw = raw.split('$', 1)[-1].strip()

        # 清理可能的转义字符
        raw = raw.replace('\\/', '/').replace('\\u0026', '&').strip()

        headers = {
            'User-Agent': self.header['User-Agent'],
            'Referer': self.header['Referer']
        }

        if '.m3u8' in raw:
            return {
                'parse': 0,
                'playUrl': '',
                'url': raw,
                'header': headers,
                'jx': 0,
                'format': 'application/x-mpegURL'
            }

        if raw.endswith(('.mp4', '.flv', '.mkv', '.avi', '.webm', '.mov')):
            return {
                'parse': 0,
                'playUrl': '',
                'url': raw,
                'header': headers,
                'jx': 0
            }

        return {
            'parse': 1,
            'playUrl': '',
            'url': raw,
            'header': headers,
            'jx': 0
        }

    def localProxy(self, param):
        return [404, "text/plain", ""]

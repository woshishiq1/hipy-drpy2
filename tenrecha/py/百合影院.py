import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from base.spider import Spider  # 导入基础爬虫类
import sys
sys.path.append('..')  # 将上级目录添加到系统路径，以便导入base.spider

# 目标网站首页地址
xurl = "https://www.baihetv.com/"
# 请求头，模拟浏览器访问
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2102J2SC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.31 Mobile Safari/537.36',
    'Referer': xurl,
}

class Spider(Spider):
    """百合影院爬虫类，继承自基础Spider类"""

    def getName(self):
        """返回爬虫名称"""
        return "百合影院"

    def init(self, extend):
        """初始化方法，可扩展"""
        pass

    def isVideoFormat(self, url):
        """判断是否为视频格式，未实现"""
        pass

    def manualVideoCheck(self):
        """手动视频检查，未实现"""
        pass

    def homeContent(self, filter):
        """获取首页分类信息"""
        resp = requests.get(xurl, headers=headers, timeout=10)  # 请求首页
        html = resp.text
        soup = BeautifulSoup(html, 'lxml')  # 解析HTML
        class_items = []
        # 选择导航栏中的菜单项
        nav_items = soup.select('.stui-header__menu li')
        for item in nav_items[:7]:  # 只取前7个分类
            a = item.select_one('a')
            if not a:
                continue
            href = a.get('href')
            name = a.get_text(strip=True)
            # 从链接中提取分类ID，如 /list/1.html 提取出 1
            match = re.search(r'/list/([^/.]+)\.html', href)
            if match:
                class_items.append({
                    "type_id": match.group(1),
                    "type_name": name
                })
        return {
            "class": class_items,
            "filters": {}  # 暂无筛选条件
        }

    def _parse_video_items(self, soup):
        """解析视频列表项，提取视频ID、名称、图片、备注等"""
        videos = []
        items = soup.select('li')  # 选择所有li标签
        for li in items:
            a = li.select_one('.lazyload')  # 图片懒加载标签
            if not a:
                continue
            href = a.get('href')  # 视频详情页链接
            name = a.get('title', '').strip()  # 视频名称
            pic = a.get('data-original', '')  # 图片地址
            if pic and not pic.startswith('http'):
                pic = urljoin(xurl, pic)  # 补全图片URL
            remark_tag = li.select_one('.text-right')  # 备注（如更新至第几集）
            remark = remark_tag.get_text(strip=True) if remark_tag else ''
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def homeVideoContent(self):
        """获取首页视频内容列表"""
        resp = requests.get(xurl, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {'list': self._parse_video_items(soup)}

    def categoryContent(self, cid, pg, filter, ext):
        """获取分类页面内容，支持筛选和分页"""
        page = int(pg) if pg else 1
        cateId = ext.get('cateId', cid) if ext else cid
        class_ = ext.get('class', '') if ext else ''
        area = ext.get('area', '') if ext else ''
        lang = ext.get('lang', '') if ext else ''
        letter = ext.get('letter', '') if ext else ''
        year = ext.get('year', '') if ext else ''
        by = ext.get('by', '') if ext else ''
        # 构造分类URL，格式示例：/tags/1--国语---1---2024.html
        url = f"{xurl}/tags/{cateId}-{area}-{by}-{class_}-{lang}-{letter}---{page}---{year}.html"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {
            'list': self._parse_video_items(soup),
            'page': page,
            'pagecount': page + 1,  # 简单处理，实际应解析总页数
            'limit': 90,
            'total': 9999
        }

    def detailContent(self, ids):
        """获取视频详情页内容，包括基本信息、演员、导演、简介、播放列表等"""
        did = ids[0]
        if not did.startswith('http'):
            did = urljoin(xurl, did)  # 补全链接
        resp = requests.get(did, headers=headers, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, 'lxml')
        vod = {}

        vod["vod_id"] = did

        # 标题
        title_tag = soup.select_one('h1')
        vod["vod_name"] = title_tag.get_text(strip=True) if title_tag else ''

        # 封面图
        img_tag = soup.select_one('.stui-content__thumb img')
        if img_tag:
            pic = img_tag.get('data-original') or img_tag.get('src') or ''
            if pic and not pic.startswith('http'):
                pic = urljoin(xurl, pic)
            vod["vod_pic"] = pic
        else:
            vod["vod_pic"] = ''

        # 年份
        year_tag = soup.select_one('p:contains("年份")')
        if year_tag:
            year_text = year_tag.get_text(strip=True)
            year_match = re.search(r'(\d{4})', year_text)
            vod["vod_year"] = year_match.group(1) if year_match else ''
        else:
            vod["vod_year"] = ''

        # 地区
        area_tag = soup.select_one('p:contains("地区")')
        if area_tag:
            area_text = area_tag.get_text(strip=True).replace('地区：', '')
            vod["vod_area"] = area_text.strip()
        else:
            vod["vod_area"] = ''

        # 状态（如更新至XX集/已完结）
        status_tag = soup.select_one('p:contains("状态")')
        if status_tag:
            status_text = status_tag.get_text(strip=True).replace('状态：', '')
            vod["vod_remarks"] = status_text.strip()
        else:
            vod["vod_remarks"] = ''

        # 类型
        type_tags = soup.select('p:contains("类型") a')
        if type_tags:
            vod["type_name"] = '/'.join([a.get_text(strip=True) for a in type_tags])
        else:
            vod["type_name"] = ''

        # 演员
        actor_tags = soup.select('p:contains("演员") a')
        vod["vod_actor"] = '/'.join(filter(None, [a.get_text(strip=True) for a in actor_tags]))

        # 导演
        director_tags = soup.select('p:contains("导演") a')
        vod["vod_director"] = '/'.join(filter(None, [a.get_text(strip=True) for a in director_tags]))

        # 简介
        intro_tag = soup.select_one('span.detail-content')
        if intro_tag:
            intro_text = intro_tag.get_text(strip=True)
            intro_text = re.sub(r'^剧情[：:]\s*', '', intro_text)  # 去除“剧情：”前缀
            vod["vod_content"] = intro_text
        else:
            vod["vod_content"] = ''

        # 播放列表解析（多线路）
        tabs = soup.select('.stui-vodlist__head h4')  # 线路名称（如“播放源1”）
        playlists = soup.select('.stui-content__playlist')  # 对应线路的剧集列表
        play_from = []  # 线路名称列表
        play_url = []   # 对应线路的剧集URL拼接字符串
        seen = set()
        for i, tab in enumerate(tabs):
            if i >= len(playlists):
                break
            name = tab.get_text(strip=True)
            name = re.sub(r'\s*\d+$', '', name).strip()  # 去除末尾数字，如“播放源1” -> “播放源”
            if name in ['猜您喜欢', '同类型', '同主演', '同'] or name in seen:
                continue  # 过滤无效或重复线路
            seen.add(name)
            eps = []
            for a in playlists[i].select('li a'):
                href = a.get('href')
                title = a.get_text(strip=True)
                if href and '1080P' not in title:  # 过滤标题含1080P的条目（可能为广告）
                    if not href.startswith('http'):
                        href = urljoin(xurl, href)
                    eps.append(f"{title}${href}")  # 格式：剧集名称$播放链接
            if eps:
                play_from.append(name)
                play_url.append('#'.join(eps))  # 多个剧集用#分隔

        vod["vod_play_from"] = '$$$'.join(play_from)  # 多个线路用$$$分隔
        vod["vod_play_url"] = '$$$'.join(play_url)

        return {'list': [vod]}

    def searchContent(self, key, quick, page='1'):
        """搜索视频内容，支持分页"""
        page = int(page) if page else 1
        url = f"{xurl}/search/{key}----------{page}---.html"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {
            'list': self._parse_video_items(soup),
            'page': page,
            'pagecount': page + 1,
            'limit': 90,
            'total': 9999
        }

    def playerContent(self, flag, id, vipFlags):
        """获取视频播放地址，支持解析加密播放器配置"""
        try:
            play_url = id if id.startswith('http') else xurl + id
            resp = requests.get(play_url, headers=headers, timeout=10)
            html = resp.text

            # 匹配播放器配置对象，如 var player_xxx = {...};
            pattern = r'var\s+player_\w+\s*=\s*(\{[\s\S]+?\});'
            match = re.search(pattern, html)
            video_url = ''

            if match:
                obj_str = match.group(1)
                obj_str = re.sub(r'(\w+):', r'"\1":', obj_str)  # 将key加上引号以符合JSON格式
                try:
                    config = json.loads(obj_str)
                    video_url = config.get('url') or ''
                except json.JSONDecodeError:
                    pass

            # 如果没找到，再尝试正则匹配"url":"..."
            if not video_url:
                url_match = re.search(r'"url":"([^"]+)"', html)
                if url_match:
                    video_url = url_match.group(1)

            # 判断是否为有效视频格式
            if video_url and re.search(r'm3u8|mp4|mkv', video_url, re.I):
                parse = 0  # 不需要二次解析
                if not video_url.startswith('http'):
                    video_url = urljoin(xurl, video_url)
            else:
                parse = 1  # 需要解析（如跳转其他解析接口）
                video_url = play_url

            return {"parse": parse, "playUrl": "", "url": video_url, "header": headers}
        except Exception as e:
            print(f"playerContent error: {e}")
            return {"parse": 1, "playUrl": "", "url": xurl + id, "header": headers}

    def localProxy(self, params):
        """本地代理，支持m3u8、媒体、ts片段等资源请求"""
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        if params['type'] == "media":
            return self.proxyMedia(params)
        if params['type'] == "ts":
            return self.proxyTs(params)
        return None
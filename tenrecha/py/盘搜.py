import sys
import json
import requests
import random
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.append('..')
from base.spider import Spider


class CloudSearchSpider(Spider):
    """网盘资源搜索爬虫"""

    DEFAULT_BASE_URL = "http://hao.tgsou.xyz"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/138.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }

    # 每页数量，300 对电视端略大，建议 50-100
    SEARCH_PAGE_SIZE = 100

    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    PAN_CONFIG = {
     'baidu': {
            'api_type': 'baidu',
            'name': '百度',
            'keywords': ['baidu'],
            'icon': 'baidu.png'
        },
          'quark': {
            'api_type': 'quark',
            'name': '夸克',
            'keywords': ['pan.quark.cn'],
            'icon': 'quark.png'
        },
        'uc': {
            'api_type': 'uc',
            'name': 'UC',
            'keywords': ['drive.uc.cn'],
            'icon': 'uc.png'
        },
        'ali': {
            'api_type': 'aliyun',
            'name': '阿里',
            'keywords': ['alipan.com', 'aliyundrive.com'],
            'icon': 'ali.png'
        },
        'a123': {
            'api_type': '123',
            'name': '123',
            'keywords': [
                '123684.com',
                '123685.com',
                '123912.com',
                '123pan.com',
                '123pan.cn',
                '123592.com'
            ],
            'icon': '123.png'
        },
        'a189': {
            'api_type': 'tianyi',
            'name': '天翼',
            'keywords': ['cloud.189.cn'],
            'icon': '189.png'
        }
    }

    # 接口类型转内部类型
    REVERSE_PAN_MAP = {v['api_type']: k for k, v in PAN_CONFIG.items()}

    # 网盘简称
    PAN_SHORT_NAMES = {k: v['name'] for k, v in PAN_CONFIG.items()}

    def __init__(self):
        super().__init__()

        self.base_url = self.DEFAULT_BASE_URL
        self.proxy = ''
        self.pan_priority = ''
        self.pan_order = ''
        self.channels = ''
        self.plugins = ''
        self.cloud_types = ''

        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        retries = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )

        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def init(self, extend):
        try:
            extend_dict = json.loads(extend) if extend else {}

            self.base_url = extend_dict.get(
                'server',
                self.DEFAULT_BASE_URL
            ).rstrip('/')

            self.proxy = extend_dict.get('proxy', '')
            self.pan_priority = extend_dict.get('pan_priority', '')
            self.pan_order = extend_dict.get('pan_order', '')

            # 搜索接口过滤参数
            self.channels = extend_dict.get('channels', '')
            self.plugins = extend_dict.get('plugins', '')
            self.cloud_types = extend_dict.get('cloud_types', '')

        except json.JSONDecodeError:
            self._reset_to_defaults()

        if self.proxy:
            self.session.proxies = {
                "http": self.proxy,
                "https": self.proxy
            }

    def _reset_to_defaults(self):
        self.base_url = self.DEFAULT_BASE_URL
        self.proxy = ''
        self.pan_priority = ''
        self.pan_order = ''
        self.channels = ''
        self.plugins = ''
        self.cloud_types = ''

    def getName(self):
        return "盘搜"

    def homeContent(self, filter):
        return {
            'class': [
                {
                    "type_id": "1",
                    "type_name": "盘搜|仅支持搜索"
                }
            ],
            'list': []
        }

    def homeVideoContent(self):
        return {}

    def categoryContent(self, cid, page, filter, ext):
        return {
            'list': [
                {
                    "vod_id": "1",
                    "vod_name": "无内容，仅支持搜索",
                    "vod_pic": "",
                    "vod_remarks": "盘搜"
                }
            ],
            'page': 1,
            'pagecount': 1,
            'limit': 1,
            'total': 1
        }

    def detailContent(self, did):
        result = {'list': []}

        if not did or not did[0]:
            return result

        resource_url = did[0]

        pan_type = self._extract_pan_type_from_url(resource_url)
        pan_config = self.PAN_CONFIG.get(pan_type, {})
        pan_name = pan_config.get('name', '网盘资源')
        pan_icon = self._get_icon_url(pan_config.get('icon', ''))

        result['list'].append({
            "vod_id": resource_url,
            "vod_name": f"{pan_name}资源",
            "vod_pic": pan_icon,
            "vod_play_from": "盘搜",
            "vod_play_url": f"盘搜${resource_url}",
            "vod_content": f"网盘类型: {pan_name}\n资源链接: {resource_url}"
        })

        return result

    def searchContent(self, key, quick, pg="1"):
        return self._perform_search(key, pg)

    def searchContentPage(self, key, quick, page):
        return self._perform_search(key, page)

    def _perform_search(self, keywords, page_str):
        try:
            page = int(page_str)
        except (ValueError, TypeError):
            page = 1

        result = {
            'list': [],
            'page': page,
            'pagecount': 1,
            'limit': self.SEARCH_PAGE_SIZE,
            'total': 0
        }

        if not keywords:
            return result

        try:
            params = {
                'kw': keywords
            }

            if self.channels:
                params['channels'] = self.channels

            if self.plugins:
                params['plugins'] = self.plugins

            if self.cloud_types:
                params['cloud_types'] = self.cloud_types

            url = f"{self.base_url}/api/search"

            search_response = self.session.get(
                url,
                params=params,
                timeout=self.REQUEST_TIMEOUT
            )

            search_response.raise_for_status()

            search_data = search_response.json()

            if search_data.get('code') != 0:
                return result

            all_results = self._parse_and_sort_results(search_data, keywords)

            total_count = len(all_results)
            start_index = (page - 1) * self.SEARCH_PAGE_SIZE
            end_index = start_index + self.SEARCH_PAGE_SIZE

            paged_results = all_results[start_index:end_index]

            result.update({
                'list': paged_results,
                'total': total_count,
                'pagecount': max(
                    1,
                    (total_count + self.SEARCH_PAGE_SIZE - 1) // self.SEARCH_PAGE_SIZE
                )
            })

        except requests.RequestException as e:
            print(f"盘搜请求失败: {e}")
        except Exception as e:
            print(f"盘搜搜索异常: {e}")

        return result

    def _parse_and_sort_results(self, data, keywords):
        if self.pan_order:
            enabled_pan_types = [
                pan.strip()
                for pan in self.pan_order.split(',')
                if pan.strip()
            ]
            sort_by_pan_order = True

        elif self.pan_priority:
            enabled_pan_types = [
                pan.strip()
                for pan in self.pan_priority.split(',')
                if pan.strip()
            ]
            sort_by_pan_order = True

        else:
            enabled_pan_types = []
            sort_by_pan_order = False

        all_items = []
        all_images = []

        merged_data = data.get('data', {}).get('merged_by_type', {})

        # 收集全部图片，用于兜底封面
        for items in merged_data.values():
            for item in items:
                images = item.get('images')
                if images:
                    all_images.extend(images)

        # 使用稳定随机种子，避免重启后随机图大幅变化
        seed = int(
            hashlib.md5(keywords.encode('utf-8')).hexdigest(),
            16
        )
        rng = random.Random(seed)

        for cloud_type, items in merged_data.items():
            pan_type = self.REVERSE_PAN_MAP.get(cloud_type, cloud_type)

            # 如果配置了网盘过滤，只保留指定网盘
            if enabled_pan_types and pan_type not in enabled_pan_types:
                continue

            for item in items:
                resource_url = item.get('url')

                if not resource_url:
                    continue

                pan_config = self.PAN_CONFIG.get(pan_type, {})
                pan_icon = self._get_icon_url(pan_config.get('icon', ''))
                pan_short = self.PAN_SHORT_NAMES.get(pan_type, '网盘')

                vod_pic = self._get_best_image(
                    item,
                    all_images,
                    pan_icon,
                    rng
                )

                dt_obj = self._to_datetime(item.get('datetime'))
                time_str = dt_obj.strftime("%m-%d") if dt_obj else ""

                source = item.get('source', '盘搜')

                if time_str:
                    remarks = f"{pan_short}:{time_str}|{source}"
                else:
                    remarks = f"{pan_short}|{source}"

                all_items.append({
                    "vod_id": resource_url,
                    "vod_name": item.get('note', ''),
                    "vod_pic": vod_pic,
                    "vod_remarks": remarks,
                    "_timestamp": dt_obj.timestamp() if dt_obj else 0,
                    "_pan_type": pan_type
                })

        # 排序逻辑
        if sort_by_pan_order and enabled_pan_types:
            pan_order_map = {
                pan: idx
                for idx, pan in enumerate(enabled_pan_types)
            }

            all_items.sort(
                key=lambda x: (
                    pan_order_map.get(
                        x['_pan_type'],
                        len(enabled_pan_types)
                    ),
                    -x['_timestamp']
                )
            )

        else:
            all_items.sort(
                key=lambda x: -x['_timestamp']
            )

        # 删除内部临时字段
        for item in all_items:
            item.pop('_timestamp', None)
            item.pop('_pan_type', None)

        return all_items

    def _get_best_image(self, item, all_images, pan_icon, rng):
        images = item.get('images')

        if images:
            return images[0]

        if all_images:
            return rng.choice(all_images)

        return pan_icon

    def playerContent(self, flag, pid, vipFlags):
        result = {
            "parse": 0,
            "header": self.HEADERS,
            "url": ""
        }

        if not pid:
            return result

        url = pid.strip()

        if not url.startswith('push:'):
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'

            result['url'] = f"push:{url}"

        else:
            result['url'] = url

        return result

    def _to_datetime(self, time_str):
        if not time_str:
            return None

        if time_str == "0001-01-01T00:00:00Z":
            return None

        try:
            time_str_clean = time_str.replace('Z', '+00:00')
            return datetime.fromisoformat(time_str_clean)

        except (ValueError, TypeError):
            pass

        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

        except (ValueError, TypeError):
            return None

    def _extract_pan_type_from_url(self, url):
        if not url:
            return "unknown"

        parsed = urlparse(url)
        url_lower = parsed.netloc.lower() or url.lower()

        for pan_type, config in self.PAN_CONFIG.items():
            keywords = config.get('keywords', [])

            if any(keyword in url_lower for keyword in keywords):
                return pan_type

        return "unknown"

    def _get_icon_url(self, icon_name):
        if not icon_name:
            return ""

        return f"http://127.0.0.1:9978/file/Download/lib/icon/{icon_name}"


Spider = CloudSearchSpider
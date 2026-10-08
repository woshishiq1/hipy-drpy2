import json, re, sys, requests, hashlib, base64
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.append('..')
from base.spider import Spider

# 频道配置
CHANNELS = [
    {"type_id": "GUAGUA35", "type_name": "视频精选"},
    # 综合多盘
    {"type_id": "youxigs", "type_name": "综合资源 1"},
    {"type_id": "qixingzhenren", "type_name": "综合资源 2"},
    {"type_id": "ucwpzy", "type_name": "综合资源 3"},
    {"type_id": "vip115hot", "type_name": "综合资源 4"},
    {"type_id": "Netdisk_Movies", "type_name": "综合自愈 5"},
    # 百度网盘
    {"type_id": "douerpan", "type_name": "百度网盘 1"},
    {"type_id": "bdwpzhpd", "type_name": "百度网盘 2"},
    {"type_id": "wydwpzy", "type_name": "百度网盘 3"},
    {"type_id": "Baidu_Netdisk", "type_name": "百度网盘 4"},
    # 阿里云盘
    {"type_id": "aliyunys", "type_name": "阿里云盘 1"},
    {"type_id": "sharealiyun", "type_name": "阿里云盘 2"},
    {"type_id": "Aliyun_4K_Movies", "type_name": "阿里云盘 3"},
    # 夸克网盘
    {"type_id": "sgkwpzy", "type_name": "夸克网盘 1"},
    {"type_id": "qukanmovie", "type_name": "夸克网盘 2"},
    {"type_id": "sharepanfilms", "type_name": "夸克网盘 3"},
    {"type_id": "quark_movies", "type_name": "夸克网盘 4"},
    {"type_id": "panjclub", "type_name": "夸克网盘 5"},
    # UC网盘
    {"type_id": "yunpanuc", "type_name": "UC网盘 1"},
    {"type_id": "ucshare", "type_name": "UC网盘 2"},
    # 天翼云盘
    {"type_id": "zyywpzy", "type_name": "天翼云盘 1"},
    {"type_id": "txtyzy", "type_name": "天翼云盘 2"},
    {"type_id": "tyypzhpd", "type_name": "天翼云盘 3"},
    # 115网盘
    {"type_id": "ysxb48", "type_name": "115网盘 1"},
    {"type_id": "channel_shares_115", "type_name": "115网盘 2"},
    # 其他资源
    {"type_id": "zyfb123", "type_name": "123网盘"},
    {"type_id": "tubeget", "type_name": "磁力链接"},
    {"type_id": "xiangnikanj", "type_name": "短剧专区"}
]

class Spider(Spider):
    def __init__(self):
        self.host = "https://t.me"
        self.cache = {}
        self.channels = CHANNELS
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 15  # Default timeout in seconds
        
        # Pre-compile regex patterns
        self.patterns = {
            '百度网盘': re.compile(r'pan\.baidu\.com', re.I),
            '夸克网盘': re.compile(r'pan\.quark\.cn', re.I),
            '阿里云盘': re.compile(r'www\.aliyundrive\.com|www\.alipan\.com', re.I),
            '移动云盘': re.compile(r'yun\.139\.com|caiyun\.139\.com', re.I),
            '天翼云盘': re.compile(r'cloud\.189\.cn', re.I),
            '115网盘': re.compile(r'www\.115\.com|115cdn\.com', re.I),
            'UC网盘': re.compile(r'pan\.uc\.cn|drive\.uc\.cn', re.I),
            '123网盘': re.compile(r'123pan\.(?:com|cn)|123(?:684|865|912|592)\.com', re.I),
            '磁力': re.compile(r'^magnet:\?xt=urn:btih:', re.I)
        }
        print("[TGCHANNEL] Spider initialized")
        
    def init(self, extend=""):
        pass
    
    
    def getName(self):
        return "TG推送"
    
    def homeContent(self, _):
        class_list = [{
            "type_name": ch.get('type_name', ch.get('name', '')),
            "type_id": ch.get('type_id', ch.get('id', ''))
        } for ch in self.channels if isinstance(ch, dict)]
        return {
            'class': class_list,
            'filters': {}
        }
    
    def _get_link_type(self, url):
        for name, pattern in self.patterns.items():
            if pattern.search(url):
                return name
    
    def _check_links(self, links):
        if not links: return set()
        return set(links)
    
    def _parse_tg_html(self, html):
        vod_list = []
        blocks = html.split('tgme_widget_message_bubble')[1:]
        
        for idx, block in enumerate(blocks):
            vids = re.findall(r'<video[^>]*?src=["\']([^"\']+\.mp4[^"\']*)["\']', block, re.S)
            hrefs = re.findall(r'href=["\']?(https?://[^"\'\s>]+)', block)
            magnets = re.findall(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}', block, re.I)
            
            links = list(set([u for u in hrefs + magnets if self._get_link_type(u)]))
            if not vids and not links:
                continue

            text_match = re.search(r'js-message_?text[^>]*?>(.*?)</div>', block, re.S)
            if text_match:
                text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                title = lines[0] if lines else "TG资源"
            else:
                bolds = re.findall(r'<b[^>]*?>(.*?)</b>', block, re.S)
                title = "".join([re.sub(r'<[^>]+>', '', b).strip() for b in bolds])
                title = title if len(title) >= 2 else "TG资源"

            title = re.sub(r'^(名称：|资源标题：)', '', title)
            title = re.sub(r'(全\s*\d+\s*集|共\s*\d+\s*集|\d+\s*集\s*全|(?:更新至|更新到|更至|更新)\s*(?:第)?\s*\d+\s*(?:集)?|剧情|加更|更新).*$', '', title)
            title = title.strip()
            title = title[:100] + "..." if len(title) > 100 else title
            pic_match = re.search(r'background-image:url\([\'"]?(.*?)[\'"]?\)', block)
            pic = pic_match.group(1) if pic_match else "https://api.xinac.net/icon/?url=https://t.me"
            
            vod_list.append({
                'title': title,
                'pic': pic,
                'vids': vids[:3],
                'links': links
            })
        
        # 批量检查链接有效性
        all_links = [l for v in vod_list for l in v['links']]
        valid_links = self._check_links(all_links)
        
        result = []
        skipped_count = 0
        for idx, vod in enumerate(vod_list):
            play_froms, play_urls = [], []
            
            if vod['vids']:
                play_froms.append("短视频")
                play_urls.append("#".join([f"视频{i+1}${u}" for i, u in enumerate(vod['vids'])]))
            
            active_links = [l for l in vod['links'][:5] if l in valid_links]
            
            for link in active_links:
                if (link_type := self._get_link_type(link)) == '磁力':
                    play_urls.append(link)
                else:
                    play_urls.append(f"一键推送${link}")
                play_froms.append(link_type)
            
            if not play_urls:
                skipped_count += 1
                continue
            
            unique_id = hashlib.md5((vod['title'] + str(vod['vids']) + str(vod['links'])).encode()).hexdigest()
            result.append({
                "vod_name": vod['title'],
                "vod_id": json.dumps({
                    "id": unique_id,
                    "n": vod['title'],
                    "p": vod['pic'],
                    "f": "$$$".join(play_froms),
                    "u": "$$$".join(play_urls)
                }),
                "vod_pic": vod['pic'],
                "vod_remarks": " | ".join(play_froms[:3])
            })
        
        if not result:
            print(f"[TGCHANNEL] WARNING: No valid items to return!")
        return result
    
    def categoryContent(self, tid, pg, _filter, _extend):
        pg = int(pg)
        
        if pg == 1:
            url = f"{self.host}/s/{tid}"
        else:
            cache_key = f"{tid}_{pg}"
            if cache_key not in self.cache:
                return {'list': []}
            url = f"{self.host}/s/{tid}?before={self.cache[cache_key]}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            html = response.text
        except requests.exceptions.Timeout:
            print(f"[TGCHANNEL] ERROR: Request timed out after {self.timeout}s")
            return {'list': [], 'page': pg, 'pagecount': pg}
        except requests.exceptions.ConnectionError as e:
            print(f"[TGCHANNEL] ERROR: Connection error: {e}")
            return {'list': [], 'page': pg, 'pagecount': pg}
        except Exception as e:
            print(f"[TGCHANNEL] ERROR: Unexpected error fetching HTML: {e}")
            import traceback
            traceback.print_exc()
            return {'list': [], 'page': pg, 'pagecount': pg}
        
        if match := re.search(r'before=(\d+)', html):
            self.cache[f"{tid}_{pg+1}"] = match.group(1)
        
        vod_list = self._parse_tg_html(html)[::-1]
        return {'list': vod_list, 'page': pg, 'pagecount': pg + 1}
    
    def detailContent(self, ids):
        data = json.loads(ids[0])
        pic = data['p']
        
        return {'list': [{
            "vod_name": data['n'],
            "vod_pic": pic,
            "vod_play_from": data['f'],
            "vod_play_url": data['u'],
            "vod_content": data['n']
        }]}
    
    def playerContent(self, _flag, id, _vipFlags):
        url = id.strip()
        
        if "$" in url:
            url = url.split("$")[1].strip()
            
        # 如果是短视频(直连)或mp4结尾，不使用push协议
        if _flag == "短视频" or url.lower().endswith(".mp4"):
            pass
        elif not url.startswith("magnet:") and not url.startswith("push://"):
            url = f"push://{url}"
            
        return {
            'parse': 0,
            'playUrl': '',
            'url': url,
            'header': json.dumps({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://t.me/'
            })
        }
    
    def _fetch_search(self, channel, key):
        if chan_id := channel.get('id', channel.get('type_id')):
            try:
                url = f"{self.host}/s/{chan_id}?q={quote(key)}"
                res = self.session.get(url, timeout=10)
                if res.status_code == 200:
                    return self._parse_tg_html(res.text)
            except:
                pass
        return []

    def searchContent(self, key, _quick, _pg="1"):
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_search, channel, key) for channel in self.channels]
            for future in as_completed(futures):
                if res := future.result():
                    results.extend(res)
                    if len(results) > 50: # Limit total results to prevent overload
                         break
        return {'list': results}
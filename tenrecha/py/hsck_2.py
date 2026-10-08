import requests
from bs4 import BeautifulSoup
import json
import csv
import re
import os
from urllib.parse import urljoin, unquote
import base64
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# ================== 配置区 ==================
base_url = "http://6043ck.cc/"
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
]

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# 保存路径（当前目录下创建文件夹）
save_dir = os.path.join(os.getcwd(), "hsck_data")
os.makedirs(save_dir, exist_ok=True)

json_file = os.path.join(save_dir, "hsck_title_attr.json")
csv_file = os.path.join(save_dir, "hsck_title_attr.csv")
m3u_file = os.path.join(save_dir, "hsck_live.m3u")
total_sql_file = os.path.join(save_dir, "mac_vod_manual.sql")  # 完整總表

# 分类列表：total_pages=0 会自动跳过
CATEGORIES = [
    {"pattern": "vodtype/8-{}.html", "total_pages": 107, "type_id": 28, "desc": "无码中文字幕"},
    {"pattern": "vodtype/9-{}.html", "total_pages": 796, "type_id": 29, "desc": "有码中文字幕"},
    {"pattern": "vodtype/10-{}.html", "total_pages": 257, "type_id": 30, "desc": "日本无码"},
    {"pattern": "vodtype/7-{}.html", "total_pages": 587, "type_id": 31, "desc": "日本有码"},
    {"pattern": "vodtype/15-{}.html", "total_pages": 919, "type_id": 32, "desc": "国产视频"},
    {"pattern": "vodtype/21-{}.html", "total_pages": 38, "type_id": 33, "desc": "欧美高清"},
    {"pattern": "vodtype/22-{}.html", "total_pages": 7, "type_id": 34, "desc": "动漫剧情"},
    {"pattern": "vodtype/26-{}.html", "total_pages": 7, "type_id": 35, "desc": "骑兵破解"},
]

max_workers = 50  # 电脑版调高速度

session = requests.Session()
retry = Retry(total=5, backoff_factor=2, status_forcelist=[403, 429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

seen_play_urls = set()

print("开始电脑版多分类**正序**爬取...")

def escape_sql_string(s):
    if s is None or s in ["未找到", "提取失败"]:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "''")
    return s

def crawl_single_page(category, page):
    global seen_play_urls

    url = base_url + category["pattern"].format(page)
    print(f"\n分类: {category['desc']} 第 {page} 页: {url}")
    
    try:
        time.sleep(random.uniform(2, 5))# 电脑延时缩短
        headers["User-Agent"] = random.choice(user_agents)
        response = session.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('a', href=re.compile(r'/vodplay/\d+-\d+-\d+\.html'))
        print(f"本页 {len(items)} 个视频项")

        page_videos = []
        for item in items:
            play_url = urljoin(base_url, item['href'])
            if play_url in seen_play_urls:
                continue
            
            title = item.get('title', '').strip()
            if not title:
                title = item.get_text(strip=True) or "未知标题"
            
            cover_url = "未找到"
            if 'data-original' in item.attrs:
                cover_url = item['data-original']
            if cover_url.startswith('//'):
                cover_url = 'https:' + cover_url
            elif cover_url != "未找到" and not cover_url.startswith('http'):
                cover_url = urljoin(base_url, cover_url)

            video_url = "未找到"
            try:
                time.sleep(random.uniform(0.8, 2))
                play_res = session.get(play_url, headers=headers, timeout=60)
                play_text = play_res.text
                
                m = re.search(r'var\s+player_\w+\s*=\s*(\{.*?\})\s*;?', play_text, re.DOTALL)
                if m:
                    config_str = m.group(1).replace("'", '"')
                    config = json.loads(config_str)
                    url_enc = config.get('url', '')
                    encrypt = int(config.get('encrypt', 0) or 0)
                    if encrypt == 1:
                        video_url = unquote(url_enc)
                    elif encrypt == 2:
                        decoded = base64.b64decode(url_enc + '==').decode('utf-8')
                        video_url = unquote(decoded)
                    else:
                        video_url = url_enc
                
                if not video_url.startswith('http'):
                    direct = re.search(r'(https?://[^\s"\']+\.m3u8)', play_text)
                    if direct:
                        video_url = direct.group(1)
            except:
                video_url = "提取失败"
            
            video_data = {
                "标题": title,
                "封面": cover_url,
                "播放页面": play_url,
                "视频地址": video_url,
                "type_id": category["type_id"],
                "category_desc": category["desc"]
            }
            page_videos.append(video_data)
            seen_play_urls.add(play_url)
            print(f"  {title} -> 封面: {cover_url} -> 视频: {video_url}")
        
        return page_videos
    except Exception as e:
        print(f"第 {page} 页失败: {e}")
        return []

# 多分类爬取 - 正序
all_videos = []
for category in CATEGORIES:
    if category["total_pages"] <= 0:
        print(f"跳过分类: {category['desc']} (total_pages = {category['total_pages']})")
        continue
    
    print(f"\n开始爬取分类: {category['desc']} (type_id: {category['type_id']})，总页数: {category['total_pages']}")
    
    # 改成正序：1 到 total_pages
    # pages = list(range(1, category["total_pages"] + 1))
    # 改成倒序：total_pages 到 1
    pages = list(range(category["total_pages"], 0, -1))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(crawl_single_page, category, page) for page in pages]
        for future in as_completed(futures):
            all_videos.extend(future.result())

# 保存 JSON（完整）
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(all_videos, f, ensure_ascii=False, indent=4)

# 保存 CSV（包含 category_desc）
csv_fieldnames = ["category_desc", "标题", "封面", "播放页面", "视频地址", "type_id"]
with open(csv_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
    writer.writeheader()
    writer.writerows(all_videos)

# 生成 FongMi M3U 直播源（group-title 按分类命名）
print("\n生成 FongMi M3U 直播源...")
m3u_lines = ["#EXTM3U"]

for v in all_videos:
    if v["视频地址"] == "提取失败" or not v["视频地址"].startswith('http'):
        continue
    
    name = v["标题"].replace("#", "").replace("\n", " ").strip()
    logo = v["封面"] if v["封面"] != "未找到" else ""
    group = v["category_desc"]
    
    extinf = f'#EXTINF:-1 tvg-id="" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
    m3u_lines.append(extinf)
    m3u_lines.append(v["视频地址"])

with open(m3u_file, 'w', encoding='utf-8') as f:
    f.write("\n".join(m3u_lines))

# ==================== 蘋果CMS SQL - 總表 + 按分類獨立表 ====================

print("\n生成苹果CMS SQL 文件...")

# 先把有效影片按 type_id 分組
videos_by_type = defaultdict(list)
valid_videos = []

for v in all_videos:
    if v["视频地址"] != "提取失败" and v["视频地址"].startswith('http'):
        valid_videos.append(v)
        videos_by_type[v["type_id"]].append(v)

# 1. 總表（全部）
sql_lines = []
sql_lines.append("-- 苹果CMS v10 手动导入SQL - 全部影片\n")
sql_lines.append("INSERT INTO mac_vod (type_id, vod_name, vod_pic, vod_play_from, vod_play_url, vod_status) VALUES")

for i, v in enumerate(valid_videos):
    name = escape_sql_string(v["标题"])
    pic = escape_sql_string(v["封面"])
    play_from = "ckm3u8"
    play_url = escape_sql_string(f"第01集${v['视频地址']}")
    type_id = v["type_id"]
    
    line = f"({type_id}, '{name}', '{pic}', '{play_from}', '{play_url}', 1)"
    line += "," if i < len(valid_videos) - 1 else ";"
    sql_lines.append(line)

with open(total_sql_file, 'w', encoding='utf-8') as f:
    f.write("\n".join(sql_lines))

print(f"已生成完整總表：{total_sql_file} ({len(valid_videos)} 筆)")

# 2. 按分類獨立檔案
for type_id, videos in videos_by_type.items():
    category_desc = videos[0]["category_desc"] if videos else "未知"
    sql_filename = f"mac_vod_type_{type_id}.sql"
    sql_path = os.path.join(save_dir, sql_filename)
    
    sql_lines = []
    sql_lines.append(f"-- 苹果CMS v10 手动导入SQL - {category_desc} (type_id={type_id})\n")
    sql_lines.append("INSERT INTO mac_vod (type_id, vod_name, vod_pic, vod_play_from, vod_play_url, vod_status) VALUES")
    
    for i, v in enumerate(videos):
        name = escape_sql_string(v["标题"])
        pic = escape_sql_string(v["封面"])
        play_from = "ckm3u8"
        play_url = escape_sql_string(f"第01集${v['视频地址']}")
        
        line = f"({type_id}, '{name}', '{pic}', '{play_from}', '{play_url}', 1)"
        line += "," if i < len(videos) - 1 else ";"
        sql_lines.append(line)
    
    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_lines))
    
    print(f"已生成分類檔案：{sql_filename} ({len(videos)} 筆)")

print(f"\n大功告成！共爬取 {len(all_videos)} 個記錄，有效影片 {len(valid_videos)} 個")
print(f"文件保存到: {save_dir}")
print(f" - {os.path.basename(json_file)}")
print(f" - {os.path.basename(csv_file)}")
print(f" - {os.path.basename(m3u_file)}")
print(f" - {os.path.basename(total_sql_file)} （完整總表）")
print(" - mac_vod_type_xx.sql （各分類獨立表）")
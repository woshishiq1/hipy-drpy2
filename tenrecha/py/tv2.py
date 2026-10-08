#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

class WhosTvToBox:
    """
    功能：从 Whos.tv 抓取视频 M3U8 链接，并生成 TVBox 兼容的 M3U 和 JSON 格式文件。
    """
    def __init__(self, start_url="https://whos.tv/videos", max_list_pages=5, max_workers=5):
        self.start_url = start_url
        self.max_list_pages = max_list_pages
        self.max_workers = max_workers
        self.session = requests.Session()
        # 模拟浏览器请求头，防止被拦截
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://whos.tv/"
        })
        self.lock = Lock()
        
        # --- 路径自动适配逻辑 ---
        # 如果在安卓 (Termux) 运行，使用 /sdcard/；否则使用当前目录下的 output
        if os.path.exists("/sdcard/"):
            self.output_dir = "/sdcard/whos_tv_m3u"
        else:
            self.output_dir = os.path.join(os.getcwd(), "output_tvbox")
            
        os.makedirs(self.output_dir, exist_ok=True)
        self.m3u_file = os.path.join(self.output_dir, "whos_live.m3u")
        self.json_file = os.path.join(self.output_dir, "whos_vod.json")
        
        # 内存存储结果：{ "m3u8_url": "video_title" }
        self.video_results = {}

    def fetch(self, url):
        """通用网络请求方法，带有简单的错误处理"""
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception as e:
            return None

    def get_video_links(self):
        """第一步：扫描列表页，获取所有视频详情页的链接"""
        print(f"🚀 [1/3] 开始获取列表页 (共 {self.max_list_pages} 页)...")
        detail_urls = set()
        
        for i in range(1, self.max_list_pages + 1):
            target_url = f"{self.start_url}/page-{i}" if i > 1 else self.start_url
            html = self.fetch(target_url)
            if not html:
                print(f"   ⚠️ 无法加载页面: {target_url}")
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            # 过滤规则：包含 /videos/ 且不含 /page/ 的链接
            links = [urljoin(target_url, a['href']) for a in soup.find_all('a', href=True) 
                     if '/videos/' in a['href'] and '/page-' not in a['href']]
            
            before_count = len(detail_urls)
            detail_urls.update(links)
            print(f"   📑 第 {i} 页扫描完成，新增 {len(detail_urls) - before_count} 条，累计 {len(detail_urls)} 条")
            
        return list(detail_urls)

    def parse_video_details(self, detail_url):
        """第二步：解析每一个详情页，提取标题和 M3U8"""
        html = self.fetch(detail_url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # --- 提取并清洗标题 ---
        h1 = soup.find('h1')
        raw_title = h1.get_text(strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "未知视频")
        clean_title = re.sub(r' - Whos\.tv|Whos\.tv - |视频 - |【.*】', '', raw_title).strip()
        # 避免 M3U 逗号冲突
        clean_title = clean_title.replace(',', ' ').replace('"', '')

        # --- 提取 M3U8 地址 ---
        # 这里的正则可以处理大部分被转义的 URL 情况
        m3u8_match = re.search(r'https?[:\\/]+[^"\']+\.m3u8[^"\']*', html)
        if m3u8_match:
            raw_url = m3u8_match.group(0)
            # 处理转义字符：将 \/ 还原为 /
            m3u8_url = raw_url.replace('\\/', '/').replace('\\', '')
            
            with self.lock:
                self.video_results[m3u8_url] = clean_title
            print(f"   ✅ 成功获取: {clean_title}")

    def generate_files(self):
        """第三步：将结果持久化为 M3U 和 JSON"""
        if not self.video_results:
            print("❌ 错误：未采集到任何视频数据，请检查网络或网站结构。")
            return
        
        print(f"\n📦 [3/3] 正在生成 TVBox 配置文件...")
        
        # 1. 生成 M3U (直播流格式)
        try:
            with open(self.m3u_file, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for url, title in self.video_results.items():
                    f.write(f'#EXTINF:-1 tvg-name="{title}" group-title="WhosTV",{title}\n')
                    f.write(url + "\n")
            
            # 2. 生成 JSON (点播列表格式)
            vod_list = []
            for url, title in self.video_results.items():
                vod_list.append({
                    "vod_name": title,
                    "vod_id": url,
                    "vod_play_from": "WhosTV",
                    "vod_play_url": f"播放${url}"
                })
            
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump({"list": vod_list}, f, ensure_ascii=False, indent=4)
                
            print(f"✨ 全部任务完成！")
            print(f"📂 输出目录: {self.output_dir}")
            print(f"📺 直播文件 (M3U): {os.path.basename(self.m3u_file)}")
            print(f"🎬 点播文件 (JSON): {os.path.basename(self.json_file)}")
            
        except Exception as e:
            print(f"❌ 文件写入失败: {e}")

    def run(self):
        """主入口"""
        detail_urls = self.get_video_links()
        if not detail_urls:
            return
            
        print(f"🚀 [2/3] 开始并发解析 (线程数: {self.max_workers})...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.parse_video_details, detail_urls)
        
        self.generate_files()

if __name__ == "__main__":
    # 配置参数：
    # max_list_pages: 扫描前几页的内容
    # max_workers: 并发线程，不建议超过 10，以免请求过快被服务器屏蔽
    app = WhosTvToBox(max_list_pages=5, max_workers=5)
    app.run()

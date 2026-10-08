#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import aiosqlite
import re
import json
import time
import logging
import os
from urllib.parse import quote, urljoin
from pyquery import PyQuery as pq
from datetime import datetime
import hashlib

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class AsyncLSPCrawler:
    def __init__(self, db_path="lsp_videos.db", max_concurrent=10):
        self.base_url = "https://xn--oq2a.lspcm48.lat"
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.session = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 视频ID缓存，用于快速去重
        self.existing_video_ids = set()
        
        # 数据库连接池
        self.db = None
        
        # 断点续爬状态
        self.crawl_state = {}
        
    async def init_database(self):
        """初始化SQLite数据库 - 改进版"""
        self.db = await aiosqlite.connect(self.db_path)
        
        # 创建categories表
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT,
                last_updated TEXT
            )
        ''')
        
        # 创建videos表 - 简化结构
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                category_id TEXT,
                name TEXT,
                image TEXT,
                actor TEXT,
                director TEXT,
                remarks TEXT,
                pubdate TEXT,
                area TEXT,
                year TEXT,
                content TEXT,
                play_url TEXT,
                crawl_time TEXT,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        ''')
        
        # 创建meta表用于存储爬取状态
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # 创建crawl_state表用于断点续爬
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS crawl_state (
                category_id TEXT PRIMARY KEY,
                current_page INTEGER DEFAULT 1,
                total_pages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                last_updated TEXT
            )
        ''')
        
        # 创建索引
        await self.db.execute('CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category_id)')
        await self.db.execute('CREATE INDEX IF NOT EXISTS idx_videos_crawl_time ON videos(crawl_time)')
        
        await self.db.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")
        
        # 加载现有视频ID到内存
        await self._load_existing_video_ids()
        # 加载爬取状态
        await self._load_crawl_state()
    
    async def _load_existing_video_ids(self):
        """加载已存在的视频ID到内存中"""
        try:
            cursor = await self.db.execute("SELECT id FROM videos")
            rows = await cursor.fetchall()
            self.existing_video_ids = set(row[0] for row in rows)
            logger.info(f"已加载 {len(self.existing_video_ids)} 个现有视频ID到内存")
        except Exception as e:
            logger.warning(f"加载现有视频ID失败: {e}")
            self.existing_video_ids = set()
    
    async def _load_crawl_state(self):
        """加载爬取状态"""
        try:
            cursor = await self.db.execute("SELECT * FROM crawl_state")
            rows = await cursor.fetchall()
            for row in rows:
                self.crawl_state[row[0]] = {
                    'current_page': row[1],
                    'total_pages': row[2],
                    'status': row[3],
                    'last_updated': row[4]
                }
            logger.info(f"已加载 {len(self.crawl_state)} 个分类的爬取状态")
        except Exception as e:
            logger.warning(f"加载爬取状态失败: {e}")
            self.crawl_state = {}
    
    async def save_crawl_state(self, category_id, current_page, total_pages, status='crawling'):
        """保存爬取状态"""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await self.db.execute('''
                INSERT OR REPLACE INTO crawl_state 
                (category_id, current_page, total_pages, status, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (category_id, current_page, total_pages, status, current_time))
            await self.db.commit()
            
            # 更新内存状态
            self.crawl_state[category_id] = {
                'current_page': current_page,
                'total_pages': total_pages,
                'status': status,
                'last_updated': current_time
            }
        except Exception as e:
            logger.error(f"保存爬取状态失败: {e}")
    
    async def clear_crawl_state(self, category_id=None):
        """清除爬取状态"""
        try:
            if category_id:
                await self.db.execute("DELETE FROM crawl_state WHERE category_id = ?", (category_id,))
                if category_id in self.crawl_state:
                    del self.crawl_state[category_id]
            else:
                await self.db.execute("DELETE FROM crawl_state")
                self.crawl_state = {}
            await self.db.commit()
            logger.info("爬取状态已清除")
        except Exception as e:
            logger.error(f"清除爬取状态失败: {e}")
    
    def _generate_video_id(self, video_url):
        """根据视频URL生成唯一ID"""
        return hashlib.md5(video_url.encode()).hexdigest()
    
    async def save_categories(self, categories):
        """保存分类列表"""
        try:
            for category in categories:
                await self.db.execute(
                    "INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)",
                    (category['id'], category['name'])
                )
            await self.db.commit()
            logger.info(f"保存了 {len(categories)} 个分类")
        except Exception as e:
            logger.error(f"保存分类失败: {e}")
    
    async def batch_save_videos(self, videos):
        """批量保存视频数据"""
        if not videos:
            return 0
            
        success_count = 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for video in videos:
            try:
                await self.db.execute('''
                    INSERT OR REPLACE INTO videos 
                    (id, category_id, name, image, actor, director, remarks, 
                     pubdate, area, year, content, play_url, crawl_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video['id'],
                    video['category_id'],
                    video['name'],
                    video['image'],
                    video['actor'],
                    video['director'],
                    video['remarks'],
                    video['pubdate'],
                    video['area'],
                    video['year'],
                    video['content'],
                    video['play_url'],
                    current_time
                ))
                success_count += 1
                # 更新内存缓存
                self.existing_video_ids.add(video['id'])
            except Exception as e:
                logger.error(f"保存视频失败 {video['id']}: {e}")
        
        await self.db.commit()
        return success_count
    
    async def get_last_crawled_page(self, category_id):
        """获取上次爬取的页码"""
        try:
            cursor = await self.db.execute(
                "SELECT value FROM meta WHERE key = ?", 
                (f"last_page_{category_id}",)
            )
            row = await cursor.fetchone()
            if row:
                return int(row[0])
        except Exception:
            pass
        return 0
    
    async def save_last_crawled_page(self, category_id, page):
        """保存最后爬取的页码"""
        try:
            await self.db.execute('''
                INSERT OR REPLACE INTO meta (key, value) 
                VALUES (?, ?)
            ''', (f"last_page_{category_id}", str(page)))
            await self.db.commit()
        except Exception as e:
            logger.error(f"保存页码失败: {e}")
    
    async def update_category_last_updated(self, category_id):
        """更新分类的最后更新时间"""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await self.db.execute(
                "UPDATE categories SET last_updated = ? WHERE id = ?",
                (current_time, category_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.warning(f"更新分类最后更新时间失败: {e}")
    
    async def fetch(self, url, retry=3, timeout=10):
        """改进的异步请求函数"""
        async with self.semaphore:
            for i in range(retry):
                try:
                    async with self.session.get(
                        url, 
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                            'Referer': self.base_url
                        }
                    ) as response:
                        if response.status == 200:
                            text = await response.text()
                            return text
                        else:
                            logger.warning(f"请求失败 {url}: 状态码 {response.status}")
                except asyncio.TimeoutError:
                    if i == retry - 1:
                        logger.error(f"请求超时: {url}")
                except Exception as e:
                    if i == retry - 1:
                        logger.error(f"请求失败: {url} - {e}")
                
                # 指数退避延迟
                await asyncio.sleep(2 ** i)
            
            return None
    
    async def get_all_categories(self):
        """获取全部分类"""
        logger.info("获取分类列表中...")
        categories = []
        try:
            html = await self.fetch(f"{self.base_url}/index.php")
            if html:
                doc = pq(html)
                items = doc('.tabs li a')
                for item in items.items():
                    name = item.text().strip()
                    href = item.attr('href')
                    if name and href:
                        match = re.search(r'/(\d+).html', href)
                        if match:
                            categories.append({
                                'name': name,
                                'id': match.group(1)
                            })
            logger.info(f"发现 {len(categories)} 个分类")
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
        
        return categories
    
    async def get_category_page_count(self, category_id):
        """获取分类的总页数"""
        try:
            html = await self.fetch(f"{self.base_url}/index.php/vod/type/id/{category_id}/page/1.html")
            if html:
                doc = pq(html)
                
                # 查找分页元素
                pagination = doc('.pagination a')
                page_numbers = []
                
                for page in pagination.items():
                    page_text = page.text().strip()
                    if page_text.isdigit():
                        page_numbers.append(int(page_text))
                
                if page_numbers:
                    return max(page_numbers)
                
                # 如果没有分页，检查是否有内容
                items = doc('.grid .grid__item')
                if len(items) > 0:
                    return 1
                    
        except Exception as e:
            logger.error(f"获取页数失败: {e}")
        
        return 1
    
    async def get_videos_from_page(self, category_id, category_name, page):
        """获取指定页面的视频列表"""
        try:
            url = f"{self.base_url}/index.php/vod/type/id/{category_id}/page/{page}.html"
            html = await self.fetch(url)
            if not html:
                return []
                
            doc = pq(html)
            items = doc('.grid .grid__item')
            videos = []
            
            for item in items.items():
                a = item.find('a')
                href = a.attr('href')
                name = item.find('h3').text().strip()
                
                if not name or not href:
                    continue
                
                # 生成唯一ID
                video_id = self._generate_video_id(href)
                
                # 检查是否已存在
                if video_id in self.existing_video_ids:
                    continue
                    
                img = item.find('img').attr('data-original') or item.find('img').attr('src')
                desc = item.find('.duration-video').text() or ''
                
                # 处理图片URL
                if img and not img.startswith('http'):
                    img = urljoin(self.base_url, img)
                
                video_data = {
                    'id': video_id,
                    'category_id': category_id,
                    'name': name,
                    'image': img,
                    'actor': '',
                    'director': '',
                    'remarks': desc,
                    'pubdate': '',
                    'area': '',
                    'year': '',
                    'content': '',
                    'play_url': '',
                    'original_url': href
                }
                
                videos.append(video_data)
            
            return videos
        except Exception as e:
            logger.error(f"获取第{page}页失败: {e}")
            return []
    
    async def get_video_detail(self, video_data):
        """获取视频详细信息"""
        try:
            video_url = video_data['original_url']
            if not video_url.startswith('http'):
                video_url = urljoin(self.base_url, video_url)
                
            html = await self.fetch(video_url, timeout=15)
            if not html:
                return video_data
                
            doc = pq(html)
            
            # 提取详细信息
            title = doc('.section-header__title--video').text() or video_data['name']
            description = doc('.video-footer__description').text() or ''
            
            # 更新基本信息
            video_data['name'] = title.strip()
            video_data['content'] = description.strip()
            
            # 提取播放链接
            play_url = await self.extract_play_url(html)
            if play_url:
                video_data['play_url'] = play_url
            
            return video_data
            
        except Exception as e:
            logger.error(f"获取详情失败 {video_data['id']}: {e}")
            return video_data
    
    async def extract_play_url(self, html):
        """从HTML中提取播放链接"""
        try:
            # 方法1: 从HlsJsPlayer配置中提取
            player_match = re.search(r'let player = new HlsJsPlayer\s*\(\s*({.*?})\s*\)', html, re.DOTALL)
            if player_match:
                player_config = player_match.group(1)
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', player_config)
                if url_match:
                    return url_match.group(1)
            
            # 方法2: 直接搜索m3u8链接
            m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
            if m3u8_match:
                return m3u8_match.group(0)
            
            # 方法3: 从script标签中查找
            doc = pq(html)
            scripts = doc('script')
            for script in scripts.items():
                script_text = script.text()
                if 'm3u8' in script_text:
                    m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', script_text)
                    if m3u8_match:
                        return m3u8_match.group(0)
        except Exception as e:
            logger.error(f"提取播放链接失败: {e}")
        
        return ""
    
    async def process_video_batch(self, videos):
        """批量处理视频"""
        if not videos:
            return 0, 0
        
        # 并发获取视频详情
        tasks = [self.get_video_detail(video) for video in videos]
        detailed_videos = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_videos = []
        for video in detailed_videos:
            if not isinstance(video, Exception):
                valid_videos.append(video)
        
        # 批量保存
        success_count = await self.batch_save_videos(valid_videos)
        
        return len(videos), success_count
    
    async def crawl_category_incremental(self, category_id, category_name, max_pages=3, resume=False):
        """增量爬取单个分类 - 支持断点续爬"""
        logger.info(f"开始增量爬取分类: {category_name}")
        
        # 获取总页数
        page_count = await self.get_category_page_count(category_id)
        actual_pages = min(page_count, max_pages)
        logger.info(f"分类 {category_name} 共有 {page_count} 页，本次爬取前 {actual_pages} 页")
        
        # 断点续爬逻辑
        start_page = 1
        if resume and category_id in self.crawl_state:
            state = self.crawl_state[category_id]
            if state['status'] == 'crawling':
                start_page = state['current_page']
                logger.info(f"检测到未完成的爬取任务，从第 {start_page} 页继续")
        
        total_videos = 0
        total_success = 0
        
        for page in range(start_page, actual_pages + 1):
            # 保存当前爬取状态
            await self.save_crawl_state(category_id, page, actual_pages, 'crawling')
            
            # 获取当前页视频
            videos = await self.get_videos_from_page(category_id, category_name, page)
            if not videos:
                logger.info(f"第 {page} 页无新视频，停止爬取")
                break
            
            # 批量处理视频详情
            video_count, success_count = await self.process_video_batch(videos)
            
            total_videos += video_count
            total_success += success_count
            
            logger.info(f"第 {page} 页: {video_count}个新视频, 成功保存{success_count}个")
            
            # 更新最后爬取页码
            await self.save_last_crawled_page(category_id, page)
            
            # 页间延迟
            await asyncio.sleep(0.5)
        
        # 标记爬取完成
        if total_success > 0:
            await self.update_category_last_updated(category_id)
            await self.save_crawl_state(category_id, actual_pages, actual_pages, 'completed')
        else:
            await self.save_crawl_state(category_id, start_page, actual_pages, 'no_new_videos')
        
        logger.info(f"分类 {category_name} 完成: 发现{total_videos}个新视频, 成功保存{total_success}个")
        return total_videos, total_success
    
    async def crawl_category_full(self, category_id, category_name, resume=False):
        """全量爬取单个分类 - 支持断点续爬"""
        logger.info(f"开始全量爬取分类: {category_name}")
        
        page_count = await self.get_category_page_count(category_id)
        logger.info(f"分类 {category_name} 共有 {page_count} 页")
        
        # 断点续爬逻辑
        start_page = 1
        if resume and category_id in self.crawl_state:
            state = self.crawl_state[category_id]
            if state['status'] == 'crawling':
                start_page = state['current_page']
                logger.info(f"检测到未完成的爬取任务，从第 {start_page} 页继续")
        
        total_videos = 0
        total_success = 0
        
        for page in range(start_page, page_count + 1):
            # 保存当前爬取状态
            await self.save_crawl_state(category_id, page, page_count, 'crawling')
            
            videos = await self.get_videos_from_page(category_id, category_name, page)
            if not videos:
                logger.info(f"第 {page} 页无视频，停止爬取")
                break
            
            video_count, success_count = await self.process_video_batch(videos)
            total_videos += video_count
            total_success += success_count
            
            logger.info(f"第 {page} 页: {video_count}个视频, 成功{success_count}个")
            await self.save_last_crawled_page(category_id, page)
            await asyncio.sleep(0.3)
        
        # 标记爬取完成
        await self.save_crawl_state(category_id, page_count, page_count, 'completed')
        
        logger.info(f"分类 {category_name} 完成: 总计{total_videos}个视频, 成功{total_success}个")
        return total_videos, total_success
    
    async def incremental_update(self, max_pages_per_category=3, resume=False):
        """增量更新全站数据 - 支持断点续爬"""
        logger.info("开始增量更新全站数据...")
        start_time = time.time()
        
        self.session = aiohttp.ClientSession()
        
        try:
            # 获取分类
            categories = await self.get_all_categories()
            if not categories:
                logger.error("未找到任何分类！")
                return
            
            # 保存分类信息
            await self.save_categories(categories)
            
            total_new_videos = 0
            total_updated_categories = 0
            
            # 并发爬取所有分类
            tasks = []
            for category in categories:
                task = self.crawl_category_incremental(
                    category['id'], 
                    category['name'], 
                    max_pages_per_category,
                    resume
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            for videos, success in results:
                total_new_videos += videos
                if success > 0:
                    total_updated_categories += 1
            
            # 统计最终结果
            cursor = await self.db.execute("SELECT COUNT(*) FROM videos")
            final_count = (await cursor.fetchone())[0]
            
            elapsed_time = time.time() - start_time
            logger.info(f"\n增量更新完成！用时: {elapsed_time:.1f}秒")
            logger.info(f"数据库总计: {final_count} 个视频")
            logger.info(f"本次更新: 在{total_updated_categories}个分类中发现{total_new_videos}个新视频")
            
        finally:
            await self.session.close()
    
    async def crawl_all_data(self, resume=False):
        """全量爬取全站数据 - 支持断点续爬"""
        logger.info("开始全量爬取LSP传媒全站数据...")
        start_time = time.time()
        
        self.session = aiohttp.ClientSession()
        
        try:
            categories = await self.get_all_categories()
            if not categories:
                logger.error("未找到任何分类！")
                return
            
            await self.save_categories(categories)
            
            total_all_videos = 0
            total_all_success = 0
            
            tasks = []
            for category in categories:
                task = self.crawl_category_full(category['id'], category['name'], resume)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            for videos, success in results:
                total_all_videos += videos
                total_all_success += success
            
            cursor = await self.db.execute("SELECT COUNT(*) FROM videos")
            final_count = (await cursor.fetchone())[0]
            
            elapsed_time = time.time() - start_time
            logger.info(f"\n全量爬取完成！用时: {elapsed_time:.1f}秒")
            logger.info(f"数据库总计: {final_count} 个视频")
            logger.info(f"本次爬取: {total_all_videos}个视频, 成功{total_all_success}个")
            
        finally:
            await self.session.close()

    async def export_to_json(self, file_path):
        """导出视频数据到JSON文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 查询所有视频数据
            cursor = await self.db.execute('''
                SELECT 
                    v.id, v.name, v.image, v.actor, v.director, v.remarks,
                    v.pubdate, v.area, v.year, v.content, v.play_url,
                    c.name as category_name, v.crawl_time
                FROM videos v
                LEFT JOIN categories c ON v.category_id = c.id
                ORDER BY v.crawl_time DESC
            ''')
            
            rows = await cursor.fetchall()
            
            # 转换为字典列表
            videos = []
            for row in rows:
                video = {
                    "vod_id": row[0],
                    "vod_name": row[1],
                    "vod_pic": row[2] or "",
                    "vod_actor": row[3] or "",
                    "vod_director": row[4] or "",
                    "vod_remarks": row[5] or "",
                    "vod_pubdate": row[6] or "",
                    "vod_area": row[7] or "",
                    "vod_year": row[8] or "",
                    "vod_content": row[9] or "",
                    "vod_play_from": "hsck",
                    "vod_play_url": f"正片${row[10]}" if row[10] else "",
                    "type_name": row[11] or ""
                }
                videos.append(video)
            
            # 写入JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(videos, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON导出成功。文件: {file_path} 总视频数: {len(videos)}")
            return len(videos)
            
        except Exception as e:
            logger.error(f"导出JSON失败: {e}")
            return 0

    async def export_to_txt(self, file_path):
        """导出视频数据到TXT文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 按分类查询视频数据
            cursor = await self.db.execute('''
                SELECT 
                    c.name as category_name,
                    v.name as video_name,
                    v.play_url
                FROM videos v
                LEFT JOIN categories c ON v.category_id = c.id
                WHERE v.play_url != ''
                ORDER BY c.name, v.name
            ''')
            
            rows = await cursor.fetchall()
            
            # 按分类组织数据
            category_data = {}
            for row in rows:
                category_name, video_name, play_url = row
                if category_name not in category_data:
                    category_data[category_name] = []
                category_data[category_name].append((video_name, play_url))
            
            # 写入TXT文件
            with open(file_path, 'w', encoding='utf-8') as f:
                for category_name, videos in category_data.items():
                    f.write(f"{category_name},#genre#\n")
                    for video_name, play_url in videos:
                        f.write(f"{video_name},{play_url}\n")
                    f.write("\n")
            
            total_videos = sum(len(videos) for videos in category_data.values())
            logger.info(f"TXT导出成功。文件: {file_path} 总视频数: {total_videos}")
            return total_videos
            
        except Exception as e:
            logger.error(f"导出TXT失败: {e}")
            return 0

    async def export_to_m3u(self, file_path):
        """导出视频数据到M3U文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 查询所有有播放链接的视频数据
            cursor = await self.db.execute('''
                SELECT 
                    v.name as video_name,
                    v.image,
                    c.name as category_name,
                    v.play_url
                FROM videos v
                LEFT JOIN categories c ON v.category_id = c.id
                WHERE v.play_url != ''
                ORDER BY c.name, v.name
            ''')
            
            rows = await cursor.fetchall()
            
            # 写入M3U文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for row in rows:
                    video_name, image, category_name, play_url = row
                    # M3U条目
                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{video_name}" tvg-logo="{image or ""}" group-title="{category_name or ""}",{video_name}\n')
                    f.write(f"{play_url}\n")
            
            logger.info(f"M3U导出成功。文件: {file_path} 总视频数: {len(rows)}")
            return len(rows)
            
        except Exception as e:
            logger.error(f"导出M3U失败: {e}")
            return 0

    async def export_data(self, file_path, format_type='json'):
        """通用导出函数"""
        format_type = format_type.lower()
        
        if format_type == 'json':
            return await self.export_to_json(file_path)
        elif format_type == 'txt':
            return await self.export_to_txt(file_path)
        elif format_type == 'm3u':
            return await self.export_to_m3u(file_path)
        else:
            logger.error(f"不支持的格式: {format_type}")
            return 0
    
    async def get_crawl_status(self):
        """获取爬取状态"""
        if not self.crawl_state:
            logger.info("没有找到爬取状态信息")
            return
        
        logger.info("\n当前爬取状态:")
        for category_id, state in self.crawl_state.items():
            cursor = await self.db.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
            row = await cursor.fetchone()
            category_name = row[0] if row else category_id
            
            status_map = {
                'pending': '等待开始',
                'crawling': '爬取中',
                'completed': '已完成',
                'no_new_videos': '无新视频'
            }
            
            status_text = status_map.get(state['status'], state['status'])
            logger.info(f"  {category_name}: 第{state['current_page']}/{state['total_pages']}页 - {status_text}")
    
    async def get_stats(self):
        """获取数据库统计信息"""
        try:
            cursor = await self.db.execute("SELECT COUNT(*) FROM videos")
            total_videos = (await cursor.fetchone())[0]
            
            cursor = await self.db.execute("SELECT COUNT(DISTINCT category_id) FROM videos")
            total_categories = (await cursor.fetchone())[0]
            
            cursor = await self.db.execute("SELECT COUNT(*) FROM videos WHERE play_url != ''")
            videos_with_play_url = (await cursor.fetchone())[0]
            
            cursor = await self.db.execute("""
                SELECT c.name, COUNT(v.id) 
                FROM categories c 
                LEFT JOIN videos v ON c.id = v.category_id 
                GROUP BY c.id, c.name 
                ORDER BY COUNT(v.id) DESC
            """)
            category_stats = await cursor.fetchall()
            
            logger.info(f"\n数据库统计:")
            logger.info(f"总视频数: {total_videos}")
            logger.info(f"有播放链接的视频数: {videos_with_play_url}")
            logger.info(f"分类数量: {total_categories}")
            logger.info("各分类视频数量:")
            for category, count in category_stats:
                logger.info(f"  {category}: {count}")
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
    
    async def reload_video_cache(self):
        """重新加载视频ID缓存"""
        await self._load_existing_video_ids()
        logger.info(f"视频ID缓存已重新加载，当前缓存 {len(self.existing_video_ids)} 个视频ID")
    
    async def reset_database(self):
        """重置数据库（删除所有数据）"""
        try:
            await self.db.execute("DELETE FROM videos")
            await self.db.execute("DELETE FROM categories")
            await self.db.execute("DELETE FROM meta")
            await self.db.execute("DELETE FROM crawl_state")
            await self.db.commit()
            await self._load_existing_video_ids()
            await self._load_crawl_state()
            logger.info("数据库已重置，所有数据已清除")
        except Exception as e:
            logger.error(f"重置数据库失败: {e}")
    
    async def close(self):
        """关闭资源"""
        if self.db:
            await self.db.close()
        if self.session:
            await self.session.close()

async def main():
    crawler = AsyncLSPCrawler(max_concurrent=15)
    
    try:
        await crawler.init_database()
        
        while True:
            print("\n" + "="*50)
            print("LSP传媒异步爬虫 - 增强版")
            print("1. 全量爬取（重新爬取所有数据）")
            print("2. 全量爬取（断点续爬）")
            print("3. 增量更新（只爬取新视频，推荐）")
            print("4. 增量更新（断点续爬）")
            print("5. 查看统计信息")
            print("6. 查看爬取状态")
            print("7. 导出数据")
            print("8. 重新加载视频ID缓存")
            print("9. 清除爬取状态")
            print("10. 重置数据库")
            print("11. 退出")
            print("="*50)
            
            choice = input("请选择操作 (1-11): ").strip()
            
            if choice == '1':
                print("开始全量爬取全站数据...")
                await crawler.crawl_all_data(resume=False)
                
            elif choice == '2':
                print("开始全量爬取（断点续爬）...")
                await crawler.crawl_all_data(resume=True)
                
            elif choice == '3':
                pages = input("请输入每个分类爬取的页数 (默认3): ").strip()
                max_pages = int(pages) if pages.isdigit() else 3
                await crawler.incremental_update(max_pages_per_category=max_pages, resume=False)
                    
            elif choice == '4':
                pages = input("请输入每个分类爬取的页数 (默认3): ").strip()
                max_pages = int(pages) if pages.isdigit() else 3
                await crawler.incremental_update(max_pages_per_category=max_pages, resume=True)
            
            elif choice == '5':
                await crawler.get_stats()
            
            elif choice == '6':
                await crawler.get_crawl_status()
            
            elif choice == '7':
                print("请选择导出格式:")
                print("1. JSON")
                print("2. TXT")
                print("3. M3U")
                format_choice = input("请选择格式 (1-3): ").strip()
                
                format_map = {'1': 'json', '2': 'txt', '3': 'm3u'}
                if format_choice in format_map:
                    file_path = input("请输入输出文件路径: ").strip()
                    if not file_path:
                        # 根据格式设置默认文件名
                        ext = format_map[format_choice]
                        file_path = f"/storage/emulated/0/lz/json/lsp.{ext}"
                    
                    total_videos = await crawler.export_data(file_path, format_map[format_choice])
                    if total_videos == 0:
                        print("警告: 数据库中没有视频数据，请先运行爬取功能！")
                else:
                    print("无效的格式选择！")
                    
            elif choice == '8':
                await crawler.reload_video_cache()
            
            elif choice == '9':
                await crawler.clear_crawl_state()
            
            elif choice == '10':
                confirm = input("确定要重置数据库吗？所有数据将被删除！(y/N): ").strip().lower()
                if confirm == 'y':
                    await crawler.reset_database()
                else:
                    print("取消重置操作")
                
            elif choice == '11':
                print("再见！")
                break
            else:
                print("无效选择！")
                
    finally:
        await crawler.close()

if __name__ == "__main__":
    # 检查依赖
    try:
        import aiohttp
        import aiosqlite
        from pyquery import PyQuery as pq
    except ImportError as e:
        print(f"缺少依赖库: {e}")
        print("请在Termux中运行: pkg install python && pip install aiohttp aiosqlite pyquery")
        exit(1)
    
    # 运行主程序
    asyncio.run(main())
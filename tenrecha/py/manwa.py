# -*- coding: utf-8 -*-
import os
import re
import json
import random
import io
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import aiohttp
from aiohttp import ClientTimeout, TCPConnector

# ===================== 日志配置 =====================
def setup_logger():
    log_dir = os.path.join(ROOT_DOWNLOAD_DIR, "crawl_logs")
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{today}_crawl.log")

    logger = logging.getLogger("MangaCrawler")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件输出
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# ===================== 核心配置区 =====================
# 漫画分类爬取地址 + 分类名称
URL_CATEGORY_MAP = {
    "https://manwagk.cc/booklist?tag=&end=1&gender=1&has_full=-1&area=2&sort=-1&level=-1": "韩国禁漫完结",
    "https://manwagk.cc/booklist?tag=&end=2&gender=1&has_full=-1&area=2&sort=-1&level=-1": "韩国禁漫连载",
    "": "",
    "": "",
}

# 根保存目录
ROOT_DOWNLOAD_DIR = "漫画合集"

# 最大下载章节数，None=下载全部章节，数字=仅下载前N章
MAX_CHAPTERS = None

# 是否自动生成PDF，True=图片+PDF，False=仅保存图片
GENERATE_PDF = False

# 并发任务数量
CONCURRENT_NUM = 8

# 随机延迟范围，防止封IP
MIN_DELAY = 5.0
MAX_DELAY = 10.5

# 断点续爬记录文件
CHECKPOINT_FILE = os.path.join(ROOT_DOWNLOAD_DIR, "crawl_checkpoint.json")

# 从第几页开始爬
START_PAGE = 1

# 关键词定位：从此标题开始往后全部爬取
START_KEYWORD = ""

# 图片AES解密密钥（网站固定）
AES_KEY = b"my2ecret782ecret"
AES_IV = b"my2ecret782ecret"

# 请求头UA池，随机切换模拟浏览器
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; K) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Version/17.4.1 Safari/605.1.15"
]

# 异步锁：防止多任务同时写文件
LOCK = asyncio.Lock()

# 初始化日志
logger = setup_logger()

# ===================== 工具函数 =====================

# 清理文件名：去除非法字符、超长截断（已强化修复所有特殊符号）
def clean_filename(name: str) -> str:
    if not name:
        return "未知"
    name = re.sub(r'[\\/:*?"<>|#\[\]{}@&^%$!~`\+=；：‘’“”《》【】…—,]', '', name)
    name = re.sub(r'[\.\…。]{2,}', ' ', name)
    name = re.sub(r'…+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip(' .。…-')
    if len(name) > 140:
        name = name[:137] + "..."
    return name if name else "未知"

# 随机获取一个浏览器UA
def get_random_ua():
    return random.choice(USER_AGENT_POOL)

# 随机延迟：防反爬
async def random_delay():
    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

# 图片AES解密：网站图片是加密传输的
def decrypt_image(encrypted_data):
    if not encrypted_data or len(encrypted_data) < 16:
        return None
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        if len(decrypted) > 300 and (decrypted.startswith(b'\xff\xd8') or b'WEBP' in decrypted[:100]):
            return decrypted
    except Exception:
        pass
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted = cipher.decrypt(encrypted_data)
        if len(decrypted) > len(encrypted_data) * 0.8 and (
            decrypted.startswith(b'\xff\xd8\xff') or decrypted.startswith(b'RIFF') or b'WEBP' in decrypted[:200]
        ):
            return decrypted
    except Exception:
        pass
    return encrypted_data

# 图片合成PDF
def images_to_pdf(img_list, pdf_path):
    if not img_list:
        return False
    try:
        c = canvas.Canvas(pdf_path, pagesize=A4)
        pw, ph = A4
        for img_data in img_list:
            img = ImageReader(io.BytesIO(img_data))
            w, h = img.getSize()
            scale = max(pw / w, ph / h)
            nw, nh = w * scale, h * scale
            x, y = (pw - nw) / 2, (ph - nh) / 2
            c.drawImage(img, x, y, width=nw, height=nh)
            c.showPage()
        c.save()
        logger.info(f"✅ PDF生成成功：{os.path.basename(pdf_path)}")
        return True
    except Exception as e:
        logger.error(f"❌ PDF生成失败：{str(e)[:60]}")
        return False

# ===================== 断点续爬模块 =====================

# 初始化断点文件
def init_checkpoint():
    os.makedirs(ROOT_DOWNLOAD_DIR, exist_ok=True)
    if not os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

# 读取断点记录
def read_checkpoint():
    init_checkpoint()
    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 写入断点记录
def write_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 判断整部漫画是否已爬完
def is_manga_crawled(checkpoint, category, title):
    if category not in checkpoint or title not in checkpoint[category]:
        return False
    return len(checkpoint[category][title]) >= MAX_CHAPTERS if MAX_CHAPTERS else False

# 判断单章节是否已下载
def is_chapter_crawled(checkpoint, category, title, chapter):
    if category not in checkpoint or title not in checkpoint[category]:
        return False
    return chapter in checkpoint[category][title]

# 更新断点：标记章节已下载
async def update_checkpoint(category, title, chapter):
    async with LOCK:
        data = read_checkpoint()
        if category not in data:
            data[category] = {}
        if title not in data[category]:
            data[category][title] = []
        if chapter not in data[category][title]:
            data[category][title].append(chapter)
            write_checkpoint(data)

# ===================== 图片下载模块 =====================

# 下载单张图片 + 解密
async def get_chapter_image(session, img_url, cache, chapter_name):
    if img_url in cache:
        return cache[img_url]

    headers = {"User-Agent": get_random_ua(), "Referer": "https://manwagk.cc/"}
    
    for attempt in range(3):
        try:
            async with session.get(img_url, headers=headers, timeout=15) as res:
                res.raise_for_status()
                data = await res.read()
            decrypted = decrypt_image(data)
            if decrypted and len(decrypted) > 500:
                cache[img_url] = decrypted
                return decrypted
            else:
                cache[img_url] = None
                return None
        except Exception as e:
            if attempt == 2:
                logger.error(f"❌ 图片下载失败（章节：{chapter_name[:30]}…）URL：{img_url[:50]} 错误：{str(e)[:40]}")
                return None
            await asyncio.sleep(1.5)
    return None

# 获取一整话的所有图片
async def get_chapter_images(session, chapter_url, chapter_name):
    cache = {}
    headers = {"User-Agent": get_random_ua(), "Referer": "https://manwagk.cc/"}
    try:
        async with session.get(chapter_url, headers=headers) as res:
            res.raise_for_status()
            html = await res.text()
        soup = BeautifulSoup(html, 'html.parser')
        urls = [img.get('data-r-src') or img.get('src') or img.get('data-original')
                for img in soup.select('.lazy_img, .img-item img')]
        urls = [u for u in urls if u and u.startswith('http')]

        img_list = []
        batch_size = 30
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"📥 章节「{chapter_name[:30]}…」第{i//batch_size +1}批图片（{len(batch)}张）")
            tasks = [get_chapter_image(session, u, cache, chapter_name) for u in batch]
            results = await asyncio.gather(*tasks)
            img_list.extend([img for img in results if img])

        logger.info(f"📸 章节「{chapter_name[:30]}…」解密完成：{len(img_list)} 张有效图片")
        return img_list
    except Exception as e:
        logger.error(f"❌ 章节「{chapter_name[:30]}…」获取图片失败：{str(e)[:50]}")
        await random_delay()
        return []

# 保存章节图片到本地 + 生成PDF
async def download_chapter(final_dir, manga_title, chapter_name, img_list):
    manga_clean = clean_filename(manga_title)
    chapter_clean = clean_filename(chapter_name)
    chapter_dir = os.path.join(final_dir, manga_clean, chapter_clean)

    async with LOCK:
        os.makedirs(chapter_dir, exist_ok=True)
        await asyncio.sleep(0.15)

    success_count = 0
    for idx, img_data in enumerate(img_list, 1):
        img_path = os.path.join(chapter_dir, f"{idx:03d}.jpg")
        for attempt in range(5):
            try:
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                success_count += 1
                break
            except Exception:
                if attempt == 4:
                    logger.error(f"❌ 保存失败：{manga_clean} → {chapter_clean} 第{idx:03d}.jpg")

    if GENERATE_PDF and success_count > 0:
        pdf_path = os.path.join(chapter_dir, f"{chapter_clean}.pdf")
        images_to_pdf(img_list, pdf_path)

    logger.info(f"✅ 章节保存完成：{manga_clean} → {chapter_clean}（{success_count}/{len(img_list)}张）")
    await random_delay()

# ===================== 翻页爬取核心 =====================

# 获取某一页的漫画列表
async def get_manga_list(session, base_url, page):
    clean_url = re.sub(r'&?page=\d+', '', base_url).rstrip('&')
    separator = '&' if '?' in clean_url else '?'
    crawl_url = f"{clean_url}{separator}page={page}"

    headers = {"User-Agent": get_random_ua(), "Referer": "https://manwagk.cc/"}
    try:
        async with session.get(crawl_url, headers=headers) as res:
            res.raise_for_status()
            html = await res.text()
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.manga-list-2 li a') or soup.select('.book-list li a')
        manga_list = []
        seen = set()
        for item in items:
            title = (item.get('title') or item.select_one('img').get('alt', '未知')).strip()
            url = item.get('href', '')
            if not url.startswith('http'):
                url = f"https://manwagk.cc{url}" if url.startswith('/') else f"https://manwagk.cc/{url}"
            if url not in seen:
                seen.add(url)
                manga_list.append({"title": title, "url": url})
        logger.info(f"📄 第{page}页 → {len(manga_list)} 部漫画")
        await random_delay()
        return manga_list
    except Exception as e:
        logger.error(f"❌ 第{page}页爬取失败：{str(e)[:50]}")
        await random_delay()
        return []

# 获取漫画的所有章节列表
async def get_chapter_list(session, manga_url):
    headers = {"User-Agent": get_random_ua(), "Referer": "https://manwagk.cc/"}
    try:
        async with session.get(manga_url, headers=headers) as res:
            res.raise_for_status()
            html = await res.text()
        soup = BeautifulSoup(html, 'html.parser')
        chapters = []
        for a in soup.select('.detail-list-select li a') or soup.select('.chapter-list li a'):
            name = a.text.strip()
            url = a.get('href', '')
            if not url.startswith('http'):
                url = f"https://manwagk.cc{url}" if url.startswith('/') else f"https://manwagk.cc/{url}"
            chapters.append({"name": name, "url": url})
        await random_delay()
        return chapters
    except Exception as e:
        logger.error(f"❌ 获取章节列表失败：{str(e)[:50]}")
        await random_delay()
        return []

# 处理单页漫画：关键词过滤 + 断点跳过 + 下载
async def crawl_page(session, sem, fixed_url, page, category_name, final_dir, checkpoint, manga_list, keyword_started):
    async with sem:
        if page < START_PAGE:
            logger.info(f"⏭️ 第{page}页 < 起始页，跳过")
            return 0, keyword_started

        count = 0
        for manga in manga_list:
            title = manga["title"]
            url = manga["url"]
            title_clean = clean_filename(title)

            if START_KEYWORD.strip() and not keyword_started:
                if START_KEYWORD in title:
                    logger.info(f"\n🔍 触发关键词「{START_KEYWORD}」，从此开始爬取")
                    keyword_started = True
                else:
                    continue

            if is_manga_crawled(checkpoint, category_name, title_clean):
                logger.info(f"⏭️ 已完成：{title_clean}")
                continue

            count += 1
            logger.info(f"\n📚 开始处理漫画：{title_clean}")

            chapters = await get_chapter_list(session, url)
            if not chapters:
                logger.warning(f"⚠️ 漫画「{title_clean}」无章节，跳过")
                continue
            if MAX_CHAPTERS:
                chapters = chapters[:MAX_CHAPTERS]

            for ch in chapters:
                ch_name = ch["name"]
                ch_url = ch["url"]
                ch_clean = clean_filename(ch_name)

                if is_chapter_crawled(checkpoint, category_name, title_clean, ch_clean):
                    logger.info(f" ⏭️ 章节已下载：{ch_clean}")
                    continue

                logger.info(f" 🔍 开始下载：{ch_clean}")
                imgs = await get_chapter_images(session, ch_url, ch_name)
                if not imgs:
                    logger.warning(f" ⚠️ 章节「{ch_clean}」无有效图片，跳过")
                    continue

                await download_chapter(final_dir, title, ch_name, imgs)
                await update_checkpoint(category_name, title_clean, ch_clean)

        return count, keyword_started

# 爬取单个分类（连载/完结）
async def crawl_single_category(fixed_url, category_name):
    final_dir = os.path.join(ROOT_DOWNLOAD_DIR, category_name)
    os.makedirs(final_dir, exist_ok=True)
    checkpoint = read_checkpoint()
    logger.info(f"\n=============== 开始爬取分类：【{category_name}】 ===============")

    timeout = ClientTimeout(total=35)
    connector = TCPConnector(limit=CONCURRENT_NUM * 2, limit_per_host=6, verify_ssl=False)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        sem = asyncio.Semaphore(CONCURRENT_NUM)
        page = 1
        total = 0
        keyword_started = False if START_KEYWORD.strip() else True

        while True:
            manga_list = await get_manga_list(session, fixed_url, page)
            if not manga_list:
                logger.info(f"\n📌 【{category_name}】第{page}页无数据，爬取结束！")
                break

            processed, keyword_started = await crawl_page(
                session, sem, fixed_url, page, category_name, final_dir, checkpoint, manga_list, keyword_started
            )
            total += processed
            checkpoint = read_checkpoint()
            page += 1

    logger.info(f"=============== 【{category_name}】完成，共处理 {total} 部漫画 ===============\n")
    return total

# 主入口
async def main():
    logger.info("=============== 漫画爬虫 v2.6（带日志保存）启动 ===============")
    init_checkpoint()
    total_all = 0
    for url, name in URL_CATEGORY_MAP.items():
        if not url or not name:
            continue
        total_all += await crawl_single_category(url, name)
        await asyncio.sleep(2)

    logger.info(f"=============== 全部任务结束！共处理 {total_all} 部漫画 ===============")

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯标准库图片下载器（零依赖，直接运行）
用法: python downloader.py <网页URL>
"""

import os
import re
import sys
import ssl
from urllib import request, parse, error
from pathlib import Path


# 忽略 SSL 证书验证（防止部分网站报错）
ssl._create_default_https_context = ssl._create_unverified_context

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_html(url: str, timeout: int = 15) -> str:
    """获取网页 HTML"""
    req = request.Request(url, headers=HEADERS)
    with request.urlopen(req, timeout=timeout) as resp:
        # 自动检测编码
        data = resp.read()
        charset = resp.headers.get_content_charset()
        if not charset:
            # 从 meta 标签猜测
            m = re.search(rb'charset=["\']?([^"\'>]+)', data)
            charset = m.group(1).decode() if m else "utf-8"
        return data.decode(charset, errors="ignore")


def extract_images(html: str, base_url: str) -> list:
    """提取图片 URL（支持 jpg/png/gif/webp）"""
    # 匹配 src / data-original / data-src 中的图片地址
    pattern = re.compile(
        r'(?:src|data-original|data-src)\s*=\s*["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']',
        re.IGNORECASE,
    )
    found = pattern.findall(html)
    
    # 去重并补全相对路径
    seen = set()
    result = []
    for u in found:
        full = parse.urljoin(base_url, u)
        if full not in seen:
            seen.add(full)
            result.append(full)
    return result


def download_file(url: str, save_path: Path, timeout: int = 30) -> bool:
    """下载单个文件"""
    try:
        req = request.Request(url, headers=HEADERS)
        with request.urlopen(req, timeout=timeout) as resp:
            with open(save_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  ✗ 失败: {url[:60]}... | {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("=" * 50)
        print("  纯标准库图片批量下载器")
        print("=" * 50)
        print("用法:")
        print(f"  python {sys.argv[0]} <网页URL>")
        print("\n示例:")
        print(f'  python {sys.argv[0]} https://www.example.com')
        sys.exit(1)

    target_url = sys.argv[1]
    domain = parse.urlparse(target_url).netloc or "images"
    save_dir = Path(__file__).parent / f"downloaded_{domain}"
    save_dir.mkdir(exist_ok=True)

    print(f"🌐 正在抓取: {target_url}")
    try:
        html = fetch_html(target_url)
    except Exception as e:
        print(f"无法获取网页: {e}")
        sys.exit(1)

    print("🔍 解析图片链接...")
    img_urls = extract_images(html, target_url)
    print(f"📷 发现 {len(img_urls)} 张图片，开始下载...\n")

    success = 0
    for i, img_url in enumerate(img_urls, 1):
        # 生成本地文件名
        parsed = parse.urlparse(img_url)
        filename = os.path.basename(parsed.path)
        if not filename or "." not in filename:
            filename = f"img_{i:03d}.jpg"
        
        # 防止文件名冲突
        filepath = save_dir / filename
        counter = 1
        while filepath.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            filepath = save_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        print(f"[{i}/{len(img_urls)}] {img_url[:70]}...")
        if download_file(img_url, filepath):
            success += 1

    print(f"\n✅ 完成！成功下载 {success}/{len(img_urls)} 张")
    print(f"📂 保存位置: {save_dir.resolve()}")


if __name__ == "__main__":
    main()
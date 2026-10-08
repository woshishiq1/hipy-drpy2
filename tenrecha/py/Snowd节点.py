# HW - 一键获取节点并上传到粘贴板

import requests
import base64
import urllib.parse
import sys
import subprocess
import os


def fetch_and_process():
    """获取并处理节点数据，返回SS链接列表"""
    try:
        response = requests.get("https://snowd.com/api/locations.php", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success') != 1 or 'data' not in data:
            return []
        
        results = []
        for loc in data['data']:
            if not isinstance(loc, dict):
                continue
            
            accs = loc.get('accs')
            country = loc.get('country')
            if not accs or not country:
                continue
            
            if '@' not in accs:
                continue
            prefix, suffix = accs.split('@', 1)
            
            try:
                decoded_prefix = base64.b64decode(prefix).decode('utf-8')
            except (base64.binascii.Error, UnicodeDecodeError):
                continue
            
            combined = f"{decoded_prefix}@{suffix}"
            encoded = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
            
            results.append(f"ss://{encoded}#{urllib.parse.quote(country)}")
        
        return results
        
    except requests.RequestException as e:
        print(f"网络请求失败: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        return []


def upload_to_pastebin(content):
    """将内容上传到 shz.6670088.xyz，返回分享链接"""
    url = "https://shz.6670088.xyz/"
    files = {
        'c': ('nodes.txt', content, 'text/plain')
    }
    data = {
        'e': '1d',  # 1天后过期
    }
    try:
        response = requests.post(url, files=files, data=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        paste_url = result.get('url')
        if not paste_url:
            print("错误：API返回数据缺少'url'字段", file=sys.stderr)
            sys.exit(1)
        return paste_url
    except requests.exceptions.RequestException as e:
        print(f"上传失败: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"解析响应失败: {e}", file=sys.stderr)
        sys.exit(1)


def copy_to_clipboard(text):
    """复制文本到剪贴板"""
    try:
        if sys.platform == "win32":
            import pyperclip
            pyperclip.copy(text)
        elif sys.platform == "darwin":
            subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE).communicate(text.encode('utf-8'))
        else:
            try:
                subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE).communicate(text.encode('utf-8'))
            except FileNotFoundError:
                subprocess.Popen(['xsel', '-i', '--clipboard'], stdin=subprocess.PIPE).communicate(text.encode('utf-8'))
        print("✓ 链接已复制到剪贴板")
    except Exception as e:
        print(f"注意: 自动复制失败 ({e})，请手动复制", file=sys.stderr)


def main():
    print("正在获取节点列表...")
    nodes = fetch_and_process()
    
    if not nodes:
        print("错误：未获取到任何节点数据", file=sys.stderr)
        sys.exit(1)
    
    content = "\n".join(nodes)
    print(f"获取到 {len(nodes)} 个节点，正在上传...")
    
    link = upload_to_pastebin(content)
    print(f"分享链接: {link}")
    copy_to_clipboard(link)


if __name__ == "__main__":
    main()

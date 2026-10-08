#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZakaTV 纯福利本地包 · 一键起服务
================================
只用 Python 标准库，不装任何东西。双击 / 命令行跑一下就行。

跑起来后，壳里填它打印出来的那条地址（配置地址），例如：
    http://192.168.1.20:9978/ZakaTV.json
包内 jar / py 走的是相对路径，服务一起来就自动生效。
"""
import os
import json
import socket
import sys
import functools
import http.server
import socketserver

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9978


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.json': 'application/json; charset=utf-8',
        '.jar': 'application/java-archive',
        '.py': 'text/plain; charset=utf-8',
        '.m3u': 'audio/x-mpegurl',
        '.m3u8': 'application/vnd.apple.mpegurl',
        '': 'application/octet-stream',
    }

    def end_headers(self):
        # 壳 / 网页版跨域取配置与资源
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def main():
    os.chdir(ROOT)
    handler = functools.partial(Handler, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.ThreadingTCPServer(('0.0.0.0', PORT), handler)
    except OSError as e:
        print(f"\n  端口 {PORT} 被占了（{e}）")
        print(f"  换一个：python3 启动本地包.py 9979\n")
        return 1

    ip = lan_ip()
    print()
    print("  ================================================")
    print("   ZakaTV 纯福利本地包 · 服务已起来")
    print("  ================================================")
    print(f"   本机：    http://127.0.0.1:{PORT}/ZakaTV.json")
    print(f"   局域网：  http://{ip}:{PORT}/ZakaTV.json")
    print()
    print("  壳里的「配置地址」填上面那条（盒子跟这台机器同一个网就用局域网那条）")
    print()
    def _n(rel):
        """站数直接数配置里的 sites，别写死 —— 加站以后这里跟着变。"""
        try:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
                return len(json.load(f).get('sites') or [])
        except Exception:
            return '?'

    print(f"   主配置    http://{ip}:{PORT}/ZakaTV.json        （{_n('ZakaTV.json')} 站）")
    print(f"   测试线    http://{ip}:{PORT}/ztv2.json          （{_n('ztv2.json')} 站）")
    print(f"   PY 插件   http://{ip}:{PORT}/py配置/ZakaTV-py插件.json   （{_n('py配置/ZakaTV-py插件.json')} 个）")
    print()
    print("  Ctrl+C 停")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  停了。")
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

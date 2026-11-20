# -*- coding: utf-8 -*-
"""局域网课表服务: 把 kebiao.ics 以 HTTP 提供给 iPhone 日历订阅
用法:  python serve.py [端口]
iPhone: 设置 -> 日历 -> 添加已订阅的日历 -> http://<电脑IP>:8090/kebiao.ics
配合 Tailscale/ngrok 可在外网访问。
"""
import http.server
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print("课表服务: http://0.0.0.0:%d/kebiao.ics" % PORT)
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
import http.server
import socket
import urllib.request
import urllib.error
import datetime
import os
import config
from utils import parse_subdomain

CLR_TIME = "\033[90m"
CLR_GET = "\033[92m"
CLR_POST = "\033[93m"
CLR_ERR = "\033[91m"
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[96m"

def log_event(method: str, host: str, path: str, status_code: int, extra: str = ""):
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    method_color = CLR_POST if method in ["POST", "PUT", "DELETE"] else CLR_GET
    status_color = CLR_ERR if status_code >= 400 else CLR_GET
    
    print(
        f"{CLR_TIME}[{time_str}]{CLR_RESET} "
        f"{method_color}{method:<6}{CLR_RESET} "
        f"Host: {CLR_CYAN}{host:<30}{CLR_RESET} "
        f"Path: {path} -> "
        f"Status: {status_color}{status_code}{CLR_RESET} "
        f"{extra}"
    )

def get_html_content():
    """Читает указанный в конфиге файл"""
    if os.path.exists(config.HTML_TOOL_PATH):
        with open(config.HTML_TOOL_PATH, "r", encoding="utf-8") as f:
            return f.read(), 200
    else:
        return f"<h1>404 Not Found</h1><p>File '{config.HTML_TOOL_PATH}' not found on server.</p>", 404


class YggProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def handle_proxy(self):
        host_header = self.headers.get('Host', '')
        target_ip, target_port, display_host = parse_subdomain(host_header)

        # Перехватываем управление для локального HTML
        if not target_ip:
            if config.HTML_TOOL_ENABLED:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                
                response_html, status = get_html_content()
                self.wfile.write(response_html.encode('utf-8'))
                log_event(self.command, host_header, self.path, status, f"(Local HTML: {config.HTML_TOOL_PATH})")
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h1>404 Not Found</h1>".encode('utf-8'))
                log_event(self.command, host_header, self.path, 404, "(HTML Tool Disabled)")
            return

        # Логика проксирования
        if ":" in target_ip:
            target_url = f"http://[{target_ip}]:{target_port}{self.path}"
        else:
            target_url = f"http://{target_ip}:{target_port}{self.path}"

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers = {key: value for key, value in self.headers.items()}
        req_headers['Host'] = display_host
        if 'Content-Length' in req_headers and not body:
            del req_headers['Content-Length']

        req = urllib.request.Request(url=target_url, data=body, headers=req_headers, method=self.command)

        try:
            # Используем типизированный таймаут (int) из конфига
            with urllib.request.urlopen(req, timeout=config.TIMEOUT_SECONDS) as res:
                self.send_response(res.status)
                for key, value in res.getheaders():
                    if key.lower() != 'transfer-encoding':
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(res.read())
                log_event(self.command, host_header, self.path, res.status, f"-> Ygg: {display_host}")

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, value in e.headers.items():
                if key.lower() != 'transfer-encoding':
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(e.read())
            log_event(self.command, host_header, self.path, e.code, f"{CLR_ERR}-> HTTP Error from node{CLR_RESET}")

        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            err_msg = f"<h1>502 Bad Gateway</h1><p>Node unreachable</p>"
            self.wfile.write(err_msg.encode('utf-8'))
            log_event(self.command, host_header, self.path, 502, f"{CLR_ERR}-> Node offline / Connection Reset{CLR_RESET}")

    def do_GET(self): self.handle_proxy()
    def do_POST(self): self.handle_proxy()
    def do_PUT(self): self.handle_proxy()
    def do_DELETE(self): self.handle_proxy()
    def do_OPTIONS(self): self.handle_proxy()
    def do_HEAD(self): self.handle_proxy()
    def do_PATCH(self): self.handle_proxy()
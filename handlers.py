import http.server
import socket
import urllib.request
import urllib.error
import datetime
import os
import ssl
import config
from utils import parse_subdomain, is_valid_ygg_ip

CLR_TIME = "\033[90m"
CLR_GET = "\033[92m"
CLR_POST = "\033[93m"
CLR_ERR = "\033[91m"
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[96m"

# Отключаем валидацию SSL для нод
ssl_context = ssl._create_unverified_context()

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
    if os.path.exists(config.HTML_TOOL_PATH):
        with open(config.HTML_TOOL_PATH, "r", encoding="utf-8") as f:
            return f.read(), 200
    else:
        return f"<h1>404 Not Found</h1><p>File '{config.HTML_TOOL_PATH}' not found.</p>", 404


# --- КРИТИЧЕСКАЯ ЗАЩИТА: КАСТОМНЫЙ БЕЗОПАСНЫЙ КЛИЕНТ ---
class SafeYggDirector(urllib.request.HTTPHandler, urllib.request.HTTPSHandler):
    """
    Кастомный обработчик для urllib, который перехватывает запросы,
    резолвит домены и проверяет, что финальный IP принадлежит Yggdrasil.
    """
    def __init__(self, context=None):
        urllib.request.HTTPHandler.__init__(self)
        urllib.request.HTTPSHandler.__init__(self, context=context)

    def do_open(self, http_class, req, **http_conn_args):
        host = req.host
        if not host:
            raise urllib.error.URLError("No host intended")

        # Если в хосте есть ']', значит это IPv6 (например, "[202:68d0:...:3148]:80")
        if ']' in host:
            # Отсекаем порт после скобки и убираем сами квадратные скобки
            clean_host = host.split(']')[0].strip("[]")
        else:
            # Для обычных доменов (например, i113d.ikote.ru:80) делим по первому двоеточию
            clean_host = host.split(':')[0]

        try:
            # Принудительно резолвим имя в IPv6 адреса
            infos = socket.getaddrinfo(clean_host, None, socket.AF_INET6)
            resolved_ips = [info[4][0] for info in infos]
        except Exception as e:
            raise urllib.error.URLError(f"DNS Resolution failed for {clean_host}: {e}")

        # Проверяем абсолютно ВСЕ IP, в которые разрезолвился домен
        for ip in resolved_ips:
            if not is_valid_ygg_ip(ip):
                raise PermissionError(f"Block: Destination {ip} is outside Yggdrasil subnet!")

        return super().do_open(http_class, req, **http_conn_args)
    
    
safe_opener = urllib.request.build_opener(SafeYggDirector(context=ssl_context))
urllib.request.install_opener(safe_opener)
# --------------------------------------------------------


def make_nginx_error_html(status_code: int, status_text: str, error_details: str, provider: str) -> str:
    """Генерирует компактную и легко читаемую страницу ошибки"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{status_code} {status_text}</title>
        <style>
            body {{
                background-color: #fafafa;
                color: #111;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 85vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 550px;
                width: 100%;
                text-align: left;
            }}
            .error-header {{
                display: flex;
                align-items: center;
                margin-bottom: 16px;
            }}
            h1 {{
                font-size: 28px;
                font-weight: 600;
                margin: 0 16px 0 0;
                padding-right: 16px;
                border-right: 2px solid #ddd;
                line-height: 1;
            }}
            .status-title {{
                font-size: 20px;
                font-weight: 500;
                color: #333;
                margin: 0;
            }}
            .details {{
                font-size: 15px;
                line-height: 1.6;
                color: #555;
                margin: 0 0 24px 0;
            }}
            hr {{
                border: 0;
                border-top: 1px solid #e5e5e5;
                margin: 0 0 12px 0;
            }}
            .footer {{
                font-size: 12px;
                color: #888;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-header">
                <h1>{status_code}</h1>
                <p class="status-title">{status_text}</p>
            </div>
            <p class="details">{error_details}</p>
            <hr>
            <div class="footer">
                <a href="https://github.com/kotecat/ygg-http-proxy" target="_blank" style="color: #888; text-decoration: none;">ygg-http-proxy</a> ({provider})
            </div>
        </div>
    </body>
    </html>
    """


class YggProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def handle_proxy(self):
        host_header = self.headers.get('Host', '')
        target_ip, target_port, display_host, is_secure = parse_subdomain(host_header)

        if not target_ip:
            if config.HTML_TOOL_ENABLED:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                response_html, status = get_html_content()
                self.wfile.write(response_html.encode('utf-8'))
                log_event(self.command, host_header, self.path, status, f"(Local HTML)")
            else:
                self.send_response(404)
                self.end_headers()
                log_event(self.command, host_header, self.path, 404, "(Disabled)")
            return

        scheme = "https" if is_secure else "http"
        
        if ":" in target_ip:
            target_url = f"{scheme}://[{target_ip}]:{target_port}{self.path}"
        else:
            target_url = f"{scheme}://{target_ip}:{target_port}{self.path}"

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers = {key: value for key, value in self.headers.items()}
        req_headers['Host'] = display_host
        if 'Content-Length' in req_headers and not body:
            del req_headers['Content-Length']

        req = urllib.request.Request(url=target_url, data=body, headers=req_headers, method=self.command)

        try:
            with urllib.request.urlopen(req, timeout=config.TIMEOUT_SECONDS) as res:
                self.send_response(res.status)
                for key, value in res.getheaders():
                    if key.lower() != 'transfer-encoding':
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(res.read())
                log_event(self.command, host_header, self.path, res.status, f"-> Ygg ({scheme}): {display_host}")

        except urllib.error.HTTPError as e:
            # --- ОШИБКА ОТ САМОГО САЙТА (404, 5xx, 403 и т.д.) ---
            if e.code >= 500:
                # Глушим все серверные ошибки (5xx), маскируя под 400 Bad Request
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                
                details = f"Remote Yggdrasil node is online, but its web server returned internal error (HTTP {e.code})."
                html = make_nginx_error_html(400, "Bad Request", details, "Remote Host")
                self.wfile.write(html.encode('utf-8'))
                log_event(self.command, host_header, self.path, 400, f"{CLR_ERR}-> Overrode Remote 5xx ({e.code}) to 400{CLR_RESET}")
            else:
                # 404, 403 и прочие клиентские ошибки отдаем как есть
                try:
                    remote_err_page = e.read()
                    self.send_response(e.code)
                    for key, value in e.headers.items():
                        if key.lower() != 'transfer-encoding':
                            self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(remote_err_page)
                    log_event(self.command, host_header, self.path, e.code, f"-> Remote Node HTTP Error (Proxied)")
                except Exception:
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    html = make_nginx_error_html(400, "Bad Request", f"Remote host returned HTTP {e.code}", "Remote Host")
                    self.wfile.write(html.encode('utf-8'))

        except (urllib.error.URLError, PermissionError) as e:
            # --- ОШИБКА НАШЕЙ ПРОКСИ (Сайт оффлайн, упал DNS, блок чужой подсети) ---
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            if "outside Yggdrasil" in reason:
                details = "Access denied: Target IP address is outside the allowed Yggdrasil subnet."
            elif "Name or service not known" in reason:
                details = "DNS Resolution failed: The requested Yggdrasil domain does not exist."
            else:
                details = f"Proxy connection failed: {reason}"
                
            html = make_nginx_error_html(400, "Bad Request", details, "Proxy Server")
            self.wfile.write(html.encode('utf-8'))
            log_event(self.command, host_header, self.path, 400, f"{CLR_ERR}-> Proxy Handled Error: {reason}{CLR_RESET}")

        except Exception as e:
            # --- КРИТИЧЕСКИЙ СБОЙ ВНУТРИ КОДА ПРОКСИ ---
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            details = f"Internal proxy exception: {type(e).__name__}"
            html = make_nginx_error_html(400, "Bad Request", details, "Proxy Server Core")
            self.wfile.write(html.encode('utf-8'))
            log_event(self.command, host_header, self.path, 400, f"{CLR_ERR}-> Internal Exception: {e}{CLR_RESET}")

    def do_GET(self): self.handle_proxy()
    def do_POST(self): self.handle_proxy()
    def do_PUT(self): self.handle_proxy()
    def do_DELETE(self): self.handle_proxy()
    def do_OPTIONS(self): self.handle_proxy()
    def do_HEAD(self): self.handle_proxy()
    def do_PATCH(self): self.handle_proxy()
    
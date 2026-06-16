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
        # Инициализируем оба родительских класса для http и https
        urllib.request.HTTPHandler.__init__(self)
        urllib.request.HTTPSHandler.__init__(self, context=context)

    def do_open(self, http_class, req, **http_conn_args):
        host = req.host
        if not host:
            raise urllib.error.URLError("No host intended")

        # Отрезаем порт от хоста для резолва, если он есть
        clean_host = host.split(':')[0].strip("[]")

        try:
            # Принудительно резолвим имя в IPv6 адреса
            infos = socket.getaddrinfo(clean_host, None, socket.AF_INET6)
            resolved_ips = [info[4][0] for info in infos]
        except Exception as e:
            raise urllib.error.URLError(f"DNS Resolution failed for {clean_host}: {e}")

        # Проверяем абсолютно ВСЕ IP, в которые разрезолвился домен
        for ip in resolved_ips:
            if not is_valid_ygg_ip(ip):
                # Если хоть один IP ведет наружу сети Yggdrasil — рубим запрос!
                raise PermissionError(f"Block: Destination {ip} is outside Yggdrasil subnet!")

        # Если все IP валидны, передаем запрос стандартному механизму urllib
        return super().do_open(http_class, req, **http_conn_args)


# Создаем безопасныйopener и регистрируем его как глобальный для urllib
safe_opener = urllib.request.build_opener(SafeYggDirector(context=ssl_context))
urllib.request.install_opener(safe_opener)
# --------------------------------------------------------


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
            # Запрос пойдет через наш safe_opener автоматически
            with urllib.request.urlopen(req, timeout=config.TIMEOUT_SECONDS) as res:
                self.send_response(res.status)
                for key, value in res.getheaders():
                    if key.lower() != 'transfer-encoding':
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(res.read())
                log_event(self.command, host_header, self.path, res.status, f"-> Ygg ({scheme}): {display_host}")

        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            # Ловим ошибки сети и блокировки
            status_code = getattr(e, 'code', 400)
            self.send_response(status_code)
            self.end_headers()
            
            err_msg = f"<h1>{status_code} Gateway Error</h1><p>{str(e)}</p>"
            self.wfile.write(err_msg.encode('utf-8'))
            log_event(self.command, host_header, self.path, status_code, f"{CLR_ERR}-> Error: {e}{CLR_RESET}")

        except Exception as e:
            self.send_response(400)
            self.end_headers()
            log_event(self.command, host_header, self.path, 400, f"{CLR_ERR}-> {type(e).__name__}: {e}{CLR_RESET}")

    def do_GET(self): self.handle_proxy()
    def do_POST(self): self.handle_proxy()
    def do_PUT(self): self.handle_proxy()
    def do_DELETE(self): self.handle_proxy()
    def do_OPTIONS(self): self.handle_proxy()
    def do_HEAD(self): self.handle_proxy()
    def do_PATCH(self): self.handle_proxy()

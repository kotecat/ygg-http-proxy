import http.server
import socket
import config
import handlers

class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    address_family = socket.AF_INET6

if __name__ == '__main__':
    # Сервер заводится строго на параметрах из config.py
    server = ThreadedHTTPServer((config.PROXY_HOST, config.PROXY_PORT), handlers.YggProxyHandler)
    print(f"\033[92m[SUCCESS]\033[0m Шлюз запущен на [{config.PROXY_HOST}]:{config.PROXY_PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[93m[INFO]\033[0m Сервер остановлен.")
        server.server_close()

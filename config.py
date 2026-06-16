import os

def load_env():
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
                    except ValueError:
                        continue

load_env()

# Основные настройки сервера
PROXY_HOST = os.getenv("PROXY_HOST", "::")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8384"))
DOMAIN_SUFFIX = os.getenv("DOMAIN_SUFFIX", ".ikote.ru")
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "15"))

# Настройки локального HTML-инструмента
HTML_TOOL_ENABLED = os.getenv("HTML_TOOL_ENABLED", "False").lower() == "true"
HTML_TOOL_PATH = os.getenv("HTML_TOOL_PATH", "index.html")
HTML_TOOL_SUBDOMAIN = os.getenv("HTML_TOOL_SUBDOMAIN", "ygg")

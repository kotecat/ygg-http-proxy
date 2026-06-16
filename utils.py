import config

def is_valid_ygg_ip(ip: str) -> bool:
    """
    Проверяет, принадлежит ли IPv6 адрес диапазону Yggdrasil (200::/7).
    """
    if not ip or ":" not in ip:
        return False
    first_block = ip.split(":")[0].lower()
    try:
        val = int(first_block, 16)
        return 512 <= val <= 767
    except ValueError:
        return False

def parse_subdomain(host_header: str) -> tuple:
    """
    Парсит заголовок Host. Гарантированно отличает IPv6 от текстовых доменов.
    """
    if ':' in host_header:
        host_header = host_header.split(':')[0]
        
    subdomain = host_header.replace(config.DOMAIN_SUFFIX, "")

    if not subdomain or host_header == config.DOMAIN_SUFFIX.strip('.') or (config.HTML_TOOL_ENABLED and subdomain == config.HTML_TOOL_SUBDOMAIN):
        return None, None, None, False

    target_port = None
    is_secure = False

    # 1. Вытаскиваем порт через префикс "-p"
    if "-p" in subdomain:
        try:
            parts = subdomain.split("-p")
            target_port = int(parts[1])
            subdomain = parts[0]
        except (ValueError, IndexError):
            pass

    # 2. Проверяем маркеры безопасности
    if subdomain.endswith("-secure"):
        is_secure = True
        subdomain = subdomain[:-7]
    elif subdomain.endswith("-s"):
        is_secure = True
        subdomain = subdomain[:-2]

    if target_port is None:
        target_port = 443 if is_secure else 80

    raw_node = subdomain

    # 3. ОПРЕДЕЛЯЕМ: IPv6 это или текстовый домен
    # Считаем количество дефисов. В полном IPv6 их должно быть ровно 7 (8 групп)
    dash_count = raw_node.count("-")
    
    # Проверяем, что все символы — это шестнадцатеричные цифры или дефисы (характерно для IPv6)
    is_hex_with_dashes = all(c.isalnum() or c == '-' for c in raw_node) and not any(c.isalpha() and c.lower() > 'f' for c in raw_node)

    if dash_count == 7 and is_hex_with_dashes:
        # Это точно попытка передать IPv6 адрес
        target_ip = raw_node.replace("-", ":")
        
        # Строгая проверка на подсеть Yggdrasil
        if not is_valid_ygg_ip(target_ip):
            return None, None, None, False
            
        display_host = f"[{target_ip}]:{target_port}"
    else:
        # Это текстовый домен
        if raw_node.endswith("-ygg"):
            raw_node = raw_node[:-4]

        protected_node = raw_node.replace("--", "__DOUBLE_DASH__")
        dotted_node = protected_node.replace("-", ".")
        final_node = dotted_node.replace("__DOUBLE_DASH__", "-")

        target_ip = f"{final_node}.ygg"
        display_host = f"{target_ip}:{target_port}"

    return target_ip, target_port, display_host, is_secure


if __name__ == "__main__":
    # Тестируем валидацию подсети
    test_hosts = [
        "200-bebe-a335-e048-85fe-5f9a-ea30-bebe.ikote.ru", # Валидный Yggdrasil IPv6
        "2a00-1450-4010-c0d-0-0-0-65.ikote.ru",             # Злоумышленник: IPv6 Гугла (должен заблочить!)
        "0-0-0-0-0-0-0-1.ikote.ru",                         # Злоумышленник: Локалхост ::1 (должен заблочить!)
        "sharkord-untitled-ygg.ikote.ru"                    # Текстовое имя (всегда ок)
    ]
    
    print("--- ТЕСТ ПАРСЕРА С ЗАЩИТОЙ ПОДСЕТИ ---")
    for host in test_hosts:
        ip, port, disp, sec = parse_subdomain(host)
        status = "\033[92mРАЗРЕШЕНО\033[0m" if ip else "\033[91mЗАБЛОКИРОВАНО\033[0m"
        print(f"Host: {host}\n  -> Статус: {status}\n  -> IP:     {ip}")
        print("-" * 30)
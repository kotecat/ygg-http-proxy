import config

def parse_subdomain(host_header: str) -> tuple[str, int, str]:
    """
    Парсит заголовок Host и возвращает (target_ip, target_port, display_host)
    """
    if ':' in host_header:
        host_header = host_header.split(':')[0]
        
    subdomain = host_header.replace(config.DOMAIN_SUFFIX, "")

    if not subdomain or host_header == config.DOMAIN_SUFFIX.strip('.') or (config.HTML_TOOL_ENABLED and subdomain == config.HTML_TOOL_SUBDOMAIN):
        return None, None, None

    target_port = 80

    if "-p" in subdomain:
        try:
            parts = subdomain.split("-p")
            target_port = int(parts[1])
            raw_node = parts[0]
        except (ValueError, IndexError):
            raw_node = subdomain
    else:
        raw_node = subdomain

    # Восстанавливаем IPv6 или формируем .ygg домен
    if raw_node.startswith("200-") and "-" in raw_node:
        target_ip = raw_node.replace("-", ":")
        display_host = f"[{target_ip}]:{target_port}"
    else:
        # 1. Отрезаем суффикс "-ygg", если он есть
        if raw_node.endswith("-ygg"):
            raw_node = raw_node[:-4]

        # 2. Временный маркер для двойных дефисов, чтобы их не заговняло при замене
        # (Используем редкую строку, которая точно не встретится в домене)
        protected_node = raw_node.replace("--", "__DOUBLE_DASH__")

        # 3. Меняем все одиночные дефисы на точки
        dotted_node = protected_node.replace("-", ".")

        # 4. Возвращаем двойным дефисам их законный вид (но уже как одиночный дефис)
        final_node = dotted_node.replace("__DOUBLE_DASH__", "-")

        # 5. Дописываем зону .ygg
        target_ip = f"{final_node}.ygg"
        display_host = f"{target_ip}:{target_port}"

    return target_ip, target_port, display_host


if __name__ == "__main__":
    # Быстрый ручной тест парсера
    test_hosts = [
        "sharkord-untitled-ygg",
        "kote-ygg.ikote.ru",
        "kote-ygg-p8080.ikote.ru",
        "200-bebe-a335-e048-85fe-5f9a-ea30-bebe.ikote.ru",
        "200-bebe-a335-e048-85fe-5f9a-ea30-bebe-p3000.ikote.ru",
        "ygg.ikote.ru"
    ]

    print("--- ТЕСТ ПАРСЕРА ПОДДОМЕНОВ ---")
    for host in test_hosts:
        ip, port, display = parse_subdomain(host)
        print(f"Host: {host}")
        print(f"  -> IP/Node: {ip}")
        print(f"  -> Port:    {port}")
        print(f"  -> Display: {display}")
        print("-" * 30)
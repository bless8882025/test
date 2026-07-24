#!/usr/bin/env python3
"""
bench.py - Консольная программа для тестирования доступности HTTP-серверов

Реализует требования тестового задания для стажера по Автотестированию (Python).
"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import requests


def parse_arguments():
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Программа для тестирования доступности HTTP-серверов",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-H", "--hosts",
        help="Хосты для тестирования (через запятую без пробелов), например: https://ya.ru,https://google.com"
    )
    group.add_argument(
        "-f", "--file",
        type=Path,
        help="Путь к файлу со списком хостов (по одному на строку)"
    )
    
    parser.add_argument(
        "-C", "--count",
        type=int,
        default=1,
        help="Количество запросов на каждый хост"
    )
    
    parser.add_argument(
        "-O", "--output",
        type=Path,
        help="Путь к файлу для сохранения результата (если не указан — вывод в консоль)"
    )
    
    args = parser.parse_args()
    
    # Валидация count
    if args.count < 1:
        parser.error("Параметр --count должен быть положительным целым числом")
    
    return args


def validate_hosts(hosts: List[str]) -> List[str]:
    """Валидация списка хостов."""
    url_pattern = re.compile(
        r'^https?://'  # http:// или https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # домен
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # порт
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    valid_hosts = []
    for host in hosts:
        host = host.strip()
        if not host:
            continue
        if not url_pattern.match(host):
            print(f"Предупреждение: '{host}' не соответствует формату https://example.com. Пропускаем.", file=sys.stderr)
            continue
        valid_hosts.append(host)
    
    if not valid_hosts:
        print("Ошибка: Не найдено валидных хостов.", file=sys.stderr)
        sys.exit(1)
    
    return valid_hosts


def get_hosts_from_args(args) -> List[str]:
    """Получение списка хостов из аргументов или файла."""
    if args.hosts:
        hosts = [h.strip() for h in args.hosts.split(",")]
    else:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                hosts = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Ошибка: Файл {args.file} не найден.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Ошибка чтения файла: {e}", file=sys.stderr)
            sys.exit(1)
    
    return validate_hosts(hosts)


def measure_request(host: str) -> Dict[str, Any]:
    """Выполнение одного HTTP-запроса и замер времени."""
    start_time = time.perf_counter()
    try:
        response = requests.get(host, timeout=10)
        elapsed = (time.perf_counter() - start_time) * 1000  # в миллисекундах
        
        if response.status_code >= 400:
            return {
                "status": "failed",
                "time": elapsed,
                "error": f"HTTP {response.status_code}"
            }
        return {
            "status": "success",
            "time": elapsed
        }
        
    except requests.exceptions.Timeout:
        return {"status": "error", "time": None, "error": "Таймаут запроса"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "time": None, "error": "Не удалось подключиться"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "time": None, "error": str(e)}
    except Exception as e:
        return {"status": "error", "time": None, "error": f"Неизвестная ошибка: {e}"}


async def test_host(host: str, count: int) -> Dict[str, Any]:
    """Тестирование одного хоста (с возможностью расширения под asyncio)."""
    times = []
    success = 0
    failed = 0
    errors = 0
    
    for _ in range(count):
        result = measure_request(host)
        if result["time"] is not None:
            times.append(result["time"])
        
        if result["status"] == "success":
            success += 1
        elif result["status"] == "failed":
            failed += 1
        else:
            errors += 1
    
    stats = {
        "Host": host,
        "Success": success,
        "Failed": failed,
        "Errors": errors,
    }
    
    if times:
        stats.update({
            "Min": round(min(times), 2),
            "Max": round(max(times), 2),
            "Avg": round(sum(times) / len(times), 2)
        })
    else:
        stats.update({
            "Min": "-",
            "Max": "-",
            "Avg": "-"
        })
    
    return stats


def print_stats(stats_list: List[Dict], output_file=None):
    """Вывод статистики."""
    lines = []
    separator = "=" * 80
    
    lines.append(separator)
    lines.append("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    lines.append(separator)
    
    for stats in stats_list:
        lines.append(f"Host: {stats['Host']}")
        lines.append(f"Success: {stats['Success']}")
        lines.append(f"Failed:  {stats['Failed']}")
        lines.append(f"Errors:  {stats['Errors']}")
        lines.append(f"Min:     {stats['Min']} ms")
        lines.append(f"Max:     {stats['Max']} ms")
        lines.append(f"Avg:     {stats['Avg']} ms")
        lines.append("-" * 60)
    
    output_text = "\n".join(lines)
    
    if output_file:
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_text + "\n")
            print(f"Результаты сохранены в файл: {output_file}")
        except Exception as e:
            print(f"Ошибка записи в файл: {e}", file=sys.stderr)
            print(output_text)
    else:
        print(output_text)


async def main():
    args = parse_arguments()
    hosts = get_hosts_from_args(args)
    
    print(f"Запуск тестирования {len(hosts)} хост(ов) с {args.count} запросами каждый...")
    
    stats_list = []
    for host in hosts:
        print(f"Тестирование {host}...")
        stats = await test_host(host, args.count)
        stats_list.append(stats)
    
    print_stats(stats_list, args.output)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nТестирование прервано пользователем.")
    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        sys.exit(1)

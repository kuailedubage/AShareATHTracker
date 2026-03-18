#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 new_high_stocks.json 读取数据，注入 output/report.html 模板，生成 index.html
"""

import json
import re
import os
from datetime import date

TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), 'output', 'report.html')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'new_high_stocks.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'index.html')


def main():
    # Read data
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    if not stocks:
        print("No stocks in data file, generating empty report.")

    # Read template
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Replace DATA array
    #    Match: const DATA=[...]; (the entire array, which may span multiple lines)
    data_json = json.dumps(stocks, ensure_ascii=False, separators=(',', ':'))
    html = re.sub(
        r'const DATA=\[.*?\];',
        f'const DATA={data_json};',
        html,
        count=1,
        flags=re.DOTALL,
    )

    # 2. Update date in title and hero section
    today = date.today().strftime('%Y-%m-%d')
    today_dot = date.today().strftime('%Y.%m.%d')

    # <title>A股历史新高雷达 | 2026-03-18</title>
    html = re.sub(
        r'(<title>A股历史新高雷达 \| )\d{4}-\d{2}-\d{2}(</title>)',
        rf'\g<1>{today}\2',
        html,
    )
    # Hero date line: 2026.03.18 · NEON NOIR EDITION
    html = re.sub(
        r'\d{4}\.\d{2}\.\d{2}( · NEON NOIR EDITION)',
        rf'{today_dot}\1',
        html,
    )

    # Write output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated {OUTPUT_FILE} with {len(stocks)} stocks, date={today}")


if __name__ == '__main__':
    main()

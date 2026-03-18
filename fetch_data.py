#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股历史新高股票筛选器
Step 1: 获取所有A股月K线历史最高价
Step 2: 获取当日实时数据，比较是否创新高
Step 3: 对创新高的股票获取日K线，计算各项指标
"""

import json
import os
import re
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from easyquotation import helpers

# --- Config ---
CACHE_FILE = '/workspace/historical_highs.json'
RESULT_FILE = '/workspace/new_high_stocks.json'
MAX_WORKERS = 30
TIMEOUT = 8

# --- Step 0: Get all A-share stock codes ---
def get_all_codes():
    """Get all A-share codes, categorized by board.
    Uses broad prefix matching to be future-proof for new code ranges.
    """
    codes = helpers.get_stock_codes()
    result = []
    for c in codes:
        if not c.isdigit() or len(c) != 6:
            continue  # Skip index codes (sh000xxx, zzxxxx, etc.)
        if c.startswith('6'):
            # 上交所: 68xxxx=科创板, 其余=主板
            board = '科创板' if c.startswith('68') else '主板'
            result.append(('sh', c, board))
        elif c.startswith(('0', '1')):
            # 深交所主板: 000/001/002/003... 及未来可能的1开头
            result.append(('sz', c, '主板'))
        elif c.startswith('3'):
            # 深交所创业板: 300/301/302...
            result.append(('sz', c, '创业板'))
        elif c.startswith(('4', '8', '9')):
            # 北交所: 腾讯接口不支持大部分北交所股票的K线数据，跳过
            continue
        else:
            print(f"  [WARN] 未识别的股票代码: {c}")
    return result

# --- Step 1: Fetch monthly kline to get historical high ---
def fetch_monthly_kline(prefix, code, retries=2):
    """Fetch monthly kline for a stock.
    Returns dict with both full ATH and ATH excluding current month.
    """
    symbol = f'{prefix}{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},month,,,800,qfq'
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            data = json.loads(r.text)
            stock_data = data.get('data', {}).get(symbol, {})
            klines = stock_data.get('qfqmonth') or stock_data.get('month')
            if not klines or len(klines) < 2:
                return None

            ipo_date = klines[0][0]
            first_open = float(klines[0][1])

            # Scan all bars for full ATH and low
            all_time_high = -999999
            high_date = ''
            all_time_low = 999999
            low_date = ''
            for k in klines:
                try:
                    h = float(k[3])
                    l = float(k[4])
                    if h > all_time_high:
                        all_time_high = h
                        high_date = k[0]
                    if l < all_time_low:
                        all_time_low = l
                        low_date = k[0]
                except (ValueError, IndexError):
                    continue

            # Scan excluding current month (last bar) for pre-month ATH
            ath_excl_current = -999999
            ath_excl_date = ''
            for k in klines[:-1]:
                try:
                    h = float(k[3])
                    if h > ath_excl_current:
                        ath_excl_current = h
                        ath_excl_date = k[0]
                except (ValueError, IndexError):
                    continue

            return {
                'code': code,
                'prefix': prefix,
                'all_time_high': all_time_high,
                'high_date': high_date,
                'ath_excl_current_month': ath_excl_current,
                'ath_excl_current_month_date': ath_excl_date,
                'all_time_low': all_time_low,
                'low_date': low_date,
                'ipo_date': ipo_date,
                'first_open': first_open,
                'month_count': len(klines)
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.3)
    return None

def fetch_all_historical_highs(stock_list):
    """Fetch historical highs for all stocks using monthly klines"""
    # Check cache for incremental mode
    cached = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cached = json.load(f)
        print(f"Loaded {len(cached)} cached entries")

    results = dict(cached)
    to_fetch = [(p, c, b) for p, c, b in stock_list if c not in cached]

    if not to_fetch:
        print("All stocks cached, skipping full fetch")
        return results

    print(f"Fetching monthly klines for {len(to_fetch)} stocks...")
    done = 0
    total = len(to_fetch)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for prefix, code, board in to_fetch:
            f = executor.submit(fetch_monthly_kline, prefix, code)
            futures[f] = (code, board)

        for future in as_completed(futures):
            code, board = futures[future]
            done += 1
            if done % 200 == 0:
                print(f"  Progress: {done}/{total}")
            try:
                res = future.result()
                if res:
                    res['board'] = board
                    results[code] = res
            except Exception:
                pass

    # Save cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"Cached {len(results)} stocks to {CACHE_FILE}")

    return results

# --- Step 2: Get real-time data using easyquotation tencent ---
def get_realtime_data(stock_list):
    """Get real-time quotes for all stocks"""
    import easyquotation
    q = easyquotation.use('tencent')

    codes = [c for _, c, _ in stock_list]
    print(f"Fetching real-time data for {len(codes)} stocks...")
    data = q.real(codes)
    print(f"Got real-time data for {len(data)} stocks")
    return data

# --- Step 3: Fetch daily kline for new-high stocks ---
def fetch_daily_kline(prefix, code, days=60):
    """Fetch daily kline, return list of [date, open, close, high, low, volume, ...]"""
    symbol = f'{prefix}{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq'
    try:
        r = requests.get(url, timeout=TIMEOUT)
        data = json.loads(r.text)
        stock_data = data.get('data', {}).get(symbol, {})
        klines = stock_data.get('qfqday') or stock_data.get('day')
        return klines
    except Exception:
        return None

# --- Step 4: Find new-high stocks and calculate metrics ---
def find_new_high_stocks(historical, realtime, stock_list):
    """Find stocks that hit all-time high today.
    Two-pass approach:
      Pass 1: Use cached ATH for quick filtering (candidates)
      Pass 2: Re-fetch monthly klines for candidates to verify & update cache
    """
    board_map = {c: b for _, c, b in stock_list}
    prefix_map = {c: p for p, c, _ in stock_list}

    # --- Pass 1: Quick filter using cached ATH ---
    candidates = []
    for code, rt in realtime.items():
        if code not in historical:
            continue

        hist = historical[code]
        name = rt.get('name', '')

        # Exclude ST stocks
        if 'ST' in name.upper() or 'st' in name:
            continue

        # Exclude new stocks (IPO < 3 months, less than 3 monthly bars)
        if hist.get('month_count', 0) < 4:
            continue

        today_high = rt.get('high', 0)
        if today_high <= 0:
            continue

        prev_ath = hist.get('all_time_high', 0)

        # Use cached ATH as initial filter
        if today_high >= prev_ath:
            candidates.append((code, rt, hist))

    if not candidates:
        return []

    # --- Pass 2: Re-fetch monthly + daily klines to verify ---
    # Monthly kline (exclude current month) + Daily kline (exclude today) = true ATH before today
    print(f"  Pass 1: {len(candidates)} candidates from cache, verifying with fresh klines...")

    # Load cache for updating
    cached = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cached = json.load(f)

    from datetime import date
    today_str = date.today().strftime('%Y-%m-%d')

    def verify_stock(item):
        code, rt, hist = item
        prefix = prefix_map.get(code, hist.get('prefix', 'sz'))

        # 1) Monthly kline (one request, returns both full ATH and excl-current-month ATH)
        fresh = fetch_monthly_kline(prefix, code)

        # 2) Daily kline for recent 30 days → fill current month gap (exclude today)
        daily_ath = 0
        daily_ath_date = ''
        daily_klines = fetch_daily_kline(prefix, code, days=30)
        if daily_klines:
            for k in daily_klines:
                try:
                    if k[0] >= today_str:
                        continue  # skip today
                    h = float(k[3])
                    if h > daily_ath:
                        daily_ath = h
                        daily_ath_date = k[0]
                except (ValueError, IndexError):
                    continue

        return code, rt, hist, fresh, daily_ath, daily_ath_date

    verified_results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(verify_stock, c) for c in candidates]
        for f in as_completed(futures):
            try:
                code, rt, hist, fresh, daily_ath, daily_ath_date = f.result()
                verified_results[code] = (rt, hist, fresh, daily_ath, daily_ath_date)
            except:
                pass

    new_highs = []
    cache_updated = False
    for code, (rt, hist, fresh, daily_ath, daily_ath_date) in verified_results.items():
        if fresh:
            monthly_ath = fresh['ath_excl_current_month']
            monthly_ath_date = fresh['ath_excl_current_month_date']
            all_time_low = fresh['all_time_low']
            low_date = fresh['low_date']
            ipo_date = fresh['ipo_date']
            first_open = fresh['first_open']
            # Update cache with full data (including current month)
            fresh['board'] = board_map.get(code, hist.get('board', ''))
            cached[code] = fresh
            cache_updated = True
        else:
            monthly_ath = hist.get('all_time_high', 0)
            monthly_ath_date = hist.get('high_date', '')
            all_time_low = hist.get('all_time_low', 0)
            low_date = hist.get('low_date', '')
            ipo_date = hist.get('ipo_date', '')
            first_open = hist.get('first_open', 0)

        # True ATH before today = max(monthly ATH excluding current month, daily ATH excluding today)
        if daily_ath > monthly_ath:
            true_ath = daily_ath
            ath_date = daily_ath_date
        else:
            true_ath = monthly_ath
            ath_date = monthly_ath_date

        today_high = rt.get('high', 0)

        # Verify against true pre-today ATH
        if today_high >= true_ath:
            name = rt.get('name', '')
            new_highs.append({
                'code': code,
                'prefix': prefix_map.get(code, 'sz'),
                'name': name,
                'board': board_map.get(code, ''),
                'today_high': today_high,
                'prev_ath': true_ath,
                'prev_ath_date': ath_date,
                'now_price': rt.get('now', 0),
                'close_yesterday': rt.get('close', 0),
                'open': rt.get('open', 0),
                'low': rt.get('low', 0),
                'volume': rt.get('成交量(手)', 0),
                'turnover': rt.get('turnover', 0),
                'pe': rt.get('PE', 0),
                'pb': rt.get('PB', 0),
                'market_cap': rt.get('总市值', 0),
                'float_cap': rt.get('流通市值', 0),
                'amplitude': rt.get('振幅', 0),
                'all_time_low': all_time_low,
                'low_date': low_date,
                'ipo_date': ipo_date,
                'first_open': first_open,
                'change_pct': rt.get('涨跌(%)', 0),
            })
        else:
            print(f"  [FILTERED] {code} {rt.get('name','')} - cached ATH={hist.get('all_time_high',0):.2f}, "
                  f"fresh ATH={true_ath:.2f}, today_high={today_high:.2f}")

    # Save updated cache
    if cache_updated:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cached, f, ensure_ascii=False)
        print(f"  Cache updated ({len(cached)} stocks)")

    print(f"  Pass 2: {len(new_highs)} verified new-high stocks")
    return new_highs

def calculate_metrics(new_highs):
    """For each new-high stock, fetch daily kline and calculate detailed metrics"""
    print(f"Calculating metrics for {len(new_highs)} new-high stocks...")

    def process_stock(stock):
        klines = fetch_daily_kline(stock['prefix'], stock['code'], days=120)
        if not klines or len(klines) < 5:
            return stock

        # Parse kline data
        closes = []
        highs = []
        dates = []
        volumes = []
        for k in klines:
            try:
                dates.append(k[0])
                closes.append(float(k[2]))  # close
                highs.append(float(k[3]))   # high
                volumes.append(float(k[5]))
            except (ValueError, IndexError):
                continue

        if len(closes) < 5:
            return stock

        # Current price (last close in kline or realtime)
        current_close = closes[-1]
        today_high = stock['today_high']

        # 1. Pullback from high (新高后回落%)
        pullback_pct = round((today_high - current_close) / today_high * 100, 2)
        stock['pullback_pct'] = pullback_pct

        # 2. Consecutive new high days
        consecutive_days = 0
        running_max = 0
        for i in range(len(highs) - 1, -1, -1):
            if i == len(highs) - 1:
                running_max = highs[i]
                consecutive_days = 1
            else:
                if highs[i] >= running_max * 0.998:
                    # This day also set a new high at that point
                    pass
                else:
                    break
                consecutive_days += 1
                running_max = highs[i]

        # Recalculate: count backwards how many days the high kept increasing
        consecutive_days = 1
        for i in range(len(highs) - 2, -1, -1):
            if highs[i + 1] > highs[i]:
                consecutive_days += 1
            else:
                break
        stock['consecutive_new_high_days'] = consecutive_days

        # 3. MA5 deviation
        ma5 = sum(closes[-5:]) / 5
        ma5_deviation = round((current_close - ma5) / ma5 * 100, 2)
        stock['ma5_deviation'] = ma5_deviation
        stock['ma5'] = round(ma5, 2)

        # 4. Next day gain needed to hit new high again
        gap_to_new_high = round((today_high - current_close) / current_close * 100, 2)
        stock['gap_to_new_high'] = gap_to_new_high

        # 5. Next day drop to break MA5
        drop_to_ma5 = round((current_close - ma5) / current_close * 100, 2)
        stock['drop_to_break_ma5'] = drop_to_ma5

        # 6. Gain from all-time low
        atl = stock.get('all_time_low', 0)
        if atl > 0:
            gain_from_low = round((current_close - atl) / atl * 100, 2)
            stock['gain_from_low'] = gain_from_low
        else:
            stock['gain_from_low'] = 0

        # 7. Gain since 2024-09-24 bull market
        # Find the close on or near 2024-09-24
        bull_start_close = None
        for i, d in enumerate(dates):
            if d >= '2024-09-24':
                bull_start_close = closes[i]
                break
        # If not found in 120 days, try to find from the earliest available
        if bull_start_close is None and len(closes) > 0:
            bull_start_close = closes[0]  # Use earliest available
            stock['bull_start_note'] = f'earliest: {dates[0]}'

        if bull_start_close and bull_start_close > 0:
            stock['gain_since_924'] = round((current_close - bull_start_close) / bull_start_close * 100, 2)
            stock['price_at_924'] = bull_start_close
        else:
            stock['gain_since_924'] = 0

        # 8. Real turnover rate (use realtime data)
        # Already have stock['turnover']

        # 9. IPO price approximation (first_open from monthly data)
        stock['ipo_price'] = stock.get('first_open', 0)

        # 10. Recent price trend for scoring
        if len(closes) >= 20:
            ma20 = sum(closes[-20:]) / 20
            stock['ma20'] = round(ma20, 2)
            stock['ma20_deviation'] = round((current_close - ma20) / ma20 * 100, 2)

        if len(closes) >= 10:
            ma10 = sum(closes[-10:]) / 10
            stock['ma10'] = round(ma10, 2)

        # Volume ratio (today vs 5-day avg)
        if len(volumes) >= 6:
            avg_vol_5 = sum(volumes[-6:-1]) / 5
            if avg_vol_5 > 0:
                stock['volume_ratio'] = round(volumes[-1] / avg_vol_5, 2)

        # Strength score (composite)
        score = 0
        score += min(consecutive_days * 5, 30)  # Consecutive days: max 30
        score += min(max(0, -pullback_pct) * 2, 10)  # Less pullback = stronger
        if ma5_deviation > 0:
            score += min(ma5_deviation * 2, 15)  # Above MA5
        if stock.get('ma20_deviation', 0) > 0:
            score += min(stock['ma20_deviation'], 20)  # Above MA20
        score += min(stock.get('volume_ratio', 1) * 5, 15)  # Volume expansion
        if stock.get('gain_since_924', 0) > 50:
            score += 10  # Strong bull market performance
        stock['strength_score'] = round(min(score, 100), 1)

        return stock

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_stock, s) for s in new_highs]
        results = []
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except:
                pass

    return results


def add_extra_metrics(new_highs):
    """Add extra metrics: days since prev ATH, MA breaks, consecutive streaks"""
    from datetime import datetime
    print("Calculating extra metrics (ATH streaks, MA breaks)...")

    def process(stock):
        code = stock['code']
        prefix = stock['prefix']

        # Fetch longer daily kline (250 days) for better streak detection
        klines = fetch_daily_kline(prefix, code, days=250)
        if not klines or len(klines) < 5:
            stock.update({'days_since_prev_ath': -1, 'true_consecutive_ath_days': 0,
                          'longest_daily_higher_high': stock.get('consecutive_new_high_days', 0),
                          'broke_ma5_after_ath': False, 'broke_ma10_after_ath': False, 'broke_ma20_after_ath': False})
            return stock

        dates, closes, highs = [], [], []
        for k in klines:
            try:
                dates.append(k[0])
                closes.append(float(k[2]))
                highs.append(float(k[3]))
            except:
                continue

        n = len(highs)
        if n < 5:
            return stock

        # Fetch monthly kline to get ATH before current month (for accurate running max start)
        symbol = f'{prefix}{code}'
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},month,,,800,qfq'
        prev_ath_from_monthly = 0
        prev_ath_month = ''
        try:
            r = requests.get(url, timeout=TIMEOUT)
            data = json.loads(r.text)
            stock_data = data.get('data', {}).get(symbol, {})
            mklines = stock_data.get('qfqmonth') or stock_data.get('month')
            if mklines and len(mklines) >= 2:
                for mk in mklines[:-1]:  # exclude current month
                    h = float(mk[3])
                    if h > prev_ath_from_monthly:
                        prev_ath_from_monthly = h
                        prev_ath_month = mk[0]
        except:
            pass

        # --- A. True consecutive ATH days ---
        # Track running max from prev monthly ATH (before current month)
        running_max = prev_ath_from_monthly if prev_ath_from_monthly > 0 else 0
        ath_day_indices = []
        for i in range(n):
            if highs[i] > running_max:
                running_max = highs[i]
                ath_day_indices.append(i)

        # Count backwards from today: consecutive ATH days
        true_consec = 0
        if ath_day_indices and ath_day_indices[-1] == n - 1:
            true_consec = 1
            for j in range(len(ath_day_indices) - 2, -1, -1):
                if ath_day_indices[j + 1] - ath_day_indices[j] == 1:
                    true_consec += 1
                else:
                    break
        stock['true_consecutive_ath_days'] = true_consec

        # --- B. Days since previous ATH ---
        if len(ath_day_indices) > true_consec:
            prev_idx = ath_day_indices[len(ath_day_indices) - true_consec - 1]
            prev_date_str = dates[prev_idx]
            try:
                today_dt = datetime.strptime(dates[-1], '%Y-%m-%d')
                prev_dt = datetime.strptime(prev_date_str, '%Y-%m-%d')
                stock['days_since_prev_ath'] = (today_dt - prev_dt).days
                stock['prev_ath_date'] = prev_date_str
            except:
                stock['days_since_prev_ath'] = -1
        elif prev_ath_month:
            try:
                today_dt = datetime.strptime(dates[-1], '%Y-%m-%d')
                prev_dt = datetime.strptime(prev_ath_month, '%Y-%m-%d')
                stock['days_since_prev_ath'] = (today_dt - prev_dt).days
                stock['prev_ath_date'] = prev_ath_month
            except:
                stock['days_since_prev_ath'] = -1
        else:
            stock['days_since_prev_ath'] = -1

        # --- C. Longest consecutive daily higher-high streak ---
        # Each day's high > previous day's high (not necessarily ATH)
        longest = 1
        current = 1
        for i in range(1, n):
            if highs[i] > highs[i - 1]:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        stock['longest_daily_higher_high'] = longest

        # --- D. After previous ATH, did price break below MA5/10/20? ---
        broke_ma5 = False
        broke_ma10 = False
        broke_ma20 = False

        if len(ath_day_indices) > true_consec:
            check_start = ath_day_indices[len(ath_day_indices) - true_consec - 1] + 1
            check_end = ath_day_indices[len(ath_day_indices) - true_consec] if true_consec > 0 else n
            for i in range(check_start, check_end):
                if i >= 4:
                    ma5_i = sum(closes[i - 4:i + 1]) / 5
                    if closes[i] < ma5_i:
                        broke_ma5 = True
                if i >= 9:
                    ma10_i = sum(closes[i - 9:i + 1]) / 10
                    if closes[i] < ma10_i:
                        broke_ma10 = True
                if i >= 19:
                    ma20_i = sum(closes[i - 19:i + 1]) / 20
                    if closes[i] < ma20_i:
                        broke_ma20 = True

        stock['broke_ma5_after_ath'] = broke_ma5
        stock['broke_ma10_after_ath'] = broke_ma10
        stock['broke_ma20_after_ath'] = broke_ma20

        return stock

    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = [executor.submit(process, s) for s in new_highs]
        results = []
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except:
                pass
    return results

# --- Step 5: Get 924 bull market start prices ---
def fetch_924_prices(new_highs):
    """Fetch prices around 2024-09-24 for gain calculation"""
    print("Fetching 924 bull market reference prices...")

    def fetch_long_kline(stock):
        symbol = f"{stock['prefix']}{stock['code']}"
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,2024-09-20,2024-10-10,20,qfq'
        try:
            r = requests.get(url, timeout=TIMEOUT)
            data = json.loads(r.text)
            stock_data = data.get('data', {}).get(symbol, {})
            klines = stock_data.get('qfqday') or stock_data.get('day')
            if klines:
                # Find closest to 2024-09-24
                for k in klines:
                    if k[0] >= '2024-09-24':
                        return stock['code'], float(k[1])  # open on that day
                return stock['code'], float(klines[0][2])  # first available close
        except:
            pass
        return stock['code'], None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_long_kline, s) for s in new_highs]
        prices_924 = {}
        for f in as_completed(futures):
            try:
                code, price = f.result()
                if price:
                    prices_924[code] = price
            except:
                pass

    return prices_924

# --- Step 6: Fetch industry & concept from Eastmoney ---
# Non-meaningful board tags to filter out
BOARD_BLACKLIST = {
    '融资融券', '深股通', '沪股通', '富时罗素', '标准普尔', 'MSCI中国',
    '最近多板', '东方财富热股', '昨日高振幅', '昨日涨停', '昨日连板',
    '昨日触板', '今日热门', 'HS300_', '上证180_', '上证50_', '科创50',
    '沪深300', '中证500', '中证1000', '转债标的', '股权激励',
    '高送转', '次新股', '创业板综', '深成500', '深证100R',
    '预盈预增', '预亏预减', '送转填权', '资产重组', '定增破发',
}
# Substrings to filter out from concept tags
CONCEPT_BLACKLIST_KEYWORDS = ['板块', '指数', '成份', '上证', '深证', '中证',
                               'MSCI', '标普', '富时', '央国企改革', '沪深']

def fetch_stock_concepts(code):
    """Fetch industry & concept tags from Eastmoney for a single stock code."""
    url = (
        'https://datacenter.eastmoney.com/securities/api/data/v1/get'
        '?reportName=RPT_F10_CORETHEME_BOARDTYPE'
        '&columns=SECURITY_CODE,BOARD_NAME,BOARD_TYPE'
        f'&filter=(SECURITY_CODE=%22{code}%22)'
    )
    try:
        r = requests.get(url, timeout=TIMEOUT)
        data = r.json()
        if not data.get('success') or not data.get('result', {}).get('data'):
            return None, None

        industries = []
        concepts = []
        for item in data['result']['data']:
            name = item.get('BOARD_NAME', '')
            btype = item.get('BOARD_TYPE', '')
            if not name:
                continue
            # Skip blacklisted tags
            if name in BOARD_BLACKLIST:
                continue
            # Skip tags that look like index/region boards
            if btype == '板块':
                continue
            if btype == '行业':
                industries.append(name)
            else:
                # Concept tag - additional filtering
                if any(kw in name for kw in CONCEPT_BLACKLIST_KEYWORDS):
                    continue
                concepts.append(name)

        # Take top industry (most specific: last one is usually broadest, first is specific)
        industry = industries[0] if industries else ''
        # Take top 3-5 concept tags
        concept_str = '/'.join(concepts[:5]) if concepts else ''
        return industry, concept_str
    except Exception as e:
        return None, None


def fetch_all_concepts(new_highs):
    """Fetch industry & concept for all new-high stocks from Eastmoney."""
    print(f"Fetching industry/concept from Eastmoney for {len(new_highs)} stocks...")

    def fetch_one(stock):
        industry, concept = fetch_stock_concepts(stock['code'])
        return stock['code'], industry, concept

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_one, s) for s in new_highs]
        results = {}
        for f in as_completed(futures):
            try:
                code, industry, concept = f.result()
                results[code] = (industry, concept)
            except:
                pass

    updated = 0
    for s in new_highs:
        if s['code'] in results:
            ind, con = results[s['code']]
            if ind is not None:
                s['industry'] = ind
                updated += 1
            if con is not None:
                s['concept'] = con

    print(f"  Updated industry/concept for {updated}/{len(new_highs)} stocks")
    return new_highs


# --- Main ---
def main():
    print("=" * 60)
    print("A股历史新高股票筛选器")
    print("=" * 60)

    # Step 0: Get stock list
    stock_list = get_all_codes()
    print(f"Total A-share stocks: {len(stock_list)}")

    # Step 1: Historical highs (monthly kline)
    historical = fetch_all_historical_highs(stock_list)
    print(f"Got historical data for {len(historical)} stocks")

    # Step 2: Real-time data
    realtime = get_realtime_data(stock_list)

    # Step 3: Find new-high stocks
    new_highs = find_new_high_stocks(historical, realtime, stock_list)
    print(f"\nFound {len(new_highs)} stocks hitting all-time highs today")

    if not new_highs:
        print("No stocks found hitting all-time highs today.")
        # Save empty result
        with open(RESULT_FILE, 'w') as f:
            json.dump([], f)
        return

    # Step 4: Get 924 reference prices
    prices_924 = fetch_924_prices(new_highs)
    for s in new_highs:
        if s['code'] in prices_924:
            p924 = prices_924[s['code']]
            s['price_at_924'] = p924
            if p924 > 0:
                s['gain_since_924'] = round((s['now_price'] - p924) / p924 * 100, 2)

    # Step 5: Calculate detailed metrics
    new_highs = calculate_metrics(new_highs)

    # Step 6: Extra metrics (ATH streaks, MA breaks, days since prev ATH)
    new_highs = add_extra_metrics(new_highs)

    # Step 7: Fetch industry & concept from Eastmoney
    new_highs = fetch_all_concepts(new_highs)

    # Sort by strength score
    new_highs.sort(key=lambda x: x.get('strength_score', 0), reverse=True)

    # Print summary
    print(f"\n{'='*80}")
    print(f"今日创历史新高股票: {len(new_highs)} 只")
    print(f"{'='*80}")
    for i, s in enumerate(new_highs[:20]):
        print(f"{i+1:3d}. {s['code']} {s['name']:8s} | 新高:{s['today_high']:8.2f} | "
              f"回落:{s.get('pullback_pct',0):5.2f}% | 连续:{s.get('consecutive_new_high_days',0)}天 | "
              f"强度:{s.get('strength_score',0):5.1f}")

    # Save results
    with open(RESULT_FILE, 'w') as f:
        json.dump(new_highs, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {RESULT_FILE}")

if __name__ == '__main__':
    main()

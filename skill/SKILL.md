---
name: ashare-ath-tracker
description: A股全市场历史新高股票扫描器 - 扫描所有A股，找出创上市以来历史新高的股票，计算强度评分等指标，生成 Neon Noir 风格交互式 HTML 报告。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - pip
    emoji: "📈"
    homepage: https://github.com/kuailedubage/AShareATHTracker
---

# A股历史新高雷达 (A-Share ATH Tracker)

扫描 A 股全市场，找出**当日创上市以来股价历史新高**的股票，并生成 Neon Noir 风格的交互式数据报告。

## 功能概述

1. 获取全部 A 股（主板/创业板/科创板）的月 K 线历史最高价
2. 获取当日实时行情，筛选出今日创历史新高的股票
3. 计算丰富的技术指标和分析维度
4. 生成单文件交互式 HTML 报告（ECharts 可视化）

## 计算指标

每只创新高股票包含以下指标：
- 涨跌幅、新高后回落幅度、连续新高天数
- MA5/MA10/MA20 偏离度
- 继续创新高所需涨幅、跌破 MA5 所需跌幅
- 924 牛市以来涨幅、上市以来最大涨幅
- 实际换手率（基于自由流通股本）
- 强度评分（综合多维指标的 0-100 分数）
- 行业、核心概念、驱动题材
- 近期公告（最近 14 天重要公告）

## 报告包含的图表

1. **KPI 仪表盘** — 新高数量、平均强度、平均回落、平均涨幅
2. **题材概念热力矩阵** — TreeMap，面积=出现次数，颜色=涨跌幅（红涨绿跌）
3. **板块分布饼图** — 主板/创业板/科创板占比
4. **市值规模分布** — 小盘/中盘/中大盘/大盘
5. **TOP15 热门概念** — 概念频率横向柱状图
6. **强势度评分排名** — 横向柱状图
7. **连续新高 × 牛市涨幅** — 气泡散点图
8. **涨幅对比** — 924 以来涨幅 vs 历史最低涨幅
9. **换手率 × 回落幅度** — 散点图
10. **TOP6 强势股雷达图** — 多维雷达
11. **风险收益矩阵** — 跌破 MA5 vs 创新高所需幅度
12. **可排序可搜索数据表格** — 全量字段展示

## 使用方法

### 环境准备

```bash
pip install easyquotation requests pandas
```

### 运行扫描

```bash
# 克隆仓库
git clone https://github.com/kuailedubage/AShareATHTracker.git
cd AShareATHTracker

# 安装依赖
pip install -r requirements.txt

# 运行数据扫描（约需 10-20 分钟，首次需全量拉取月K线）
python fetch_data.py

# 生成 HTML 报告
python generate_report.py
```

运行完成后：
- `new_high_stocks.json` — 结构化数据（可直接用于进一步分析）
- `index.html` — 交互式 HTML 报告（可直接在浏览器打开）

### 在 Agent 中使用

当用户请求查看 A 股历史新高数据或报告时：

1. 克隆仓库并安装依赖：
```bash
git clone https://github.com/kuailedubage/AShareATHTracker.git /tmp/ath-tracker
cd /tmp/ath-tracker
pip install -r requirements.txt
```

2. 运行扫描和报告生成：
```bash
python fetch_data.py
python generate_report.py
```

3. 读取 `new_high_stocks.json` 获取结构化数据，或展示 `index.html` 报告给用户。

### 数据格式

`new_high_stocks.json` 是一个 JSON 数组，每个元素包含：

```json
{
  "code": "688525",
  "name": "佰维存储",
  "board": "科创板",
  "industry": "半导体",
  "concept": "存储芯片/国产替代/AI算力",
  "driving_concept": "存储芯片",
  "today_high": 259.99,
  "now_price": 258.09,
  "change_pct": 9.46,
  "pullback_pct": 0.73,
  "consecutive_new_high_days": 5,
  "ma5_deviation": 12.79,
  "gap_to_new_high": 0.74,
  "drop_to_break_ma5": 11.34,
  "gain_since_924": 244.3,
  "gain_from_low": 1620.6,
  "turnover": 13.27,
  "strength_score": 75.9,
  "market_cap": 1205.62,
  "recent_announcements": ["[2026-03-15] 关于签订重大合同的公告"]
}
```

## 注意事项

- 数据来源为腾讯财经（via easyquotation）和东方财富
- 扫描需在 A 股交易时间结束后运行（15:00 之后）以获取完整日内数据
- 首次运行需全量拉取约 5000 只股票的月 K 线，后续运行仅增量更新
- 历史新高缓存保存在 `historical_highs.json`，加速后续运行
- 仅供研究参考，不构成投资建议

## 在线预览

最新报告：https://kuailedubage.github.io/AShareATHTracker/

## 源码

https://github.com/kuailedubage/AShareATHTracker

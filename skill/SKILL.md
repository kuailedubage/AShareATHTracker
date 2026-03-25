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

## Skill 文件结构

本 skill 是自包含的，安装后即可直接运行：

```
ashare-ath-tracker/
├── SKILL.md              # 本文件（skill 定义与使用说明）
├── fetch_data.py         # 数据采集脚本（全市场扫描 + 指标计算）
├── generate_report.py    # 报告生成脚本（注入数据到 HTML 模板）
├── requirements.txt      # Python 依赖
└── output/
    └── report.html       # Neon Noir 风格 HTML 报告模板
```

## Agent 调用指南

当用户请求 A 股历史新高扫描或报告时，按以下步骤操作：

### Step 1: 安装依赖

```bash
cd <skill_directory>
pip install -r requirements.txt
```

### Step 2: 运行扫描

```bash
python fetch_data.py
```

此脚本会：
- 获取全部 A 股（约 5000 只）月 K 线，计算历史最高价
- 获取当日实时行情，筛选出创历史新高的股票
- 计算各项技术指标、获取概念题材、公告信息
- 输出 `new_high_stocks.json`

**注意**：首次运行需全量拉取月 K 线（约 10-20 分钟），后续运行有缓存（`historical_highs.json`）会快很多。应在 A 股收盘后（15:00 CST 之后）运行以获取完整数据。

### Step 3: 生成报告

```bash
python generate_report.py
```

生成 `index.html`，可直接在浏览器打开的交互式报告。

### Step 4: 返回结果

- **结构化数据**：读取 `new_high_stocks.json`，向用户展示或进一步分析
- **可视化报告**：展示 `index.html`（单文件 HTML，含所有图表和数据表格）

## 计算指标

每只创新高股票包含以下字段：

| 字段 | 说明 |
|------|------|
| `code` / `name` | 股票代码 / 名称 |
| `board` | 市场分类（主板/创业板/科创板） |
| `industry` | 所属行业 |
| `concept` | 核心概念（多个用 / 分隔） |
| `driving_concept` | 驱动题材（最相关的单个概念） |
| `change_pct` | 今日涨跌幅 % |
| `pullback_pct` | 新高后回落幅度 % |
| `consecutive_new_high_days` | 连续创新高天数（vs 前一日） |
| `true_consecutive_ath_days` | 连续创新高天数（vs 历史） |
| `ma5_deviation` | 收盘价 vs MA5 偏离 % |
| `gap_to_new_high` | 隔日需涨多少才能继续创新高 % |
| `drop_to_break_ma5` | 隔日需跌多少才会跌破 MA5 % |
| `gain_since_924` | 924 牛市以来涨幅 % |
| `gain_from_low` | 上市以来最低点涨幅 % |
| `turnover` | 实际换手率 %（基于自由流通股本） |
| `strength_score` | 综合强度评分（0-100） |
| `market_cap` | 总市值（亿元） |
| `recent_announcements` | 近 14 天重要公告列表 |

## 报告图表

1. **KPI 仪表盘** — 新高数量、平均强度、平均回落、平均涨幅
2. **题材概念热力矩阵** — TreeMap，红涨绿跌
3. **板块分布饼图** — 主板/创业板/科创板
4. **市值规模分布** — 柱状图
5. **TOP15 热门概念** — 横向柱状图
6. **强势度评分排名** — 横向柱状图
7. **连续新高 × 牛市涨幅** — 气泡散点图
8. **涨幅对比** — 924 涨幅 vs 历史最低涨幅
9. **换手率 × 回落幅度** — 散点图
10. **TOP6 多维雷达** — 强度/连续新高/偏离/涨幅/换手/量比
11. **风险收益矩阵** — 跌破 MA5 vs 创新高所需幅度
12. **全量数据表格** — 可排序可搜索

## 数据示例

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
  "strength_score": 75.9,
  "market_cap": 1205.62
}
```

## 注意事项

- 数据来源：腾讯财经（via easyquotation）+ 东方财富
- 应在 A 股收盘后运行（15:00 CST 之后）
- 首次运行需全量拉取月 K 线，`historical_highs.json` 缓存加速后续运行
- 仅供研究参考，不构成投资建议

## 在线预览

https://kuailedubage.github.io/AShareATHTracker/

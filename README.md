# AShareATHTracker

A股历史新高股票追踪器 - 自动扫描创上市以来新高的A股，生成 Neon Noir 风格交互式分析报告。

## 功能

- 扫描全部A股（主板/创业板/科创板/北交所），筛选当日创上市以来历史新高的股票
- 自动排除次新股和ST股
- 计算丰富的技术指标：新高回落幅度、连续新高天数、MA偏离、强度评分等
- 生成单文件交互式 HTML 报告（ECharts + TailwindCSS + GSAP ScrollTrigger）

## 使用方法

```bash
pip install easyquotation requests
python fetch_data.py
```

运行后生成 `new_high_stocks.json` 数据文件和 `output/report.html` 交互式报告。

## 报告包含

- 仪表盘概览（新高数、板块分布、平均强度评分）
- 行业热力矩阵图（TreeMap）
- 强度评分柱状图
- 板块分布饼图
- 散点气泡图（连续新高天数 vs 924牛市涨幅）
- 涨幅对比、换手率分析等多维度图表
- 可排序可搜索的完整数据表格（25列）

## 数据源

- 腾讯财经 K线接口（前复权）
- easyquotation 实时行情

## 颜色约定

红色 = 涨，绿色 = 跌（A股市场惯例）

# 输出格式说明（v3.0）

## JSON 输出（result.json）

```json
{
  "name": "张三",
  "gender": "男",
  "solar_date": "1990-05-20",
  "bazi": ["庚午", "辛巳", "乙酉", "庚辰"],
  "birth_year": 1990,
  "timeline": [
    {
      "year": 1990, "age": 1,
      "open": 50.0, "close": 55.2, "high": 58.0, "low": 47.0,
      "da_yun": "辛巳", "liu_nian": "庚午",
      "trend": "牛",
      "summary": "1990年(1岁) 未起运 流年庚午 📈"
    }
  ],
  "summary": {
    "bazi_summary": {
      "four_pillars": "庚午 辛巳 乙酉 庚辰",
      "day_master": "乙(阴木)",
      "gender": "男"
    },
    "dim_scores": {
      "事业": 5.0, "财运": 4.0, "姻缘": 2.5, "健康": 2.0,
      "学业": 3.0, "人际": 2.5, "子女": 3.5, "精神": 2.5
    },
    "dim_desc": {
      "事业": "事业发展与职业运",
      "财运": "财富积累与理财运",
      "姻缘": "感情婚姻与伴侣缘",
      "健康": "身体健康与精力",
      "学业": "学业智慧与进修运",
      "人际": "人际关系与贵人运",
      "子女": "子女缘分与亲子关系",
      "精神": "心态幸福与精神状态"
    },
    "highlights": [
      {
        "year": 2001, "age": 12,
        "type": "人生巅峰", "emoji": "⭐",
        "desc": "2001年(12岁) 大运壬午 流年辛巳\n运势达到最高点 75.4"
      }
    ],
    "life_phases": [
      {
        "name": "少年期", "range": "1-18岁",
        "avg_score": 62.1, "rating": "牛市",
        "bull_years": 10, "bear_years": 8,
        "peak_year": 2001, "peak_score": 75.4
      }
    ],
    "statistics": {
      "total_years": 80, "avg_score": 57.7,
      "max_score": 75.4, "min_score": 39.9,
      "bull_years": 43, "bear_years": 37
    }
  }
}
```

### timeline 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| year | int | 公历年份 |
| age | int | 虚岁 |
| open | float | K线开盘价（上年收盘） |
| close | float | K线收盘价（EMA平滑后的运势得分） |
| high | float | K线最高价 |
| low | float | K线最低价 |
| da_yun | string | 当前大运干支 |
| liu_nian | string | 当年流年干支 |
| trend | string | "牛"（上升）或 "熊"（下降） |
| is_peak | bool | 仅出现在人生最高峰年份 |
| summary | string | 可读的年份摘要 |

### summary 字段说明

| 字段 | 说明 |
|------|------|
| bazi_summary | 八字概要（四柱、日主、性别） |
| dim_scores | 八大维度评分（1.0-5.0，0.5步长） |
| dim_desc | 各维度中文描述 |
| highlights | 高能年份列表（含类型、emoji、详细描述） |
| life_phases | 人生五阶段分析（含均分、评级、牛熊比） |
| statistics | 整体统计数据 |

## HTML 输出（chart.html）

独立 HTML 文件，包含：

1. **标题区**：姓名 + 八字信息
2. **K线主图**（ECharts Candlestick）
   - 绿色 = 牛市（收盘 > 开盘）
   - 红色 = 熊市（收盘 < 开盘）
   - 自动标记最高/最低点
   - 支持鼠标悬停查看详情
   - 底部 dataZoom 滑块
3. **逐年明细条形图**
   - 每年一行，显示年份/岁数/得分
   - 颜色与K线对应

### Coze 兼容说明

HTML 可直接嵌入 Coze 的卡片组件或 WebView 中：
- 使用 CDN 引入 ECharts，无本地依赖
- 所有样式内联，无外部 CSS 文件
- 自适应宽度（`width: 100%`）
- 暗色主题兼容深浅背景

## 解读指南

### 对话输出结构

向用户展示结果时，按以下结构输出：

#### 1. 多维度评分表格

从 `summary.dim_scores` 渲染星级评分表：

```markdown
| 维度 | 评分 | 说明 |
|------|------|------|
| 事业 | ★★★★★ (5.0) | 官印双全，事业运极佳 |
| 财运 | ★★★★ (4.0) | 财星旺相，偏财运不错 |
| 姻缘 | ★★½ (2.5) | 正财偏弱，感情需经营 |
| ... | ... | ... |
```

评分渲染：`int(score)` 个 ★ + 半分时加 ½ + 补 ☆ 至5星

#### 2. 高能年份解读

从 `summary.highlights` 逐一说明：
- ⭐ 人生巅峰 → 最佳机遇期
- ⚠️ 人生低谷 → 韬光养晦期
- 🔄 大运转换 → 人生方向转变点
- 🚀 最大涨幅 → 爆发年
- ⚡ 最大跌幅 → 风险年

#### 3. 人生阶段总结

从 `summary.life_phases` 按阶段解读：
- 少年期 → 成长环境、学业基础
- 青年期 → 事业起步、感情发展
- 壮年期 → 事业黄金期
- 中年期 → 收获期
- 晚年期 → 晚运

#### 4. K线图表

分享 HTML 图表文件。

#### 5. 免责声明

提醒仅供参考娱乐，命运靠自己。

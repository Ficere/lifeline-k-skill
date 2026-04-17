# 📈 人生K线图 / Lifeline K-Chart

将八字命理转化为金融K线图 —— 输入出生日期，生成百年运势的可交互 Candlestick 图表。

Transform BaZi (Four Pillars of Destiny) into a stock-style K-line chart — input a birth date, get an interactive 100-year fortune candlestick visualization.

遵循 [Agent Skills 开放标准](https://agentskills.io)，兼容 Claude Code、Cursor、GitHub Copilot、Codex、Windsurf、Gemini CLI、Perplexity Computer 等 30+ AI Agent 平台。

## 安装 / Install

```bash
npx skills add Ficere/lifeline-k-skill
```

> 需要 Node.js。安装后 Agent 会自动发现并按需加载该技能。
>
> Requires Node.js. Once installed, your agent will auto-discover and load this skill when relevant.

<details>
<summary>其他安装方式 / Alternative methods</summary>

**手动安装 / Manual install：**

```bash
git clone https://github.com/Ficere/lifeline-k-skill.git
# 将整个目录复制到你的 Agent 的 skills 目录下即可
# Copy the directory to your agent's skills folder:
#   Claude Code:  ~/.claude/skills/
#   Cursor:       .cursor/skills/
#   Copilot:      .github/skills/
#   Codex:        ~/.codex/skills/
#   Gemini CLI:   .gemini/skills/
```

**Perplexity Computer：**

下载本仓库 zip → 在 [Skills 管理页面](https://www.perplexity.ai/computer/skills) 上传。

</details>

## 使用 / Usage

安装后直接用自然语言触发，无需任何配置：

```
帮我生成人生K线图，张三 1990年5月20日 08:30 出生，男
```

```
画一个运势走势图，李四 1985-03-12 06:00 女
```

```
我想看看未来十年的运势K线
```

## 功能 / Features

| 模块 | 说明 |
|------|------|
| **八字排盘** | 四柱八字自动校验（内置儒略日算法计算日柱） |
| **大运推算** | 根据年干阴阳和性别，顺/逆推 10+ 步大运 |
| **逐年评分** | 综合十神关系、长生十二诀、地支合冲的 6 维评分模型 |
| **OHLC 生成** | 运势分数 → 开盘/收盘/最高/最低，模拟真实K线波动 |
| **可交互图表** | ECharts Candlestick，支持缩放/悬停/标注极值，暗色金融风格 |
| **Coze 兼容** | HTML 输出可直接嵌入 Coze 卡片/WebView |

<details>
<summary>评分模型详情 / Scoring model</summary>

基准分 50，逐维度加减：

| 维度 | 权重 | 说明 |
|------|------|------|
| 大运天干十神 | ×1.5 | 正财/正官/正印加分，偏官/劫财扣分 |
| 大运地支长生 | ×1.2 | 帝旺/临官旺，死/绝/病弱 |
| 流年天干十神 | ×2.0 | 每年变化的主要波动来源 |
| 流年地支长生 | ×1.5 | 每年运势的地支影响 |
| 大运流年交互 | ±3 | 天干之间的十神关系 |
| 地支合冲 | ±4~5 | 六合加分、六冲扣分 |

最终分值钳制在 5-95 范围内。详见 `references/algorithm.md`。

</details>

## 独立脚本 / Standalone Script

`scripts/lifeline_k.py` 也可以脱离 Agent 平台独立运行（Python 3，无第三方依赖）：

```bash
python scripts/lifeline_k.py --input data.json --output result.json --html chart.html
```

<details>
<summary>输入 JSON 示例 / Sample input</summary>

```json
{
  "name": "张三",
  "gender": "男",
  "solar_date": "1990-05-20",
  "birth_time": "08:30",
  "bazi": ["庚午", "辛巳", "乙酉", "庚辰"],
  "lunar_month": 4,
  "lunar_day": 26
}
```

> 日柱由脚本自动校验，如与输入不一致会自动修正并提示。

</details>

## 目录结构 / Structure

```
lifeline-k/
├── SKILL.md               # 技能入口（Agent 自动读取）
├── scripts/
│   └── lifeline_k.py      # 计算引擎 + HTML 生成
├── references/
│   ├── algorithm.md        # 评分算法详解
│   └── output-template.md  # 输出格式说明
├── LICENSE
└── README.md
```

## 免责声明 / Disclaimer

本项目仅供学习和娱乐。命理学并非精确科学，运势K线图为算法推演结果，不构成人生决策依据。人生走向取决于个人努力和选择。

For educational and entertainment purposes only. The K-line chart is algorithmically generated and does not constitute life advice.

## License

MIT

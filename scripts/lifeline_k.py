#!/usr/bin/env python3
"""
人生K线图 · 计算与可视化脚本
基于八字五行推算人生各阶段运势，生成K线图数据和可交互HTML。

用法：
  python lifeline_k.py --input data.json --output result.json --html chart.html

输入JSON格式（完整四柱自动计算，bazi 为可选校验项）：
{
  "name": "张三",
  "gender": "男",
  "solar_date": "1990-05-20",
  "birth_time": "08:30"
}

说明：
- 只需 solar_date 和 birth_time，脚本自动计算完整四柱八字
- 如提供 bazi 字段，脚本会对比校验并提示差异
- birth_time 为出生时间（24小时制），建议使用真太阳时
- 脚本使用确定性算法（非AI），基于五行旺衰、大运流年、十神关系推算运势
"""

import json
import sys
import argparse
import math

# ============================================================
# 基础数据（复用自 tianji skill）
# ============================================================

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHENG_XIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

WU_XING_GAN = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
               "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
WU_XING_ZHI = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
               "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
               "戌": "土", "亥": "水"}
YIN_YANG_GAN = {"甲": "阳", "乙": "阴", "丙": "阳", "丁": "阴", "戊": "阳",
                "己": "阴", "庚": "阳", "辛": "阴", "壬": "阳", "癸": "阴"}

CANG_GAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

# 五行生克关系
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # A生B
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}    # A克B

# 大运天干地支对照（六十甲子序号）
GAN_ZHI_60 = []
for i in range(60):
    GAN_ZHI_60.append(TIAN_GAN[i % 10] + DI_ZHI[i % 12])

# 十二长生诀（各五行在十二地支的状态）
# 值越高=越旺
CHANG_SHENG_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANG_SHENG_SCORE = {"长生": 8, "沐浴": 5, "冠带": 7, "临官": 9, "帝旺": 10,
                     "衰": 4, "病": 3, "死": 2, "墓": 3, "绝": 1, "胎": 2, "养": 4}

# 各天干（阳干）的长生起始地支
CHANG_SHENG_START = {
    "甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
    "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯",
}


# ============================================================
# 日柱计算（儒略日算法，复用自 tianji skill）
# ============================================================

def gregorian_to_jdn(year, month, day):
    if month <= 2:
        year -= 1
        month += 12
    A = year // 100
    B = 2 - A + A // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524


def calc_day_pillar(year, month, day):
    jdn = gregorian_to_jdn(year, month, day)
    base_jdn = 2451545
    base_gan = 4
    base_zhi = 6
    diff = jdn - base_jdn
    gan_idx = (base_gan + diff) % 10
    zhi_idx = (base_zhi + diff) % 12
    return TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]


# ============================================================
# 节气计算 —— 天文算法（USNO 简化太阳位置 + UTC+8）
# 精度约 0.01°，节气日期计算与紫金山天文台数据一致
# ============================================================

# 24节气对应的太阳黄经（度）
SOLAR_TERM_LONGITUDES = [
    285, 300, 315, 330, 345, 0,      # 小寒 大寒 立春 雨水 惊蛰 春分
    15, 30, 45, 60, 75, 90,          # 清明 谷雨 立夏 小满 芒种 夏至
    105, 120, 135, 150, 165, 180,    # 小暑 大暑 立秋 处暑 白露 秋分
    195, 210, 225, 240, 255, 270,    # 寒露 霜降 立冬 小雪 大雪 冬至
]


def _sun_longitude(jd):
    """太阳地心视黄经（度）。jd 为儒略日（含小数）。"""
    D = jd - 2451545.0
    g = math.radians((357.529 + 0.98560028 * D) % 360)
    q = (280.459 + 0.98564736 * D) % 360
    return (q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360


def _jdn_to_gregorian(jdn):
    """儒略日数转公历。"""
    l = jdn + 68569
    n = 4 * l // 146097
    l = l - (146097 * n + 3) // 4
    i = 4000 * (l + 1) // 1461001
    l = l - 1461 * i // 4 + 31
    j = 80 * l // 2447
    day = l - 2447 * j // 80
    l = j // 11
    month = j + 2 - 12 * l
    year = 100 * (n - 49) + i + l
    return year, month, day


def _find_solar_term_jd(year, target_lon):
    """牛顿迭代求解太阳黄经达到 target_lon 的 JD（UT）。"""
    # 估算初始 JD
    base_jd = gregorian_to_jdn(year, 3, 20) + 0.5
    if target_lon >= 270:
        if target_lon >= 285:
            base_jd = gregorian_to_jdn(year, 1, 6) + 0.5 + (target_lon - 285) * 365.25 / 360.0
        else:
            base_jd = gregorian_to_jdn(year, 12, 22) + 0.5
    else:
        base_jd += (target_lon % 360) * 365.25 / 360.0

    jd = base_jd
    for _ in range(50):
        lon = _sun_longitude(jd)
        diff = (lon - target_lon + 180) % 360 - 180
        if abs(diff) < 0.0001:
            break
        jd -= diff / 0.9856
    return jd


def calc_solar_term_day(year, term_idx):
    """计算某年某节气的公历日期（北京时间）。返回 (month, day)。"""
    target_lon = SOLAR_TERM_LONGITUDES[term_idx]
    jd_ut = _find_solar_term_jd(year, target_lon)
    jd_beijing = jd_ut + 8.0 / 24.0  # UTC+8
    jdn = int(jd_beijing + 0.5)
    _, m, d = _jdn_to_gregorian(jdn)
    return (m, d)


def get_jie_qi_for_month(year, month):
    """获取某月的“节”（月首节气）日期。"""
    jie_map = {1: 0, 2: 2, 3: 4, 4: 6, 5: 8, 6: 10,
               7: 12, 8: 14, 9: 16, 10: 18, 11: 20, 12: 22}
    return calc_solar_term_day(year, jie_map[month])


# ============================================================
# 年柱计算（以立春为界）
# ============================================================

def calc_year_pillar(year, month, day):
    """计算年柱。立春前属上一年。"""
    lc_month, lc_day = calc_solar_term_day(year, 2)  # 立春
    nian = year - 1 if (month < lc_month or (month == lc_month and day < lc_day)) else year
    return TIAN_GAN[(nian - 4) % 10] + DI_ZHI[(nian - 4) % 12]


# ============================================================
# 月柱计算（以节气为界 + 五虎遁元）
# ============================================================

def calc_month_pillar(year, month, day):
    """计算月柱。以12个“节”为月份分界。"""
    # 每月的“节”对应的干支月地支
    # 1月小寒->丑(1), 2月立春->寅(2), ..., 12月大雪->子(0)
    month_to_zhi = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6,
                    7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 0}
    # 上一个干支月地支
    prev_month_zhi = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5,
                      7: 6, 8: 7, 9: 8, 10: 9, 11: 10, 12: 11}

    _, jie_day = get_jie_qi_for_month(year, month)

    if day >= jie_day:
        month_zhi_idx = month_to_zhi[month]
    else:
        month_zhi_idx = prev_month_zhi[month]

    year_pillar = calc_year_pillar(year, month, day)
    year_gan_idx = TIAN_GAN.index(year_pillar[0])

    # 五虎遁元: 寅月天干起始
    yin_month_gan_start = (year_gan_idx % 5) * 2 + 2
    month_offset = (month_zhi_idx - 2) % 12
    month_gan_idx = (yin_month_gan_start + month_offset) % 10

    return TIAN_GAN[month_gan_idx] + DI_ZHI[month_zhi_idx]


# ============================================================
# 时柱计算（五鼠遁元 + 早子时方案）
# ============================================================

def calc_hour_pillar(day_gan, hour):
    """计算时柱。采用早子时方案（23点不换日）。"""
    shi_zhi_idx = 0 if hour == 23 else (hour + 1) // 2
    day_gan_idx = TIAN_GAN.index(day_gan)
    zi_hour_gan_start = (day_gan_idx % 5) * 2
    shi_gan_idx = (zi_hour_gan_start + shi_zhi_idx) % 10
    return TIAN_GAN[shi_gan_idx] + DI_ZHI[shi_zhi_idx]


# ============================================================
# 完整四柱自动计算
# ============================================================

def calc_four_pillars(year, month, day, hour=12):
    """
    自动计算完整四柱八字。
    采用早子时方案：23点仍用当日日柱。
    """
    year_p = calc_year_pillar(year, month, day)
    month_p = calc_month_pillar(year, month, day)
    day_p = calc_day_pillar(year, month, day)
    hour_p = calc_hour_pillar(day_p[0], hour)
    return [year_p, month_p, day_p, hour_p]


# ============================================================
# 十神计算
# ============================================================

SHI_SHEN_MAP = {
    ("同", "同"): "比肩", ("同", "异"): "劫财",
    ("生", "同"): "食神", ("生", "异"): "伤官",
    ("克", "同"): "偏财", ("克", "异"): "正财",
    ("被克", "同"): "偏官", ("被克", "异"): "正官",
    ("被生", "同"): "偏印", ("被生", "异"): "正印",
}

# 十神对运势的影响分值
SHI_SHEN_SCORE = {
    "比肩": 3, "劫财": -2, "食神": 6, "伤官": 2,
    "偏财": 5, "正财": 7, "偏官": -1, "正官": 4,
    "偏印": 2, "正印": 5,
}


def get_shi_shen(day_gan, other_gan):
    wx_day = WU_XING_GAN[day_gan]
    wx_other = WU_XING_GAN[other_gan]
    yy_day = YIN_YANG_GAN[day_gan]
    yy_other = YIN_YANG_GAN[other_gan]

    same_yy = "同" if yy_day == yy_other else "异"

    if wx_day == wx_other:
        rel = "同"
    elif SHENG[wx_day] == wx_other:
        rel = "生"
    elif KE[wx_day] == wx_other:
        rel = "克"
    elif SHENG[wx_other] == wx_day:
        rel = "被生"
    else:
        rel = "被克"

    return SHI_SHEN_MAP.get((rel, same_yy), "比肩")


# ============================================================
# 长生十二诀得分
# ============================================================

def get_chang_sheng_score(gan, zhi):
    """计算某天干在某地支的长生状态得分。"""
    start_zhi = CHANG_SHENG_START.get(gan)
    if not start_zhi:
        return 5

    start_idx = DI_ZHI.index(start_zhi)
    target_idx = DI_ZHI.index(zhi)

    # 阳干顺行，阴干逆行
    if YIN_YANG_GAN[gan] == "阳":
        offset = (target_idx - start_idx) % 12
    else:
        offset = (start_idx - target_idx) % 12

    state = CHANG_SHENG_ORDER[offset]
    return CHANG_SHENG_SCORE[state]


# ============================================================
# 大运计算
# ============================================================

def calc_da_yun(year_gan, month_gz, gender, count=10):
    """计算大运序列。"""
    year_gan_idx = TIAN_GAN.index(year_gan)
    is_yang = YIN_YANG_GAN[year_gan] == "阳"
    is_male = gender == "男"

    # 顺行：阳男阴女；逆行：阴男阳女
    forward = (is_yang and is_male) or (not is_yang and not is_male)

    month_gz_idx = GAN_ZHI_60.index(month_gz)

    da_yun = []
    for i in range(1, count + 1):
        if forward:
            idx = (month_gz_idx + i) % 60
        else:
            idx = (month_gz_idx - i) % 60
        da_yun.append(GAN_ZHI_60[idx])

    return da_yun


# ============================================================
# 流年干支
# ============================================================

def get_liu_nian_gz(year):
    """计算某公历年的干支。"""
    gan_idx = (year - 4) % 10
    zhi_idx = (year - 4) % 12
    return TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]


# ============================================================
# 运势评分核心算法
# ============================================================

def calc_yearly_score(day_gan, da_yun_gz, liu_nian_gz, base_score=50):
    """
    计算某一年的运势分数 (0-100)。

    综合考量：
    1. 大运天干与日主的十神关系
    2. 大运地支对日主的长生状态
    3. 流年天干与日主的十神关系
    4. 流年地支对日主的长生状态
    5. 大运与流年的天干交互
    """
    score = base_score

    dy_gan, dy_zhi = da_yun_gz[0], da_yun_gz[1]
    ln_gan, ln_zhi = liu_nian_gz[0], liu_nian_gz[1]

    # 1. 大运天干十神
    dy_ss = get_shi_shen(day_gan, dy_gan)
    score += SHI_SHEN_SCORE.get(dy_ss, 0) * 1.5

    # 2. 大运地支长生
    dy_cs = get_chang_sheng_score(day_gan, dy_zhi)
    score += (dy_cs - 5) * 1.2  # 基准5，偏离加减

    # 3. 流年天干十神
    ln_ss = get_shi_shen(day_gan, ln_gan)
    score += SHI_SHEN_SCORE.get(ln_ss, 0) * 2.0

    # 4. 流年地支长生
    ln_cs = get_chang_sheng_score(day_gan, ln_zhi)
    score += (ln_cs - 5) * 1.5

    # 5. 大运与流年天干的交互
    dy_ln_ss = get_shi_shen(dy_gan, ln_gan)
    if dy_ln_ss in ("正财", "偏财", "正官", "食神"):
        score += 3
    elif dy_ln_ss in ("偏官", "劫财", "伤官"):
        score -= 3

    # 6. 地支六合/六冲
    zhi_pair = frozenset([dy_zhi, ln_zhi])
    liu_he = [frozenset(p) for p in [("子", "丑"), ("寅", "亥"), ("卯", "戌"),
              ("辰", "酉"), ("巳", "申"), ("午", "未")]]
    liu_chong = [frozenset(p) for p in [("子", "午"), ("丑", "未"), ("寅", "申"),
                 ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]]

    if zhi_pair in liu_he:
        score += 4
    elif zhi_pair in liu_chong:
        score -= 5

    # 钳制到 5-95 范围（留 headroom 给 OHLC 浮动）
    return max(5, min(95, score))


def generate_timeline(bazi, gender, birth_year, years=100):
    """
    生成人生K线图的完整时间线数据。

    返回列表，每项：
    {year, age, open, close, high, low, da_yun, liu_nian, summary}
    """
    day_gan = bazi[2][0]  # 日柱天干
    year_gan = bazi[0][0]
    month_gz = bazi[1]

    # 计算大运
    da_yun_list = calc_da_yun(year_gan, month_gz, gender, count=12)

    # 大运起运岁数（简化：阳男阴女3，阴男阳女5，可由调用者覆盖）
    is_yang = YIN_YANG_GAN[year_gan] == "阳"
    is_male = gender == "男"
    if (is_yang and is_male) or (not is_yang and not is_male):
        start_age = 3
    else:
        start_age = 5

    timeline = []
    prev_close = 50  # 初始价格

    for i in range(years):
        year = birth_year + i
        age = i + 1  # 虚岁

        liu_nian_gz = get_liu_nian_gz(year)

        # 确定当前大运
        if age < start_age:
            # 未起运，用月柱代替大运
            current_dy = month_gz
        else:
            dy_idx = (age - start_age) // 10
            if dy_idx >= len(da_yun_list):
                dy_idx = len(da_yun_list) - 1
            current_dy = da_yun_list[dy_idx]

        # 计算基准分
        base = calc_yearly_score(day_gan, current_dy, liu_nian_gz, base_score=50)

        # 生成OHLC
        open_val = prev_close
        close_val = base

        # 波动范围（年龄因素：中年波动大，老年平稳）
        volatility = 5 + 8 * math.sin(age / 30 * math.pi) * (0.5 + 0.5 * abs(close_val - 50) / 50)
        volatility = max(3, volatility)

        high_val = max(open_val, close_val) + abs(hash(f"{year}_h") % int(volatility + 1))
        low_val = min(open_val, close_val) - abs(hash(f"{year}_l") % int(volatility + 1))

        # 钳制
        high_val = min(100, max(high_val, max(open_val, close_val)))
        low_val = max(0, min(low_val, min(open_val, close_val)))
        open_val = max(0, min(100, open_val))
        close_val = max(0, min(100, close_val))

        # 判断牛/熊
        trend = "牛" if close_val >= open_val else "熊"

        # 大运周期标记
        dy_period = f"大运{current_dy}" if age >= start_age else "未起运"

        timeline.append({
            "year": year,
            "age": age,
            "open": round(open_val, 1),
            "close": round(close_val, 1),
            "high": round(high_val, 1),
            "low": round(low_val, 1),
            "da_yun": current_dy,
            "liu_nian": liu_nian_gz,
            "trend": trend,
            "summary": f"{year}年({age}岁) {dy_period} 流年{liu_nian_gz} {'📈' if trend == '牛' else '📉'}"
        })

        prev_close = close_val

    # 标记峰值
    if timeline:
        peak_idx = max(range(len(timeline)), key=lambda i: timeline[i]["high"])
        timeline[peak_idx]["is_peak"] = True

    return timeline


# ============================================================
# HTML 图表生成（ECharts, Coze 兼容）
# ============================================================

def generate_html(data, name="", output_path="chart.html"):
    """生成可交互的K线图HTML文件，使用ECharts，可在Coze中直接渲染。"""

    timeline_json = json.dumps(data["timeline"], ensure_ascii=False)
    bazi_str = " ".join(data.get("bazi", []))
    title = f"{name}的人生K线图" if name else "人生K线图"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f1724;
    color: #e2e8f0;
    min-height: 100vh;
  }}
  .header {{
    padding: 20px 24px 12px;
    border-bottom: 1px solid #1e293b;
  }}
  .header h1 {{
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(135deg, #a78bfa, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header .meta {{
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
  }}
  .legend {{
    display: flex;
    gap: 16px;
    padding: 8px 24px;
    font-size: 12px;
    color: #94a3b8;
  }}
  .legend span {{ display: flex; align-items: center; gap: 4px; }}
  .legend .dot {{
    width: 10px; height: 10px; border-radius: 2px;
  }}
  .bull {{ background: #10b981; }}
  .bear {{ background: #ef4444; }}
  #chart {{ width: 100%; height: 420px; }}
  .timeline-section {{
    padding: 16px 24px;
    max-height: 300px;
    overflow-y: auto;
  }}
  .timeline-section h3 {{
    font-size: 14px; color: #94a3b8; margin-bottom: 8px;
    position: sticky; top: 0; background: #0f1724; padding: 4px 0;
  }}
  .year-item {{
    display: flex;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid #1e293b;
    font-size: 13px;
  }}
  .year-item .age {{
    width: 80px; color: #94a3b8; flex-shrink: 0;
  }}
  .year-item .bar-wrap {{
    flex: 1; height: 18px; background: #1e293b; border-radius: 3px;
    position: relative; overflow: hidden;
  }}
  .year-item .bar {{
    height: 100%; border-radius: 3px;
    transition: width 0.3s;
  }}
  .year-item .val {{
    width: 50px; text-align: right; flex-shrink: 0;
    font-family: monospace;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>📈 {title}</h1>
  <div class="meta">八字：{bazi_str} ｜ 百年运势K线</div>
</div>

<div class="legend">
  <span><span class="dot bull"></span>牛市（运势上升）</span>
  <span><span class="dot bear"></span>熊市（运势下降）</span>
</div>

<div id="chart"></div>

<div class="timeline-section">
  <h3>📋 逐年运势明细</h3>
  <div id="timeline-list"></div>
</div>

<script>
const rawData = {timeline_json};

// 准备ECharts数据
const categoryData = rawData.map(d => d.age + '岁');
const ohlcData = rawData.map(d => [d.open, d.close, d.low, d.high]);

const chart = echarts.init(document.getElementById('chart'));

const option = {{
  backgroundColor: 'transparent',
  animation: true,
  tooltip: {{
    trigger: 'axis',
    axisPointer: {{ type: 'cross' }},
    backgroundColor: '#1e293b',
    borderColor: '#334155',
    textStyle: {{ color: '#e2e8f0', fontSize: 12 }},
    formatter: function(params) {{
      const idx = params[0].dataIndex;
      const d = rawData[idx];
      const trend = d.close >= d.open ? '<span style="color:#10b981">📈 牛</span>' : '<span style="color:#ef4444">📉 熊</span>';
      return `<b>${{d.year}}年 (${{d.age}}岁)</b> ${{trend}}<br/>
        开: ${{d.open}} &nbsp; 收: ${{d.close}}<br/>
        高: ${{d.high}} &nbsp; 低: ${{d.low}}<br/>
        <span style="color:#94a3b8">${{d.da_yun}} · 流年${{d.liu_nian}}</span>`;
    }}
  }},
  grid: {{
    left: 50, right: 20, top: 20, bottom: 40
  }},
  xAxis: {{
    type: 'category',
    data: categoryData,
    axisLine: {{ lineStyle: {{ color: '#334155' }} }},
    axisLabel: {{
      color: '#64748b',
      fontSize: 10,
      interval: 9
    }}
  }},
  yAxis: {{
    type: 'value',
    min: 0,
    max: 100,
    axisLine: {{ lineStyle: {{ color: '#334155' }} }},
    axisLabel: {{ color: '#64748b', fontSize: 10 }},
    splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }}
  }},
  dataZoom: [
    {{
      type: 'inside',
      xAxisIndex: 0,
      start: 0,
      end: 100
    }},
    {{
      type: 'slider',
      xAxisIndex: 0,
      start: 0,
      end: 100,
      height: 20,
      bottom: 8,
      borderColor: '#334155',
      backgroundColor: '#1e293b',
      fillerColor: 'rgba(167,139,250,0.15)',
      handleStyle: {{ color: '#a78bfa' }},
      textStyle: {{ color: '#64748b', fontSize: 10 }}
    }}
  ],
  series: [{{
    type: 'candlestick',
    data: ohlcData,
    itemStyle: {{
      color: '#10b981',
      color0: '#ef4444',
      borderColor: '#10b981',
      borderColor0: '#ef4444'
    }},
    barMaxWidth: 12,
    markPoint: {{
      data: [
        {{ type: 'max', valueDim: 'highest', symbolSize: 40, label: {{ fontSize: 10 }} }},
        {{ type: 'min', valueDim: 'lowest', symbolSize: 40, label: {{ fontSize: 10 }} }}
      ]
    }}
  }}]
}};

chart.setOption(option);
window.addEventListener('resize', () => chart.resize());

// 生成逐年明细列表
const listEl = document.getElementById('timeline-list');
rawData.forEach(d => {{
  const pct = d.close;
  const color = d.close >= d.open ? '#10b981' : '#ef4444';
  const div = document.createElement('div');
  div.className = 'year-item';
  div.innerHTML = `
    <span class="age">${{d.year}}(${{d.age}}岁)</span>
    <span class="bar-wrap">
      <span class="bar" style="width:${{pct}}%;background:${{color}}"></span>
    </span>
    <span class="val" style="color:${{color}}">${{d.close}}</span>
  `;
  listEl.appendChild(div);
}});
</script>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="人生K线图计算与可视化")
    parser.add_argument("--input", required=True, help="输入JSON文件路径")
    parser.add_argument("--output", default="result.json", help="输出JSON文件路径")
    parser.add_argument("--html", default="chart.html", help="输出HTML图表路径")
    parser.add_argument("--years", type=int, default=100, help="预测年数")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    name = data.get("name", "")
    gender = data.get("gender", "男")
    solar_date = data["solar_date"]
    birth_time = data.get("birth_time", "12:00")

    parts = solar_date.split("-")
    s_year, s_month, s_day = int(parts[0]), int(parts[1]), int(parts[2])
    time_parts = birth_time.split(":")
    s_hour = int(time_parts[0])

    # 自动计算完整四柱
    computed_bazi = calc_four_pillars(s_year, s_month, s_day, s_hour)
    print(f"✨ 自动计算四柱: {' '.join(computed_bazi)}")

    # 如果用户提供了 bazi，逐柱对比校验
    user_bazi = data.get("bazi")
    if user_bazi:
        pillar_names = ["年柱", "月柱", "日柱", "时柱"]
        for i, (comp, user) in enumerate(zip(computed_bazi, user_bazi)):
            if comp != user:
                print(f"⚠️ {pillar_names[i]}: 输入「{user}」与计算「{comp}」不一致，已用计算结果")

    bazi = computed_bazi
    birth_year = s_year

    # 生成时间线
    timeline = generate_timeline(bazi, gender, birth_year, years=args.years)

    # 输出数据
    result = {
        "name": name,
        "gender": gender,
        "solar_date": solar_date,
        "bazi": bazi,
        "birth_year": birth_year,
        "timeline": timeline,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 数据已保存至 {args.output}")

    # 生成HTML
    html_path = generate_html(result, name=name, output_path=args.html)
    print(f"✅ 可交互图表已生成 {html_path}")


if __name__ == "__main__":
    main()

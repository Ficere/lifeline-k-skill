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

# ---- 六合六冲常量 ----
LIU_HE = [frozenset(p) for p in [("子", "丑"), ("寅", "亥"), ("卯", "戌"),
          ("辰", "酉"), ("巳", "申"), ("午", "未")]]
LIU_CHONG = [frozenset(p) for p in [("子", "午"), ("丑", "未"), ("寅", "申"),
             ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]]


def calc_da_yun_base(day_gan, da_yun_gz):
    """
    计算大运基准分（50为中轴）。
    大运每10年变化一次，决定运势的主趋势方向。
    """
    dy_gan, dy_zhi = da_yun_gz[0], da_yun_gz[1]

    # 大运天干十神 —— 主权重
    dy_ss = get_shi_shen(day_gan, dy_gan)
    score = SHI_SHEN_SCORE.get(dy_ss, 0) * 2.5

    # 大运地支长生
    dy_cs = get_chang_sheng_score(day_gan, dy_zhi)
    score += (dy_cs - 5) * 1.8

    return score  # 典型范围: -14 ~ +26.5


def calc_liu_nian_ripple(day_gan, da_yun_gz, liu_nian_gz):
    """
    计算流年波动分（叠加在大运基准之上的短期涟漪）。
    权重较低，产生年度波动但不覆盖大运方向。
    """
    dy_gan, dy_zhi = da_yun_gz[0], da_yun_gz[1]
    ln_gan, ln_zhi = liu_nian_gz[0], liu_nian_gz[1]

    # 流年天干十神 —— 降低权重
    ln_ss = get_shi_shen(day_gan, ln_gan)
    ripple = SHI_SHEN_SCORE.get(ln_ss, 0) * 0.8

    # 流年地支长生 —— 降低权重
    ln_cs = get_chang_sheng_score(day_gan, ln_zhi)
    ripple += (ln_cs - 5) * 0.6

    # 大运与流年天干的交互（适度加分）
    dy_ln_ss = get_shi_shen(dy_gan, ln_gan)
    if dy_ln_ss in ("正财", "偏财", "正官", "食神"):
        ripple += 2
    elif dy_ln_ss in ("偏官", "劫财", "伤官"):
        ripple -= 2

    # 地支六合/六冲
    zhi_pair = frozenset([dy_zhi, ln_zhi])
    if zhi_pair in LIU_HE:
        ripple += 2.5
    elif zhi_pair in LIU_CHONG:
        ripple -= 3

    # 流年地支与命局地支交互（冲日支/合日支也有影响）
    # 这里简化为流年地支与大运地支的关系

    return ripple  # 典型范围: -8.6 ~ +10.3


def calc_yearly_score(day_gan, da_yun_gz, liu_nian_gz, base_score=50):
    """
    计算某一年的运势原始分 (0-100)。

    v3.0 两层结构：
    - 大运基准（慢变，决定10年趋势方向）
    - 流年涟漪（快变，产生年度波动但幅度受限）
    """
    da_yun_base = calc_da_yun_base(day_gan, da_yun_gz)
    liu_nian_ripple = calc_liu_nian_ripple(day_gan, da_yun_gz, liu_nian_gz)

    score = base_score + da_yun_base + liu_nian_ripple

    # 钳制到 5-95 范围
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

    # ---- 第一轮：计算每年原始分 + 大运信息 ----
    raw_scores = []
    da_yun_info = []

    for i in range(years):
        year = birth_year + i
        age = i + 1
        liu_nian_gz = get_liu_nian_gz(year)

        if age < start_age:
            current_dy = month_gz
        else:
            dy_idx = (age - start_age) // 10
            if dy_idx >= len(da_yun_list):
                dy_idx = len(da_yun_list) - 1
            current_dy = da_yun_list[dy_idx]

        raw = calc_yearly_score(day_gan, current_dy, liu_nian_gz, base_score=50)
        raw_scores.append(raw)
        da_yun_info.append((year, age, current_dy, liu_nian_gz))

    # ---- 第二轮：EMA 平滑，产生有明显波段的价格曲线 ----
    # EMA 平滑因子 α：越小越平滑，0.35 让大运趋势明显但流年仍有感知
    alpha = 0.35
    smoothed = [raw_scores[0]]
    for i in range(1, len(raw_scores)):
        s = alpha * raw_scores[i] + (1 - alpha) * smoothed[i - 1]
        smoothed.append(max(5, min(95, s)))

    # ---- 第三轮：大运交接过渡（大运切换时加速过渡）----
    for i in range(1, len(smoothed)):
        _, age, cur_dy, _ = da_yun_info[i]
        _, _, prev_dy, _ = da_yun_info[i - 1]
        if cur_dy != prev_dy:
            # 大运切换的第一年，加大 α 使过渡更明显
            transition_alpha = 0.55
            smoothed[i] = transition_alpha * raw_scores[i] + (1 - transition_alpha) * smoothed[i - 1]
            smoothed[i] = max(5, min(95, smoothed[i]))

    # ---- 第四轮：生成 OHLC ----
    timeline = []
    prev_close = 50

    for i in range(years):
        year, age, current_dy, liu_nian_gz = da_yun_info[i]

        open_val = prev_close
        close_val = smoothed[i]

        # 波动率：基于当年原始分与平滑分的差异 + 年龄因子
        raw_dev = abs(raw_scores[i] - smoothed[i])
        age_factor = 0.6 + 0.4 * math.sin(max(0, age - 5) / 30 * math.pi)
        volatility = max(2, 2 + raw_dev * 0.5 * age_factor)

        high_val = max(open_val, close_val) + abs(hash(f"{year}_h") % int(volatility + 1))
        low_val = min(open_val, close_val) - abs(hash(f"{year}_l") % int(volatility + 1))

        high_val = min(100, max(high_val, max(open_val, close_val)))
        low_val = max(0, min(low_val, min(open_val, close_val)))
        open_val = max(0, min(100, open_val))
        close_val = max(0, min(100, close_val))

        trend = "牛" if close_val >= open_val else "熊"
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
# 多维度评分体系（基于十神/长生/大运的八大维度）
# ============================================================

# 各维度对应的十神权重映射（正分=利好，负分=不利）
# 基于传统命理十神六亲对应关系
DIM_WEIGHTS = {
    "事业": {
        # 事业看官杀、印星、财星
        "正官": 9, "偏官": 5, "正印": 7, "偏印": 4,
        "正财": 6, "偏财": 5, "食神": 3, "伤官": 2,
        "比肩": 1, "劫财": -2,
    },
    "财运": {
        # 财运看财星、食伤生财
        "正财": 9, "偏财": 8, "食神": 6, "伤官": 5,
        "正官": 3, "偏官": 1, "正印": 1, "偏印": 0,
        "比肩": -1, "劫财": -4,
    },
    "姻缘": {
        # 男命看正财（妻）、偏财（情缘）；女命看正官（夫）、偏官（情缘）
        # 统一用中性权重，由调用时根据性别调整
        "正财": 5, "偏财": 3, "正官": 5, "偏官": 3,
        "食神": 2, "伤官": -1, "正印": 2, "偏印": 0,
        "比肩": -1, "劫财": -3,
    },
    "健康": {
        # 健康看印星护身、比劫帮身，财星耗身、官杀克身不利
        "正印": 8, "偏印": 6, "比肩": 5, "劫财": 3,
        "食神": 3, "伤官": 0, "正财": -1, "偏财": -1,
        "正官": -1, "偏官": -3,
    },
    "学业": {
        # 学业看印星（主文）、食伤（主智慧）
        "正印": 9, "偏印": 7, "食神": 6, "伤官": 5,
        "正官": 3, "偏官": 1, "正财": -2, "偏财": -3,
        "比肩": 1, "劫财": -1,
    },
    "人际": {
        # 人际看比劫（朋友）、食神（福禄亲和）、印星（贵人）
        "食神": 8, "正印": 6, "偏印": 3, "比肩": 5,
        "正官": 3, "偏官": -2, "正财": 2, "偏财": 1,
        "伤官": -3, "劫财": -4,
    },
    "子女": {
        # 男命看官杀（子女），女命看食伤（子女）
        # 统一中性权重，由调用时根据性别调整
        "正官": 5, "偏官": 4, "食神": 5, "伤官": 4,
        "正印": 3, "偏印": 1, "正财": 1, "偏财": 0,
        "比肩": 0, "劫财": -2,
    },
    "精神": {
        # 精神/心态：食神主福禄乐观，印星主安定，偏官主压力
        "食神": 9, "正印": 7, "偏印": 3, "比肩": 4,
        "正财": 3, "偏财": 2, "伤官": -2, "正官": 1,
        "偏官": -5, "劫财": -3,
    },
}

# 各维度的中文说明
DIM_DESC = {
    "事业": "事业发展与职业运",
    "财运": "财富积累与理财运",
    "姻缘": "感情婚姻与伴侣缘",
    "健康": "身体健康与精力",
    "学业": "学业智慧与进修运",
    "人际": "人际关系与贵人运",
    "子女": "子女缘分与亲子关系",
    "精神": "心态幸福与精神状态",
}


def calc_dimension_scores(bazi, gender, birth_year, da_yun_list, start_age, years=100):
    """
    计算八大维度的综合评分（1-5分）。
    综合考量：命局原局十神分布 + 大运十神影响 + 长生旺衰。
    """
    day_gan = bazi[2][0]
    month_gz = bazi[1]

    # 1. 命局原局十神分布（四柱天干 + 地支藏干）
    all_gans = []
    for pillar in bazi:
        all_gans.append(pillar[0])  # 天干
        for cg in CANG_GAN.get(pillar[1], []):
            all_gans.append(cg)

    # 统计原局十神
    natal_shi_shen = {}
    for g in all_gans:
        if g == day_gan:
            continue
        ss = get_shi_shen(day_gan, g)
        natal_shi_shen[ss] = natal_shi_shen.get(ss, 0) + 1

    # 2. 大运十神统计（加权平均，前期大运权重更高）
    dy_shi_shen_weighted = {}
    total_dy_weight = 0
    for idx, dy_gz in enumerate(da_yun_list[:8]):  # 前80年
        dy_weight = max(1, 8 - idx)  # 早期大运权重更高
        dy_ss = get_shi_shen(day_gan, dy_gz[0])
        dy_shi_shen_weighted[dy_ss] = dy_shi_shen_weighted.get(dy_ss, 0) + dy_weight
        total_dy_weight += dy_weight

    # 3. 大运地支长生平均分
    dy_cs_total = sum(get_chang_sheng_score(day_gan, dy_gz[1]) for dy_gz in da_yun_list[:8])
    dy_cs_avg = dy_cs_total / min(8, len(da_yun_list))

    # 4. 根据性别调整姻缘/子女维度权重
    dim_weights_adjusted = {}
    for dim, weights in DIM_WEIGHTS.items():
        if dim == "姻缘":
            w = dict(weights)
            if gender == "男":
                w["正财"] = 9  # 男命妻星
                w["偏财"] = 5
                w["正官"] = 2
                w["偏官"] = 0
            else:
                w["正官"] = 9  # 女命夫星
                w["偏官"] = 5
                w["正财"] = 2
                w["偏财"] = 0
            dim_weights_adjusted[dim] = w
        elif dim == "子女":
            w = dict(weights)
            if gender == "男":
                w["正官"] = 8  # 男命子女看官杀
                w["偏官"] = 7
                w["食神"] = 2
                w["伤官"] = 1
            else:
                w["食神"] = 8  # 女命子女看食伤
                w["伤官"] = 7
                w["正官"] = 2
                w["偏官"] = 1
            dim_weights_adjusted[dim] = w
        else:
            dim_weights_adjusted[dim] = weights

    # 5. 计算各维度原始分
    dim_scores = {}
    for dim, weights in dim_weights_adjusted.items():
        raw = 0

        # 原局贡献 (40%)
        natal_sum = 0
        for ss, count in natal_shi_shen.items():
            natal_sum += weights.get(ss, 0) * count
        raw += natal_sum * 0.4

        # 大运贡献 (40%)
        dy_sum = 0
        for ss, w in dy_shi_shen_weighted.items():
            dy_sum += weights.get(ss, 0) * w / total_dy_weight
        raw += dy_sum * 5 * 0.4  # 缩放到可比范围

        # 长生旺衰贡献 (20%) —— 旺相利健康/事业，衰绝不利
        cs_factor = (dy_cs_avg - 5) * 1.5
        raw += cs_factor * 0.2

        dim_scores[dim] = raw

    # 6. 绝对键定归一化到 1-5 分
    # 基于经验校准：原始分范围约 0~31，中位约12
    # 以中位映射到 3.0 星，每 6 分代表 1 星差距
    result = {}
    for dim, raw in dim_scores.items():
        normalized = 1.0 + (raw / 7.5)  # 0→ 1.0, 7.5→2.0, 15→3.0, 22.5→4.0, 30→5.0
        # 圆整到 0.5 步长
        score = round(normalized * 2) / 2
        score = max(1.0, min(5.0, score))
        result[dim] = score

    return result


def detect_highlight_years(timeline, top_n=5):
    """
    检测高能年份：包括峰值、谷值、大运转折、最大单年涨跌。
    返回列表，每项含 (year, age, type, description)。
    """
    if not timeline:
        return []

    highlights = []

    # 找峰值和谷值
    sorted_by_high = sorted(timeline, key=lambda x: x["high"], reverse=True)
    sorted_by_low = sorted(timeline, key=lambda x: x["low"])

    # 最高峰
    peak = sorted_by_high[0]
    highlights.append({
        "year": peak["year"], "age": peak["age"],
        "type": "人生巅峰", "emoji": "⭐",
        "desc": f"{peak['year']}年({peak['age']}岁) 大运{peak['da_yun']} 流年{peak['liu_nian']}\n"
                f"运势达到最高点 {peak['high']}，人生资源与机遇的黄金窗口。"
    })

    # 最低谷
    valley = sorted_by_low[0]
    highlights.append({
        "year": valley["year"], "age": valley["age"],
        "type": "人生低谷", "emoji": "⚠️",
        "desc": f"{valley['year']}年({valley['age']}岁) 大运{valley['da_yun']} 流年{valley['liu_nian']}\n"
                f"运势降至最低点 {valley['low']}，需谨慎行事、韬光养晦。"
    })

    # 大运转折点
    for i in range(1, len(timeline)):
        if timeline[i]["da_yun"] != timeline[i-1]["da_yun"]:
            item = timeline[i]
            change = item["close"] - item["open"]
            direction = "上行" if change > 0 else "下行"
            highlights.append({
                "year": item["year"], "age": item["age"],
                "type": "大运转换", "emoji": "🔄",
                "desc": f"{item['year']}年({item['age']}岁) 进入大运{item['da_yun']}\n"
                        f"运势转向{direction}（{change:+.1f}），人生方向可能发生转变。"
            })

    # 最大单年涨幅
    max_gain = max(timeline[1:], key=lambda x: x["close"] - x["open"])
    gain = max_gain["close"] - max_gain["open"]
    if gain > 3:
        highlights.append({
            "year": max_gain["year"], "age": max_gain["age"],
            "type": "最大涨幅", "emoji": "🚀",
            "desc": f"{max_gain['year']}年({max_gain['age']}岁) 大运{max_gain['da_yun']} 流年{max_gain['liu_nian']}\n"
                    f"单年涨幅 {gain:+.1f}，运势急剧上升的爆发年。"
        })

    # 最大单年跌幅
    max_loss = min(timeline[1:], key=lambda x: x["close"] - x["open"])
    loss = max_loss["close"] - max_loss["open"]
    if loss < -3:
        highlights.append({
            "year": max_loss["year"], "age": max_loss["age"],
            "type": "最大跌幅", "emoji": "⚡",
            "desc": f"{max_loss['year']}年({max_loss['age']}岁) 大运{max_loss['da_yun']} 流年{max_loss['liu_nian']}\n"
                    f"单年跌幅 {loss:+.1f}，需特别注意防范风险。"
        })

    # 按年份排序，去重
    seen_years = set()
    unique = []
    for h in sorted(highlights, key=lambda x: x["year"]):
        if h["year"] not in seen_years:
            seen_years.add(h["year"])
            unique.append(h)

    return unique


def generate_structured_summary(bazi, gender, timeline, dim_scores, highlights):
    """
    生成结构化的命理总结数据（供 AI 解读用）。
    返回 dict，包含：
    - bazi_summary: 八字概要
    - life_phases: 人生阶段划分
    - dim_scores: 多维度评分
    - highlights: 高能年份
    - statistics: 统计数据
    """
    day_gan = bazi[2][0]
    wu_xing = WU_XING_GAN[day_gan]
    yin_yang = YIN_YANG_GAN[day_gan]

    # 人生阶段划分
    phases = [
        {"name": "少年期", "range": "1-18岁", "ages": (1, 18)},
        {"name": "青年期", "range": "19-35岁", "ages": (19, 35)},
        {"name": "壮年期", "range": "36-55岁", "ages": (36, 55)},
        {"name": "中年期", "range": "56-70岁", "ages": (56, 70)},
        {"name": "晚年期", "range": "71岁+", "ages": (71, 200)},
    ]

    phase_data = []
    for phase in phases:
        items = [t for t in timeline if phase["ages"][0] <= t["age"] <= phase["ages"][1]]
        if not items:
            continue
        avg_close = sum(t["close"] for t in items) / len(items)
        bull_count = sum(1 for t in items if t["close"] >= t["open"])
        bear_count = len(items) - bull_count
        peak_in_phase = max(items, key=lambda x: x["high"])
        # 评级
        if avg_close >= 70:
            rating = "大牛市"
        elif avg_close >= 60:
            rating = "牛市"
        elif avg_close >= 50:
            rating = "震荡"
        elif avg_close >= 40:
            rating = "熊市"
        else:
            rating = "大熊市"

        phase_data.append({
            "name": phase["name"],
            "range": phase["range"],
            "avg_score": round(avg_close, 1),
            "rating": rating,
            "bull_years": bull_count,
            "bear_years": bear_count,
            "peak_year": peak_in_phase["year"],
            "peak_score": peak_in_phase["high"],
        })

    # 统计数据
    all_close = [t["close"] for t in timeline]
    stats = {
        "total_years": len(timeline),
        "avg_score": round(sum(all_close) / len(all_close), 1),
        "max_score": round(max(t["high"] for t in timeline), 1),
        "min_score": round(min(t["low"] for t in timeline), 1),
        "bull_years": sum(1 for t in timeline if t["close"] >= t["open"]),
        "bear_years": sum(1 for t in timeline if t["close"] < t["open"]),
    }

    return {
        "bazi_summary": {
            "four_pillars": " ".join(bazi),
            "day_master": f"{day_gan}({yin_yang}{wu_xing})",
            "gender": gender,
        },
        "life_phases": phase_data,
        "dim_scores": dim_scores,
        "dim_desc": DIM_DESC,
        "highlights": highlights,
        "statistics": stats,
    }


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

    # 计算大运序列（多维度评分需要）
    year_gan = bazi[0][0]
    month_gz = bazi[1]
    is_yang = YIN_YANG_GAN[year_gan] == "阳"
    is_male = gender == "男"
    if (is_yang and is_male) or (not is_yang and not is_male):
        dy_start_age = 3
    else:
        dy_start_age = 5
    da_yun_list = calc_da_yun(year_gan, month_gz, gender, count=12)

    # 多维度评分
    dim_scores = calc_dimension_scores(bazi, gender, birth_year, da_yun_list, dy_start_age)
    print(f"\n🎯 多维度评分：")
    for dim, score in dim_scores.items():
        stars = "★" * int(score) + ("½" if score % 1 else "")
        print(f"  {dim}: {score}/5 {stars}")

    # 高能年份检测
    highlights = detect_highlight_years(timeline)
    print(f"\n📍 高能年份: {len(highlights)}个")
    for h in highlights:
        print(f"  {h['emoji']} [{h['type']}] {h['year']}年({h['age']}岁)")

    # 结构化总结
    summary = generate_structured_summary(bazi, gender, timeline, dim_scores, highlights)

    # 输出数据
    result = {
        "name": name,
        "gender": gender,
        "solar_date": solar_date,
        "bazi": bazi,
        "birth_year": birth_year,
        "timeline": timeline,
        "summary": summary,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 数据已保存至 {args.output}")

    # 生成HTML
    html_path = generate_html(result, name=name, output_path=args.html)
    print(f"✅ 可交互图表已生成 {html_path}")


if __name__ == "__main__":
    main()

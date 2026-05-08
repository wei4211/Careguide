"""CareGuide 規則式風險評分模組。

依照企劃書 100 分制設計：
- ADL 30 分
- IADL 20 分
- 健康與安全 20 分
- 家庭照顧支持 20 分
- 照顧者壓力 10 分
"""

from typing import Dict, List, Tuple


ADL_TABLE = {
    "bathing":   {"none": 0, "sometimes": 3, "often": 5},
    "dressing":  {"none": 0, "sometimes": 2, "often": 4},
    "eating":    {"none": 0, "sometimes": 2, "often": 4},
    "toileting": {"none": 0, "sometimes": 3, "often": 5},
    "transfer":  {"none": 0, "sometimes": 3, "often": 5},
}

MOBILITY_TABLE = {
    "independent": 0,
    "aid":         3,
    "assisted":    5,
    "unable":      7,
}

IADL_TABLE = {
    "meal":      {"independent": 0, "partial": 2, "unable": 4},
    "shopping":  {"independent": 0, "partial": 2, "unable": 4},
    "transport": {"independent": 0, "partial": 3, "unable": 5},
    "medication":{"independent": 0, "partial": 3, "unable": 5},
    "housework": {"independent": 0, "partial": 1, "unable": 2},
}

FALL_TABLE       = {"none": 0, "once": 4, "multiple": 6}
CHRONIC_TABLE    = {"none": 0, "one": 2, "multiple": 4}
COGNITIVE_TABLE  = {"none": 0, "mild": 3, "obvious": 6}
HOSPITAL_TABLE   = {"none": 0, "yes": 4}

LIVING_TABLE     = {"with_family": 0, "alone_daytime": 4, "alone": 6}
CAREGIVER_TABLE  = {"stable": 0, "partial": 4, "none": 6}
SUPPORT_TABLE    = {"sufficient": 0, "moderate": 3, "insufficient": 5}
EMERGENCY_TABLE  = {"yes": 0, "uncertain": 2, "no": 3}

PRESSURE_TABLE   = {"low": 0, "medium": 3, "high": 5}
CG_HEALTH_TABLE  = {"good": 0, "fair": 2, "poor": 3}
RESPITE_TABLE    = {"none": 0, "maybe": 1, "needed": 2}


def _lookup(table: Dict[str, int], key: str) -> int:
    return table.get(key, 0)


def calculate_adl_score(data: Dict) -> int:
    score = 0
    for field, mapping in ADL_TABLE.items():
        score += _lookup(mapping, data.get(field, "none"))
    score += _lookup(MOBILITY_TABLE, data.get("mobility", "independent"))
    return min(score, 30)


def calculate_iadl_score(data: Dict) -> int:
    score = 0
    for field, mapping in IADL_TABLE.items():
        score += _lookup(mapping, data.get(field, "independent"))
    return min(score, 20)


def calculate_health_score(data: Dict) -> int:
    score = 0
    score += _lookup(FALL_TABLE,      data.get("fall_history", "none"))
    score += _lookup(CHRONIC_TABLE,   data.get("chronic", "none"))
    score += _lookup(COGNITIVE_TABLE, data.get("cognitive", "none"))
    score += _lookup(HOSPITAL_TABLE,  data.get("hospital", "none"))
    return min(score, 20)


def calculate_family_score(data: Dict) -> int:
    score = 0
    score += _lookup(LIVING_TABLE,    data.get("living_status", "with_family"))
    score += _lookup(CAREGIVER_TABLE, data.get("caregiver", "stable"))
    score += _lookup(SUPPORT_TABLE,   data.get("family_support", "sufficient"))
    score += _lookup(EMERGENCY_TABLE, data.get("emergency", "yes"))
    return min(score, 20)


def calculate_caregiver_score(data: Dict) -> int:
    score = 0
    score += _lookup(PRESSURE_TABLE,  data.get("caregiver_pressure", "low"))
    score += _lookup(CG_HEALTH_TABLE, data.get("caregiver_health", "good"))
    score += _lookup(RESPITE_TABLE,   data.get("respite", "none"))
    return min(score, 10)


def calculate_total_score(data: Dict) -> Dict[str, int]:
    adl = calculate_adl_score(data)
    iadl = calculate_iadl_score(data)
    health = calculate_health_score(data)
    family = calculate_family_score(data)
    caregiver = calculate_caregiver_score(data)
    total = adl + iadl + health + family + caregiver
    return {
        "adl_score": adl,
        "iadl_score": iadl,
        "health_score": health,
        "family_score": family,
        "caregiver_score": caregiver,
        "total_score": total,
    }


def get_risk_level(total: int) -> Tuple[str, str]:
    if total <= 24:
        return ("低度照護需求", "low")
    if total <= 49:
        return ("中度照護需求", "medium")
    if total <= 74:
        return ("高度照護需求", "high")
    return ("極高度照護需求", "very_high")


def extract_risk_factors(data: Dict) -> List[str]:
    factors: List[str] = []

    mobility = data.get("mobility", "independent")
    if mobility in ("assisted", "unable"):
        factors.append("行動能力明顯下降")
    elif mobility == "aid":
        factors.append("行動需要輔具協助")

    if data.get("fall_history") == "multiple":
        factors.append("半年內多次跌倒")
    elif data.get("fall_history") == "once":
        factors.append("半年內曾跌倒")

    adl_heavy = [f for f, m in ADL_TABLE.items() if data.get(f) == "often"]
    if adl_heavy:
        factors.append("日常生活多項需要他人協助")

    iadl_unable = [f for f, m in IADL_TABLE.items() if data.get(f) == "unable"]
    if len(iadl_unable) >= 2:
        factors.append("獨立生活能力受限")

    if data.get("cognitive") == "obvious":
        factors.append("有明顯認知或記憶退化")
    elif data.get("cognitive") == "mild":
        factors.append("有輕微認知或記憶退化情形")

    if data.get("living_status") == "alone":
        factors.append("獨居")
    elif data.get("living_status") == "alone_daytime":
        factors.append("白天經常無人照顧")

    if data.get("caregiver") == "none":
        factors.append("缺乏穩定主要照顧者")

    if data.get("family_support") == "insufficient":
        factors.append("家人支援不足")

    if data.get("emergency") == "no":
        factors.append("緊急狀況時無人可協助")

    if data.get("caregiver_pressure") == "high":
        factors.append("主要照顧者壓力偏高")

    if data.get("respite") == "needed":
        factors.append("明顯需要喘息服務")

    if data.get("hospital") == "yes":
        factors.append("近期曾住院或頻繁就醫")

    return factors


def evaluate(data: Dict) -> Dict:
    """整合計算結果，回傳完整評估。"""
    scores = calculate_total_score(data)
    level_name, level_code = get_risk_level(scores["total_score"])
    factors = extract_risk_factors(data)
    return {
        **scores,
        "risk_level": level_name,
        "risk_level_code": level_code,
        "risk_factors": factors,
    }

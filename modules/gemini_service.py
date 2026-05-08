"""Gemini API 串接：產生白話照護建議與個案摘要。

若未設定 API Key，會回傳一份使用本地規則組成的備援文字，
讓網站在沒有 Gemini 連線時仍能運作。
"""

import os
import re
from typing import Dict, List, Optional

try:
    from google import genai
except ImportError:
    genai = None


SYSTEM_PROMPT = (
    "你是一位高齡照護需求諮詢助理。"
    "請根據資料產生白話、溫和、具體的照護建議。"
    "規則："
    "1. 不可進行醫療診斷。"
    "2. 不可判定使用者一定符合長照資格。"
    "3. 必須提醒使用者仍需尋求正式長照評估或專業人員協助。"
    "4. 語氣親切清楚，避免艱深專業術語。"
    "5. 以繁體中文回答。"
)

ADVICE_FORMAT = (
    "請依照以下五個段落輸出，每段以中文標題開頭：\n"
    "一、個案狀況摘要\n"
    "二、主要照護風險說明\n"
    "三、建議了解的照護服務\n"
    "四、家屬或照顧者可採取的行動\n"
    "五、注意事項與系統限制"
)


def _has_api_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def strip_markdown(text: str) -> str:
    """把 Gemini 常見的 Markdown 符號清掉，留下純文字結構。

    給 PDF / TXT 報告使用 — HTML 路徑改用 markdown filter 渲染。
    """
    if not text:
        return ""
    s = text
    # 標題 ### → 純文字
    s = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", s, flags=re.MULTILINE)
    # 粗體 **xxx** / __xxx__ → xxx
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    # 斜體 *xxx* / _xxx_ → xxx（避免破壞 1.2 等小數，要求兩端都是非空白字）
    s = re.sub(r"(?<!\*)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)", r"\1", s)
    s = re.sub(r"(?<!_)_(?!\s)([^_\n]+?)(?<!\s)_(?!_)", r"\1", s)
    # 行內程式碼 `xxx` → xxx
    s = re.sub(r"`([^`\n]+)`", r"\1", s)
    # 水平線 --- / *** → 空行
    s = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", s, flags=re.MULTILINE)
    # 列表符號 - / * 開頭 → ・
    s = re.sub(r"^[ \t]*[-*][ \t]+", "・", s, flags=re.MULTILINE)
    # 連續多個空行 → 兩行
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _client():
    if genai is None:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _build_user_prompt(payload: Dict) -> str:
    risk_factors = payload.get("risk_factors") or []
    factors_text = "\n".join(f"- {f}" for f in risk_factors) or "- 無明顯主要風險因素"

    description = payload.get("user_description") or "（使用者未補充描述）"

    return (
        f"個案資料：\n"
        f"- 年齡：{payload.get('age', '未填')} 歲\n"
        f"- 性別：{payload.get('gender', '未填')}\n"
        f"- 居住狀況：{payload.get('living_status_label', '未填')}\n"
        f"- 主要照顧者：{payload.get('caregiver_label', '未填')}\n\n"
        f"系統評估結果：\n"
        f"- ADL 分數：{payload.get('adl_score', 0)} / 30\n"
        f"- IADL 分數：{payload.get('iadl_score', 0)} / 20\n"
        f"- 健康安全分數：{payload.get('health_score', 0)} / 20\n"
        f"- 家庭支持分數：{payload.get('family_score', 0)} / 20\n"
        f"- 照顧者壓力分數：{payload.get('caregiver_score', 0)} / 10\n"
        f"- 總分：{payload.get('total_score', 0)} / 100\n"
        f"- 照護需求等級：{payload.get('risk_level', '未判定')}\n\n"
        f"主要風險因素：\n{factors_text}\n\n"
        f"使用者補充描述：\n「{description}」\n\n"
        f"{ADVICE_FORMAT}"
    )


# 從新到舊，遇到 503/quota 等錯誤時自動換下一個
# 注意：gemini-1.5-flash 已於 2025-09 停用，不要放回來
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def generate_care_advice(payload: Dict) -> str:
    """根據評估結果產生照護建議文字。"""
    if genai is None:
        return _fallback_advice(payload, error="google-genai SDK 未安裝")

    client = _client()
    if client is None:
        return _fallback_advice(payload)

    user_prompt = _build_user_prompt(payload)
    contents = [{"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}]}]

    errors: List[str] = []
    for model in MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(model=model, contents=contents)
            text = getattr(response, "text", None)
            if text:
                return text.strip()
            errors.append(f"{model}: 回傳空白內容（可能被安全過濾擋下）")
        except Exception as exc:  # 503、quota、network 等都會被 catch
            errors.append(f"{model}: {exc}")
            continue

    # 把所有失敗原因都丟進去，方便除錯
    error_summary = " | ".join(errors) if errors else "所有模型皆失敗"
    return _fallback_advice(payload, error=error_summary)


def generate_full_report(payload: Dict, advice: Optional[str] = None) -> str:
    """整合個案摘要報告文字（給 /report 頁面使用）。"""
    advice_raw = advice or payload.get("ai_advice") or generate_care_advice(payload)
    advice_text = strip_markdown(advice_raw)
    factors = payload.get("risk_factors") or []
    factors_block = "\n".join(f"  {i+1}. {f}" for i, f in enumerate(factors)) or "  （無顯著風險因素）"

    return (
        "CareGuide 個案照護需求摘要報告\n"
        "================================\n\n"
        "一、基本資料\n"
        f"  年齡：{payload.get('age', '未填')} 歲\n"
        f"  性別：{payload.get('gender', '未填')}\n"
        f"  居住狀況：{payload.get('living_status_label', '未填')}\n"
        f"  主要照顧者：{payload.get('caregiver_label', '未填')}\n\n"
        "二、照護需求等級\n"
        f"  總分：{payload.get('total_score', 0)} / 100\n"
        f"  等級：{payload.get('risk_level', '未判定')}\n\n"
        "三、各面向分數\n"
        f"  日常生活能力 ADL：{payload.get('adl_score', 0)} / 30\n"
        f"  工具性日常生活能力 IADL：{payload.get('iadl_score', 0)} / 20\n"
        f"  健康與安全風險：{payload.get('health_score', 0)} / 20\n"
        f"  家庭照顧支持：{payload.get('family_score', 0)} / 20\n"
        f"  照顧者壓力：{payload.get('caregiver_score', 0)} / 10\n\n"
        "四、主要風險因素\n"
        f"{factors_block}\n\n"
        "五、AI 照護建議\n"
        f"{advice_text}\n\n"
        "六、系統限制與提醒\n"
        "  本系統僅提供初步照護需求評估，不取代正式長照評估或醫療診斷。\n"
        "  若有急性醫療、嚴重跌倒或安全疑慮，請優先尋求醫療或專業協助。\n"
    )


def _fallback_advice(payload: Dict, error: Optional[str] = None) -> str:
    """無 API 或 API 失敗時的備援回應。"""
    level = payload.get("risk_level", "未判定")
    factors: List[str] = payload.get("risk_factors") or []
    factor_lines = "\n".join(f"- {f}" for f in factors) or "- 目前未偵測到顯著主要風險"

    note = ""
    if error:
        note = f"\n（系統提示：AI 服務暫時無法回應，以下為本地建議。錯誤：{error}）\n"
    elif not _has_api_key():
        note = "\n（系統提示：尚未設定 Gemini API Key，以下為本地預設建議。）\n"

    return (
        f"{note}"
        f"一、個案狀況摘要\n"
        f"根據問卷資料，此個案被評估為「{level}」。\n\n"
        f"二、主要照護風險說明\n"
        f"主要風險因素如下：\n{factor_lines}\n\n"
        f"三、建議了解的照護服務\n"
        f"可進一步了解居家服務、日間照顧、交通接送、輔具補助、無障礙改善與喘息服務等資源，\n"
        f"並可撥打 1966 長照專線或聯繫所在地長期照顧管理中心進行正式評估。\n\n"
        f"四、家屬或照顧者可採取的行動\n"
        f"建議記錄長者近期跌倒、用藥、就醫情形與日常生活協助需求，作為後續正式評估參考。\n"
        f"若主要照顧者壓力偏高，請主動了解喘息服務或其他支援資源。\n\n"
        f"五、注意事項與系統限制\n"
        f"本系統僅提供初步照護需求評估，不取代正式長照評估或醫療診斷。\n"
        f"若有急性醫療、嚴重跌倒或安全疑慮，請優先尋求醫療或專業協助。\n"
    )

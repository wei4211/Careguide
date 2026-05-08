"""產生個案摘要報告 PDF。

優先使用作業系統內的繁中 TTF/TTC 字型，將字型嵌入 PDF，
這樣不論在哪台電腦或 PDF 閱讀器都能正確顯示繁體中文。
"""

import html
import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# (字型檔路徑, .ttc subfontIndex, 註冊用字型名稱)
# 第一個成功載入的就會被採用。順序：macOS → Windows → Linux。
_FONT_CANDIDATES: List[Tuple[str, Optional[int], str]] = [
    # macOS — 繁中 sans-serif
    ("/System/Library/Fonts/STHeiti Light.ttc", 0, "STHeitiTC-Light"),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0, "STHeitiTC-Medium"),
    ("/Library/Fonts/Hiragino Sans GB.ttc", 0, "HiraginoSansGB-W3"),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0, "HiraginoSansGB-W3"),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 7, "STSongti-TC-Regular"),
    # Windows — 繁中
    ("C:\\Windows\\Fonts\\msjh.ttc", 0, "MSJhengHei"),
    ("C:\\Windows\\Fonts\\msjh.ttf", None, "MSJhengHei"),
    ("C:\\Windows\\Fonts\\mingliu.ttc", 0, "MingLiU"),
    # Linux — 常見 Noto / WQY
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0, "NotoSansCJK"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0, "NotoSansCJK"),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0, "WenQuanYiMicroHei"),
]

CHINESE_FONT: Optional[str] = None
_FONT_REGISTERED = False


def _try_register(path: str, subfont_index: Optional[int], name: str) -> bool:
    if not Path(path).exists():
        return False
    try:
        if path.lower().endswith(".ttc") and subfont_index is not None:
            font = TTFont(name, path, subfontIndex=subfont_index)
        else:
            font = TTFont(name, path)
        pdfmetrics.registerFont(font)
        return True
    except Exception:
        return False


def _ensure_font() -> str:
    """確保中文字型已註冊，回傳註冊名稱。"""
    global CHINESE_FONT, _FONT_REGISTERED
    if _FONT_REGISTERED and CHINESE_FONT:
        return CHINESE_FONT

    # 允許使用者用環境變數覆蓋（例如自備一個 .ttf）
    custom_path = os.getenv("CAREGUIDE_PDF_FONT")
    if custom_path:
        if _try_register(custom_path, None, "CareGuideCustom"):
            CHINESE_FONT = "CareGuideCustom"
            _FONT_REGISTERED = True
            return CHINESE_FONT

    for path, idx, name in _FONT_CANDIDATES:
        if _try_register(path, idx, name):
            CHINESE_FONT = name
            _FONT_REGISTERED = True
            return CHINESE_FONT

    raise RuntimeError(
        "找不到可用的中文字型。請設定環境變數 CAREGUIDE_PDF_FONT 指向一個 "
        ".ttf 或 .otf 中文字型檔，或安裝 Noto Sans CJK / 思源黑體。"
    )


# ---- 樣式 ----

PRIMARY = HexColor("#2563eb")
MUTED = HexColor("#6b7280")
BORDER = HexColor("#e5e7eb")
TEXT = HexColor("#1f2937")

LEVEL_COLORS = {
    "low": HexColor("#16a34a"),
    "medium": HexColor("#f59e0b"),
    "high": HexColor("#ea580c"),
    "very_high": HexColor("#dc2626"),
}


def _styles() -> Dict[str, ParagraphStyle]:
    base = {"fontName": CHINESE_FONT, "textColor": TEXT, "leading": 18}
    return {
        "title":   ParagraphStyle("title",   fontSize=20, spaceAfter=4,  textColor=TEXT,    fontName=CHINESE_FONT, leading=24, alignment=1),
        "subtitle":ParagraphStyle("subtitle",fontSize=10, spaceAfter=14, textColor=MUTED,   fontName=CHINESE_FONT, leading=14, alignment=1),
        "h2":      ParagraphStyle("h2",      fontSize=13, spaceBefore=10,spaceAfter=6,     textColor=PRIMARY, fontName=CHINESE_FONT, leading=18),
        "body":    ParagraphStyle("body",    fontSize=10.5, spaceAfter=4, **base),
        "small":   ParagraphStyle("small",   fontSize=9,  textColor=MUTED, fontName=CHINESE_FONT, leading=14),
        "level":   ParagraphStyle("level",   fontSize=22, fontName=CHINESE_FONT, leading=28, textColor=TEXT),
        "score":   ParagraphStyle("score",   fontSize=28, fontName=CHINESE_FONT, leading=32, textColor=PRIMARY, alignment=2),
    }


def _esc(text) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def _info_table(record: Dict, styles) -> Table:
    rows = [
        ["年齡",      f"{_esc(record.get('age')) or '未填'} 歲"],
        ["性別",      _esc(record.get("gender")) or "未填"],
        ["居住狀況",  _esc(record.get("living_status_label")) or "未填"],
        ["主要照顧者", _esc(record.get("caregiver_label")) or "未填"],
    ]
    data = [[Paragraph(k, styles["body"]), Paragraph(v, styles["body"])] for k, v in rows]
    t = Table(data, colWidths=[35 * mm, None])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), CHINESE_FONT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f9fafb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _level_block(record: Dict, styles) -> Table:
    code = record.get("risk_level_code") or "low"
    color = LEVEL_COLORS.get(code, PRIMARY)

    level_text = f'<font color="{color.hexval()}"><b>{_esc(record.get("risk_level"))}</b></font>'
    level_style = ParagraphStyle("level_text", fontName=CHINESE_FONT, fontSize=18, leading=22)
    score_text = (
        f'<font color="{color.hexval()}" size="28"><b>{_esc(record.get("total_score", 0))}</b></font>'
        f'<font color="{MUTED.hexval()}" size="11"> / 100</font>'
    )
    score_style = ParagraphStyle("score_text", fontName=CHINESE_FONT, fontSize=28, leading=30, alignment=2)

    data = [[
        [
            Paragraph("照護需求等級", styles["small"]),
            Paragraph(level_text, level_style),
        ],
        [
            Paragraph("總分", styles["small"]),
            Paragraph(score_text, score_style),
        ],
    ]]
    t = Table(data, colWidths=[None, 60 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LINEBEFORE", (0, 0), (0, 0), 4, color),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f9fafb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t


def _scores_table(record: Dict, styles) -> Table:
    rows = [
        ("日常生活能力 ADL",       record.get("adl_score", 0),       30),
        ("工具性日常生活能力 IADL", record.get("iadl_score", 0),      20),
        ("健康與安全風險",         record.get("health_score", 0),    20),
        ("家庭照顧支持",           record.get("family_score", 0),    20),
        ("照顧者壓力",             record.get("caregiver_score", 0), 10),
    ]
    data = [[
        Paragraph("<b>面向</b>", styles["body"]),
        Paragraph("<b>分數</b>", styles["body"]),
        Paragraph("<b>滿分</b>", styles["body"]),
    ]]
    for label, score, max_v in rows:
        data.append([
            Paragraph(_esc(label), styles["body"]),
            Paragraph(_esc(score), styles["body"]),
            Paragraph(_esc(max_v), styles["body"]),
        ])
    t = Table(data, colWidths=[None, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), CHINESE_FONT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#eff6ff")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _factors_block(record: Dict, styles):
    factors = record.get("risk_factors") or []
    if not factors:
        return Paragraph("（目前未偵測到顯著主要風險因素）", styles["body"])
    items = [Paragraph(f"{i + 1}. {_esc(f)}", styles["body"]) for i, f in enumerate(factors)]
    return KeepTogether(items)


def _advice_paragraphs(advice_text: str, styles):
    if not advice_text:
        return [Paragraph("（無 AI 建議內容）", styles["body"])]
    flow = []
    for raw in advice_text.split("\n"):
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 4))
            continue
        flow.append(Paragraph(_esc(line), styles["body"]))
    return flow


def build_report_pdf(record: Dict, advice: Optional[str] = None) -> bytes:
    """根據評估記錄產出 PDF bytes。"""
    from .gemini_service import strip_markdown  # 延遲匯入，避免循環依賴

    _ensure_font()
    styles = _styles()
    advice_text = strip_markdown(advice or record.get("ai_advice") or "")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="CareGuide 個案照護需求摘要報告",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    flow = []
    flow.append(Paragraph("CareGuide 個案照護需求摘要報告", styles["title"]))
    flow.append(Paragraph(
        f"報告編號 #{record.get('id', '—')}　|　建立時間：{_esc(record.get('created_at', '—'))}",
        styles["subtitle"],
    ))

    flow.append(_level_block(record, styles))
    flow.append(Spacer(1, 14))

    flow.append(Paragraph("一、基本資料", styles["h2"]))
    flow.append(_info_table(record, styles))
    flow.append(Spacer(1, 8))

    flow.append(Paragraph("二、各面向分數", styles["h2"]))
    flow.append(_scores_table(record, styles))
    flow.append(Spacer(1, 8))

    flow.append(Paragraph("三、主要風險因素", styles["h2"]))
    flow.append(_factors_block(record, styles))
    flow.append(Spacer(1, 8))

    if record.get("user_description"):
        flow.append(Paragraph("四、使用者補充描述", styles["h2"]))
        flow.append(Paragraph(_esc(record["user_description"]), styles["body"]))
        flow.append(Spacer(1, 8))
        advice_idx = "五"
        notes_idx = "六"
    else:
        advice_idx = "四"
        notes_idx = "五"

    flow.append(Paragraph(f"{advice_idx}、AI 照護建議", styles["h2"]))
    flow.extend(_advice_paragraphs(advice_text, styles))
    flow.append(Spacer(1, 10))

    flow.append(Paragraph(f"{notes_idx}、系統限制與提醒", styles["h2"]))
    flow.append(Paragraph(
        "本系統僅提供初步照護需求評估，不取代正式長照評估或醫療診斷。"
        "若有急性醫療、嚴重跌倒或安全疑慮，請優先尋求醫療或專業協助。"
        "需要正式評估時，可撥打 1966 長照服務專線或聯繫所在地長期照顧管理中心。",
        styles["body"],
    ))

    doc.build(flow)
    return buf.getvalue()

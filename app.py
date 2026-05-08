"""CareGuide Flask 主應用程式。"""

import os
from urllib.parse import urlparse

import markdown as md
from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from markupsafe import Markup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from modules import auth, database, gemini_service, pdf_generator
from modules.risk_score import evaluate


# 表單代碼 ↔ 中文標籤對照（給結果頁與報告使用）
LIVING_LABELS = {
    "with_family": "與家人同住",
    "alone_daytime": "白天常獨處",
    "alone": "獨居",
}
CAREGIVER_LABELS = {
    "stable": "有穩定照顧者",
    "partial": "部分時間可照顧",
    "none": "無穩定照顧者",
}
LEVEL_DESCRIPTIONS = {
    "low": "目前照護風險較低，可持續觀察。",
    "medium": "已有部分照護需求，建議了解相關照護資源。",
    "high": "照護需求較明顯，建議尋求正式評估或專業協助。",
    "very_high": "照護風險較高，建議盡快尋求正式長照或醫療相關協助。",
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "careguide-dev-secret")

    database.init_db()

    # 將 current_user 注入所有模板
    @app.context_processor
    def inject_user():
        return {"current_user": auth.current_user()}

    # Jinja filter：把 Markdown 文字轉為 HTML
    @app.template_filter("markdown")
    def render_markdown(text: str) -> Markup:
        if not text:
            return Markup("")
        html = md.markdown(text, extensions=["extra", "sane_lists", "nl2br"])
        return Markup(html)

    # ---------- 公開頁 ----------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    # ---------- 註冊 / 登入 ----------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if auth.current_user():
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "")
            display_name = request.form.get("display_name", "")
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if password != confirm:
                flash("兩次輸入的密碼不一致", "danger")
                return render_template("register.html",
                                       form={"username": username, "display_name": display_name})

            ok, msg = auth.register_user(username, password, display_name)
            if not ok:
                flash(msg, "danger")
                return render_template("register.html",
                                       form={"username": username, "display_name": display_name})

            user = auth.authenticate(username, password)
            if user:
                auth.login_session(user)
            flash("註冊成功，已為你自動登入", "success")
            return redirect(url_for("index"))

        return render_template("register.html", form={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if auth.current_user():
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user = auth.authenticate(username, password)
            if not user:
                flash("帳號或密碼錯誤", "danger")
                return render_template("login.html", form={"username": username})

            auth.login_session(user)
            next_url = _safe_redirect_target(request.args.get("next") or request.form.get("next"))
            return redirect(next_url or url_for("index"))

        return render_template("login.html", form={})

    @app.route("/logout", methods=["POST"])
    def logout():
        auth.logout_session()
        flash("已登出", "info")
        return redirect(url_for("index"))

    # ---------- 評估流程（需登入） ----------
    @app.route("/assessment")
    @auth.login_required
    def assessment():
        return render_template("assessment.html")

    @app.route("/evaluate", methods=["POST"])
    @auth.login_required
    def evaluate_route():
        user = auth.current_user()
        form = request.form.to_dict()
        scores = evaluate(form)

        living_status = form.get("living_status", "")
        caregiver = form.get("caregiver", "")

        ai_payload = {
            **scores,
            "age": form.get("age"),
            "gender": form.get("gender"),
            "living_status_label": LIVING_LABELS.get(living_status, living_status or "未填"),
            "caregiver_label": CAREGIVER_LABELS.get(caregiver, caregiver or "未填"),
            "user_description": form.get("description", ""),
        }
        advice = gemini_service.generate_care_advice(ai_payload)

        record = {
            "user_id": user["id"],
            "age": _to_int(form.get("age")),
            "gender": form.get("gender"),
            "living_status": living_status,
            "caregiver": caregiver,
            "user_description": form.get("description", ""),
            "ai_advice": advice,
            "raw_input": form,
            **scores,
        }
        assessment_id = database.save_assessment(record)
        return redirect(url_for("result", assessment_id=assessment_id))

    @app.route("/result/<int:assessment_id>")
    @auth.login_required
    def result(assessment_id: int):
        user = auth.current_user()
        record = database.get_assessment(assessment_id, user_id=user["id"])
        if not record:
            abort(404)
        _decorate_record(record)
        return render_template("result.html", record=record)

    @app.route("/result/<int:assessment_id>/regenerate", methods=["POST"])
    @auth.login_required
    def regenerate_advice(assessment_id: int):
        user = auth.current_user()
        record = database.get_assessment(assessment_id, user_id=user["id"])
        if not record:
            abort(404)
        _decorate_record(record)
        ai_payload = {
            **record,
            "user_description": record.get("user_description", ""),
        }
        new_advice = gemini_service.generate_care_advice(ai_payload)
        database.update_ai_advice(assessment_id, new_advice)
        flash("AI 建議已重新產生", "success")
        return redirect(url_for("result", assessment_id=assessment_id))

    @app.route("/report/<int:assessment_id>")
    @auth.login_required
    def report(assessment_id: int):
        user = auth.current_user()
        record = database.get_assessment(assessment_id, user_id=user["id"])
        if not record:
            abort(404)
        _decorate_record(record)
        report_text = gemini_service.generate_full_report(record, advice=record.get("ai_advice"))
        database.save_report(assessment_id, report_text)
        return render_template("report.html", record=record, report_text=report_text)

    @app.route("/report/<int:assessment_id>/download.pdf")
    @auth.login_required
    def report_pdf(assessment_id: int):
        user = auth.current_user()
        record = database.get_assessment(assessment_id, user_id=user["id"])
        if not record:
            abort(404)
        _decorate_record(record)
        pdf_bytes = pdf_generator.build_report_pdf(record, advice=record.get("ai_advice"))
        filename = f"careguide_report_{assessment_id}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    @app.route("/records")
    @auth.login_required
    def records():
        user = auth.current_user()
        items = database.get_all_records(limit=50, user_id=user["id"])
        return render_template("records.html", records=items)

    @app.route("/records/<int:assessment_id>/delete", methods=["POST"])
    @auth.login_required
    def delete_record(assessment_id: int):
        user = auth.current_user()
        record = database.get_assessment(assessment_id, user_id=user["id"])
        if not record:
            abort(404)
        database.delete_record(assessment_id)
        flash("已刪除該筆評估紀錄", "info")
        return redirect(url_for("records"))

    return app


def _decorate_record(record: dict) -> None:
    record["living_status_label"] = LIVING_LABELS.get(
        record.get("living_status"), record.get("living_status") or "未填"
    )
    record["caregiver_label"] = CAREGIVER_LABELS.get(
        record.get("caregiver"), record.get("caregiver") or "未填"
    )
    record["level_description"] = LEVEL_DESCRIPTIONS.get(
        record.get("risk_level_code"), ""
    )


def _safe_redirect_target(target: str | None) -> str | None:
    """避免開放重新導向：只允許站內相對路徑。"""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith("/"):
        return None
    return target


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    application = create_app()
    # 使用 8000 而非 5000，避開 macOS AirPlay Receiver 占用 port 5000 的問題
    application.run(host="127.0.0.1", port=8000, debug=True)

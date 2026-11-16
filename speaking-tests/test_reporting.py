"""Reports must preserve saved evidence and scores without invoking live services."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest

from backend.speaking.app import create_app
from backend.speaking.config import Settings
from backend.speaking.reporting.data import build_report_data
from backend.speaking.reporting.pdf import render_report


def report_session():
    answer = "I build a website with my classmates. We shared the work."
    evaluation = {"status": "available", "aspects": {
        "coherence": {"score": 6, "justification": "The answer connects two points."},
        "vocabulary": {"score": 0, "justification": "A real zero must stay zero."},
        "grammar": {"score": None, "justification": "Insufficient evidence."},
        "task_response": {"score": 7.5, "justification": "The answer addresses the question."}},
        "assessment_criteria": {
            "professional_performance": {"conceptual_accuracy": {"score": 6, "quote": "I build a website", "justification": "The example is relevant.", "suggestion": "Explain your own contribution."}},
            "oral_expression": {"accuracy": {"score": 9, "justification": "No independent assessment."}},
            "nonverbal": {"eye_contact": {"score": 8, "justification": "No candidate video."}}},
        "polishing": {"original": answer, "corrections": [{"original": "I build", "revised": "I built", "reason": "Use the past tense for a completed project."}]}}
    dimensions = [{"key": key, "score": item["score"], "comment": item["justification"]} for key, item in evaluation["aspects"].items()]
    turn = {"id": "answer-1", "question_id": "question-1", "question": "Describe a project you worked on.", "stage": "part1", "answer": answer,
            "transcript_available": True, "skipped": False, "audio_id": None, "pronunciation": {"status": "unavailable"}, "evaluation": evaluation,
            "voice_coach": {"metrics": {"words_per_minute": 120, "pause_count": 2, "speaking_span_seconds": 12},
                            "advice": {"status": "ok", "advice": "The estimated pace is 120 words per minute."}, "scope": "Energy-based estimates, not pronunciation scores."}}
    return {"id": "report-test", "created_at": "2026-11-16T10:00:00+08:00", "setup": {"exam": "ielts", "mode": "coach", "candidate_name": "QA learner"},
            "set_title": "Report verification fixture", "status": "completed", "turns": [turn], "plan": [{"id": "question-1"}], "index": 1,
            "messages": [], "recordings": {}, "pending_question_id": None,
            "report": {"source": "live_model", "summary": "A saved assessment used for report testing.", "dimensions": dimensions,
                       "examples": [], "strengths": ["Uses a relevant example."], "improvements": ["Explain the sequence more clearly."], "next_steps": ["Repeat the answer with one clear reason."],
                       "coverage": {"answered": 1, "submitted": 1, "skipped": 0, "planned": 1, "early_finish": False},
                       "layered": {"questions": [{"turn_id": "answer-1", **deepcopy(evaluation)}], "feature_names": {"conceptual_accuracy": "Content relevance", "accuracy": "Pronunciation accuracy", "eye_contact": "Eye contact"}}}}


def test_report_preserves_raw_scores_nulls_and_actual_evidence():
    session = report_session()
    original = deepcopy(session)
    view = build_report_data(session)
    assert [item["score"] for item in view["dimensions"]] == [6, 0, None, 7.5]
    question = view["questions"][0]
    assert question["revised_answer"].startswith("I built a website")
    assert question["groups"][0]["items"][0]["quote"] in question["answer"]
    assert question["groups"][1]["items"][0]["score"] is None
    assert question["groups"][2]["items"][0]["score"] is None
    assert session == original


@pytest.mark.parametrize("value", [True, "6", float("nan"), float("inf"), -1, 11])
def test_report_rejects_invalid_scores_without_display_mapping(value):
    session = report_session()
    session["report"]["dimensions"][0]["score"] = value
    assert build_report_data(session)["dimensions"][0]["score"] is None


def test_skipped_or_missing_transcript_does_not_receive_scores():
    session = report_session()
    session["turns"][0]["skipped"] = True
    question = build_report_data(session)["questions"][0]
    assert question["status"] == "skipped"
    assert all(item["score"] is None for item in question["dimensions"])


def test_aggregate_score_precision_and_pdf_page_content_are_preserved():
    session = report_session()
    session["report"]["dimensions"][0]["score"] = 6.25
    view = build_report_data(session)
    assert view["dimensions"][0]["score"] == 6.25
    pdf = PdfReader(BytesIO(render_report(view)))
    assert "6.25/10" in "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert all(len((page.extract_text() or "").strip()) > 100 for page in pdf.pages)


def test_pdf_is_searchable_paginated_and_handles_untrusted_long_text():
    session = report_session()
    session["turns"][0]["answer"] += " <script>literal text</script> & 你好\n" + "A long recorded answer. " * 180
    view = build_report_data(session)
    pdf = PdfReader(BytesIO(render_report(view)))
    content = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert len(pdf.pages) >= 4
    for expected in ["ispeak", "Contents", "Performance overview", "Answer review", "Question 1", "Next practice steps", "6/10", "0/10", "Not assessed", "literal text", "你好", "120 words per minute"]:
        assert expected in content
    assert "8/10" not in content
    assert pdf.outline


def test_pdf_and_web_use_saved_data_without_live_calls(tmp_path):
    class NoLiveCalls:
        async def complete(self, *args, **kwargs):
            raise AssertionError("Report export must not call a model")
    app = create_app(settings=replace(Settings(), runtime=tmp_path), provider=NoLiveCalls())
    session = report_session()
    app.state.engine.store.create(session)
    before = app.state.engine.store.get(session["id"])
    with TestClient(app) as client:
        data = client.get("/api/speaking/sessions/report-test/report-data")
        result = client.get("/api/speaking/sessions/report-test/report.pdf")
        assert data.status_code == result.status_code == 200
        assert data.json()["dimensions"][0]["score"] == 6
        assert result.headers["content-type"] == "application/pdf"
        assert "ispeak-speaking-report.pdf" in result.headers["content-disposition"]
        assert result.content.startswith(b"%PDF-")
        assert client.get("/api/speaking/sessions/unknown/report.pdf").status_code == 404
        pending = report_session(); pending.update(id="pending-report", report=None, status="active")
        app.state.engine.store.create(pending)
        assert client.get("/api/speaking/sessions/pending-report/report.pdf").status_code == 409
        pending = report_session(); pending.update(id="stale-report", status="active")
        app.state.engine.store.create(pending)
        assert client.get("/api/speaking/sessions/stale-report/report.pdf").status_code == 409
    assert app.state.engine.store.get(session["id"]) == before

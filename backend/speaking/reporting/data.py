"""One report contract for the web view and PDF. Never run an evaluator here."""
import math

DIMENSIONS = {
    "coherence": "Coherence and cohesion",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
    "task_response": "Task response and development",
}
GROUPS = {
    "professional_performance": "Content and task response",
    "way_of_expression": "Language and organization",
    "oral_expression": "Independent audio assessment",
    "nonverbal": "Candidate video assessment",
}
SCOPE = "Scores are 0-10 text-based practice metrics, not IELTS bands or TOEFL scores. Missing evidence remains unassessed."


def practice_score(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and 0 <= value <= 10 else None


def text(value):
    return value if isinstance(value, str) else ""


def strings(value):
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def dimension_items(values):
    output = []
    for key, label in DIMENSIONS.items():
        item = values.get(key) if isinstance(values, dict) else None
        item = item if isinstance(item, dict) else {}
        output.append({"key": key, "label": label, "score": practice_score(item.get("score")),
                       "comment": text(item.get("comment") or item.get("justification"))})
    return output


def build_report_data(session):
    report = session.get("report")
    if not report:
        raise ValueError("Feedback has not been generated yet.")
    layer = report.get("layered") or {}
    raw_dimensions = {item["key"]: item for item in report.get("dimensions", [])
                      if isinstance(item, dict) and item.get("key") in DIMENSIONS}
    dimensions = dimension_items(raw_dimensions)
    names = layer.get("feature_names") or {}
    evaluations = {item.get("turn_id"): item for item in layer.get("questions", []) if isinstance(item, dict)}
    questions = []
    for index, turn in enumerate(session.get("turns", []), 1):
        evaluation = evaluations.get(turn.get("id")) or turn.get("evaluation") or {}
        usable = not turn.get("skipped") and turn.get("transcript_available", True) and bool(text(turn.get("answer")).strip())
        groups = []
        for key, label in GROUPS.items():
            items = []
            for feature_key, feature in (evaluation.get("assessment_criteria", {}).get(key) or {}).items():
                if not isinstance(feature, dict):
                    continue
                quote = text(feature.get("quote"))
                # Text features must cite the actual answer; unavailable evidence never becomes zero.
                grounded = key not in ("professional_performance", "way_of_expression") or bool(quote and quote in turn.get("answer", ""))
                value = practice_score(feature.get("score")) if usable and grounded else None
                if key == "nonverbal":
                    value = None  # The current product does not collect candidate video.
                if key == "oral_expression" and turn.get("pronunciation", {}).get("status") != "available":
                    value = None
                items.append({"key": feature_key, "label": names.get(feature_key, feature_key.replace("_", " ").title()),
                              "score": value, "quote": quote if grounded else "",
                              "comment": text(feature.get("justification")), "suggestion": text(feature.get("suggestion"))})
            if items:
                groups.append({"key": key, "label": label, "items": items})
        polishing = evaluation.get("polishing") or {}
        corrections = []
        for item in polishing.get("corrections", []):
            if isinstance(item, dict) and text(item.get("original")).strip() and item["original"] in turn.get("answer", ""):
                corrections.append({key: text(item.get(key)) for key in ("original", "revised", "reason")})
        voice = turn.get("voice_coach") or {}
        revised_answer = text(turn.get("answer"))
        for correction in corrections:
            revised_answer = revised_answer.replace(correction["original"], correction["revised"], 1)
        metrics, advice = voice.get("metrics") or {}, voice.get("advice") or {}
        questions.append({"id": text(turn.get("id")), "number": index, "question": text(turn.get("question")),
                          "stage": text(turn.get("stage")), "answer": text(turn.get("answer")),
                          "status": "skipped" if turn.get("skipped") else "unavailable" if not usable else evaluation.get("status", "not_assessed"),
                          "dimensions": dimension_items(evaluation.get("aspects", {}) if usable else {}),
                          "groups": groups, "corrections": corrections, "revised_answer": revised_answer,
                          "voice": {"pace": metrics.get("words_per_minute"), "pauses": metrics.get("pause_count"),
                                    "span": metrics.get("speaking_span_seconds"), "advice": text(advice.get("advice")) if advice.get("status") == "ok" else "",
                                    "scope": text(voice.get("scope"))} if voice else None})
    setup = session.get("setup") or {}
    return {"version": "ispeak-report-v1", "session_id": session["id"], "title": text(session.get("set_title")),
            "exam": text(setup.get("exam")).upper(), "mode": text(setup.get("mode")),
            "candidate": text(setup.get("candidate_name")), "created_at": text(session.get("created_at")),
            "source": text(report.get("source")), "summary": text(report.get("summary")), "scope": SCOPE,
            "coverage": report.get("coverage") or {}, "dimensions": dimensions,
            "strengths": strings(report.get("strengths")), "improvements": strings(report.get("improvements")),
            "next_steps": strings(report.get("next_steps")), "questions": questions}

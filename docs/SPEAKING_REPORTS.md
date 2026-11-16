# ispeak assessment views and PDF reports

Completed practice sessions have an Overview with a four-dimension radar and an Answer review tab. Each answer includes the original transcript, assessed dimensions, evidence quotations, and safe revisions already returned by the evaluator. Details stay collapsed until requested.

The **Download PDF report** button generates a searchable A4 document with a cover, clickable contents, overview chart, dimension feedback, answer details, saved voice advice, and next practice steps. **Export JSON** and browser printing remain available.

## Data and scoring

- `GET /api/speaking/sessions/{id}/report-data` supplies the web assessment view.
- `GET /api/speaking/sessions/{id}/report.pdf` downloads the PDF from the same saved data contract.
- Both read the existing session store. Neither endpoint runs an LLM, speech service, avatar, or fine-tuned model, and neither modifies the saved assessment.
- Practice scores retain their original 0-10 values. There is no 5-10 display conversion. Missing, invalid, unavailable, or unsupported scores remain **Not assessed**. The radar draws a filled shape only when all four dimensions are available.
- Candidate-video criteria remain unassessed. Acoustic scores require an independent available audio assessment. Saved pace/pause advice is included only if it has already been generated through the existing voice-review module.
- Scores remain formative practice metrics, not official IELTS bands or TOEFL scores. Skipped answers and incomplete sessions are identified explicitly.

## Integration and provenance

The chart geometry, section navigation, question accordion pattern, and report composition are adapted from the user-provided PolyInterview project. `reporting/indexed_doc_template.py` reuses its table-of-contents and PDF-bookmark implementation. Domain labels, missing-evidence handling, and the session-data adapter are specific to ispeak. The original project is unchanged.

This feature adds ReportLab (`reportlab>=4,<5`) to `requirements-speaking.txt`. Install the updated requirements in the application's Python environment, then rebuild the frontend after source changes. No Docker or additional model is required for reporting.

## Verification

Reporting tests cover unchanged raw scores, missing evidence, unsupported audio/video scores, skipped answers, searchable multipage PDFs, Unicode and literal markup, completed-session enforcement, and export without model calls or state changes. Live media and fine-tuned inference remain in their existing modules.

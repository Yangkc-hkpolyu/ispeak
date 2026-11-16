"""Generate reports only from saved session data, never from client-supplied scores."""
import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .data import build_report_data


def report_router(store, engine):
    router = APIRouter(prefix="/api/speaking/sessions", tags=["assessment reports"])

    def saved_report(session_id):
        current = store.get(session_id)
        if current.get("status") != "completed" or not current.get("report"):
            raise HTTPException(409, "Finish this session and generate feedback before downloading a report.")
        return build_report_data(engine.public(current))

    @router.get("/{session_id}/report-data")
    async def report_data(session_id: str):
        return saved_report(session_id)

    @router.get("/{session_id}/report.pdf")
    async def report_pdf(session_id: str):
        from .pdf import render_report

        data = saved_report(session_id)
        content = await asyncio.to_thread(render_report, data)
        return Response(content, media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="ispeak-speaking-report.pdf"',
            "Cache-Control": "no-store",
        })

    return router

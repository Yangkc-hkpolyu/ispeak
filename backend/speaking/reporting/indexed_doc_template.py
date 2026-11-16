"""Custom BaseDocTemplate that drives the TableOfContents flowable.

Watches for paragraphs with style name 'TOCHeading1' / 'TOCHeading2', notifies
a TOCEntry with a content-relative page number, bookmarks the page, and adds a
PDF outline entry. Also tracks the first content page so the footer can skip
frontmatter (cover + TOC pages) and start numbering at 1 on Overall Performance.

Multi-pass note: ReportLab's multiBuild may run several passes until the TOC
layout converges. `first_content_page` is set in afterFlowable AFTER the
first level-0 heading is placed, but the per-page footer hook (onPage) runs
BEFORE the first flowable on each page. To make the first content page's
footer render correctly, we persist `first_content_page` across passes (only
the per-pass detection flag is reset at handle_documentBegin). At convergence
multiBuild stops iterating only when layout is stable, so the prior pass's
value equals the current pass's actual first content page.
"""
import itertools

from reportlab.platypus import BaseDocTemplate, Paragraph


class IndexedDocTemplate(BaseDocTemplate):
    """BaseDocTemplate variant with afterFlowable wired for TOC building."""

    _STYLE_TO_LEVEL = {"TOCHeading1": 0, "TOCHeading2": 1}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cross-pass anchor used by the onPage footer callback.
        self.first_content_page: int | None = None
        # Per-pass detection flag, reset at handle_documentBegin.
        self._pass_first_content_page: int | None = None
        self._toc_key_counter = itertools.count()

    def handle_documentBegin(self):
        """Reset per-pass state so each multiBuild pass produces stable keys.

        `first_content_page` is intentionally NOT reset here: the onPage footer
        callback needs the prior pass's value on the first content page, since
        onPage fires before afterFlowable for that page.
        """
        super().handle_documentBegin()
        self._pass_first_content_page = None
        self._toc_key_counter = itertools.count()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        level = self._STYLE_TO_LEVEL.get(flowable.style.name)
        if level is None:
            return
        text = flowable.getPlainText()
        key = f"toc-{next(self._toc_key_counter)}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=(level > 0))
        if level == 0 and self._pass_first_content_page is None:
            self._pass_first_content_page = self.page
            # Publish for the next pass's onPage callbacks.
            self.first_content_page = self.page
        base = self._pass_first_content_page or self.page
        content_page = self.page - base + 1
        self.notify("TOCEntry", (level, text, content_page, key))

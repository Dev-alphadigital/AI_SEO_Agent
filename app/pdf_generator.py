"""
PDF report generator — converts Markdown SEO reports to professional PDFs.

Pipeline: Markdown → HTML (with tables extension) → Styled HTML → PDF (Playwright/Chromium).

Uses Playwright (already installed) for pixel-perfect rendering.
"""

import re
from pathlib import Path
from typing import Optional

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# ---------------------------------------------------------------------------
# CSS for professional PDF layout
# ---------------------------------------------------------------------------
PDF_CSS = """
@page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;

    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: #888;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
    font-size: 11px;
    line-height: 1.55;
    color: #1a1a1a;
    max-width: 100%;
    overflow-wrap: break-word;
    word-wrap: break-word;
}

/* ---- Headings ---- */
h1 {
    font-size: 22px;
    font-weight: 700;
    color: #111;
    border-bottom: 3px solid #2563eb;
    padding-bottom: 8px;
    margin: 0 0 12px 0;
    page-break-after: avoid;
}

h2 {
    font-size: 16px;
    font-weight: 600;
    color: #1e3a5f;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 5px;
    margin: 24px 0 10px 0;
    page-break-after: avoid;
}

h3 {
    font-size: 13px;
    font-weight: 600;
    color: #334155;
    margin: 16px 0 6px 0;
    page-break-after: avoid;
}

h4 {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    margin: 12px 0 4px 0;
}

/* ---- Paragraphs & lists ---- */
p {
    margin: 0 0 8px 0;
}

ul, ol {
    margin: 4px 0 10px 0;
    padding-left: 22px;
}

li {
    margin-bottom: 3px;
}

strong {
    font-weight: 600;
    color: #111;
}

em {
    color: #555;
}

hr {
    border: none;
    border-top: 1.5px solid #e2e8f0;
    margin: 16px 0;
}

/* ---- Tables — the core of SEO reports ---- */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px 0;
    font-size: 9px;
    line-height: 1.4;
    table-layout: auto;
    page-break-inside: auto;
}

thead {
    display: table-header-group;
}

tr {
    page-break-inside: avoid;
    page-break-after: auto;
}

th {
    background-color: #1e3a5f;
    color: #fff;
    font-weight: 600;
    text-align: left;
    padding: 5px 5px;
    border: 1px solid #1e3a5f;
    overflow-wrap: break-word;
    word-wrap: break-word;
}

td {
    padding: 4px 5px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
    overflow-wrap: break-word;
    word-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
}

/* Zebra striping */
tbody tr:nth-child(even) {
    background-color: #f8fafc;
}

tbody tr:hover {
    background-color: #eff6ff;
}

/* ---- Wide tables (6+ cols): SERP competitor overview, keyword competition ---- */
table.table-wide {
    font-size: 8px;
}

table.table-wide th:first-child,
table.table-wide td:first-child {
    width: 24px;
    text-align: center;
    white-space: nowrap;
}

/* "Why They Rank" / last column gets generous space */
table.table-wide td:last-child {
    min-width: 120px;
}

/* Numeric columns stay compact */
table.table-wide td {
    white-space: normal;
}

/* ---- Medium tables (4-5 cols): keyword targets ---- */
table.table-medium {
    font-size: 9px;
}

/* ---- Narrow tables (2-3 cols): recommendations, internal linking ---- */
table.table-narrow {
    font-size: 9px;
}

table.table-narrow td {
    max-width: none;
    white-space: normal;
}

table.table-narrow th,
table.table-narrow td {
    padding: 5px 8px;
}

/* ---- Code / inline code ---- */
code {
    background-color: #f1f5f9;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
}

/* ---- Links ---- */
a {
    color: #2563eb;
    text-decoration: none;
}

/* ---- Client profile box ---- */
.client-profile {
    background-color: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 10px 0 16px 0;
}

/* ---- Cover / header area ---- */
.report-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: #fff;
    padding: 24px 28px;
    border-radius: 8px;
    margin-bottom: 20px;
}

.report-header h1 {
    color: #fff;
    border-bottom: none;
    margin: 0 0 8px 0;
    font-size: 24px;
}

.report-header p {
    color: #cbd5e1;
    margin: 2px 0;
    font-size: 12px;
}

/* ---- Issue / alert callout ---- */
.issue-box {
    background-color: #fef2f2;
    border-left: 4px solid #dc2626;
    padding: 8px 12px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
}

/* Prevent page breaks inside important sections */
h2 + *, h3 + * {
    page-break-before: avoid;
}
"""


def _classify_tables(html: str) -> str:
    """Add CSS classes to tables based on column count for smart styling."""
    def _replace_table(match):
        table_html = match.group(0)
        # Count <th> tags in the first <tr> or <thead>
        th_count = len(re.findall(r'<th', table_html.split('</tr>')[0]))
        if th_count >= 6:
            # Wide SERP-style table: narrow "#" first column
            return table_html.replace('<table>', '<table class="table-wide">', 1)
        elif th_count <= 3:
            # Narrow recommendation/linking table: equal flexible columns
            return table_html.replace('<table>', '<table class="table-narrow">', 1)
        else:
            # Medium table (4-5 cols like keyword targets)
            return table_html.replace('<table>', '<table class="table-medium">', 1)
    return re.sub(r'<table>.*?</table>', _replace_table, html, flags=re.DOTALL)


def _md_to_styled_html(md_content: str) -> str:
    """Convert markdown to a fully styled HTML document ready for PDF rendering."""
    if not HAS_MARKDOWN:
        raise ImportError("Install 'markdown' package: pip install markdown")

    # Convert MD → HTML
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )

    # Post-process: classify tables by column count for smart CSS
    html_body = _classify_tables(html_body)

    # Post-process: wrap client profile section in a styled box
    html_body = re.sub(
        r'(<p><strong>Client:</strong>.*?)((?=<h)|$)',
        r'<div class="client-profile">\1</div>\2',
        html_body,
        count=1,
        flags=re.DOTALL,
    )

    # Post-process: extract title + subtitle for a styled header
    header_html = ""
    # Match the first <h1> and the <h2> + <p> that follow
    h1_match = re.search(r'<h1>(.*?)</h1>', html_body)
    h2_match = re.search(r'<h2>Target:\s*(.*?)\s*\|\s*Keyword:\s*(.*?)</h2>', html_body)
    date_match = re.search(r'<p><em>Generated:\s*(.*?)</em></p>', html_body)

    if h1_match:
        title = h1_match.group(1)
        url_text = ""
        keyword_text = ""
        date_text = ""

        if h2_match:
            url_text = h2_match.group(1).strip()
            keyword_text = h2_match.group(2).strip()
        if date_match:
            date_text = date_match.group(1).strip()

        header_html = f'''<div class="report-header">
            <h1>{title}</h1>
            {"<p><strong>URL:</strong> " + url_text + "</p>" if url_text else ""}
            {"<p><strong>Keyword:</strong> " + keyword_text + "</p>" if keyword_text else ""}
            {"<p><strong>Generated:</strong> " + date_text + "</p>" if date_text else ""}
        </div>'''

        # Remove the original h1, h2 (target line), date line, and <hr>
        html_body = re.sub(r'<h1>.*?</h1>\s*', '', html_body, count=1)
        html_body = re.sub(r'<h2>Target:.*?</h2>\s*', '', html_body, count=1)
        html_body = re.sub(r'<p><em>Generated:.*?</em></p>\s*', '', html_body, count=1)
        html_body = re.sub(r'^<hr\s*/?>\s*', '', html_body.strip(), count=1)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>{PDF_CSS}</style>
</head>
<body>
{header_html}
{html_body}
</body>
</html>"""

    return full_html


def generate_pdf(
    md_content: str,
    output_path: str,
    timeout: int = 30000,
) -> dict:
    """
    Convert a Markdown SEO report to a professionally styled PDF.

    Args:
        md_content: The full markdown report content.
        output_path: Path to save the PDF file.
        timeout: Playwright page timeout in ms.

    Returns:
        {"success": bool, "error": str|None, "path": str}
    """
    if not HAS_PLAYWRIGHT:
        return {"success": False, "error": "Playwright not installed. Run: pip install playwright && playwright install chromium", "path": ""}

    if not HAS_MARKDOWN:
        return {"success": False, "error": "Markdown not installed. Run: pip install markdown", "path": ""}

    try:
        styled_html = _md_to_styled_html(md_content)

        # Ensure output directory exists
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Use Playwright Chromium to render HTML → PDF
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(styled_html, wait_until="networkidle", timeout=timeout)

            # Small delay to ensure CSS is fully applied
            page.wait_for_timeout(500)

            page.pdf(
                path=str(out),
                format="A4",
                margin={
                    "top": "20mm",
                    "bottom": "20mm",
                    "left": "15mm",
                    "right": "15mm",
                },
                print_background=True,
                display_header_footer=True,
                header_template='<span></span>',
                footer_template='''
                    <div style="font-size:9px; color:#888; width:100%; text-align:center; padding:0 15mm;">
                        Page <span class="pageNumber"></span> of <span class="totalPages"></span>
                    </div>
                ''',
            )
            browser.close()

        return {"success": True, "error": None, "path": str(out)}

    except Exception as e:
        return {"success": False, "error": str(e), "path": ""}


def md_file_to_pdf(md_path: str, pdf_path: Optional[str] = None) -> dict:
    """
    Convenience: read a .md file and convert it to PDF.

    Args:
        md_path: Path to the markdown file.
        pdf_path: Output PDF path. If None, uses same name with .pdf extension.

    Returns:
        {"success": bool, "error": str|None, "path": str}
    """
    md_file = Path(md_path)
    if not md_file.exists():
        return {"success": False, "error": f"File not found: {md_path}", "path": ""}

    md_content = md_file.read_text(encoding="utf-8")

    if not pdf_path:
        pdf_path = str(md_file.with_suffix(".pdf"))

    return generate_pdf(md_content, pdf_path)

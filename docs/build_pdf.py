"""
build_pdf.py — Convert executive_report.md to a polished PDF.

Uses the fpdf2 library (MIT-licensed, pure-Python) with DejaVu fonts
for Unicode support.

Usage:
    python build_pdf.py
"""

import re
import os
import textwrap
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH    = os.path.join(SCRIPT_DIR, "executive_report.md")
FIG_DIR    = os.path.join(SCRIPT_DIR, "figures")
OUT_PATH   = os.path.join(SCRIPT_DIR, "VisionMetrics_AI_Executive_Report.pdf")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
CLR_DARK      = (30, 30, 40)
CLR_HEADING1  = (20, 60, 120)
CLR_HEADING2  = (30, 80, 150)
CLR_HEADING3  = (50, 100, 170)
CLR_BODY      = (40, 40, 50)
CLR_CAPTION   = (100, 100, 120)
CLR_ACCENT    = (0, 102, 204)
CLR_TABLE_HDR = (30, 70, 130)
CLR_TABLE_ALT = (235, 240, 250)
CLR_RULE      = (180, 190, 210)
CLR_REF       = (60, 60, 80)

# ---------------------------------------------------------------------------
# Custom PDF class
# ---------------------------------------------------------------------------
class ReportPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=25)

        # Use Arial TTF for Unicode support on Windows
        fonts_dir = r"C:\Windows\Fonts"
        arial_regular = os.path.join(fonts_dir, "arial.ttf")
        if os.path.isfile(arial_regular):
            self.add_font("ArialUni", "", arial_regular, uni=True)
            self.add_font("ArialUni", "B", os.path.join(fonts_dir, "arialbd.ttf"), uni=True)
            self.add_font("ArialUni", "I", os.path.join(fonts_dir, "ariali.ttf"), uni=True)
            self.add_font("ArialUni", "BI", os.path.join(fonts_dir, "arialbi.ttf"), uni=True)
            self.font_family_main = "ArialUni"
        else:
            self.font_family_main = "Helvetica"

        self._page_count = 0

    # -- header / footer --
    def header(self):
        if self.page_no() == 1:
            return  # title page has its own header
        self.set_font(self.font_family_main, "I", 8)
        self.set_text_color(*CLR_CAPTION)
        self.cell(0, 8, "VisionMetrics AI — Executive Report", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*CLR_RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family_main, "I", 7)
        self.set_text_color(*CLR_CAPTION)
        self.cell(0, 10, f"— {self.page_no()} —", align="C")


# ---------------------------------------------------------------------------
# Markdown parser / renderer
# ---------------------------------------------------------------------------
def clean_md(text: str) -> str:
    """Strip HTML anchor tags used for references."""
    text = re.sub(r'<a id="ref\d+"></a>', '', text)
    # Replace rare Unicode arrows that may be missing from the font
    text = text.replace('\u21d2', '=>')
    return text

def strip_inline(text: str) -> str:
    """Remove markdown bold/italic markers for plain text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Replace markdown references [[N]](#refN) with [N]
    text = re.sub(r'\[\[(\d+)\]\]\(#ref\d+\)', r'[\1]', text)
    # Remove markdown links, keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text

def render_inline(pdf: ReportPDF, text: str, size: float = 10, color=CLR_BODY, align: str = "J"):
    """Render a paragraph with inline bold and italic via multi_cell."""
    # For simplicity, we render the whole paragraph with multi_cell.
    # We handle bold/italic by splitting into segments.
    pdf.set_font(pdf.font_family_main, "", size)
    pdf.set_text_color(*color)

    # Replace markdown references [[N]](#refN) with [N]
    text = re.sub(r'\[\[(\d+)\]\]\(#ref\d+\)', r'[\1]', text)
    # Replace markdown links [text](url) with text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # We'll use a simple approach: write segments with style changes
    segments = []
    pos = 0
    # Pattern for **bold** and *italic*
    pattern = re.compile(r'(\*\*(.+?)\*\*|\*(.+?)\*)')
    for m in pattern.finditer(text):
        if m.start() > pos:
            segments.append(("", text[pos:m.start()]))
        if m.group(2):  # bold
            segments.append(("B", m.group(2)))
        elif m.group(3):  # italic
            segments.append(("I", m.group(3)))
        pos = m.end()
    if pos < len(text):
        segments.append(("", text[pos:]))

    if not segments:
        segments = [("", text)]

    # Use write() for inline styling
    line_h = size * 0.45  # approximate line height in mm
    for style, seg in segments:
        pdf.set_font(pdf.font_family_main, style, size)
        pdf.write(line_h, seg)
    pdf.ln(line_h + 2)


def parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse a markdown table into headers and rows."""
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:  # skip separator
        row = [c.strip() for c in line.strip("|").split("|")]
        rows.append(row)
    return headers, rows


def render_table(pdf: ReportPDF, headers: list[str], rows: list[list[str]]):
    """Render a table with styled header and alternating rows."""
    num_cols = len(headers)
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable_w / num_cols

    # Compute column widths proportionally based on content
    max_lens = []
    for i in range(num_cols):
        ml = len(strip_inline(headers[i]))
        for row in rows:
            if i < len(row):
                ml = max(ml, len(strip_inline(row[i])))
        max_lens.append(max(ml, 5))
    total = sum(max_lens)
    col_ws = [usable_w * (ml / total) for ml in max_lens]

    # Ensure minimum column width
    min_w = 18
    for i in range(len(col_ws)):
        if col_ws[i] < min_w:
            col_ws[i] = min_w

    # Re-normalise
    total2 = sum(col_ws)
    col_ws = [usable_w * (w / total2) for w in col_ws]

    row_h = 7
    pdf.set_font(pdf.font_family_main, "B", 8)

    # Check if we need a page break for the table
    estimated_height = row_h * (len(rows) + 1) + 4
    if pdf.get_y() + estimated_height > pdf.h - 30:
        pdf.add_page()

    # Header
    pdf.set_fill_color(*CLR_TABLE_HDR)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(col_ws[i], row_h, strip_inline(h)[:50], border=1, fill=True, align="C")
    pdf.ln()

    # Rows
    pdf.set_font(pdf.font_family_main, "", 8)
    for ri, row in enumerate(rows):
        if ri % 2 == 0:
            pdf.set_fill_color(*CLR_TABLE_ALT)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(*CLR_BODY)
        max_lines = 1
        # Calculate how many lines each cell needs
        cell_texts = []
        cell_lines_list = []
        for ci in range(num_cols):
            txt = strip_inline(row[ci]) if ci < len(row) else ""
            # Approximate characters per line
            chars_per_line = max(int(col_ws[ci] / 1.8), 10)
            wrapped = textwrap.wrap(txt, width=chars_per_line) or [""]
            cell_texts.append(wrapped)
            cell_lines_list.append(len(wrapped))
            max_lines = max(max_lines, len(wrapped))

        cell_h = row_h * max_lines
        # Check page break
        if pdf.get_y() + cell_h > pdf.h - 25:
            pdf.add_page()

        y_start = pdf.get_y()
        for ci in range(num_cols):
            x = pdf.l_margin + sum(col_ws[:ci])
            pdf.set_xy(x, y_start)
            fill = True
            # Draw cell background
            pdf.cell(col_ws[ci], cell_h, "", border=1, fill=fill)
            # Write text inside
            pdf.set_xy(x + 1, y_start + 1)
            for li, line in enumerate(cell_texts[ci]):
                pdf.set_xy(x + 1, y_start + 1 + li * row_h)
                align = "R" if line.replace(",", "").replace(".", "").replace("+", "").replace("–", "").replace("-", "").replace("€", "").replace(" ", "").replace("~", "").isdigit() else "L"
                pdf.cell(col_ws[ci] - 2, row_h - 1, line, align=align)

        pdf.set_y(y_start + cell_h)

    pdf.ln(4)


def build_pdf():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        raw = f.read()

    raw = clean_md(raw)
    lines = raw.split("\n")

    pdf = ReportPDF()
    pdf.set_margins(20, 20, 20)

    # -----------------------------------------------------------------------
    # Title page
    # -----------------------------------------------------------------------
    pdf.add_page()

    pdf.ln(50)
    pdf.set_font(pdf.font_family_main, "B", 28)
    pdf.set_text_color(*CLR_HEADING1)
    pdf.cell(0, 14, "VisionMetrics AI", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(pdf.font_family_main, "", 14)
    pdf.set_text_color(*CLR_BODY)
    pdf.cell(0, 8, "Privacy-preserving computer vision", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "for retail showcase analytics", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Decorative line
    pdf.set_draw_color(*CLR_ACCENT)
    pdf.set_line_width(0.8)
    cx = pdf.w / 2
    pdf.line(cx - 40, pdf.get_y(), cx + 40, pdf.get_y())
    pdf.ln(8)

    pdf.set_font(pdf.font_family_main, "", 11)
    pdf.set_text_color(*CLR_BODY)
    pdf.cell(0, 7, "Executive Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font(pdf.font_family_main, "I", 10)
    pdf.set_text_color(*CLR_CAPTION)
    pdf.cell(0, 6, "Author: Alvaro Martinez", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Course: AI / ML Analytics Final Project", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Date: April 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    # -----------------------------------------------------------------------
    # Body
    # -----------------------------------------------------------------------
    pdf.add_page()

    i = 0
    # Skip the first 7 lines (title block)
    while i < len(lines) and not lines[i].startswith("## "):
        i += 1

    table_buffer = []
    in_table = False
    in_list = False
    list_items = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if stripped == "":
            if in_table:
                headers, rows = parse_table(table_buffer)
                render_table(pdf, headers, rows)
                table_buffer = []
                in_table = False
            if in_list and list_items:
                _flush_list(pdf, list_items)
                list_items = []
                in_list = False
            i += 1
            continue

        # Horizontal rule
        if stripped == "---":
            if in_table:
                headers, rows = parse_table(table_buffer)
                render_table(pdf, headers, rows)
                table_buffer = []
                in_table = False
            if in_list and list_items:
                _flush_list(pdf, list_items)
                list_items = []
                in_list = False
            pdf.ln(2)
            pdf.set_draw_color(*CLR_RULE)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        # Table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            # Skip separator rows for detection but keep them for parsing
            table_buffer.append(stripped)
            i += 1
            continue
        elif in_table:
            headers, rows = parse_table(table_buffer)
            render_table(pdf, headers, rows)
            table_buffer = []
            in_table = False
            # Don't increment i, re-process this line
            continue

        # Headings
        if stripped.startswith("## "):
            if in_list and list_items:
                _flush_list(pdf, list_items)
                list_items = []
                in_list = False
            title = stripped[3:].strip()
            # Check space for heading
            if pdf.get_y() > pdf.h - 50:
                pdf.add_page()
            pdf.ln(6)
            pdf.set_font(pdf.font_family_main, "B", 16)
            pdf.set_text_color(*CLR_HEADING1)
            pdf.cell(0, 10, strip_inline(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*CLR_ACCENT)
            pdf.set_line_width(0.6)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 50, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        if stripped.startswith("### "):
            if in_list and list_items:
                _flush_list(pdf, list_items)
                list_items = []
                in_list = False
            title = stripped[4:].strip()
            if pdf.get_y() > pdf.h - 40:
                pdf.add_page()
            pdf.ln(4)
            pdf.set_font(pdf.font_family_main, "B", 12)
            pdf.set_text_color(*CLR_HEADING2)
            pdf.cell(0, 8, strip_inline(title), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue

        # Figure / image
        fig_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', stripped)
        if fig_match:
            if in_list and list_items:
                _flush_list(pdf, list_items)
                list_items = []
                in_list = False
            alt_text = fig_match.group(1)
            img_path = fig_match.group(2)
            # Resolve relative path
            if not os.path.isabs(img_path):
                img_path = os.path.join(SCRIPT_DIR, img_path)
            if os.path.isfile(img_path):
                # Check space
                if pdf.get_y() > pdf.h - 100:
                    pdf.add_page()
                pdf.ln(4)
                # Centre the image
                img_w = min(140, pdf.w - pdf.l_margin - pdf.r_margin)
                x_offset = (pdf.w - img_w) / 2
                pdf.image(img_path, x=x_offset, w=img_w)
                pdf.ln(2)
            else:
                pdf.set_font(pdf.font_family_main, "I", 9)
                pdf.set_text_color(*CLR_CAPTION)
                pdf.cell(0, 6, f"[Figure not found: {img_path}]", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Figure caption (italic line after image)
        if stripped.startswith("*Figure") or stripped.startswith("*Table"):
            caption = stripped.strip("*")
            pdf.set_font(pdf.font_family_main, "I", 9)
            pdf.set_text_color(*CLR_CAPTION)
            pdf.multi_cell(0, 5, strip_inline(caption), align="C")
            pdf.ln(4)
            i += 1
            continue

        # List items
        if re.match(r'^[-*]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            in_list = True
            # Determine indent level
            leading_spaces = len(line) - len(line.lstrip())
            is_numbered = bool(re.match(r'^\d+\.\s', stripped))
            # Clean the item
            if is_numbered:
                item_text = re.sub(r'^\d+\.\s*', '', stripped)
                prefix = re.match(r'^(\d+)\.\s', stripped).group(1) + "."
            else:
                item_text = re.sub(r'^[-*]\s*', '', stripped)
                prefix = "\u2022"

            list_items.append((prefix, item_text, leading_spaces))
            i += 1
            continue

        if in_list and list_items:
            _flush_list(pdf, list_items)
            list_items = []
            in_list = False

        # References section
        if stripped.startswith("[") and re.match(r'^\[\d+\]', stripped):
            pdf.set_font(pdf.font_family_main, "", 8)
            pdf.set_text_color(*CLR_REF)
            ref_text = strip_inline(stripped)
            pdf.multi_cell(0, 4.5, ref_text)
            pdf.ln(1.5)
            i += 1
            continue

        # Regular paragraph
        if stripped:
            render_inline(pdf, stripped, size=10, color=CLR_BODY)
            pdf.ln(1)

        i += 1

    # Flush any remaining
    if in_table and table_buffer:
        headers, rows = parse_table(table_buffer)
        render_table(pdf, headers, rows)
    if in_list and list_items:
        _flush_list(pdf, list_items)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    pdf.output(OUT_PATH)
    print(f"\n  PDF saved to: {OUT_PATH}\n")


def _flush_list(pdf: ReportPDF, items: list[tuple[str, str, int]]):
    """Render accumulated list items."""
    for prefix, text, indent in items:
        indent_mm = 4 + indent * 2
        pdf.set_x(pdf.l_margin + indent_mm)
        pdf.set_font(pdf.font_family_main, "B", 10)
        pdf.set_text_color(*CLR_BODY)
        pdf.cell(8, 5, prefix, align="R")
        pdf.set_x(pdf.l_margin + indent_mm + 9)
        pdf.set_font(pdf.font_family_main, "", 10)

        # Handle bold segments in list items
        text = re.sub(r'\[\[(\d+)\]\]\(#ref\d+\)', r'[\1]', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        segments = []
        pos = 0
        pattern = re.compile(r'(\*\*(.+?)\*\*|\*(.+?)\*)')
        for m in pattern.finditer(text):
            if m.start() > pos:
                segments.append(("", text[pos:m.start()]))
            if m.group(2):
                segments.append(("B", m.group(2)))
            elif m.group(3):
                segments.append(("I", m.group(3)))
            pos = m.end()
        if pos < len(text):
            segments.append(("", text[pos:]))
        if not segments:
            segments = [("", text)]

        avail_w = pdf.w - pdf.r_margin - pdf.get_x()
        # Write first with write() for inline styling
        for style, seg in segments:
            pdf.set_font(pdf.font_family_main, style, 10)
            pdf.write(5, seg)
        pdf.ln(6)


if __name__ == "__main__":
    build_pdf()

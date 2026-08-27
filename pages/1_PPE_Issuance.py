"""
PPE Issuance Form — Baran Telecom Networks / Tech 7 Automation Systems /
Exhenb Engineering Ltd JV
--------------------------------------------------------------------------
Same pattern as the Payment Voucher: add each person being issued PPE,
they sign to confirm receipt, and one approver (usually the site safety
officer / storekeeper's supervisor) signs once at the end after every
entity has been added.

DESIGN DECISIONS (opinionated, on purpose)
--------------------------------------------------------------------------
1. Columns: No., Issued To, Phone Number, Site Name, PPEs, Signature —
   mirrors the Payment Voucher exactly, with Amount swapped out for a PPE
   checklist, since this form issues equipment, not money.

2. PPEs are five fixed tick-boxes (Reflective Vest, Gloves, Safety Boots,
   Helmet, Overall) rather than a free-text field. A typed-in list of PPE
   invites inconsistent spelling/naming across forms and makes it hard to
   later answer "how many pairs of gloves did we give out this month" —
   fixed items keep the record queryable. If the site issues something
   outside these five, there's a free-text "Other" box so the form
   doesn't block on it, but it doesn't get its own dedicated tick column.

3. Approved By is a single signature, collected once, after every entity
   has been added — same reasoning as the Payment Voucher: whoever
   approves is signing off the whole day's/site's issuance, not each line.
   The "+ Add Entity" button sits above it for the same reason.

4. This lives in Streamlit's native pages/ folder so it shows up as a
   second page in the same app as the Payment Voucher, sharing the same
   letterhead and deployment — one link for the team, two forms.

5. No amount, no totals — this isn't a financial document, so those
   fields were dropped rather than left empty.
"""

import os
import io
import csv
import uuid
from datetime import date, datetime

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from PIL import Image as PILImage

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.dirname(__file__))  # parent of pages/
LETTERHEAD_PATH = os.path.join(APP_DIR, "letterhead.png")
LOG_PATH = os.path.join(APP_DIR, "ppe_issuance_log.csv")

PPE_ITEMS = ["Reflective Vest", "Gloves", "Safety Boots", "Helmet", "Overall"]

st.set_page_config(page_title="PPE Issuance Form", page_icon="🦺", layout="centered")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def next_form_number() -> str:
    """Sequential form number: PPE-YYYYMMDD-### based on today's log entries."""
    today_str = date.today().strftime("%Y%m%d")
    count_today = 1
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
            count_today += sum(1 for r in rows if r.get("form_no", "").startswith(f"PPE-{today_str}"))
    return f"PPE-{today_str}-{count_today:03d}"


def canvas_to_png_bytes(canvas_result):
    """Convert a signature canvas result to PNG bytes on white background, or None if blank."""
    if canvas_result is None or canvas_result.image_data is None or canvas_result.image_data[:, :, 3].sum() == 0:
        return None
    sig_img = PILImage.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
    white_bg = PILImage.new("RGBA", sig_img.size, "WHITE")
    white_bg.paste(sig_img, mask=sig_img)
    buf = io.BytesIO()
    white_bg.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def sig_cell(png_bytes, w=20 * mm, h=8 * mm):
    """Small signature thumbnail for a table cell, or a dash if unsigned."""
    if png_bytes:
        return RLImage(io.BytesIO(png_bytes), width=w, height=h)
    return Paragraph("—", getSampleStyleSheet()["Normal"])


def ppe_checklist_cell(ticked: dict, other: str, style):
    """Render the 5 fixed PPE items as a tick/blank checklist, plus 'Other' if given."""
    lines = []
    for item in PPE_ITEMS:
        mark = "[X]" if ticked.get(item) else "[ ]"
        lines.append(f"{mark} {item}")
    if other:
        lines.append(f"[X] {other}")
    return Paragraph("<br/>".join(lines), style)


def build_pdf(form_no: str, form_date: str, rows: list, approved_name: str, approved_png: bytes) -> bytes:
    """rows: list of dicts with issued_to, phone, site_name, ppes (dict), other, signature_png."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=15)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5)
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, alignment=TA_LEFT, leading=10)
    checklist_style = ParagraphStyle("Checklist", parent=styles["Normal"], fontSize=7.5,
                                      alignment=TA_LEFT, leading=9.5, fontName="Helvetica")
    header_cell_style = ParagraphStyle("HeaderCell", parent=styles["Normal"], fontName="Helvetica-Bold",
                                        fontSize=8.5, alignment=TA_CENTER, textColor=colors.white)
    sig_name_style = ParagraphStyle("SigName", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9)
    sig_caption_style = ParagraphStyle("SigCaption", parent=styles["Normal"], alignment=TA_CENTER,
                                        fontSize=7.5, textColor=colors.grey)

    story = []

    # --- Letterhead ---
    if os.path.exists(LETTERHEAD_PATH):
        with PILImage.open(LETTERHEAD_PATH) as im:
            w, h = im.size
        target_w = 174 * mm
        target_h = target_w * (h / w)
        story.append(RLImage(LETTERHEAD_PATH, width=target_w, height=target_h))
    story.append(Spacer(1, 3 * mm))
    story.append(Table([[""]], colWidths=[174 * mm], style=TableStyle(
        [("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.black)])))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("PPE ISSUANCE FORM", title_style))
    story.append(Spacer(1, 4 * mm))

    meta_table = Table(
        [[Paragraph(f"<b>Form No.</b> &nbsp; {form_no}", label_style),
          Paragraph(f"<b>Dated:</b> &nbsp; {form_date}", label_style)]],
        colWidths=[87 * mm, 87 * mm],
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # --- Entity rows table ---
    # Column widths sum to 174mm (content width)
    col_widths = [8 * mm, 32 * mm, 22 * mm, 26 * mm, 64 * mm, 22 * mm]
    header = [Paragraph(h, header_cell_style) for h in
              ["No.", "Issued To", "Phone No.", "Site Name", "PPEs", "Signature"]]
    table_data = [header]
    for i, r in enumerate(rows, start=1):
        table_data.append([
            Paragraph(str(i), cell_style),
            Paragraph(r["issued_to"], cell_style),
            Paragraph(r["phone"] or "-", cell_style),
            Paragraph(r["site_name"] or "-", cell_style),
            ppe_checklist_cell(r["ppes"], r.get("other", ""), checklist_style),
            sig_cell(r["signature_png"]),
        ])

    rows_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    rows_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2d3d")),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(rows_table)
    story.append(Spacer(1, 14 * mm))

    # --- Approved By (single sign-off for the whole batch) ---
    approved_table = Table(
        [
            [Paragraph("<b>Approved By</b>", label_style)],
            [sig_cell(approved_png, w=55 * mm, h=20 * mm)],
            [Paragraph(approved_name or "", sig_name_style)],
            [Paragraph("Name &amp; Signature", sig_caption_style)],
        ],
        colWidths=[65 * mm],
        rowHeights=[7 * mm, 22 * mm, 6 * mm, 5 * mm],
    )
    approved_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 1), (-1, 1), "BOTTOM"),
        ("LINEABOVE", (0, 2), (0, 2), 0.75, colors.black),
        ("TOPPADDING", (0, 2), (-1, 2), 3),
    ]))
    story.append(approved_table)

    doc.build(story)
    return buffer.getvalue()


# --------------------------------------------------------------------
# UI
# --------------------------------------------------------------------
if os.path.exists(LETTERHEAD_PATH):
    st.image(LETTERHEAD_PATH, use_container_width=True)
st.title("PPE Issuance Form")
st.caption("Add each person receiving PPE, tick what they were given, then have the approver sign once at the end.")

if "ppe_form_no" not in st.session_state:
    st.session_state.ppe_form_no = next_form_number()
if "ppe_entity_ids" not in st.session_state:
    st.session_state.ppe_entity_ids = [str(uuid.uuid4())]  # start with one blank row

col1, col2 = st.columns(2)
with col1:
    form_no = st.text_input("Form No.", value=st.session_state.ppe_form_no)
with col2:
    form_date = st.date_input("Dated", value=date.today())

st.markdown("---")
st.markdown("### People Receiving PPE")

to_remove = None
rows_data = []
for i, eid in enumerate(st.session_state.ppe_entity_ids, start=1):
    with st.expander(f"Entity {i}", expanded=(i == len(st.session_state.ppe_entity_ids))):
        c1, c2 = st.columns(2)
        with c1:
            issued_to = st.text_input("Issued To *", key=f"issued_to_{eid}")
            phone = st.text_input("Phone Number", key=f"ppe_phone_{eid}", placeholder="07XX XXX XXX")
        with c2:
            site_name = st.text_input("Site Name", key=f"ppe_site_{eid}")

        st.caption("PPEs Issued")
        ppe_cols = st.columns(len(PPE_ITEMS))
        ticked = {}
        for item, col in zip(PPE_ITEMS, ppe_cols):
            with col:
                ticked[item] = st.checkbox(item, key=f"ppe_{item}_{eid}")
        other = st.text_input("Other (optional)", key=f"ppe_other_{eid}",
                               placeholder="Anything not listed above")

        st.caption("Signature")
        canvas_result = st_canvas(
            fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
            background_color="#FFFFFF", height=100, width=300,
            drawing_mode="freedraw", key=f"ppe_sig_{eid}",
        )

        if len(st.session_state.ppe_entity_ids) > 1:
            if st.button("🗑 Remove this entity", key=f"ppe_remove_{eid}"):
                to_remove = eid

        rows_data.append(dict(
            id=eid, issued_to=issued_to, phone=phone, site_name=site_name,
            ppes=ticked, other=other,
            signature_png=canvas_to_png_bytes(canvas_result),
        ))

if to_remove:
    st.session_state.ppe_entity_ids.remove(to_remove)
    st.rerun()

if st.button("➕ Add Entity"):
    st.session_state.ppe_entity_ids.append(str(uuid.uuid4()))
    st.rerun()

st.markdown("---")
st.markdown("### Approval")
st.caption("The approver signs once, after every person above has been added.")
approved_name = st.text_input("Approved By — Name *")
approved_canvas = st_canvas(
    fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
    background_color="#FFFFFF", height=110, width=300,
    drawing_mode="freedraw", key="ppe_sig_approved",
)

st.markdown("---")
if st.button("Generate PPE Issuance PDF", type="primary"):
    errors = []
    for i, r in enumerate(rows_data, start=1):
        if not r["issued_to"]:
            errors.append(f"Entity {i}: Issued To is required.")
        if not any(r["ppes"].values()) and not r["other"]:
            errors.append(f"Entity {i}: Tick at least one PPE item (or fill in 'Other').")
        if not r["signature_png"]:
            errors.append(f"Entity {i}: Signature is required.")
    if not approved_name:
        errors.append("Approved By name is required.")
    approved_png = canvas_to_png_bytes(approved_canvas)
    if not approved_png:
        errors.append("Approved By signature is required.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        pdf_bytes = build_pdf(
            form_no, form_date.strftime("%Y-%m-%d"),
            rows_data, approved_name, approved_png,
        )

        # Append each entity as its own row in the audit log
        log_exists = os.path.exists(LOG_PATH)
        fieldnames = ["form_no", "form_date", "issued_to", "phone", "site_name"] + PPE_ITEMS + \
                     ["other", "approved_by", "generated_at"]
        with open(LOG_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not log_exists:
                writer.writeheader()
            for r in rows_data:
                row_out = {
                    "form_no": form_no,
                    "form_date": form_date.strftime("%Y-%m-%d"),
                    "issued_to": r["issued_to"],
                    "phone": r["phone"],
                    "site_name": r["site_name"],
                    "other": r["other"],
                    "approved_by": approved_name,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                }
                for item in PPE_ITEMS:
                    row_out[item] = "Yes" if r["ppes"].get(item) else "No"
                writer.writerow(row_out)

        st.success(f"PPE form {form_no} generated for {len(rows_data)} {'person' if len(rows_data)==1 else 'people'}.")
        st.download_button(
            label="⬇ Download PPE Issuance PDF",
            data=pdf_bytes,
            file_name=f"{form_no}.pdf",
            mime="application/pdf",
        )
        st.session_state.ppe_form_no = next_form_number()

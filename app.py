"""
Electronic Payment Voucher — Baran Telecom Networks / Tech 7 Automation
Systems / Exhenb Engineering Ltd JV
--------------------------------------------------------------------------
Built for the real case that drives this voucher: several workers being
paid off one voucher (e.g. a day's casuals on a site), each with their own
payment details and their own signature, signed off once by a single
approver at the end.

DESIGN DECISIONS (opinionated, on purpose)
--------------------------------------------------------------------------
1. Fields, cut down to exactly what's needed, nothing more:
   Paid To, Phone Number, Site Name, On Account Of, Amount, Signature —
   repeated per worker — then one Approved By (name + signature) at the
   very end. Everything from the previous version that wasn't asked for
   (entity/cost centre, project field, payment mode, a separate prepared-by
   signature) has been removed. That was bulk this voucher doesn't need.

2. "Phone Number" instead of a bank-account field. Casual/site workers in
   Kenya are overwhelmingly paid via mobile money (M-Pesa), so the field
   that actually gets used is a phone number, not an account number.

3. Site Name travels with each worker, not the voucher as a whole — on a
   multi-worker voucher it's common for workers to be on different sites,
   so this can't be a single global field.

4. Each worker signs their own row (acknowledging they were paid). One
   "Received By" for everyone would be meaningless once there's more than
   one payee.

5. "Approved By" is a single signature, collected once, after every
   worker row has been added — the approver is signing off the whole
   batch, not each line. The "+ Add Entity" button lives above that
   signature block for exactly this reason: add every worker first, sign
   last.

6. Total Amount and Total in Words are computed automatically once there's
   more than one row — an approver signing off a batch needs to see what
   they're approving in total, not just add up line items by eye.

7. The PDF renders the workers as table rows with the header repeated if
   the list runs to a second page, so this scales from 2 workers to 50
   without changing the layout.

8. No st.form here on purpose — the "+ Add Entity" / "Remove" buttons need
   to rerun the page immediately to redraw the row list, which a form
   would hold back until final submit.
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
LETTERHEAD_PATH = os.path.join(os.path.dirname(__file__), "letterhead.png")
LOG_PATH = os.path.join(os.path.dirname(__file__), "voucher_log.csv")
CURRENCY = "KES"

st.set_page_config(page_title="JV Payment Voucher", page_icon="🧾", layout="centered")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def next_voucher_number() -> str:
    """Sequential voucher number: PV-YYYYMMDD-### based on today's log entries."""
    today_str = date.today().strftime("%Y%m%d")
    count_today = 1
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
            count_today += sum(1 for r in rows if r.get("voucher_no", "").startswith(f"PV-{today_str}"))
    return f"PV-{today_str}-{count_today:03d}"


def amount_in_words(amount: float) -> str:
    """Minimal number-to-words for KES amounts (whole shillings + cents)."""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
             "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digit(n):
        if n < 10:
            return ones[n]
        if n < 20:
            return teens[n - 10]
        return (tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")).strip()

    def three_digit(n):
        if n >= 100:
            return (ones[n // 100] + " Hundred" + (" " + two_digit(n % 100) if n % 100 else "")).strip()
        return two_digit(n)

    whole = int(amount)
    cents = round((amount - whole) * 100)

    if whole == 0:
        words = "Zero"
    else:
        parts = []
        for value, label in [(1_000_000, "Million"), (1_000, "Thousand")]:
            chunk, whole = divmod(whole, value)
            if chunk:
                parts.append(f"{three_digit(chunk)} {label}")
        if whole:
            parts.append(three_digit(whole))
        words = " ".join(parts)

    result = f"{words} Shillings"
    if cents:
        result += f" and {two_digit(cents)} Cents"
    return result + " Only"


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


def sig_cell(png_bytes, w=18 * mm, h=8 * mm):
    """Small signature thumbnail for a table cell, or a dash if unsigned."""
    if png_bytes:
        return RLImage(io.BytesIO(png_bytes), width=w, height=h)
    return Paragraph("—", getSampleStyleSheet()["Normal"])


def build_pdf(voucher_no: str, voucher_date: str, rows: list, approved_name: str, approved_png: bytes) -> bytes:
    """rows: list of dicts with paid_to, phone, site_name, on_account_of, amount, signature_png."""
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

    story.append(Paragraph("PAYMENT VOUCHER", title_style))
    story.append(Spacer(1, 4 * mm))

    meta_table = Table(
        [[Paragraph(f"<b>PV No.</b> &nbsp; {voucher_no}", label_style),
          Paragraph(f"<b>Dated:</b> &nbsp; {voucher_date}", label_style)]],
        colWidths=[87 * mm, 87 * mm],
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # --- Worker rows table ---
    # Column widths sum to 174mm (content width)
    col_widths = [8 * mm, 32 * mm, 22 * mm, 24 * mm, 44 * mm, 22 * mm, 22 * mm]
    header = [Paragraph(h, header_cell_style) for h in
              ["No.", "Paid To", "Phone No.", "Site Name", "On Account Of", "Amount", "Signature"]]
    table_data = [header]
    total = 0.0
    for i, r in enumerate(rows, start=1):
        total += r["amount"]
        table_data.append([
            Paragraph(str(i), cell_style),
            Paragraph(r["paid_to"], cell_style),
            Paragraph(r["phone"] or "-", cell_style),
            Paragraph(r["site_name"] or "-", cell_style),
            Paragraph(r["on_account_of"], cell_style),
            Paragraph(f"{r['amount']:,.2f}", cell_style),
            sig_cell(r["signature_png"]),
        ])

    # Totals row
    table_data.append([
        "", "", "", "",
        Paragraph("<b>TOTAL</b>", cell_style),
        Paragraph(f"<b>{CURRENCY} {total:,.2f}</b>", cell_style),
        "",
    ])

    rows_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2d3d")),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("SPAN", (0, -1), (3, -1)),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ]
    rows_table.setStyle(TableStyle(style_cmds))
    story.append(rows_table)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<i>Total in Words: {amount_in_words(total)}</i>",
                            ParagraphStyle("Words", parent=styles["Normal"], fontSize=9)))
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
st.title("Payment Voucher")
st.caption("Add each person being paid, then have the approver sign once at the end.")

if "voucher_no" not in st.session_state:
    st.session_state.voucher_no = next_voucher_number()
if "entity_ids" not in st.session_state:
    st.session_state.entity_ids = [str(uuid.uuid4())]  # start with one blank row

col1, col2 = st.columns(2)
with col1:
    voucher_no = st.text_input("PV No.", value=st.session_state.voucher_no)
with col2:
    voucher_date = st.date_input("Dated", value=date.today())

st.markdown("---")
st.markdown("### People Being Paid")

to_remove = None
rows_data = []
for i, eid in enumerate(st.session_state.entity_ids, start=1):
    with st.expander(f"Entity {i}", expanded=(i == len(st.session_state.entity_ids))):
        c1, c2 = st.columns(2)
        with c1:
            paid_to = st.text_input("Paid To *", key=f"paid_to_{eid}")
            phone = st.text_input("Phone Number", key=f"phone_{eid}", placeholder="07XX XXX XXX")
            site_name = st.text_input("Site Name", key=f"site_{eid}")
        with c2:
            amount = st.number_input(f"Amount ({CURRENCY}) *", min_value=0.0, step=50.0,
                                      format="%.2f", key=f"amount_{eid}")
            on_account_of = st.text_area("On Account Of *", key=f"account_of_{eid}", height=85)

        st.caption("Signature")
        canvas_result = st_canvas(
            fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
            background_color="#FFFFFF", height=100, width=300,
            drawing_mode="freedraw", key=f"sig_{eid}",
        )

        if len(st.session_state.entity_ids) > 1:
            if st.button("🗑 Remove this entity", key=f"remove_{eid}"):
                to_remove = eid

        rows_data.append(dict(
            id=eid, paid_to=paid_to, phone=phone, site_name=site_name,
            on_account_of=on_account_of, amount=amount,
            signature_png=canvas_to_png_bytes(canvas_result),
        ))

if to_remove:
    st.session_state.entity_ids.remove(to_remove)
    st.rerun()

if st.button("➕ Add Entity"):
    st.session_state.entity_ids.append(str(uuid.uuid4()))
    st.rerun()

st.markdown("---")
st.markdown("### Approval")
st.caption("The approver signs once, after every person above has been added.")
approved_name = st.text_input("Approved By — Name *")
approved_canvas = st_canvas(
    fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
    background_color="#FFFFFF", height=110, width=300,
    drawing_mode="freedraw", key="sig_approved",
)

st.markdown("---")
if st.button("Generate Voucher PDF", type="primary"):
    errors = []
    for i, r in enumerate(rows_data, start=1):
        if not r["paid_to"]:
            errors.append(f"Entity {i}: Paid To is required.")
        if not r["amount"] or r["amount"] <= 0:
            errors.append(f"Entity {i}: Amount must be greater than zero.")
        if not r["on_account_of"]:
            errors.append(f"Entity {i}: On Account Of is required.")
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
            voucher_no, voucher_date.strftime("%Y-%m-%d"),
            rows_data, approved_name, approved_png,
        )

        # Append each paid entity as its own row in the audit log
        log_exists = os.path.exists(LOG_PATH)
        fieldnames = ["voucher_no", "voucher_date", "paid_to", "phone", "site_name",
                      "on_account_of", "amount", "approved_by", "generated_at"]
        with open(LOG_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not log_exists:
                writer.writeheader()
            for r in rows_data:
                writer.writerow({
                    "voucher_no": voucher_no,
                    "voucher_date": voucher_date.strftime("%Y-%m-%d"),
                    "paid_to": r["paid_to"],
                    "phone": r["phone"],
                    "site_name": r["site_name"],
                    "on_account_of": r["on_account_of"],
                    "amount": r["amount"],
                    "approved_by": approved_name,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                })

        st.success(f"Voucher {voucher_no} generated for {len(rows_data)} {'person' if len(rows_data)==1 else 'people'}.")
        st.download_button(
            label="⬇ Download Voucher PDF",
            data=pdf_bytes,
            file_name=f"{voucher_no}.pdf",
            mime="application/pdf",
        )
        st.session_state.voucher_no = next_voucher_number()

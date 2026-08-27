# JV Forms — BTN / Tech 7 / Exhenb

A small Streamlit app with two forms, built around the same real use
case: several people on site, added one at a time, each signing for
themselves, with a single approver signing once at the very end after
everyone's been added.

- **Payment Voucher** (`Payment_Voucher.py`) — pay several workers off one
  voucher.
- **PPE Issuance Form** (`pages/1_PPE_Issuance.py`) — issue PPE to several
  workers off one form.

Both share the same JV letterhead and the same add-entity-then-approve
pattern, and both show up as pages in one Streamlit app (see "Deploy"
below) — one link for the team, two forms in the sidebar.

## Payment Voucher

Download a PDF carrying the JV letterhead. Every voucher is logged to
`voucher_log.csv` (one row per person paid) for an audit trail.

## Fields — kept deliberately lean

Per person being paid:
- **Paid To**
- **Phone Number** — mobile money (M-Pesa) is how casual/site workers
  actually get paid in Kenya, so this replaces a bank-account field.
- **Site Name** — travels with each person, not the voucher as a whole,
  because a multi-worker voucher often spans more than one site.
- **On Account Of**
- **Amount**
- **Signature** — each person signs to acknowledge they were paid.

Once, for the whole voucher:
- **Approved By** (name + signature) — the approver reviews the full list
  and signs once, after every entity has been added. That's why the
  "+ Add Entity" button sits above the approval section: add everyone
  first, approve last.
- **Total Amount** and **Total in Words** are computed automatically —
  once there's more than one row, the approver needs to see the total
  they're signing off, not add it up by eye.

Everything from the earlier version that wasn't asked for (entity/cost
centre, a separate project field, payment mode, a prepared-by signature)
has been removed to cut the bulk.

## How it works on screen

- Each person is its own collapsible "Entity" section — add as many as
  needed with **+ Add Entity**, remove one with the 🗑 button inside it.
- The **Approved By** signature is fixed at the bottom, below every
  entity, so it's physically impossible to sign off before the list is
  complete.
- The PDF renders every person as a row in one table (header repeats if
  the list runs to a second page), followed by the total and the single
  Approved By signature block. This scales the same way from 2 people to
  50.

## PPE Issuance Form

Same pattern, different payload: instead of an amount, each person gets a
fixed checklist — **Reflective Vest, Gloves, Safety Boots, Helmet,
Overall** — ticked on screen, plus an optional free-text "Other" for
anything not on that list. Logged to `ppe_issuance_log.csv` (one row per
person, one column per PPE item, Yes/No).

The five items are deliberately fixed rather than free text: a typed-in
PPE list invites inconsistent spelling across forms and makes it hard to
later answer something like "how many pairs of gloves went out this
month." "Other" exists so an unusual item doesn't block the form, but it
doesn't get its own dedicated tick column.

The PDF shows each person's checklist as ticked/unticked lines in one
cell (`[X] Gloves` / `[ ] Helmet`), so the approver sees exactly what was
issued, per person, without cross-referencing a separate key.

## Before you deploy

`letterhead.png` is already the JV letterhead you supplied. To change the
Payment Voucher's currency, edit the top of `Payment_Voucher.py`:

```python
CURRENCY = "KES"
```

To change the PPE checklist items, edit the top of `pages/1_PPE_Issuance.py`:

```python
PPE_ITEMS = ["Reflective Vest", "Gloves", "Safety Boots", "Helmet", "Overall"]
```

## Run it locally (to test)

```bash
pip install -r requirements.txt
streamlit run Payment_Voucher.py
```

Opens at `http://localhost:8501`, with **PPE Issuance** in the sidebar as
a second page.

## Deploy so the team can use it (no install needed)

**Recommended: Streamlit Community Cloud (free, ~2 minutes)**

1. Push this whole folder to a GitHub repo (can be private) — keep the
   `pages/` folder as-is; Streamlit uses it to build the sidebar
   automatically.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click "New app", pick the repo and `Payment_Voucher.py` as the entry
   point, click Deploy.
4. You get one permanent URL with both forms available from the sidebar.

**Alternative: run it on an office server / VM**

```bash
pip install -r requirements.txt
streamlit run Payment_Voucher.py --server.port 8501 --server.address 0.0.0.0
```
Share `http://<server-ip>:8501` on the office network. For a permanent
deployment, run it under a process manager (`systemd` or `pm2`) so it
restarts automatically.

## Files

| File                          | Purpose                                              |
|-------------------------------|-------------------------------------------------------|
| `Payment_Voucher.py`          | Payment Voucher app (entry point / home page)         |
| `pages/1_PPE_Issuance.py`     | PPE Issuance Form (second sidebar page)               |
| `letterhead.png`              | JV letterhead shown on-screen and in both PDFs        |
| `requirements.txt`            | Python dependencies                                    |
| `voucher_log.csv`             | Auto-created audit log — one row per person paid      |
| `ppe_issuance_log.csv`        | Auto-created audit log — one row per person issued PPE |

## Notes on the design

- **No st.form on either page** — the "+ Add Entity" / remove buttons
  need to rerun the page immediately to redraw the row list, which a form
  would hold back until final submit. Every field validates on the final
  "Generate PDF" click instead.
- **No database** — the two log CSVs are enough audit trail for now. If
  more than one person will use either form concurrently and numbering
  starts colliding, swap the CSVs for a small SQLite file.
- **Signatures are drawn, not typed** — captured on an HTML canvas and
  embedded into the PDF as images, per person and for the approver.
- **Numbering** is sequential per day (`PV-YYYYMMDD-001` / `PPE-YYYYMMDD-001`,
  `-002`, ...), derived from each form's own log file.

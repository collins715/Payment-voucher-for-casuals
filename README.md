# JV Payment Voucher — BTN / Tech 7 / Exhenb

A one-file Streamlit app built around the real use case: several workers
being paid off one voucher (e.g. a day's casuals on a site). Add each
person, each signs their own row, and a single approver signs once at the
end. Download a PDF carrying the JV letterhead. Every voucher is logged to
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

## Before you deploy

`letterhead.png` is already the JV letterhead you supplied. To change
currency, edit the top of `app.py`:

```python
CURRENCY = "KES"
```

## Run it locally (to test)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Deploy so the team can use it (no install needed)

**Recommended: Streamlit Community Cloud (free, ~2 minutes)**

1. Push this folder to a GitHub repo (can be private).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click "New app", pick the repo and `app.py` as the entry point, click Deploy.
4. You get a permanent URL to send to whoever issues vouchers.

**Alternative: run it on an office server / VM**

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```
Share `http://<server-ip>:8501` on the office network. For a permanent
deployment, run it under a process manager (`systemd` or `pm2`) so it
restarts automatically.

## Files

| File               | Purpose                                              |
|--------------------|-------------------------------------------------------|
| `app.py`           | The whole application (form, PDF rendering, logic)   |
| `letterhead.png`   | JV letterhead shown on-screen and in the PDF header   |
| `requirements.txt` | Python dependencies                                    |
| `voucher_log.csv`  | Auto-created audit log — one row per person paid      |

## Notes on the design

- **No st.form** — the "+ Add Entity" / remove buttons need to rerun the
  page immediately to redraw the row list, which a form would hold back
  until final submit. Every field validates on the final "Generate
  Voucher PDF" click instead.
- **No database** — `voucher_log.csv` is enough audit trail for now. If
  more than one person will issue vouchers concurrently and voucher
  numbers start colliding, swap the CSV for a small SQLite file.
- **Signatures are drawn, not typed** — captured on an HTML canvas and
  embedded into the PDF as images, per person and for the approver.
- **Voucher numbering** is sequential per day (`PV-YYYYMMDD-001`, `-002`,
  ...), derived from the log file.

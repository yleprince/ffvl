# QCM Parapente BPC

A spaced-repetition trainer for the French paragliding BPC exam question bank, using
Leitner-style boxes (like Anki) to resurface questions you got wrong sooner than ones
you know well.

## How it works

- Questions and options live in [`questions.csv`](questions.csv) and
  [`options.csv`](options.csv) (generated from [`bp_corrected.md`](bp_corrected.md) by
  [`parse_qcm.py`](parse_qcm.py)). An option's `score` is positive if it's a correct
  answer, negative if it's wrong.
- On first run, the backend seeds a SQLite database from those CSVs and creates one
  review record per question, due immediately.
- Answering a question moves it between 6 Leitner boxes:
  - Correct → box + 1, next due further out (1 min → 1h → 1d → 3d → 7d → 16d)
  - Incorrect → back to box 1, due again in 1 minute
- The frontend ([`static/index.html`](static/index.html)) only ever asks the backend for
  the next due question, so it always studies what's actually due rather than the full
  question bank in random order.

## Project layout

```
backend/main.py     FastAPI app: SQLite storage, Leitner scheduling, CSV seeding
static/index.html   daisyUI frontend (mobile-first), calls the backend API
questions.csv        Question bank (id, text)
options.csv           Options per question (question id, text, score)
Dockerfile / docker-compose.yml   Single-service deployment, SQLite persisted via a volume
```

## Running locally

```bash
docker compose up --build
```

Then open http://localhost:9443. Review state is persisted to `./data/qcm.db` (mounted
as a volume), so it survives restarts and rebuilds.

## Deploying on your server

```bash
docker compose up -d --build
```

Point a reverse proxy at port 9443 (or change the host-side port in
`docker-compose.yml`). There's no authentication — this is built for personal,
single-user use, so keep it off the public internet or add basic auth / a VPN in front
if it needs to be reachable beyond your LAN.

## API

- `GET /api/next` — the next due question (or, if nothing's due, when the next one will
  be) plus overall stats
- `POST /api/answer` — `{question_id, selected_option_ids}`, returns which options were
  correct and updates the Leitner schedule
- `GET /api/stats` — total / due / mastered question counts

## Regenerating the question bank

If `bp_corrected.md` changes, regenerate the CSVs with:

```bash
python3 parse_qcm.py
```

This only rewrites `questions.csv` and `options.csv` — it doesn't touch `data/qcm.db`.
The backend seeds the database once, on startup, only if its `questions` table is empty.
So updated CSVs have no effect on an existing deployment unless you delete
`data/qcm.db` and restart, which reseeds everything from scratch and loses prior review
progress.

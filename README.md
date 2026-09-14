# QCM Parapente BPC

A spaced-repetition trainer for the French paragliding BPC exam question bank, using
Leitner-style boxes (like Anki) to resurface questions you got wrong sooner than ones
you know well. Fully static — no backend, hosted on GitHub Pages.

## How it works

- Questions and options live in [`questions.csv`](questions.csv) and
  [`options.csv`](options.csv) (generated from a source markdown file by
  [`parse_qcm.py`](parse_qcm.py)). An option's `score` is positive if it's a correct
  answer, negative if it's wrong.
- Everything runs client-side in [`index.html`](index.html): it fetches the two CSVs,
  and does its own Leitner-box scheduling and answer checking in JavaScript.
- Answering a question moves it between 6 Leitner boxes, tracked per question:
  - Correct → box + 1, next due further out (1 min → 1h → 1d → 3d → 7d → 16d)
  - Incorrect → back to box 1, due again in 1 minute
- The app always studies the next due question, not the full bank in random order.
- Progress (box, times seen, times correct, next due date) is saved to the browser's
  `localStorage`, keyed per device/browser — nothing is sent to any server. Clearing
  site data (or using a different browser/device) resets progress; there's also an
  in-app "réinitialiser ma progression" link for that.

## Project layout

```
index.html      The whole app: daisyUI UI (mobile-first) + Leitner logic + localStorage
questions.csv   Question bank (id, text)
options.csv     Options per question (question id, text, score)
parse_qcm.py    Regenerates the two CSVs from the source markdown
```

## Running locally

Any static file server works, since the page `fetch()`s the CSVs relative to itself
(opening `index.html` directly via `file://` won't work due to browser fetch
restrictions):

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Deploying to GitHub Pages

Push this repo to GitHub, then in the repo's Settings → Pages, set the source to the
`main` branch, root folder. The site will be served at
`https://<username>.github.io/<repo>/`.

## Regenerating the question bank

If the source markdown changes, regenerate the CSVs with:

```bash
python3 parse_qcm.py
```

This only rewrites `questions.csv` and `options.csv`. It doesn't affect anyone's saved
progress, since that lives entirely in each browser's `localStorage`, keyed by question
id — as long as question ids stay stable, existing progress carries over.

# SortWise — Waste Classification & Reward App

A full-stack app built around your trained MobileNet waste classifier.
Users upload a photo → the model predicts **Recyclable / Non-Recyclable /
E-Waste** → the app shows a step-by-step disposal guide → the user earns
eco-points, levels up, and unlocks badges.

```
project/
├── backend/
│   ├── app.py                 Flask server + API routes
│   ├── config.py              ⚠️ class names / preprocessing — verify first!
│   ├── model_utils.py         Rebuilds architecture + loads weights, runs predictions
│   ├── disposal_guide.py      Disposal instructions per category
│   ├── rewards.py             Points, levels, streaks, badges (SQLite)
│   ├── find_class_order.py    Diagnostic script — see Step 2 below
│   ├── requirements.txt
│   ├── model_architecture.json  Model architecture (exported from training)
│   └── model.weights.h5         ✅ your trained weights
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

---

## Step 1 — Install dependencies

Requires Python 3.10+.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 2 — ⚠️ Verify your class order and preprocessing (do this first!)

Your uploaded model file only contained the architecture and weights — not
a record of which output index corresponds to which label, or exactly how
images were preprocessed during training. `config.py` currently ships with
a **best-guess default** (alphabetical class order + MobileNet-style
preprocessing) and the app will show a warning banner until you confirm it.

**Fastest way to confirm — check your training code**, if you still have
it. Look for one of these printed during training:

```python
train_generator.class_indices        # ImageDataGenerator
train_ds.class_names                 # image_dataset_from_directory
```

Whatever order that prints IS your `CLASS_NAMES` order — copy it exactly
into `config.py`.

**If you don't have the training code anymore**, use the diagnostic
script with a couple of sample photos you know the true label of:

```bash
cd backend
python find_class_order.py path/to/a_known_recyclable_photo.jpg
python find_class_order.py path/to/a_known_ewaste_photo.jpg
```

For each image it prints the probability at every output index, under
*both* possible preprocessing modes. The mode that gives a sharp,
confident spike (not ~33/33/33) is your training preprocessing. Whichever
index consistently lights up for a photo you know the label of tells you
the class order.

Then edit `backend/config.py`:

```python
CLASS_NAMES = ["ewaste", "non_recyclable", "recyclable"]  # <- your real order
PREPROCESS_MODE = "mobilenet"                              # or "rescale"
CLASS_ORDER_VERIFIED = True                                 # removes the warning banner
```

> If your class *names* also differ (e.g. you used "organic" instead of
> "non_recyclable"), also update the keys in `backend/disposal_guide.py`
> so the right guide shows up ("ewaste" and "recyclable" strings there
> must match `config.CLASS_NAMES` exactly).

---

## Step 3 — Run the app

```bash
cd backend
python app.py
```

Open **http://localhost:5000** — the Flask server serves both the API
and the frontend, so this one command runs the whole thing.

---

## Step 4 — Try it out

1. Set your name (top right) so points are tracked under your account.
2. Drop or select a photo of a waste item.
3. Click **Classify this item** — you'll see:
   - the predicted category as a stamp
   - confidence %, plus a per-class probability breakdown
   - a numbered disposal guide specific to that category
   - eco-points earned, your level progress bar, and any new badges
4. Check the **Leaderboard** tab to see everyone's points (great for a
   classroom/society competition), and **My history** for your own log.

---

## How the reward system works

| Action | Points |
|---|---|
| Any successful scan | +10 |
| Scanning e-waste specifically | +15 bonus (encourages correct e-waste routing) |
| First scan of the day | +5 streak bonus |

**Levels:** Seedling (0) → Sprout (100) → Sapling (300) → Young Tree (600)
→ Forest Guardian (1000) → Eco Champion (2000). Tune thresholds in
`rewards.py` (`LEVEL_TITLES`).

**Badges:** First Scan, Recycler (10 recyclables), E-Waste Hero (5
e-waste items), Century Club (100 pts), Half-K Hero (500 pts), Eco
Champion (1000 pts), 7-Day Streak. Add more in `rewards.py`
(`BADGE_DEFINITIONS`) — each badge is just a name + a lambda that checks
a stats dict.

Data is stored in `backend/waste_app.db` (SQLite, created automatically
on first run — no separate database server needed). Delete this file to
reset all points/history.

---

## Customizing the disposal guides

Edit `backend/disposal_guide.py` — each category has a `summary`, an
ordered list of `steps` (title + detail), and an `avoid` list of common
mistakes. This is plain Python data, easy to extend with local
municipality info, links to nearby e-waste drop-off points, etc.

---

## Deploying beyond localhost (optional next steps)

This setup is intentionally simple (SQLite, no auth) so it's easy to run
for a class project or demo. If you want to put it in front of real
users later:
- Swap SQLite for Postgres/MySQL if you expect concurrent writers at scale.
- Add real authentication instead of free-text usernames.
- Put the Flask app behind gunicorn + nginx (or deploy to Render/Railway/
  PythonAnywhere) instead of `python app.py`'s dev server.
- Compress/resize uploads before saving if storage becomes a concern.

---

## Troubleshooting

- **"Model outputs 3 classes but config.CLASS_NAMES has N entries"** —
  your `CLASS_NAMES` list length must exactly match the model's output
  size (3, per your architecture).
- **Predictions look random / all similar confidence** — you're almost
  certainly on the wrong `PREPROCESS_MODE`. Re-run Step 2.
- **`ModuleNotFoundError: No module named 'keras'`** — activate your
  virtualenv and re-run `pip install -r requirements.txt`.
- **Port 5000 already in use** — change `port=5000` at the bottom of
  `app.py`, or stop whatever else is using that port.
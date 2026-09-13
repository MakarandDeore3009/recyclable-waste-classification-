"""
Reward / gamification system.

Uses a plain SQLite database (no login/password — just a chosen
username) so this is easy to run for a school/college/society
project without setting up real auth. Swap in proper auth later
if you deploy this publicly.
"""
import sqlite3
import datetime
from contextlib import contextmanager

import config

LEVEL_TITLES = [
    (0, "Seedling"),
    (100, "Sprout"),
    (300, "Sapling"),
    (600, "Young Tree"),
    (1000, "Forest Guardian"),
    (2000, "Eco Champion"),
]

BADGE_DEFINITIONS = [
    {"id": "first_scan", "name": "First Scan", "desc": "Classified your first item.",
     "check": lambda stats: stats["total_scans"] >= 1},
    {"id": "recycler_10", "name": "Recycler", "desc": "Correctly sorted 10 recyclables.",
     "check": lambda stats: stats["recyclable_count"] >= 10},
    {"id": "ewaste_hero_5", "name": "E-Waste Hero", "desc": "Responsibly logged 5 e-waste items.",
     "check": lambda stats: stats["ewaste_count"] >= 5},
    {"id": "century_club", "name": "Century Club", "desc": "Earned 100 total points.",
     "check": lambda stats: stats["points"] >= 100},
    {"id": "half_k_hero", "name": "Half-K Hero", "desc": "Earned 500 total points.",
     "check": lambda stats: stats["points"] >= 500},
    {"id": "eco_champion_pts", "name": "Eco Champion", "desc": "Earned 1000 total points.",
     "check": lambda stats: stats["points"] >= 1000},
    {"id": "streak_7", "name": "7-Day Streak", "desc": "Scanned items 7 days in a row.",
     "check": lambda stats: stats["streak"] >= 7},
]


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_scan_date TEXT,
                recyclable_count INTEGER DEFAULT 0,
                non_recyclable_count INTEGER DEFAULT 0,
                ewaste_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                category TEXT,
                confidence REAL,
                points_earned INTEGER,
                timestamp TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                username TEXT,
                badge_id TEXT,
                earned_at TEXT,
                PRIMARY KEY (username, badge_id)
            )
        """)


def _get_or_create_user(db, username):
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO users (username, created_at) VALUES (?, ?)",
            (username, datetime.datetime.utcnow().isoformat()),
        )
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return row


def _level_for_points(points):
    title = LEVEL_TITLES[0][1]
    level_num = 1
    for i, (threshold, name) in enumerate(LEVEL_TITLES):
        if points >= threshold:
            title = name
            level_num = i + 1
    next_threshold = None
    for threshold, _ in LEVEL_TITLES:
        if threshold > points:
            next_threshold = threshold
            break
    return level_num, title, next_threshold


def record_scan(username, category, confidence):
    """
    Record a classification result for a user, update points/streak/
    category counts, evaluate newly earned badges, and return a
    summary dict for the API response.
    """
    today = datetime.date.today().isoformat()
    with get_db() as db:
        user = _get_or_create_user(db, username)

        points_earned = config.POINTS_PER_SCAN
        if category == "ewaste":
            points_earned += config.POINTS_BONUS_EWASTE

        # Streak logic: consecutive calendar days with at least one scan
        last_date = user["last_scan_date"]
        streak = user["streak"] or 0
        if last_date != today:
            if last_date == (datetime.date.today() - datetime.timedelta(days=1)).isoformat():
                streak += 1
            else:
                streak = 1
            points_earned += config.POINTS_DAILY_FIRST_SCAN_BONUS

        new_points = (user["points"] or 0) + points_earned

        col_map = {
            "recyclable": "recyclable_count",
            "non_recyclable": "non_recyclable_count",
            "ewaste": "ewaste_count",
        }
        count_col = col_map.get(category)

        if count_col:
            db.execute(
                f"""UPDATE users SET points = ?, streak = ?, last_scan_date = ?,
                    {count_col} = {count_col} + 1 WHERE username = ?""",
                (new_points, streak, today, username),
            )
        else:
            db.execute(
                "UPDATE users SET points = ?, streak = ?, last_scan_date = ? WHERE username = ?",
                (new_points, streak, today, username),
            )

        db.execute(
            "INSERT INTO scans (username, category, confidence, points_earned, timestamp) VALUES (?, ?, ?, ?, ?)",
            (username, category, confidence, points_earned, datetime.datetime.utcnow().isoformat()),
        )

        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        stats = {
            "points": user["points"],
            "streak": user["streak"],
            "total_scans": db.execute(
                "SELECT COUNT(*) c FROM scans WHERE username = ?", (username,)
            ).fetchone()["c"],
            "recyclable_count": user["recyclable_count"],
            "non_recyclable_count": user["non_recyclable_count"],
            "ewaste_count": user["ewaste_count"],
        }

        newly_earned = []
        already_earned = {
            r["badge_id"] for r in db.execute(
                "SELECT badge_id FROM badges WHERE username = ?", (username,)
            ).fetchall()
        }
        for badge in BADGE_DEFINITIONS:
            if badge["id"] not in already_earned and badge["check"](stats):
                db.execute(
                    "INSERT INTO badges (username, badge_id, earned_at) VALUES (?, ?, ?)",
                    (username, badge["id"], datetime.datetime.utcnow().isoformat()),
                )
                newly_earned.append({"id": badge["id"], "name": badge["name"], "desc": badge["desc"]})

        level_num, level_title, next_threshold = _level_for_points(stats["points"])

        return {
            "points_earned": points_earned,
            "total_points": stats["points"],
            "streak": stats["streak"],
            "level": level_num,
            "level_title": level_title,
            "points_to_next_level": (next_threshold - stats["points"]) if next_threshold else 0,
            "newly_earned_badges": newly_earned,
        }


def get_profile(username):
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            return None
        badges = db.execute(
            "SELECT badge_id, earned_at FROM badges WHERE username = ? ORDER BY earned_at",
            (username,),
        ).fetchall()
        badge_lookup = {b["id"]: b for b in BADGE_DEFINITIONS}
        earned_badges = [
            {
                "id": row["badge_id"],
                "name": badge_lookup[row["badge_id"]]["name"],
                "desc": badge_lookup[row["badge_id"]]["desc"],
                "earned_at": row["earned_at"],
            }
            for row in badges if row["badge_id"] in badge_lookup
        ]
        level_num, level_title, next_threshold = _level_for_points(user["points"])
        return {
            "username": user["username"],
            "points": user["points"],
            "streak": user["streak"],
            "level": level_num,
            "level_title": level_title,
            "points_to_next_level": (next_threshold - user["points"]) if next_threshold else 0,
            "recyclable_count": user["recyclable_count"],
            "non_recyclable_count": user["non_recyclable_count"],
            "ewaste_count": user["ewaste_count"],
            "badges": earned_badges,
        }


def get_history(username, limit=20):
    with get_db() as db:
        rows = db.execute(
            "SELECT category, confidence, points_earned, timestamp FROM scans WHERE username = ? ORDER BY id DESC LIMIT ?",
            (username, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_leaderboard(limit=10):
    with get_db() as db:
        rows = db.execute(
            "SELECT username, points, streak FROM users ORDER BY points DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
REWARD_POINTS = {
    "recyclable": 10,
    "non-recyclable": 5,
    "ewaste": 20
}


def get_reward_points(category):
    category = category.lower().strip()

    return REWARD_POINTS.get(category, 0)
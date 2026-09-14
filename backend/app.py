"""
============================================================
SORTWISE - WASTE CLASSIFICATION BACKEND
============================================================

Features:
- Flask REST API
- MongoDB user accounts
- JWT authentication
- Secure password hashing
- Waste image classification
- Recyclable / Non-Recyclable / E-Waste
- Persistent eco points
- Persistent total scans
- Persistent total classifications
- Category-wise statistics
- Levels
- Badges
- Daily streak
- Scan history
- Leaderboard
- User profile
- Logout
- Frontend file serving
- Health check

Required packages:
    pip install flask flask-cors flask-jwt-extended pymongo
    pip install werkzeug pillow numpy tensorflow

MongoDB:
    mongodb://localhost:27017/

Database:
    sortwise

Collections:
    users
    scans
============================================================
"""

import os
import traceback
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory,
)

from flask_cors import CORS

from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from bson import ObjectId
from pymongo import MongoClient

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from werkzeug.utils import secure_filename


# ============================================================
# APP CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

FRONTEND_CANDIDATES = [
    BASE_DIR,
    BASE_DIR / "frontend",
    BASE_DIR.parent / "frontend",
    BASE_DIR / "templates",
    BASE_DIR.parent / "templates",
]

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY",
    "sortwise-super-secret-key-change-this",
)

app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)

jwt = JWTManager(app)


# ============================================================
# GROQ LLM CONFIGURATION
# ============================================================

# Get a free API key at https://console.groq.com
# Supported free models: llama3-8b-8192, llama3-70b-8192,
#                        mixtral-8x7b-32768, gemma2-9b-it
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

print(f"[Groq] Model: {GROQ_MODEL}")
if not GROQ_API_KEY:
    print("[Groq] WARNING: GROQ_API_KEY is not set. Chat will not work.")


# ============================================================
# MONGODB
# ============================================================

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017/",
)

MONGO_DB_NAME = os.getenv(
    "MONGO_DB",
    "sortwise",
)


def ensure_unique_field_index(collection, field):
    """
    Safely ensure a UNIQUE index exists for a field.

    This specifically fixes the common SortWise error:

        Index already exists with a different name:
        email_1

    Older versions may already have:
        email_1
        username_1

    We reuse a correct existing index instead of trying to
    create another index with a different name.
    """

    indexes = collection.index_information()

    desired_key = [(field, 1)]

    # --------------------------------------------------------
    # Find an existing index on this exact field
    # --------------------------------------------------------
    for index_name, index_info in indexes.items():

        key = index_info.get("key", [])

        if key == desired_key:

            is_unique = bool(
                index_info.get("unique", False)
            )

            if is_unique:
                print(
                    f"[MongoDB] Existing unique index found "
                    f"for {field}: {index_name}"
                )
                return

            # Existing index is not unique.
            # Remove it and recreate as unique.
            print(
                f"[MongoDB] Replacing non-unique index "
                f"for {field}: {index_name}"
            )

            collection.drop_index(index_name)

            break

    # --------------------------------------------------------
    # Create unique index
    # Do NOT force a custom name.
    #
    # MongoDB will normally use:
    # email_1
    # username_1
    # --------------------------------------------------------
    collection.create_index(
        [(field, 1)],
        unique=True,
    )

    print(
        f"[MongoDB] Unique index ready for {field}"
    )


try:

    mongo_client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )

    # Test MongoDB connection
    mongo_client.admin.command("ping")

    db = mongo_client[MONGO_DB_NAME]

    users_collection = db["users"]
    scans_collection = db["scans"]

    # --------------------------------------------------------
    # IMPORTANT:
    # Safely handle old email_1 / username_1 indexes.
    # --------------------------------------------------------

    ensure_unique_field_index(
        users_collection,
        "email",
    )

    ensure_unique_field_index(
        users_collection,
        "username",
    )

    # --------------------------------------------------------
    # Scan history index
    # --------------------------------------------------------

    scans_collection.create_index(
        [
            ("user_id", 1),
            ("timestamp", -1),
        ]
    )

    print("[MongoDB] Connected successfully!")
    print(f"[MongoDB] Database: {MONGO_DB_NAME}")
    print("[MongoDB] Collections ready")

except Exception as exc:

    print("[MongoDB] Connection failed!")
    print(exc)

    raise


# ============================================================
# MODEL CONFIG
# ============================================================

# IMPORTANT:
#
# The order MUST match your trained model output.
#
# Training used alphabetical folder order, so:
# 0 -> e_waste
# 1 -> non_recyclable
# 2 -> recyclable
#
# (Previously this was wrong — recyclable and e_waste were swapped,
#  causing the model to always appear to predict e_waste.)

CLASS_NAMES = [
    "e_waste",
    "non_recyclable",
    "recyclable",
]

CLASS_ORDER_VERIFIED = True

IMAGE_SIZE = (224, 224)

MODEL = None
MODEL_PATH = None


MODEL_CANDIDATES = [
    "model.keras",
    "model.h5",

    "waste_classifier.keras",
    "waste_classifier.h5",

    "waste_classifier_model.keras",
    "waste_classifier_model.h5",

    "waste_model.keras",
    "waste_model.h5",

    "best_model.keras",
    "best_model.h5",
]


# ============================================================
# FIND MODEL
# ============================================================

def find_model():

    configured = os.getenv("MODEL_PATH")

    # --------------------------------------------------------
    # Check MODEL_PATH first
    # --------------------------------------------------------

    if configured:

        path = Path(configured)

        if not path.is_absolute():
            path = BASE_DIR / path

        if path.exists():
            return path

    # --------------------------------------------------------
    # Search common folders
    # --------------------------------------------------------

    search_dirs = [
        BASE_DIR,
        BASE_DIR / "model",
        BASE_DIR / "models",

        BASE_DIR.parent,
        BASE_DIR.parent / "model",
        BASE_DIR.parent / "models",
    ]

    for directory in search_dirs:

        if not directory.exists():
            continue

        for filename in MODEL_CANDIDATES:

            candidate = directory / filename

            if candidate.exists():
                return candidate

    # --------------------------------------------------------
    # Recursive search
    # --------------------------------------------------------

    for directory in [
        BASE_DIR,
        BASE_DIR.parent,
    ]:

        try:

            for candidate in directory.rglob("*"):

                if (
                    candidate.is_file()
                    and candidate.suffix.lower()
                    in {
                        ".keras",
                        ".h5",
                        ".hdf5",
                    }
                    and candidate.name
                    in MODEL_CANDIDATES
                ):

                    return candidate

        except Exception:
            pass

    return None


# ============================================================
# LOAD MODEL
# ============================================================

def load_model_once():

    global MODEL
    global MODEL_PATH

    if MODEL is not None:
        return MODEL

    MODEL_PATH = find_model()

    if MODEL_PATH is None:

        print(
            "[Model] No model file found."
        )

        print(
            "[Model] Login and MongoDB will still work."
        )

        print(
            "[Model] Classification requires a .keras/.h5 model."
        )

        return None

    try:

        from tensorflow.keras.models import load_model

        print(
            f"[Model] Loading: {MODEL_PATH}"
        )

        MODEL = load_model(MODEL_PATH)

        print(
            "[Model] Loaded successfully!"
        )

        return MODEL

    except Exception as exc:

        print(
            "[Model] Failed to load:"
        )

        print(exc)

        traceback.print_exc()

        MODEL = None

        return None


# ============================================================
# DISPOSAL GUIDES
# ============================================================

DISPOSAL_GUIDES = {

    "recyclable": {

        "label": "Recyclable ♻️",

        "summary": (
            "This item can generally be recovered "
            "through recycling. Keep it clean and dry "
            "and follow your local recycling rules."
        ),

        "steps": [

            {
                "title": "Clean it",
                "detail": (
                    "Remove food, liquid and other "
                    "contamination when possible."
                ),
            },

            {
                "title": "Separate materials",
                "detail": (
                    "Remove parts that belong in another "
                    "waste stream."
                ),
            },

            {
                "title": "Use the recycling bin",
                "detail": (
                    "Place it in the appropriate "
                    "recycling collection."
                ),
            },
        ],

        "avoid": [

            "Do not put heavily contaminated material into recycling.",

            "Check local recycling rules because accepted "
            "materials vary.",
        ],
    },


    "non_recyclable": {

        "label": "General Waste 🗑️",

        "summary": (
            "This item is best treated as general waste "
            "when it cannot be reused or accepted by "
            "your local recycling system."
        ),

        "steps": [

            {
                "title": "Check for reuse",
                "detail": (
                    "Reuse or repair the item if there "
                    "is a practical option."
                ),
            },

            {
                "title": "Separate special waste",
                "detail": (
                    "Make sure it is not actually "
                    "e-waste or hazardous waste."
                ),
            },

            {
                "title": "Use general waste",
                "detail": (
                    "Put it in the appropriate "
                    "general-waste collection."
                ),
            },
        ],

        "avoid": [

            "Do not burn waste.",

            "Do not mix hazardous materials "
            "with ordinary household waste.",
        ],
    },


    "e_waste": {

        "label": "E-Waste ⚡",

        "summary": (
            "Electronic waste should be collected "
            "separately so useful materials can be "
            "recovered and harmful components handled safely."
        ),

        "steps": [

            {
                "title": "Keep it separate",
                "detail": (
                    "Do not put electronic items in "
                    "ordinary recycling or general waste."
                ),
            },

            {
                "title": "Protect the item",
                "detail": (
                    "Avoid damaging batteries, screens "
                    "and electronic components."
                ),
            },

            {
                "title": "Use an e-waste collection point",
                "detail": (
                    "Take it to an authorized e-waste "
                    "recycler or collection center."
                ),
            },
        ],

        "avoid": [

            "Do not burn or dismantle electronics unnecessarily.",

            "Do not put batteries or electronics "
            "into ordinary waste bins.",
        ],
    },
}


# ============================================================
# REWARDS
# ============================================================

BADGE_DEFINITIONS = [

    {
        "name": "First Scan",
        "description": "Complete your first waste scan.",
    },

    {
        "name": "Recycler",
        "description": "Classify recyclable waste.",
    },

    {
        "name": "E-Waste Hero",
        "description": "Classify e-waste.",
    },

    {
        "name": "Century Club",
        "description": "Reach 100 eco-points.",
    },

    {
        "name": "Half-K Hero",
        "description": "Reach 500 eco-points.",
    },

    {
        "name": "Eco Champion",
        "description": "Reach 1000 eco-points.",
    },

    {
        "name": "7-Day Streak",
        "description": "Maintain a 7-day scanning streak.",
    },
]


# ============================================================
# POINTS
# ============================================================

def points_for_category(category):

    return {

        "recyclable": 10,

        "non_recyclable": 5,

        "e_waste": 15,

    }.get(category, 5)


# ============================================================
# LEVEL
# ============================================================

def calculate_level(points):

    points = int(points or 0)

    level = max(
        1,
        int(points // 100) + 1
    )

    titles = {

        1: "Seedling",

        2: "Sprout",

        3: "Green Guardian",

        4: "Eco Explorer",

        5: "Eco Champion",

        6: "Planet Protector",

        7: "Earth Hero",

        8: "Sustainability Star",

        9: "Green Legend",

        10: "Earth Guardian",
    }

    title = titles.get(
        level,
        "Earth Guardian",
    )

    next_level_points = level * 100

    points_to_next = max(
        0,
        next_level_points - points,
    )

    return (
        level,
        title,
        points_to_next,
    )


# ============================================================
# DATE HELPERS
# ============================================================

def utc_now():

    return datetime.now(
        timezone.utc
    )


def normalize_timestamp(value):

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:

        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


# ============================================================
# STREAK
# ============================================================

def update_streak(user):

    now = utc_now()

    today = now.date()

    previous = normalize_timestamp(
        user.get("last_scan_at")
    )

    old_streak = int(
        user.get("streak", 0) or 0
    )

    if previous is None:

        streak = 1

    else:

        previous_day = previous.date()

        difference = (
            today - previous_day
        ).days

        if difference == 0:

            streak = max(
                old_streak,
                1
            )

        elif difference == 1:

            streak = (
                max(old_streak, 0)
                + 1
            )

        else:

            streak = 1

    return (
        streak,
        now
    )


# ============================================================
# BADGES
# ============================================================

def calculate_badges(
    user,
    category,
    streak,
):

    points = int(
        user.get("points", 0) or 0
    )

    total_scans = int(
        user.get("total_scans", 0)
        or user.get("scan_count", 0)
        or 0
    )

    existing_badges = user.get(
        "badges",
        []
    )

    earned = set()

    for badge in existing_badges:

        if isinstance(badge, dict):

            name = badge.get("name")

            if name:
                earned.add(name)

        elif isinstance(badge, str):

            earned.add(badge)

    candidates = set()

    if total_scans >= 1:

        candidates.add(
            "First Scan"
        )

    if category == "recyclable":

        candidates.add(
            "Recycler"
        )

    if category == "e_waste":

        candidates.add(
            "E-Waste Hero"
        )

    if points >= 100:

        candidates.add(
            "Century Club"
        )

    if points >= 500:

        candidates.add(
            "Half-K Hero"
        )

    if points >= 1000:

        candidates.add(
            "Eco Champion"
        )

    if streak >= 7:

        candidates.add(
            "7-Day Streak"
        )

    newly_earned = []

    for badge in BADGE_DEFINITIONS:

        name = badge["name"]

        if (
            name in candidates
            and name not in earned
        ):

            newly_earned.append(
                {
                    "name": name,
                    "description": badge["description"],
                }
            )

    all_badges = []

    # Preserve existing badge objects
    for badge in existing_badges:

        if isinstance(badge, dict):

            if badge.get("name") not in {
                b["name"]
                for b in all_badges
            }:

                all_badges.append(badge)

        elif isinstance(badge, str):

            all_badges.append(
                {
                    "name": badge,
                    "description": "",
                }
            )

    # Add newly earned badges
    existing_names = {
        badge.get("name")
        for badge in all_badges
        if isinstance(badge, dict)
    }

    for badge in newly_earned:

        if badge["name"] not in existing_names:

            all_badges.append(badge)

    return (
        all_badges,
        newly_earned,
    )


# ============================================================
# SERIALIZE USER
# ============================================================

def serialize_user(user):

    points = int(
        user.get("points", 0)
        or 0
    )

    level, level_title, points_to_next = calculate_level(
        points
    )

    total_scans = int(
        user.get("total_scans", 0)
        or user.get("scan_count", 0)
        or 0
    )

    total_classifications = int(
        user.get("total_classifications", 0)
        or total_scans
    )

    return {

        "id": str(
            user["_id"]
        ),

        "name": user.get(
            "name",
            user.get(
                "username",
                ""
            ),
        ),

        "email": user.get(
            "email",
            ""
        ),

        "username": user.get(
            "username",
            ""
        ),

        "points": points,

        "level": level,

        "level_title": level_title,

        "points_to_next_level": points_to_next,

        "streak": int(
            user.get("streak", 0)
            or 0
        ),

        "total_scans": total_scans,

        "total_classifications": total_classifications,

        # Backward compatibility
        "scan_count": total_scans,

        "recyclable_count": int(
            user.get("recyclable_count", 0)
            or 0
        ),

        "non_recyclable_count": int(
            user.get("non_recyclable_count", 0)
            or 0
        ),

        "e_waste_count": int(
            user.get("e_waste_count", 0)
            or 0
        ),

        "badges": user.get(
            "badges",
            []
        ),
    }


# ============================================================
# AUTH HELPERS
# ============================================================

def find_user_by_identity(identity):

    try:

        object_id = ObjectId(
            str(identity)
        )

        return users_collection.find_one(
            {
                "_id": object_id
            }
        )

    except Exception:

        return users_collection.find_one(
            {
                "email": str(identity).lower()
            }
        )


def get_current_user():

    identity = get_jwt_identity()

    return find_user_by_identity(
        identity
    )


# ============================================================
# FRONTEND
# ============================================================

def find_frontend_file(filename):

    for directory in FRONTEND_CANDIDATES:

        candidate = directory / filename

        if (
            candidate.exists()
            and candidate.is_file()
        ):

            return candidate

    return None


@app.route("/")
def root():

    login_file = find_frontend_file(
        "login.html"
    )

    if login_file:

        return send_from_directory(
            login_file.parent,
            login_file.name,
        )

    return jsonify(
        {
            "message": "SortWise backend is running.",
            "login": "/login.html",
            "dashboard": "/index.html",
            "health": "/api/health",
        }
    )


@app.route("/login.html")
def login_page():

    file = find_frontend_file(
        "login.html"
    )

    if not file:

        return jsonify(
            {
                "error": "login.html not found"
            }
        ), 404

    return send_from_directory(
        file.parent,
        file.name,
    )


@app.route("/index.html")
def index_page():

    file = find_frontend_file(
        "index.html"
    )

    if not file:

        return jsonify(
            {
                "error": "index.html not found"
            }
        ), 404

    return send_from_directory(
        file.parent,
        file.name,
    )


@app.route("/<path:filename>")
def frontend_files(filename):

    if filename.startswith("api/"):

        return jsonify(
            {
                "error": "API endpoint not found"
            }
        ), 404

    file = find_frontend_file(
        filename
    )

    if file:

        return send_from_directory(
            file.parent,
            file.name,
        )

    return jsonify(
        {
            "error": "File not found"
        }
    ), 404


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    model_path = find_model()

    return jsonify(
        {
            "status": "ok",

            "service": "SortWise",

            "mongodb": True,

            "database": MONGO_DB_NAME,

            "model_available": (
                MODEL is not None
                or model_path is not None
            ),

            "model_path": (
                str(MODEL_PATH)
                if MODEL_PATH
                else (
                    str(model_path)
                    if model_path
                    else None
                )
            ),

            "classes": CLASS_NAMES,

            "class_order_verified":
                CLASS_ORDER_VERIFIED,

            "groq": {
                "model": GROQ_MODEL,
                "api_key_set": bool(GROQ_API_KEY),
            },
        }
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
def register():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        name = str(
            data.get("name", "")
        ).strip()

        email = str(
            data.get("email", "")
        ).strip().lower()

        password = str(
            data.get("password", "")
        )

        username = str(
            data.get("username")
            or name
            or email.split("@")[0]
        ).strip()

        if not email or "@" not in email:

            return jsonify(
                {
                    "error":
                    "Enter a valid email."
                }
            ), 400

        if len(password) < 6:

            return jsonify(
                {
                    "error":
                    "Password must be at least 6 characters."
                }
            ), 400

        if not username:

            return jsonify(
                {
                    "error":
                    "Username is required."
                }
            ), 400

        # ----------------------------------------------------
        # Check duplicate email
        # ----------------------------------------------------

        if users_collection.find_one(
            {
                "email": email
            }
        ):

            return jsonify(
                {
                    "error":
                    "Email is already registered."
                }
            ), 409

        # ----------------------------------------------------
        # Check duplicate username
        # ----------------------------------------------------

        if users_collection.find_one(
            {
                "username": username
            }
        ):

            return jsonify(
                {
                    "error":
                    "Username is already taken."
                }
            ), 409

        now = utc_now()

        user = {

            "name": (
                name
                if name
                else username
            ),

            "email": email,

            "username": username,

            "password":
                generate_password_hash(
                    password
                ),

            # ----------------------------------------------
            # Reward statistics
            # ----------------------------------------------

            "points": 0,

            "total_scans": 0,

            "total_classifications": 0,

            # Backward compatibility
            "scan_count": 0,

            "recyclable_count": 0,

            "non_recyclable_count": 0,

            "e_waste_count": 0,

            "streak": 0,

            "last_scan_at": None,

            "badges": [],

            "created_at": now,
        }

        result = users_collection.insert_one(
            user
        )

        user["_id"] = result.inserted_id

        token = create_access_token(
            identity=str(
                user["_id"]
            )
        )

        return jsonify(
            {
                "message":
                    "Registration successful",

                "token":
                    token,

                "access_token":
                    token,

                "user":
                    serialize_user(user),
            }
        ), 201

    except Exception as exc:

        print(
            "[Register] ERROR:",
            exc
        )

        traceback.print_exc()

        return jsonify(
            {
                "error":
                    "Registration failed.",

                "details":
                    str(exc),
            }
        ), 500


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    try:

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify(
                {
                    "error":
                    "Request must contain JSON data."
                }
            ), 400

        email = str(
            data.get("email", "")
        ).strip().lower()

        password = str(
            data.get("password", "")
        )

        if not email or not password:

            return jsonify(
                {
                    "error":
                    "Email and password are required."
                }
            ), 400

        user = users_collection.find_one(
            {
                "email": email
            }
        )

        if not user:

            return jsonify(
                {
                    "error":
                    "Invalid email or password."
                }
            ), 401

        stored_password = str(
            user.get("password")
            or user.get("password_hash")
            or ""
        )

        password_valid = False

        # ----------------------------------------------------
        # Hashed password
        # ----------------------------------------------------

        if stored_password:

            try:

                password_valid = (
                    check_password_hash(
                        stored_password,
                        password,
                    )
                )

            except Exception:

                password_valid = False

            # ------------------------------------------------
            # Old database compatibility
            # ------------------------------------------------

            if (
                not password_valid
                and stored_password == password
            ):

                password_valid = True

                users_collection.update_one(
                    {
                        "_id":
                            user["_id"]
                    },
                    {
                        "$set":
                        {
                            "password":
                                generate_password_hash(
                                    password
                                )
                        }
                    },
                )

        if not password_valid:

            return jsonify(
                {
                    "error":
                    "Invalid email or password."
                }
            ), 401

        # ----------------------------------------------------
        # Upgrade older users
        # ----------------------------------------------------

        updates = {}

        if "name" not in user:

            updates["name"] = user.get(
                "username",
                email.split("@")[0],
            )

        if "username" not in user:

            updates["username"] = (
                email.split("@")[0]
            )

        if "points" not in user:

            updates["points"] = 0

        if "total_scans" not in user:

            updates["total_scans"] = int(
                user.get(
                    "scan_count",
                    0
                )
                or 0
            )

        if "total_classifications" not in user:

            updates[
                "total_classifications"
            ] = int(
                user.get(
                    "scan_count",
                    0
                )
                or 0
            )

        if "scan_count" not in user:

            updates["scan_count"] = int(
                user.get(
                    "total_scans",
                    0
                )
                or 0
            )

        if "recyclable_count" not in user:

            updates["recyclable_count"] = 0

        if "non_recyclable_count" not in user:

            updates[
                "non_recyclable_count"
            ] = 0

        if "e_waste_count" not in user:

            updates["e_waste_count"] = 0

        if "streak" not in user:

            updates["streak"] = 0

        if "last_scan_at" not in user:

            updates["last_scan_at"] = None

        if "badges" not in user:

            updates["badges"] = []

        if updates:

            users_collection.update_one(
                {
                    "_id":
                        user["_id"]
                },
                {
                    "$set":
                        updates
                },
            )

            user.update(updates)

        token = create_access_token(
            identity=str(
                user["_id"]
            )
        )

        return jsonify(
            {
                "message":
                    "Login successful",

                "token":
                    token,

                "access_token":
                    token,

                "user":
                    serialize_user(user),
            }
        ), 200

    except Exception as exc:

        print(
            "[Login] ERROR:",
            exc
        )

        traceback.print_exc()

        return jsonify(
            {
                "error":
                    "Internal server error.",

                "details":
                    str(exc),
            }
        ), 500


# ============================================================
# CURRENT USER
# ============================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
@jwt_required()
def me():

    try:

        user = get_current_user()

        if not user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        return jsonify(
            serialize_user(user)
        ), 200

    except Exception as exc:

        print(
            "[Me] ERROR:",
            exc
        )

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# PROFILE
# ============================================================

@app.route(
    "/api/profile",
    methods=["GET"]
)
@jwt_required()
def get_profile():

    try:

        user = get_current_user()

        if not user:

            return jsonify(
                {
                    "success": False,
                    "message":
                        "User not found",
                }
            ), 404

        return jsonify(
            {
                "success": True,

                "user":
                    serialize_user(user),
            }
        ), 200

    except Exception as exc:

        print(
            "[Profile] ERROR:",
            exc
        )

        return jsonify(
            {
                "success": False,

                "message":
                    "Unable to load profile",

                "error":
                    str(exc),
            }
        ), 500


# ============================================================
# PROFILE BY USERNAME
# ============================================================

@app.route(
    "/api/profile/<username>",
    methods=["GET"]
)
@jwt_required()
def profile_by_username(username):

    try:

        current_user = get_current_user()

        if not current_user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        requested = str(
            username
        ).strip()

        current_username = current_user.get(
            "username",
            ""
        )

        current_email = current_user.get(
            "email",
            ""
        )

        if requested not in {
            current_username,
            current_email,
        }:

            return jsonify(
                {
                    "error":
                    "Access denied."
                }
            ), 403

        return jsonify(
            serialize_user(
                current_user
            )
        ), 200

    except Exception as exc:

        print(
            "[Profile] ERROR:",
            exc
        )

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# UPDATE PROFILE
# ============================================================

@app.route(
    "/api/profile",
    methods=["PUT"]
)
@jwt_required()
def update_profile():

    try:

        current_user = get_current_user()

        if not current_user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        new_name = str(
            data.get("name", "")
        ).strip()

        new_username = str(
            data.get("username", "")
        ).strip()

        # ----------------------------------------------------
        # If neither supplied, keep current values
        # ----------------------------------------------------

        if not new_name:

            new_name = current_user.get(
                "name",
                current_user.get(
                    "username",
                    ""
                ),
            )

        if not new_username:

            new_username = current_user.get(
                "username",
                ""
            )

        if not new_username:

            return jsonify(
                {
                    "error":
                    "Username cannot be empty."
                }
            ), 400

        # ----------------------------------------------------
        # Check username uniqueness
        # ----------------------------------------------------

        existing = users_collection.find_one(
            {
                "username":
                    new_username,

                "_id":
                    {
                        "$ne":
                            current_user["_id"]
                    },
            }
        )

        if existing:

            return jsonify(
                {
                    "error":
                    "Username is already taken."
                }
            ), 409

        users_collection.update_one(
            {
                "_id":
                    current_user["_id"]
            },
            {
                "$set":
                {
                    "name":
                        new_name,

                    "username":
                        new_username,
                }
            },
        )

        updated = users_collection.find_one(
            {
                "_id":
                    current_user["_id"]
            }
        )

        return jsonify(
            serialize_user(updated)
        ), 200

    except Exception as exc:

        print(
            "[Update Profile] ERROR:",
            exc
        )

        traceback.print_exc()

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# IMAGE PREPARATION
# ============================================================

def prepare_image(file_storage):

    try:

        image = Image.open(
            file_storage
        ).convert("RGB")

    except Exception:

        raise ValueError(
            "The uploaded file is not a valid image."
        )

    image = image.resize(
        IMAGE_SIZE
    )

    array = np.asarray(
        image,
        dtype=np.float32
    )

    array = (array / 127.5) - 1.0

    array = np.expand_dims(
        array,
        axis=0
    )

    return array


# ============================================================
# NORMALIZE MODEL OUTPUT
# ============================================================

def normalize_prediction_output(
    raw_prediction
):

    if isinstance(
        raw_prediction,
        dict
    ):

        raw_prediction = next(
            iter(
                raw_prediction.values()
            )
        )

    if isinstance(
        raw_prediction,
        (
            list,
            tuple,
        )
    ):

        raw_prediction = raw_prediction[0]

    probabilities = np.asarray(
        raw_prediction,
        dtype=np.float32
    )

    probabilities = np.squeeze(
        probabilities
    )

    if probabilities.ndim != 1:

        probabilities = probabilities.reshape(
            -1
        )

    if len(probabilities) != len(
        CLASS_NAMES
    ):

        raise ValueError(
            f"Model returned "
            f"{len(probabilities)} outputs, "
            f"but SortWise expects "
            f"{len(CLASS_NAMES)} classes: "
            f"{CLASS_NAMES}"
        )

    # --------------------------------------------------------
    # Detect logits vs probabilities
    # --------------------------------------------------------

    if (
        np.any(
            probabilities < 0
        )
        or not np.isclose(
            float(
                np.sum(
                    probabilities
                )
            ),
            1.0,
            atol=0.05,
        )
    ):

        # Softmax
        exp_values = np.exp(
            probabilities
            - np.max(
                probabilities
            )
        )

        probabilities = (
            exp_values
            / np.sum(exp_values)
        )

    else:

        total = float(
            np.sum(
                probabilities
            )
        )

        if total > 0:

            probabilities = (
                probabilities
                / total
            )

    return probabilities


# ============================================================
# CLASSIFY IMAGE
# ============================================================

def classify_image(file_storage):

    model = load_model_once()

    if model is None:

        raise RuntimeError(
            "Waste classification model "
            "was not found or could not be loaded. "
            "Put your .keras/.h5 model in the backend "
            "folder or set MODEL_PATH."
        )

    image_array = prepare_image(
        file_storage
    )

    raw_prediction = model.predict(
        image_array,
        verbose=0,
    )

    probabilities = (
        normalize_prediction_output(
            raw_prediction
        )
    )

    predicted_index = int(
        np.argmax(
            probabilities
        )
    )

    category = CLASS_NAMES[
        predicted_index
    ]

    confidence = float(
        probabilities[
            predicted_index
        ]
    )

    all_probabilities = {

        CLASS_NAMES[i]:
            float(
                probabilities[i]
            )

        for i in range(
            len(CLASS_NAMES)
        )
    }

    return {

        "category":
            category,

        "confidence":
            confidence,

        "low_confidence_warning":
            confidence < 0.60,

        "all_probabilities":
            all_probabilities,
    }


# ============================================================
# CLASSIFY API
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {

    ".jpg",

    ".jpeg",

    ".png",

    ".webp",

    ".bmp",
}


@app.route(
    "/api/classify",
    methods=["POST"]
)
@jwt_required()
def classify():

    try:

        current_user = get_current_user()

        if not current_user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        # ----------------------------------------------------
        # Check image
        # ----------------------------------------------------

        if "image" not in request.files:

            return jsonify(
                {
                    "error":
                    "No image was uploaded."
                }
            ), 400

        image_file = request.files[
            "image"
        ]

        if (
            not image_file
            or not image_file.filename
        ):

            return jsonify(
                {
                    "error":
                    "Please select an image."
                }
            ), 400

        safe_filename = secure_filename(
            image_file.filename
        )

        extension = Path(
            safe_filename
        ).suffix.lower()

        if extension not in ALLOWED_IMAGE_EXTENSIONS:

            return jsonify(
                {
                    "error":
                    (
                        "Unsupported image format. "
                        "Use JPG, JPEG, PNG, WEBP or BMP."
                    )
                }
            ), 400

        # ----------------------------------------------------
        # Run model
        # ----------------------------------------------------

        prediction = classify_image(
            image_file
        )

        category = prediction[
            "category"
        ]

        points_earned = points_for_category(
            category
        )

        # ----------------------------------------------------
        # Get old statistics
        # ----------------------------------------------------

        old_points = int(
            current_user.get(
                "points",
                0
            )
            or 0
        )

        old_total_scans = int(
            current_user.get(
                "total_scans",
                current_user.get(
                    "scan_count",
                    0
                ),
            )
            or 0
        )

        old_total_classifications = int(
            current_user.get(
                "total_classifications",
                old_total_scans,
            )
            or 0
        )

        new_points = (
            old_points
            + points_earned
        )

        new_total_scans = (
            old_total_scans
            + 1
        )

        new_total_classifications = (
            old_total_classifications
            + 1
        )

        # ----------------------------------------------------
        # Calculate streak
        # ----------------------------------------------------

        streak, now = update_streak(
            current_user
        )

        # ----------------------------------------------------
        # Temporary user for badges
        # ----------------------------------------------------

        temp_user = dict(
            current_user
        )

        temp_user[
            "points"
        ] = new_points

        temp_user[
            "total_scans"
        ] = new_total_scans

        temp_user[
            "total_classifications"
        ] = new_total_classifications

        temp_user[
            "scan_count"
        ] = new_total_scans

        temp_user[
            "streak"
        ] = streak

        badges, newly_earned = (
            calculate_badges(
                temp_user,
                category,
                streak,
            )
        )

        # ----------------------------------------------------
        # Category-specific increment
        # ----------------------------------------------------

        category_increment = {

            "recyclable": {
                "recyclable_count": 1
            },

            "non_recyclable": {
                "non_recyclable_count": 1
            },

            "e_waste": {
                "e_waste_count": 1
            },
        }

        increment_fields = {

            "points":
                points_earned,

            "total_scans":
                1,

            "total_classifications":
                1,

            # Backward compatibility
            "scan_count":
                1,
        }

        increment_fields.update(
            category_increment.get(
                category,
                {}
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Use $inc for persistent statistics.
        # This prevents lost updates.
        # ----------------------------------------------------

        users_collection.update_one(
            {
                "_id":
                    current_user["_id"]
            },

            {
                "$inc":
                    increment_fields,

                "$set":
                {
                    "streak":
                        streak,

                    "last_scan_at":
                        now,

                    "badges":
                        badges,
                },
            },
        )

        # ----------------------------------------------------
        # Store scan history
        # ----------------------------------------------------

        scan_document = {

            "user_id":
                current_user["_id"],

            "username":
                current_user.get(
                    "username",
                    current_user.get(
                        "email",
                        ""
                    ),
                ),

            "name":
                current_user.get(
                    "name",
                    current_user.get(
                        "username",
                        ""
                    ),
                ),

            "category":
                category,

            "confidence":
                prediction[
                    "confidence"
                ],

            "all_probabilities":
                prediction[
                    "all_probabilities"
                ],

            "points_earned":
                points_earned,

            "timestamp":
                now,

            "original_filename":
                safe_filename,
        }

        scans_collection.insert_one(
            scan_document
        )

        # ----------------------------------------------------
        # Calculate level
        # ----------------------------------------------------

        (
            level,
            level_title,
            points_to_next,
        ) = calculate_level(
            new_points
        )

        # ----------------------------------------------------
        # Reward response
        # ----------------------------------------------------

        reward = {

            "points_earned":
                points_earned,

            "total_points":
                new_points,

            "total_scans":
                new_total_scans,

            "total_classifications":
                new_total_classifications,

            "level":
                level,

            "level_title":
                level_title,

            "points_to_next_level":
                points_to_next,

            "streak":
                streak,

            "newly_earned_badges":
                newly_earned,
        }

        return jsonify(
            {

                "success":
                    True,

                "prediction":
                    prediction,

                "disposal_guide":
                    DISPOSAL_GUIDES[
                        category
                    ],

                "reward":
                    reward,

                "class_order_verified":
                    CLASS_ORDER_VERIFIED,
            }
        ), 200

    except ValueError as exc:

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 400

    except Exception as exc:

        print(
            "[Classify] ERROR:",
            exc
        )

        traceback.print_exc()

        return jsonify(
            {
                "error":
                    "Classification failed.",

                "details":
                    str(exc),
            }
        ), 500


# ============================================================
# HISTORY
# ============================================================

@app.route(
    "/api/history/<username>",
    methods=["GET"]
)
@jwt_required()
def history(username):

    try:

        current_user = get_current_user()

        if not current_user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        requested = str(
            username
        ).strip()

        if requested not in {

            current_user.get(
                "username",
                ""
            ),

            current_user.get(
                "email",
                ""
            ),
        }:

            return jsonify(
                {
                    "error":
                    "Access denied."
                }
            ), 403

        rows = list(

            scans_collection.find(

                {
                    "user_id":
                        current_user["_id"]
                },

                {
                    "_id": 0,

                    "username": 1,

                    "name": 1,

                    "category": 1,

                    "confidence": 1,

                    "points_earned": 1,

                    "timestamp": 1,

                    "original_filename": 1,
                },

            )
            .sort(
                "timestamp",
                -1
            )
            .limit(100)
        )

        result = []

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if isinstance(
                timestamp,
                datetime
            ):

                timestamp = (
                    normalize_timestamp(
                        timestamp
                    ).isoformat()
                )

            result.append(
                {

                    "username":
                        row.get(
                            "username",
                            ""
                        ),

                    "name":
                        row.get(
                            "name",
                            ""
                        ),

                    "category":
                        row.get(
                            "category",
                            ""
                        ),

                    "confidence":
                        float(
                            row.get(
                                "confidence",
                                0
                            )
                        ),

                    "points_earned":
                        int(
                            row.get(
                                "points_earned",
                                0
                            )
                        ),

                    "timestamp":
                        timestamp,

                    "original_filename":
                        row.get(
                            "original_filename",
                            ""
                        ),
                }
            )

        return jsonify(
            result
        ), 200

    except Exception as exc:

        print(
            "[History] ERROR:",
            exc
        )

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# MY HISTORY
# ============================================================

@app.route(
    "/api/history",
    methods=["GET"]
)
@jwt_required()
def my_history():

    try:

        current_user = get_current_user()

        if not current_user:

            return jsonify(
                {
                    "error":
                    "User not found."
                }
            ), 404

        rows = list(

            scans_collection.find(

                {
                    "user_id":
                        current_user["_id"]
                },

                {
                    "_id": 0,

                    "username": 1,

                    "name": 1,

                    "category": 1,

                    "confidence": 1,

                    "points_earned": 1,

                    "timestamp": 1,

                    "original_filename": 1,
                },

            )
            .sort(
                "timestamp",
                -1
            )
            .limit(100)
        )

        result = []

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if isinstance(
                timestamp,
                datetime
            ):

                timestamp = (
                    normalize_timestamp(
                        timestamp
                    ).isoformat()
                )

            result.append(
                {

                    "username":
                        row.get(
                            "username",
                            ""
                        ),

                    "name":
                        row.get(
                            "name",
                            ""
                        ),

                    "category":
                        row.get(
                            "category",
                            ""
                        ),

                    "confidence":
                        float(
                            row.get(
                                "confidence",
                                0
                            )
                        ),

                    "points_earned":
                        int(
                            row.get(
                                "points_earned",
                                0
                            )
                        ),

                    "timestamp":
                        timestamp,

                    "original_filename":
                        row.get(
                            "original_filename",
                            ""
                        ),
                }
            )

        return jsonify(
            result
        ), 200

    except Exception as exc:

        print(
            "[My History] ERROR:",
            exc
        )

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# LEADERBOARD
# ============================================================

@app.route(
    "/api/leaderboard",
    methods=["GET"]
)
@jwt_required()
def leaderboard():

    try:

        rows = list(

            users_collection.find(

                {},

                {
                    "_id": 0,

                    "name": 1,

                    "username": 1,

                    "email": 1,

                    "points": 1,

                    "streak": 1,

                    "total_scans": 1,

                    "total_classifications": 1,
                },

            )
            .sort(
                [
                    (
                        "points",
                        -1
                    ),

                    (
                        "streak",
                        -1
                    ),
                ]
            )
            .limit(50)
        )

        result = []

        for index, row in enumerate(
            rows,
            start=1
        ):

            total_scans = int(
                row.get(
                    "total_scans",
                    0
                )
                or 0
            )

            result.append(
                {

                    "rank":
                        index,

                    "name":
                        row.get(
                            "name",
                            row.get(
                                "username",
                                "User"
                            ),
                        ),

                    "username":
                        row.get(
                            "username",
                            row.get(
                                "email",
                                "User"
                            ),
                        ),

                    "points":
                        int(
                            row.get(
                                "points",
                                0
                            )
                            or 0
                        ),

                    "streak":
                        int(
                            row.get(
                                "streak",
                                0
                            )
                            or 0
                        ),

                    "total_scans":
                        total_scans,

                    "total_classifications":
                        int(
                            row.get(
                                "total_classifications",
                                total_scans,
                            )
                            or 0
                        ),
                }
            )

        return jsonify(
            result
        ), 200

    except Exception as exc:

        print(
            "[Leaderboard] ERROR:",
            exc
        )

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    # JWT is stored client-side.
    # Frontend removes the token.

    return jsonify(
        {
            "success": True,

            "message":
                "Logged out successfully",
        }
    ), 200




# ============================================================
# GROQ AI CHATBOT
# ============================================================

@app.route("/api/chat", methods=["POST"])
@jwt_required()
def chat_with_groq():
    """
    Send a SortWise waste-management question to the Groq cloud API.

    Requires GROQ_API_KEY environment variable to be set.
    Get a free key at https://console.groq.com
    """

    try:
        # --------------------------------------------------------
        # Guard: API key must be configured
        # --------------------------------------------------------
        if not GROQ_API_KEY:
            return jsonify({
                "success": False,
                "error": (
                    "GROQ_API_KEY is not set. "
                    "Add it to your .env file or environment variables. "
                    "Get a free key at https://console.groq.com"
                ),
            }), 503

        data = request.get_json(silent=True) or {}

        user_message = str(data.get("message", "")).strip()

        if not user_message:
            return jsonify({
                "success": False,
                "error": "Please enter a message.",
            }), 400

        if len(user_message) > 2000:
            return jsonify({
                "success": False,
                "error": "Message is too long. Please keep it under 2000 characters.",
            }), 400

        # Only accept a small, safe conversation window from the frontend.
        raw_history = data.get("history", [])
        history = []

        if isinstance(raw_history, list):
            for item in raw_history[-8:]:
                if not isinstance(item, dict):
                    continue

                role = item.get("role")
                content = str(item.get("content", "")).strip()

                if role not in {"user", "assistant"} or not content:
                    continue

                history.append({
                    "role": role,
                    "content": content[:2000],
                })

        system_prompt = (
            "You are SortWise AI, the assistant inside the SortWise "
            "waste-classification application.\n\n"
            "Your purpose is to help users understand waste segregation, "
            "recycling, e-waste and safe disposal. "
            "SortWise uses three categories: Recyclable, Non-Recyclable, E-Waste.\n\n"
            "Rules:\n"
            "- Use simple, clear language suitable for a college project app.\n"
            "- Explain an item's likely category and practical disposal steps.\n"
            "- Local recycling rules vary; do not generalise.\n"
            "- For batteries, electronics, chemicals, medicines and hazardous "
            "materials, recommend an authorised collection point.\n"
            "- Never invent specific recycling centres, phone numbers or services.\n"
            "- If uncertain, say so.\n"
            "- Keep answers concise: 3-8 sentences or short bullet points.\n"
            "- Politely redirect unrelated questions back to waste management."
        )

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # --------------------------------------------------------
        # Call Groq API (OpenAI-compatible endpoint)
        # --------------------------------------------------------
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1024,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            GROQ_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            print(
                "[Groq] HTTP error:",
                response.status_code,
                response.text[:500],
            )
            # Surface a helpful message for common errors
            if response.status_code == 401:
                error_msg = "Invalid GROQ_API_KEY. Check your key at https://console.groq.com"
            elif response.status_code == 429:
                error_msg = "Groq rate limit reached. Please wait a moment and try again."
            elif response.status_code == 400:
                error_msg = f"Bad request to Groq: {response.text[:200]}"
            else:
                error_msg = f"Groq API error ({response.status_code}). Please try again."

            return jsonify({
                "success": False,
                "error": error_msg,
            }), 502

        result = response.json()

        # Groq uses the OpenAI response shape:
        # result["choices"][0]["message"]["content"]
        try:
            answer = str(
                result["choices"][0]["message"]["content"]
            ).strip()
        except (KeyError, IndexError):
            answer = ""

        if not answer:
            return jsonify({
                "success": False,
                "error": "Groq returned an empty response.",
            }), 502

        return jsonify({
            "success": True,
            "response": answer,
            "model": GROQ_MODEL,
        }), 200

    except requests.exceptions.ConnectionError:
        return jsonify({
            "success": False,
            "error": "Cannot reach Groq API. Check your internet connection.",
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "error": "Groq API timed out. Please try again.",
        }), 504

    except Exception as exc:
        print("[Groq] Chatbot error:", exc)
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "Unable to process the chatbot request.",
        }), 500

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def handle_404(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify(
            {
                "error":
                    "API endpoint not found",

                "path":
                    request.path,
            }
        ), 404

    return jsonify(
        {
            "error":
                "Page not found"
        }
    ), 404


@app.errorhandler(413)
def handle_413(error):

    return jsonify(
        {
            "error":
                "Image/file is too large. "
                "Maximum size is 8 MB."
        }
    ), 413


@app.errorhandler(500)
def handle_500(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify(
            {
                "error":
                    "Internal server error"
            }
        ), 500

    return jsonify(
        {
            "error":
                "Internal server error"
        }
    ), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    print()
    print("=" * 65)
    print(
        "SORTWISE - KNOW BEFORE YOU THROW"
    )
    print("=" * 65)

    print(
        f"Backend folder : {BASE_DIR}"
    )

    print(
        f"MongoDB        : {MONGO_DB_NAME}"
    )

    print(
        f"Mongo URI      : {MONGO_URI}"
    )

    print(
        f"Model          : "
        f"{find_model() or 'NOT FOUND'}"
    )

    print(
        f"Classes        : {CLASS_NAMES}"
    )

    print(
        f"Login          : "
        f"http://127.0.0.1:{port}/login.html"
    )

    print(
        f"Dashboard      : "
        f"http://127.0.0.1:{port}/index.html"
    )

    print(
        f"Health         : "
        f"http://127.0.0.1:{port}/api/health"
    )

    print("=" * 65)
    print()

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
    )

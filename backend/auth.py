import os
import bcrypt
import jwt

from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify

from database import users_collection

auth_bp = Blueprint("auth", __name__)

JWT_SECRET = os.getenv("JWT_SECRET")


@auth_bp.route("/register", methods=["POST"])
def register():

    data = request.get_json() or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    # Validation
    if not username or not email or not password:
        return jsonify({
            "success": False,
            "message": "All fields are required"
        }), 400

    if len(username) < 3:
        return jsonify({
            "success": False,
            "message": "Username must contain at least 3 characters"
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters"
        }), 400

    # Check existing user
    existing = users_collection.find_one({
        "$or": [
            {"email": email},
            {"username": username}
        ]
    })

    if existing:
        return jsonify({
            "success": False,
            "message": "Username or email already exists"
        }), 409

    # Hash password
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    now = datetime.now(timezone.utc)

    user = {
        "username": username,
        "email": email,
        "password_hash": password_hash,

        # Every NEW account starts independently
        "points": 0,

        "total_classifications": 0,

        "recyclable_count": 0,
        "non_recyclable_count": 0,
        "ewaste_count": 0,

        "created_at": now,
        "updated_at": now
    }

    try:

        result = users_collection.insert_one(user)

        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user_id": str(result.inserted_id)
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Could not create account"
        }), 500


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    user = users_collection.find_one({
        "email": email
    })

    if not user:
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    valid_password = bcrypt.checkpw(
        password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    )

    if not valid_password:
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    token = jwt.encode(
        {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "exp": datetime.now(timezone.utc)
                   + timedelta(days=7)
        },
        JWT_SECRET,
        algorithm="HS256"
    )

    return jsonify({
        "success": True,
        "message": "Login successful",

        "token": token,

        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "points": user.get("points", 0)
        }
    })
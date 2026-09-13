import os
import jwt

from functools import wraps
from flask import request, jsonify

JWT_SECRET = os.getenv("JWT_SECRET")


def token_required(function):

    @wraps(function)
    def decorated(*args, **kwargs):

        header = request.headers.get("Authorization")

        if not header:
            return jsonify({
                "success": False,
                "message": "Login required"
            }), 401

        if not header.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Invalid authorization format"
            }), 401

        token = header.split(" ", 1)[1]

        try:

            decoded = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=["HS256"]
            )

            user_id = decoded["user_id"]

        except jwt.ExpiredSignatureError:

            return jsonify({
                "success": False,
                "message": "Session expired. Please login again."
            }), 401

        except jwt.InvalidTokenError:

            return jsonify({
                "success": False,
                "message": "Invalid session"
            }), 401

        return function(user_id, *args, **kwargs)

    return decorated
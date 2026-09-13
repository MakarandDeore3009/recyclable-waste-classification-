"""
MongoDB connection helper.
Reads MONGO_URI from environment / .env file.
Call get_db() to get the database handle anywhere in the app.
"""

import os
from pymongo import MongoClient, DESCENDING, ASCENDING
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

_client = None
_db = None


def connect():
    """
    Open the MongoDB connection and ensure required indexes exist.
    Called once at app startup.
    """
    global _client, _db

    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/sortwise")
    db_name = uri.split("/")[-1].split("?")[0] or "sortwise"

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Ping to confirm connection
        _client.admin.command("ping")
        _db = _client[db_name]
        _ensure_indexes()
        print(f"[DB] Connected to MongoDB — database: {db_name}")
        return True
    except ConnectionFailure as e:
        print(f"[DB] WARNING: Could not connect to MongoDB: {e}")
        print("[DB] Running without a database — auth & leaderboard disabled.")
        return False


def _ensure_indexes():
    """Create indexes if they don't already exist."""
    # users collection
    _db.users.create_index("username", unique=True)
    _db.users.create_index("email", unique=True, sparse=True)
    _db.users.create_index([("points", DESCENDING)])

    # scans collection
    _db.scans.create_index("username")
    _db.scans.create_index([("username", ASCENDING), ("timestamp", DESCENDING)])


def get_db():
    """Return the database handle. Raises RuntimeError if not connected."""
    if _db is None:
        raise RuntimeError("Database not initialised. Call database.connect() first.")
    return _db


def is_connected():
    return _db is not None
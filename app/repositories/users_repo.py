"""Users + RBAC repository."""
from __future__ import annotations

from app.core import database as db


def get_user_by_email(email: str) -> dict | None:
    row = db.query_one(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(?) AND is_active = 1", (email,)
    )
    return dict(row) if row else None


def get_user(user_id: int) -> dict | None:
    row = db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return dict(row) if row else None


def create_user(email: str, password_hash: str, full_name: str = "", roles: list[str] | None = None) -> int:
    user_id = db.execute(
        "INSERT INTO users (email, password_hash, full_name) VALUES (?,?,?)",
        (email, password_hash, full_name),
    )
    for role in roles or ["viewer"]:
        db.execute(
            """INSERT INTO user_roles (user_id, role_id)
               SELECT ?, role_id FROM roles WHERE name = ?""", (user_id, role),
        )
    return user_id


def user_roles(user_id: int) -> list[str]:
    rows = db.query_all(
        """SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id = r.role_id
           WHERE ur.user_id = ?""", (user_id,),
    )
    return [r["name"] for r in rows]


def count_users() -> int:
    row = db.query_one("SELECT COUNT(*) AS c FROM users")
    return int(row["c"]) if row else 0


def log_admin_action(user_id: int | None, action: str, entity_type: str,
                     entity_id: int | None, details: str = "", ip: str = "") -> None:
    db.execute(
        """INSERT INTO admin_actions (user_id, action, entity_type, entity_id, details, ip_address)
           VALUES (?,?,?,?,?,?)""",
        (user_id, action, entity_type, entity_id, details, ip),
    )

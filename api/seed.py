#!/usr/bin/env python3
"""Seed a super-admin user interactively.

Usage:
    python -m api.seed
    # or from project root:
    FLASK_APP=api python -m api.seed
"""
import getpass
import sys

from . import create_app
from .auth import hash_password
from .models import User, UserTenantRole, Tenant, db


def main():
    app = create_app()

    with app.app_context():
        print("=== Create Super-Admin User ===\n")

        email = input("Email: ").strip().lower()
        if not email:
            print("Email is required.")
            sys.exit(1)

        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"User {email} already exists (id={existing.id}, super_admin={existing.is_super_admin})")
            if input("Update to super-admin? [y/N] ").strip().lower() == "y":
                existing.is_super_admin = True
                existing.is_active = True
                db.session.commit()
                print("Updated.")
            sys.exit(0)

        display_name = input("Display name: ").strip()
        if not display_name:
            print("Display name is required.")
            sys.exit(1)

        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            is_super_admin=True,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        # Assign admin role to all existing tenants
        tenants = Tenant.query.filter_by(is_active=True).all()
        for t in tenants:
            utr = UserTenantRole(user_id=user.id, tenant_id=t.id, role="admin")
            db.session.add(utr)

        db.session.commit()
        print(f"\nSuper-admin created: {email} (id={user.id})")
        if tenants:
            print(f"Admin role granted for {len(tenants)} tenant(s): {', '.join(t.slug for t in tenants)}")
        else:
            print("No tenants found — role will be assigned when tenants are created.")


if __name__ == "__main__":
    main()

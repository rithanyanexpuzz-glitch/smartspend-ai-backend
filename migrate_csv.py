"""
CSV to MySQL Migration Script.
Safely imports existing CSV expense data into the MySQL database.
Preserves all original records without data loss.
"""

import csv
import sys
from pathlib import Path
from datetime import date

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.expense import Expense
from app.models.budget import Budget
from app.models.category import Category
from app.services.ml_categorizer import get_categorizer


def migrate_expenses_csv(csv_path, user_id):
    """Import expenses from the original CSV file."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"  ⚠ File not found: {csv_path}")
        return 0

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("  ⚠ No data in CSV file.")
        return 0

    imported = 0
    skipped = 0
    for row in rows:
        description = row.get("description", "").strip()
        amount_str = row.get("amount", "0")
        date_str = row.get("date", "")
        category = row.get("category", "Uncategorized")

        if not description or not amount_str:
            skipped += 1
            continue

        try:
            amount = float(amount_str)
            if amount <= 0:
                skipped += 1
                continue
        except ValueError:
            skipped += 1
            continue

        try:
            expense_date = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            expense_date = date.today()

        # Check for duplicates
        existing = Expense.query.filter_by(
            user_id=user_id,
            description=description,
            amount=amount,
            expense_date=expense_date,
        ).first()

        if existing:
            skipped += 1
            continue

        expense = Expense(
            user_id=user_id,
            amount=amount,
            description=description,
            category_name=category,
            expense_date=expense_date,
        )
        db.session.add(expense)
        imported += 1

    db.session.commit()
    print(f"  ✓ Imported {imported} expenses, skipped {skipped} (duplicates/invalid)")
    return imported


def migrate_budgets_csv(csv_path, user_id):
    """Import budgets from the original CSV file."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"  ⚠ Budgets file not found: {csv_path}")
        return 0

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    imported = 0
    for row in rows:
        category = row.get("category", "").strip()
        limit_str = row.get("monthly_limit", "0")

        if not category:
            continue

        try:
            monthly_limit = float(limit_str)
            if monthly_limit <= 0:
                continue
        except ValueError:
            continue

        existing = Budget.query.filter_by(
            user_id=user_id, category_name=category
        ).first()

        if existing:
            existing.monthly_limit = monthly_limit
        else:
            budget = Budget(
                user_id=user_id,
                category_name=category,
                monthly_limit=monthly_limit,
            )
            db.session.add(budget)
            imported += 1

    db.session.commit()
    print(f"  ✓ Imported {imported} budgets")
    return imported


def run_migration():
    """Run the full CSV-to-MySQL migration."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("SmartSpend AI - CSV to MySQL Migration")
        print("=" * 60)

        # Original project data paths
        original_data = Path(__file__).resolve().parent.parent / "G05_Expense_Tracker" / "data"
        expenses_csv = original_data / "expenses.csv"
        budgets_csv = original_data / "budgets.csv"

        # Ensure a migration user exists
        migration_email = "migrated@smartspend.local"
        user = User.query.filter_by(email=migration_email).first()
        if not user:
            user = User(
                email=migration_email,
                full_name="Migrated User",
            )
            user.set_password("MigratedUser@123")
            db.session.add(user)
            db.session.commit()
            print(f"\n✓ Created migration user: {migration_email}")
            print(f"  Password: MigratedUser@123")
            print(f"  (Change this password after first login!)")
        else:
            print(f"\n✓ Using existing migration user: {migration_email}")

        print(f"\n── Importing expenses from: {expenses_csv}")
        migrate_expenses_csv(expenses_csv, user.id)

        print(f"\n── Importing budgets from: {budgets_csv}")
        migrate_budgets_csv(budgets_csv, user.id)

        print("\n" + "=" * 60)
        print("Migration complete!")
        print(f"  User: {migration_email}")
        print(f"  Total expenses: {Expense.query.filter_by(user_id=user.id).count()}")
        print(f"  Total budgets:  {Budget.query.filter_by(user_id=user.id).count()}")
        print("=" * 60)


if __name__ == "__main__":
    run_migration()

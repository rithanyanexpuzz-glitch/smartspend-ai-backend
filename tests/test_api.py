"""
SmartSpend AI - Backend Test Suite
Tests: Authentication, Expenses, Income, Budgets, AI categorization, Data isolation.
Uses SQLite in-memory for fast isolated testing.
"""

import json
import unittest
from datetime import date

from app import create_app
from app.extensions import db
from app.models import User, Category, Expense, Income, Budget


class BaseTestCase(unittest.TestCase):
    """Base test class with app setup and auth helpers."""

    def setUp(self):
        self.app = create_app("testing")
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            Category.seed_defaults()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def register_user(self, email="test@example.com", password="TestPass1", name="Test User"):
        return self.client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "full_name": name,
        })

    def login_user(self, email="test@example.com", password="TestPass1"):
        return self.client.post("/api/auth/login", json={
            "email": email,
            "password": password,
        })

    def get_token(self, email="test@example.com", password="TestPass1", name="Test User"):
        self.register_user(email, password, name)
        resp = self.login_user(email, password)
        return resp.get_json()["access_token"]

    def auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}


class TestAuth(BaseTestCase):
    """Authentication tests."""

    def test_register_success(self):
        resp = self.register_user()
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "test@example.com")

    def test_register_duplicate_email(self):
        self.register_user()
        resp = self.register_user()
        self.assertEqual(resp.status_code, 409)

    def test_register_weak_password(self):
        resp = self.register_user(password="weak")
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_email(self):
        resp = self.register_user(email="not-an-email")
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_name(self):
        resp = self.client.post("/api/auth/register", json={
            "email": "a@b.com", "password": "TestPass1",
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_success(self):
        self.register_user()
        resp = self.login_user()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.get_json())

    def test_login_wrong_password(self):
        self.register_user()
        resp = self.login_user(password="WrongPass1")
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user(self):
        resp = self.login_user(email="none@example.com")
        self.assertEqual(resp.status_code, 401)

    def test_get_profile(self):
        token = self.get_token()
        resp = self.client.get("/api/auth/profile", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["email"], "test@example.com")

    def test_update_profile(self):
        token = self.get_token()
        resp = self.client.put("/api/auth/profile",
            headers=self.auth_headers(token),
            json={"full_name": "Updated Name"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["full_name"], "Updated Name")

    def test_change_password(self):
        token = self.get_token()
        resp = self.client.post("/api/auth/change-password",
            headers=self.auth_headers(token),
            json={"current_password": "TestPass1", "new_password": "NewPass1A"},
        )
        self.assertEqual(resp.status_code, 200)
        # Verify new password works
        resp2 = self.login_user(password="NewPass1A")
        self.assertEqual(resp2.status_code, 200)

    def test_protected_route_without_token(self):
        resp = self.client.get("/api/auth/profile")
        self.assertEqual(resp.status_code, 401)

    def test_forgot_password_does_not_reveal_existence(self):
        resp = self.client.post("/api/auth/forgot-password",
            json={"email": "nonexistent@example.com"})
        self.assertEqual(resp.status_code, 200)


class TestExpenses(BaseTestCase):
    """Expense CRUD tests."""

    def test_create_expense(self):
        token = self.get_token()
        resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 150.50, "description": "Grocery shopping at FreshMart",
            "date": "2026-11-01", "category": "Food",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()["expense"]
        self.assertEqual(data["amount"], 150.50)
        self.assertEqual(data["category_name"], "Food")

    def test_create_expense_auto_categorize(self):
        token = self.get_token()
        resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 25, "description": "Taxi ride to airport",
            "date": "2026-11-01",
        })
        self.assertEqual(resp.status_code, 201)
        # Should auto-categorize (likely Transport)
        data = resp.get_json()["expense"]
        self.assertIsNotNone(data["predicted_category"])
        self.assertIsNotNone(data["prediction_confidence"])

    def test_create_expense_invalid_amount(self):
        token = self.get_token()
        resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": -10, "description": "Test", "date": "2026-11-01",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_expense_empty_description(self):
        token = self.get_token()
        resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 10, "description": "  ", "date": "2026-11-01",
        })
        self.assertEqual(resp.status_code, 400)

    def test_list_expenses(self):
        token = self.get_token()
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 100, "description": "Lunch", "date": "2026-11-01", "category": "Food",
        })
        resp = self.client.get("/api/expenses/", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["total"], 1)

    def test_list_expenses_filter_month(self):
        token = self.get_token()
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 100, "description": "Oct lunch", "date": "2026-10-15", "category": "Food",
        })
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 200, "description": "Nov lunch", "date": "2026-11-01", "category": "Food",
        })
        resp = self.client.get("/api/expenses/?month=2026-11", headers=self.auth_headers(token))
        self.assertEqual(resp.get_json()["total"], 1)

    def test_update_expense(self):
        token = self.get_token()
        create_resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 100, "description": "Lunch", "date": "2026-11-01", "category": "Food",
        })
        eid = create_resp.get_json()["expense"]["id"]
        resp = self.client.put(f"/api/expenses/{eid}", headers=self.auth_headers(token), json={
            "amount": 200, "description": "Dinner",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["expense"]["amount"], 200.0)

    def test_delete_expense(self):
        token = self.get_token()
        create_resp = self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 100, "description": "Lunch", "date": "2026-11-01", "category": "Food",
        })
        eid = create_resp.get_json()["expense"]["id"]
        resp = self.client.delete(f"/api/expenses/{eid}", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["deleted"])

    def test_delete_nonexistent_expense(self):
        token = self.get_token()
        resp = self.client.delete("/api/expenses/9999", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 404)

    def test_predict_category(self):
        token = self.get_token()
        resp = self.client.post("/api/expenses/predict", headers=self.auth_headers(token), json={
            "description": "Doctor appointment at City Hospital",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("keyword", data)
        self.assertIn("tfidf_nb", data)


class TestIncome(BaseTestCase):
    """Income CRUD tests."""

    def test_create_income(self):
        token = self.get_token()
        resp = self.client.post("/api/income/", headers=self.auth_headers(token), json={
            "amount": 50000, "description": "Monthly salary",
            "date": "2026-11-01", "category": "Salary",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["income"]["amount"], 50000.0)

    def test_list_income(self):
        token = self.get_token()
        self.client.post("/api/income/", headers=self.auth_headers(token), json={
            "amount": 50000, "description": "Salary",
            "date": "2026-11-01", "category": "Salary",
        })
        resp = self.client.get("/api/income/", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["total"], 1)

    def test_update_income(self):
        token = self.get_token()
        create_resp = self.client.post("/api/income/", headers=self.auth_headers(token), json={
            "amount": 50000, "description": "Salary", "date": "2026-11-01", "category": "Salary",
        })
        iid = create_resp.get_json()["income"]["id"]
        resp = self.client.put(f"/api/income/{iid}", headers=self.auth_headers(token), json={
            "amount": 55000,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["income"]["amount"], 55000.0)

    def test_delete_income(self):
        token = self.get_token()
        create_resp = self.client.post("/api/income/", headers=self.auth_headers(token), json={
            "amount": 50000, "description": "Salary", "date": "2026-11-01", "category": "Salary",
        })
        iid = create_resp.get_json()["income"]["id"]
        resp = self.client.delete(f"/api/income/{iid}", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)


class TestBudgets(BaseTestCase):
    """Budget management tests."""

    def test_create_budget(self):
        token = self.get_token()
        resp = self.client.post("/api/budgets/", headers=self.auth_headers(token), json={
            "category_name": "Food", "monthly_limit": 5000,
        })
        self.assertEqual(resp.status_code, 201)

    def test_budget_alert_at_80_percent(self):
        token = self.get_token()
        self.client.post("/api/budgets/", headers=self.auth_headers(token), json={
            "category_name": "Food", "monthly_limit": 1000,
        })
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 800, "description": "Big grocery run",
            "date": date.today().isoformat(), "category": "Food",
        })
        resp = self.client.get(
            f"/api/budgets/?month={date.today().strftime('%Y-%m')}",
            headers=self.auth_headers(token),
        )
        budgets = resp.get_json()["budgets"]
        food_budget = next(b for b in budgets if b["category_name"] == "Food")
        self.assertEqual(food_budget["alert"], "near limit")

    def test_budget_alert_over_limit(self):
        token = self.get_token()
        self.client.post("/api/budgets/", headers=self.auth_headers(token), json={
            "category_name": "Food", "monthly_limit": 1000,
        })
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 1100, "description": "Huge grocery run",
            "date": date.today().isoformat(), "category": "Food",
        })
        resp = self.client.get(
            f"/api/budgets/?month={date.today().strftime('%Y-%m')}",
            headers=self.auth_headers(token),
        )
        budgets = resp.get_json()["budgets"]
        food_budget = next(b for b in budgets if b["category_name"] == "Food")
        self.assertEqual(food_budget["alert"], "over budget")


class TestDataIsolation(BaseTestCase):
    """Test that users cannot see each other's data."""

    def test_user_a_cannot_see_user_b_expenses(self):
        token_a = self.get_token("a@test.com", "TestPass1", "User A")
        token_b = self.get_token("b@test.com", "TestPass1", "User B")

        self.client.post("/api/expenses/", headers=self.auth_headers(token_a), json={
            "amount": 100, "description": "User A meal", "date": "2026-11-01", "category": "Food",
        })
        self.client.post("/api/expenses/", headers=self.auth_headers(token_b), json={
            "amount": 200, "description": "User B meal", "date": "2026-11-01", "category": "Food",
        })

        resp_a = self.client.get("/api/expenses/", headers=self.auth_headers(token_a))
        resp_b = self.client.get("/api/expenses/", headers=self.auth_headers(token_b))

        expenses_a = resp_a.get_json()["expenses"]
        expenses_b = resp_b.get_json()["expenses"]

        self.assertEqual(len(expenses_a), 1)
        self.assertEqual(expenses_a[0]["description"], "User A meal")
        self.assertEqual(len(expenses_b), 1)
        self.assertEqual(expenses_b[0]["description"], "User B meal")

    def test_user_cannot_delete_others_expense(self):
        token_a = self.get_token("a@test.com", "TestPass1", "User A")
        token_b = self.get_token("b@test.com", "TestPass1", "User B")

        create_resp = self.client.post("/api/expenses/", headers=self.auth_headers(token_a), json={
            "amount": 100, "description": "A's lunch", "date": "2026-11-01", "category": "Food",
        })
        eid = create_resp.get_json()["expense"]["id"]

        resp = self.client.delete(f"/api/expenses/{eid}", headers=self.auth_headers(token_b))
        self.assertEqual(resp.status_code, 404)

    def test_user_a_cannot_see_user_b_income(self):
        token_a = self.get_token("a@test.com", "TestPass1", "User A")
        token_b = self.get_token("b@test.com", "TestPass1", "User B")

        self.client.post("/api/income/", headers=self.auth_headers(token_a), json={
            "amount": 50000, "description": "A salary", "date": "2026-11-01", "category": "Salary",
        })

        resp = self.client.get("/api/income/", headers=self.auth_headers(token_b))
        self.assertEqual(resp.get_json()["total"], 0)


class TestDashboard(BaseTestCase):
    """Dashboard API tests."""

    def test_dashboard_returns_data(self):
        token = self.get_token()
        self.client.post("/api/income/", headers=self.auth_headers(token), json={
            "amount": 50000, "description": "Salary", "date": "2026-11-01", "category": "Salary",
        })
        self.client.post("/api/expenses/", headers=self.auth_headers(token), json={
            "amount": 5000, "description": "Groceries", "date": "2026-11-01", "category": "Food",
        })
        resp = self.client.get("/api/dashboard/?month=2026-11", headers=self.auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["summary"]["total_income"], 50000.0)
        self.assertEqual(data["summary"]["total_expenses"], 5000.0)
        self.assertEqual(data["summary"]["balance"], 45000.0)


class TestMLCategorizer(BaseTestCase):
    """ML model tests (preserved from original project)."""

    def test_tfidf_predicts_food(self):
        from app.services.ml_categorizer import get_categorizer
        with self.app.app_context():
            cat = get_categorizer()
            pred, conf = cat.predict("Bought groceries at FreshMart")
            self.assertEqual(pred, "Food")
            self.assertGreater(conf, 0.0)

    def test_keyword_predicts_healthcare(self):
        from app.services.ml_categorizer import get_categorizer
        with self.app.app_context():
            cat = get_categorizer()
            pred, conf = cat.predict("Doctor appointment at City Hospital", "keyword")
            self.assertEqual(pred, "Healthcare")

    def test_both_models_return_valid_categories(self):
        from app.services.ml_categorizer import get_categorizer, ORIGINAL_CATEGORIES, EXPENSE_CATEGORIES
        with self.app.app_context():
            cat = get_categorizer()
            result = cat.predict_both("Taxi ride to airport")
            valid = set(ORIGINAL_CATEGORIES) | set(EXPENSE_CATEGORIES)
            self.assertIn(result["keyword"]["category"], valid)
            self.assertIn(result["tfidf_nb"]["category"], valid)

    def test_empty_description_returns_uncategorized(self):
        from app.services.ml_categorizer import get_categorizer
        with self.app.app_context():
            cat = get_categorizer()
            pred, conf = cat.predict("")
            self.assertEqual(pred, "Uncategorized")

    def test_model_evaluation(self):
        from app.services.ml_categorizer import get_categorizer
        with self.app.app_context():
            cat = get_categorizer()
            results = cat.evaluate()
            self.assertIn("tfidf_naive_bayes", results)
            self.assertGreater(results["tfidf_naive_bayes"]["accuracy"], 0.5)


class TestHealthCheck(BaseTestCase):
    """Basic API health check."""

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()

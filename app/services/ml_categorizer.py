"""
SmartSpend AI - ML Categorizer Service
Preserves the original TF-IDF + Naive Bayes and Keyword Rule classifiers
from the G05 Expense Tracker project, adapted for MySQL-backed operation.
"""

import csv
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# ── Original categories preserved ─────────────────────────────
ORIGINAL_CATEGORIES = ("Food", "Transport", "Shopping", "Bills", "Healthcare")

# ── Extended categories for SmartSpend AI ──────────────────────
EXPENSE_CATEGORIES = (
    "Food", "Transport", "Shopping", "Bills", "Healthcare",
    "Entertainment", "Education", "Rent", "Insurance", "Uncategorized",
)

INCOME_CATEGORIES = (
    "Salary", "Business", "Freelance", "Investment", "Rental", "Other",
)


def _tokens(text):
    """Tokenize text into lowercase alphanumeric words."""
    return re.findall(r"[a-z0-9]+", text.lower())


class KeywordRuleClassifier:
    """Rule-based classifier preserved from the original project."""

    KEYWORDS = {
        "Food": {
            "grocery", "groceries", "food", "produce", "pantry", "supermarket",
            "lunch", "dinner", "coffee", "pastry", "restaurant", "meal", "cafe",
            "bakery", "weekly", "breakfast", "snack", "pizza", "burger", "chicken",
            "rice", "vegetable", "fruit", "meat", "fish", "dairy", "milk", "bread",
            "cooking", "kitchen", "sweets", "dessert", "canteen", "tiffin",
            "biryani", "dosa", "thali", "samosa", "chai",
        },
        "Transport": {
            "taxi", "bus", "train", "fare", "fuel", "parking", "rideshare",
            "ride", "transit", "metro", "shuttle", "commute", "petrol", "diesel",
            "auto", "rickshaw", "cab", "uber", "ola", "rapido", "toll", "highway",
            "flight", "airline", "travel", "trip", "journey",
        },
        "Shopping": {
            "clothing", "electronics", "home", "shoes", "accessories", "online",
            "shopping", "purchase", "goods", "fashion", "store", "order", "amazon",
            "flipkart", "myntra", "clothes", "shirt", "dress", "gadget", "phone",
            "laptop", "watch", "jewellery", "furniture", "appliance",
        },
        "Bills": {
            "electricity", "internet", "water", "utility", "mobile", "phone",
            "bill", "service", "energy", "power", "gas", "payment", "monthly",
            "recharge", "broadband", "wifi", "dth", "cable", "telephone",
            "postpaid", "prepaid",
        },
        "Healthcare": {
            "prescription", "doctor", "dental", "pharmacy", "health", "clinic",
            "medical", "hospital", "care", "vision", "medicine", "tablet",
            "diagnosis", "surgery", "checkup", "lab", "test", "xray", "scan",
            "physiotherapy", "ayurvedic", "homeopathy",
        },
        "Entertainment": {
            "movie", "cinema", "netflix", "spotify", "game", "concert", "ticket",
            "streaming", "music", "party", "club", "event", "festival", "show",
            "theatre", "amusement", "park", "hobby",
        },
        "Education": {
            "tuition", "course", "book", "school", "college", "university",
            "exam", "coaching", "class", "study", "library", "stationery",
            "notebook", "pen", "certificate", "training", "workshop", "seminar",
        },
        "Rent": {
            "rent", "lease", "tenant", "landlord", "housing", "apartment",
            "flat", "room", "accommodation", "pg", "hostel",
        },
        "Insurance": {
            "insurance", "premium", "policy", "lic", "term", "health insurance",
            "vehicle insurance", "cover", "claim",
        },
    }

    def predict(self, description):
        words = set(_tokens(description))
        scores = {
            category: len(words & keywords)
            for category, keywords in self.KEYWORDS.items()
        }
        best = max(scores, key=lambda c: scores[c])
        return best if scores[best] > 0 else "Uncategorized"

    def predict_batch(self, descriptions):
        return [self.predict(d) for d in descriptions]


def _read_csv_rows(path):
    """Read CSV file and return list of dicts."""
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def create_tfidf_nb_model(rows):
    """Train a TF-IDF + Multinomial Naive Bayes pipeline.
    Preserved from original project with enhanced n-gram range.
    """
    descriptions = [row["description"] for row in rows]
    categories = [row["category"] for row in rows]
    if not descriptions:
        raise ValueError("Training data cannot be empty.")
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", max_features=5000),
        MultinomialNB(alpha=0.1),
    )
    return model.fit(descriptions, categories)


class MLCategorizer:
    """
    Unified ML categorizer service that wraps both classifiers.
    Preserves original model while adding confidence scores.
    """

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else None
        self.keyword_classifier = KeywordRuleClassifier()
        self.tfidf_model = None
        self._load_model()

    @staticmethod
    def _resolve_data_dir(override=None):
        """Return the first candidate directory that contains train_data_300.csv.

        Candidates (in order):
          1. Explicit override passed by the caller.
          2. <repo_root>/smartspend-ai/backend/data/   (intended production path)
          3. <repo_root>/G05_Expense_Tracker/data/     (legacy source data)
          4. <repo_root>/data/                         (generic fallback)
        """
        # __file__ is  …/smartspend-ai/backend/app/services/ml_categorizer.py
        services_dir = Path(__file__).resolve().parent   # …/app/services
        backend_dir  = services_dir.parent.parent        # …/backend
        repo_root    = backend_dir.parent.parent         # …/new project

        candidates = [
            override,
            backend_dir / "data",
            repo_root   / "G05_Expense_Tracker" / "data",
            repo_root   / "data",
        ]
        for path in candidates:
            if path and Path(path, "train_data_300.csv").exists():
                return Path(path)
        # Return the primary path even if it doesn't exist (fail clearly later)
        return backend_dir / "data"

    def _load_model(self):
        """Load or train the TF-IDF model from training data."""
        data_dir = self._resolve_data_dir(self.data_dir)
        train_path = data_dir / "train_data_300.csv"
        if train_path.exists():
            train_rows = _read_csv_rows(train_path)
            if train_rows:
                self.tfidf_model = create_tfidf_nb_model(train_rows)

    def predict(self, description, model="tfidf_nb"):
        """Predict category for a single description."""
        description = description.strip()
        if not description:
            return "Uncategorized", 0.0

        if model == "keyword":
            category = self.keyword_classifier.predict(description)
            return category, 1.0 if category != "Uncategorized" else 0.0

        if model == "tfidf_nb" and self.tfidf_model:
            predicted = self.tfidf_model.predict([description])[0]
            probabilities = self.tfidf_model.predict_proba([description])[0]
            confidence = float(np.max(probabilities))
            return predicted, confidence

        # Fallback to keyword if tfidf not available
        category = self.keyword_classifier.predict(description)
        return category, 0.5

    def predict_both(self, description):
        """Return predictions from both models for comparison."""
        keyword_cat, keyword_conf = self.predict(description, "keyword")
        tfidf_cat, tfidf_conf = self.predict(description, "tfidf_nb")
        return {
            "description": description,
            "keyword": {"category": keyword_cat, "confidence": keyword_conf},
            "tfidf_nb": {"category": tfidf_cat, "confidence": tfidf_conf},
        }

    def evaluate(self):
        """Evaluate both models on held-out test data.
        Preserved from original evaluate_models.py.
        """
        from time import perf_counter

        data_dir = self._resolve_data_dir(self.data_dir)
        test_path  = data_dir / "test_data_100.csv"
        train_path = data_dir / "train_data_300.csv"

        if not test_path.exists() or not train_path.exists():
            return {}, None

        test_rows = _read_csv_rows(test_path)
        actual = [row["category"] for row in test_rows]
        descriptions = [row["description"] for row in test_rows]

        labels = list(ORIGINAL_CATEGORIES)

        models = {
            "keyword_rules": self.keyword_classifier,
            "tfidf_naive_bayes": self.tfidf_model,
        }

        results = {}
        for name, model in models.items():
            if model is None:
                continue
            started = perf_counter()
            if name == "keyword_rules":
                predicted = [model.predict(d) for d in descriptions]
            else:
                predicted = list(model.predict(descriptions))
            elapsed = perf_counter() - started

            report = classification_report(
                actual, predicted, labels=labels,
                target_names=labels, output_dict=True, zero_division=0,
            )
            results[name] = {
                "accuracy": accuracy_score(actual, predicted),
                "precision_macro": report["macro avg"]["precision"],
                "recall_macro": report["macro avg"]["recall"],
                "f1_macro": report["macro avg"]["f1-score"],
                "classification_time_seconds": elapsed,
                "per_class": {cat: report[cat] for cat in labels},
                "confusion_matrix": confusion_matrix(
                    actual, predicted, labels=labels
                ).tolist(),
            }

        return results


# Module-level singleton (created once per process)
_categorizer_instance = None


def get_categorizer(data_dir=None):
    """Get or create the singleton categorizer instance."""
    global _categorizer_instance
    if _categorizer_instance is None:
        _categorizer_instance = MLCategorizer(data_dir)
    return _categorizer_instance

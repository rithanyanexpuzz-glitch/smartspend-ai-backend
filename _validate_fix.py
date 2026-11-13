"""Quick validation of the ML categorizer fix."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Force fresh instance (bypass singleton cache)
from app.services.ml_categorizer import MLCategorizer

cat = MLCategorizer()
print(f"tfidf_model loaded: {cat.tfidf_model is not None}")

results = cat.evaluate()
print(f"evaluate() keys: {list(results.keys()) if isinstance(results, dict) else results}")
if isinstance(results, dict) and "tfidf_naive_bayes" in results:
    print(f"tfidf_naive_bayes accuracy: {results['tfidf_naive_bayes']['accuracy']}")
    print("TEST WOULD PASS")
else:
    print("TEST WOULD FAIL")
    # Debug: show resolved data dir
    dd = MLCategorizer._resolve_data_dir(None)
    print(f"Resolved data_dir: {dd}")
    print(f"train exists: {(dd / 'train_data_300.csv').exists()}")
    print(f"test  exists: {(dd / 'test_data_100.csv').exists()}")

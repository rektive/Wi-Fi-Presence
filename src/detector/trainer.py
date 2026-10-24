"""Compiles raw capture sessions into processed training sets and trains Random Forest models."""

from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


def train_headcount_model(processed_dir: Path, model_output_path: Path) -> RandomForestClassifier:
    """Trains a Random Forest classifier mapping feature vectors to occupant counts."""
    x_files = sorted(list(processed_dir.glob("features_*.npy")))
    y_files = sorted(list(processed_dir.glob("labels_*.npy")))

    if not x_files or len(x_files) != len(y_files):
        raise FileNotFoundError(f"Missing matched feature/label .npy files in {processed_dir}")

    X_list = [np.load(f) for f in x_files]
    y_list = [np.load(f) for f in y_files]

    X = np.vstack(X_list)
    y = np.concatenate(y_list)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    clf = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    print("\n--- Model Evaluation Report ---")
    print(classification_report(y_test, preds))

    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_output_path)
    print(f"[+] Saved trained model to {model_output_path}")
    return clf

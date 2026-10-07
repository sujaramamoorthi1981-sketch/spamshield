"""Train the spam classifier.

    python -m app.ml.train                 # downloads the UCI SMS Spam Collection
    python -m app.ml.train --data sms.tsv  # tab-separated file: label<TAB>text (label: spam|ham)
"""
import argparse
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.core.config import settings

UCI_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip"


def load_rows(path: str | None) -> tuple[list[str], list[int]]:
    if path:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    else:
        print("Downloading UCI SMS Spam Collection…")
        with urllib.request.urlopen(UCI_URL, timeout=60) as resp:
            archive = zipfile.ZipFile(io.BytesIO(resp.read()))
        raw = archive.read("SMSSpamCollection").decode("utf-8", errors="replace")
    texts, labels = [], []
    for line in raw.splitlines():
        label, _, text = line.partition("\t")
        if label in ("spam", "ham") and text.strip():
            texts.append(text.strip())
            labels.append(1 if label == "spam" else 0)
    if len(set(labels)) < 2:
        raise SystemExit("Dataset needs both 'spam' and 'ham' rows.")
    return texts, labels


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="Path to a label<TAB>text file")
    args = ap.parse_args()

    texts, labels = load_rows(args.data)
    x_tr, x_te, y_tr, y_te = train_test_split(texts, labels, test_size=0.2, stratify=labels, random_state=42)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    pipe.fit(x_tr, y_tr)
    pred = pipe.predict(x_te)
    tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel().tolist()
    metrics = {
        "dataset_size": len(texts), "test_size": len(y_te),
        "accuracy": round(accuracy_score(y_te, pred), 4),
        "precision": round(precision_score(y_te, pred), 4),
        "recall": round(recall_score(y_te, pred), 4),
        "f1": round(f1_score(y_te, pred), 4),
        "confusion_matrix": {"true_negative": tn, "false_positive": fp, "false_negative": fn, "true_positive": tp},
    }
    out = Path(settings.model_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out)
    out.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Saved model to {out}. Restart the API to load it.")


if __name__ == "__main__":
    main()

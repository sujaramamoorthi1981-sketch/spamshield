"""Spam detector. Uses a trained scikit-learn pipeline if one exists at MODEL_PATH,
otherwise falls back to the rule-based engine. The response always says which engine was used."""
import json
import logging
from pathlib import Path
from threading import Lock

from app.core.config import settings
from app.ml.heuristics import heuristic_analysis

log = logging.getLogger("spamshield.detector")
THRESHOLD = 0.5


class Detector:
    def __init__(self) -> None:
        self._pipeline = None
        self._metrics: dict | None = None
        self._lock = Lock()
        self.reload()

    def reload(self) -> None:
        path = Path(settings.model_path)
        with self._lock:
            self._pipeline, self._metrics = None, None
            if not path.exists():
                log.warning("No trained model at %s; using heuristic engine. Run `python -m app.ml.train`.", path)
                return
            try:
                import joblib

                self._pipeline = joblib.load(path)
                metrics_path = path.with_suffix(".metrics.json")
                if metrics_path.exists():
                    self._metrics = json.loads(metrics_path.read_text())
                log.info("Loaded spam model from %s", path)
            except Exception:  # corrupt file, sklearn version mismatch, etc.
                log.exception("Could not load model; using heuristic engine")
                self._pipeline = None

    @property
    def info(self) -> dict:
        return {
            "engine": "model" if self._pipeline else "heuristic",
            "metrics": self._metrics,
            "note": None if self._pipeline else "No trained model found. Results come from rule-based signals.",
        }

    def _model_terms(self, text: str, limit: int = 5) -> list[str]:
        vec, clf = self._pipeline.named_steps["tfidf"], self._pipeline.named_steps["clf"]
        x = vec.transform([text]).tocoo()
        names = vec.get_feature_names_out()
        contrib = sorted(((v * clf.coef_[0][j], names[j]) for j, v in zip(x.col, x.data)), reverse=True)
        return [f"Spam-associated wording: “{n}”" for c, n in contrib[:limit] if c > 0.05]

    def predict(self, text: str) -> dict:
        h_prob, h_reasons = heuristic_analysis(text)
        if self._pipeline is not None:
            with self._lock:
                prob = float(self._pipeline.predict_proba([text])[0][1])
            reasons = self._model_terms(text) + [r for r in h_reasons if r.startswith("Contains") or r.startswith("Mentions")]
            engine = "model"
        else:
            prob, reasons, engine = h_prob, h_reasons, "heuristic"
        return {
            "label": "spam" if prob >= THRESHOLD else "ham",
            "spam_probability": round(prob, 4),
            "engine": engine,
            "reasons": reasons[:6],
        }


detector = Detector()

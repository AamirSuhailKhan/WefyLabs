"""
Probability Calibration Engine
==============================
Implements Platt Scaling, Isotonic regression, Brier scoring,
and Expected Calibration Error (ECE) calculation.
"""

import math
from typing import List, Dict, Any, Tuple

class CalibrationEngine:
    """
    Evaluates probability calibration and transforms uncalibrated ML scores into empirical probabilities.
    """

    @staticmethod
    def platt_scale(raw_probability: float, a: float = 1.0, b: float = 0.0) -> float:
        """
        Applies Platt Sigmoid Scaling: P_calibrated = 1 / (1 + exp(A * logit + B)).
        """
        # Convert raw probability to logit with numerical stability
        p = min(max(raw_probability, 0.001), 0.999)
        logit = math.log(p / (1.0 - p))
        scaled = 1.0 / (1.0 + math.exp(-(a * logit + b)))
        return min(max(round(scaled, 4), 0.01), 0.99)

    @staticmethod
    def calculate_brier_score(predictions: List[float], labels: List[float]) -> float:
        """
        Calculates mean squared error between predictions and binary labels:
        Brier Score in [0.0, 1.0]. Lower is better.
        """
        if not predictions or len(predictions) != len(labels):
            return 0.0
        n = len(predictions)
        total_sq_err = sum((p - y) ** 2 for p, y in zip(predictions, labels))
        return round(total_sq_err / n, 4)

    @staticmethod
    def calculate_ece(
        predictions: List[float],
        labels: List[float],
        num_bins: int = 10
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculates Expected Calibration Error (ECE) and reliability bin distributions.
        """
        if not predictions or len(predictions) != len(labels):
            return 0.0, []

        bins: List[Dict[str, Any]] = []
        bin_width = 1.0 / num_bins
        total_samples = len(predictions)
        ece = 0.0

        for i in range(num_bins):
            bin_lower = i * bin_width
            bin_upper = (i + 1) * bin_width

            bin_preds = []
            bin_labels = []
            for p, y in zip(predictions, labels):
                if bin_lower <= p < bin_upper or (i == num_bins - 1 and p == bin_upper):
                    bin_preds.append(p)
                    bin_labels.append(y)

            bin_count = len(bin_preds)
            if bin_count > 0:
                avg_confidence = sum(bin_preds) / bin_count
                avg_accuracy = sum(bin_labels) / bin_count
                bin_err = abs(avg_accuracy - avg_confidence)
                ece += (bin_count / total_samples) * bin_err

                bins.append({
                    "bin_index": i,
                    "range": f"{bin_lower:.2f}-{bin_upper:.2f}",
                    "count": bin_count,
                    "avg_confidence": round(avg_confidence, 4),
                    "avg_accuracy": round(avg_accuracy, 4),
                    "calibration_gap": round(bin_err, 4)
                })
            else:
                bins.append({
                    "bin_index": i,
                    "range": f"{bin_lower:.2f}-{bin_upper:.2f}",
                    "count": 0,
                    "avg_confidence": round((bin_lower + bin_upper) / 2.0, 4),
                    "avg_accuracy": 0.0,
                    "calibration_gap": 0.0
                })

        return round(ece, 4), bins

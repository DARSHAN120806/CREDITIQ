"""Risk displays and independently versioned decision policy."""
from dataclasses import dataclass
import math


def probability(value):
    if isinstance(value, bool):
        raise ValueError("Probability must be numeric")
    p = float(value)
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Probability must be finite and in [0,1]")
    return p


def risk_score(p):
    return round(100 * probability(p), 2)


def risk_band(p):
    p = probability(p)
    return "Low" if p < .05 else "Medium" if p < .15 else "High"


def risk_level(score):
    """Compatibility for unrounded scores; prefer risk_band(p)."""
    return risk_band(float(score) / 100)


def credit_health_score(p):
    """CreditIQ model index, NOT a bureau score."""
    return round(100 * (1 - probability(p)), 2)


@dataclass(frozen=True)
class DecisionPolicy:
    version: str = "sandbox-v1"
    mode: str = "SANDBOX"
    approve_below: float | None = .05
    reject_at: float | None = .15
    validation_report: str | None = None
    approved_by: str | None = None
    model_version: str | None = None
    variant: str | None = None

    def __post_init__(self):
        if self.mode not in ("SANDBOX", "SHADOW", "LIVE"):
            raise ValueError("Invalid policy mode")
        a, r = self.approve_below, self.reject_at
        if (a is None) != (r is None):
            raise ValueError("Both thresholds must be set or unset")
        if a is not None and not (0 < probability(a) < probability(r) < 1):
            raise ValueError("Require 0 < approve_below < reject_at < 1")
        if self.mode == "LIVE" and not all((a is not None, self.validation_report, self.approved_by, self.model_version, self.variant == "full")):
            raise ValueError("Live policy requires Full release binding and approval evidence")

    def evaluate(self, p, *, variant="lite", model_version=None, release_ready=False,
                 data_valid=True, supported=True, verified=False, affordable=None, product_eligible=False):
        p = probability(p)
        if variant not in ("lite", "full"):
            raise ValueError("Invalid variant")
        recommendation = "MANUAL_REVIEW"
        if data_valid and supported and self.approve_below is not None:
            recommendation = ("APPROVAL_CANDIDATE" if p < self.approve_below else
                              "REJECTION_CANDIDATE" if p >= self.reject_at else "MANUAL_REVIEW")
        decision = "MANUAL_REVIEW"
        eligible = (self.mode == "LIVE" and variant == "full" and release_ready and
                    model_version == self.model_version and data_valid and supported and verified and product_eligible)
        if eligible and recommendation == "REJECTION_CANDIDATE":
            decision = "REJECTED"
        elif eligible and recommendation == "APPROVAL_CANDIDATE" and affordable is True:
            decision = "APPROVED"
        return {"recommendation": recommendation, "decision_status": decision, "policy_version": self.version,
                "mode": self.mode, "risk_band": risk_band(p), "risk_score": risk_score(p)}

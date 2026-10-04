import pytest
from creditiq_ml.risk import DecisionPolicy, probability, risk_band, risk_score


@pytest.mark.parametrize("p,band,recommendation", [(0., "Low", "APPROVAL_CANDIDATE"), (.049999, "Low", "APPROVAL_CANDIDATE"),
    (.05, "Medium", "MANUAL_REVIEW"), (.149999, "Medium", "MANUAL_REVIEW"), (.15, "High", "REJECTION_CANDIDATE"), (1., "High", "REJECTION_CANDIDATE")])
def test_boundaries_and_sandbox_never_final(p, band, recommendation):
    result = DecisionPolicy().evaluate(p, variant="full", verified=True, affordable=True, product_eligible=True, release_ready=True)
    assert risk_band(p) == band and result["recommendation"] == recommendation
    assert result["decision_status"] == "MANUAL_REVIEW"


@pytest.mark.parametrize("p", [float("nan"), float("inf"), -.01, 1.01, True])
def test_invalid_probabilities(p):
    with pytest.raises(ValueError):
        probability(p)


def test_threshold_order_and_live_gates():
    with pytest.raises(ValueError):
        DecisionPolicy(approve_below=.2, reject_at=.1)
    with pytest.raises(ValueError):
        DecisionPolicy(mode="LIVE")
    policy = DecisionPolicy(mode="LIVE", validation_report="approved-report", approved_by="reviewer", model_version="r1", variant="full")
    context = dict(variant="full", model_version="r1", release_ready=True, verified=True, affordable=True, product_eligible=True)
    assert policy.evaluate(.01, **context)["decision_status"] == "APPROVED"
    for key, value in (("variant", "lite"), ("release_ready", False), ("model_version", "r2"), ("verified", False), ("affordable", None)):
        assert policy.evaluate(.01, **{**context, key: value})["decision_status"] == "MANUAL_REVIEW"
    assert risk_score(.049999) == 5 and risk_band(.049999) == "Low"

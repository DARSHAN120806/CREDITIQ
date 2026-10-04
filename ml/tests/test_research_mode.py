import json
import pytest
from creditiq_ml.contracts import ContractError
from creditiq_ml.provenance import source_manifest


def test_explicit_research_assumptions_only_allow_lite(data_root):
    path = data_root / "adapter_manifest.json"
    m = json.loads(path.read_text())
    m.update(mode="RESEARCH", release_ready=False, annuity_monthly_verified=False,
             research_assumptions={"authorized_by": "test", "dataset_source": "research fixture",
                                   "income_period": "annual", "annuity_period": "monthly",
                                   "currency": "unspecified_research_currency"})
    path.write_text(json.dumps(m))
    assert source_manifest("lite")["annuity_monthly_verified"] is False
    with pytest.raises(ContractError, match="Research override"):
        source_manifest("full")
    m["release_ready"] = True
    path.write_text(json.dumps(m))
    with pytest.raises(ContractError, match="Research override"):
        source_manifest("lite")


def test_implicit_research_assumptions_not_accepted(data_root):
    path = data_root / "adapter_manifest.json"
    m = json.loads(path.read_text())
    m["annuity_monthly_verified"] = False
    path.write_text(json.dumps(m))
    with pytest.raises(ContractError, match="annuity_monthly_verified"):
        source_manifest("lite")

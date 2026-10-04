"""Content-addressed inputs and atomic metadata/artifact selection."""
import hashlib
import json
import os
from pathlib import Path
from . import config as C
from .contracts import ContractError, HISTORY_GROUPS
from .io import find_file


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def source_manifest(variant):
    path = C.RAW_DIR / "adapter_manifest.json"
    if not path.exists():
        raise ContractError("Missing adapter_manifest.json: verify source semantics before training")
    m = json.loads(path.read_text(encoding="utf-8"))
    research = m.get("mode") == "RESEARCH"
    if research:
        assumptions = m.get("research_assumptions", {})
        if (variant != "lite" or m.get("release_ready") is not False or
                assumptions.get("income_period") != "annual" or
                assumptions.get("annuity_period") != "monthly" or
                assumptions.get("currency") != "unspecified_research_currency" or
                not assumptions.get("dataset_source") or not assumptions.get("authorized_by")):
            raise ContractError("Research override requires explicit Lite assumptions and release_ready=false")
    for key in ("annuity_monthly_verified", "category_mapping_verified", "cash_product_verified"):
        if research and key == "annuity_monthly_verified":
            continue  # Authorized assumption, deliberately NOT represented as verified.
        if m.get(key) is not True:
            raise ContractError(f"Unresolved dataset gate: {key}")
    currency = m.get("currency", "")
    if len(currency) != 3 or not currency.isalpha() or not currency.isupper() or not m.get("evidence"):
        raise ContractError("Manifest needs currency/domain and evidence references")
    if variant == "full":
        for key in ("schedule_complete", "schedule_versions_resolved", "payment_identity_verified", "availability_verified"):
            if m.get(key) is not True:
                raise ContractError(f"Full unavailable: {key}")
        if not (C.RAW_DIR / "installment_schedule.csv").exists():
            raise ContractError("Full requires reconciled installment_schedule.csv, including unpaid installments")
        for source in HISTORY_GROUPS:
            entry = m.get("sources", {}).get(source, {})
            if entry.get("state") not in ("COMPLETE", "CONFIRMED_EMPTY") or not entry.get("evidence"):
                raise ContractError(f"Full source incomplete: {source}")
            if find_file(source) is None:
                raise ContractError(f"Missing Full source file: {source}")
    return m


def input_manifest(variant):
    keys = ["application_train", "application_test"] + (list(HISTORY_GROUPS) if variant == "full" else [])
    sources = {key: sha256(find_file(key)) for key in keys if find_file(key)}
    for name in ["adapter_manifest.json"] + (["installment_schedule.csv"] if variant == "full" else []):
        path = C.RAW_DIR / name
        if path.exists():
            sources[name] = sha256(path)
    code = {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")}
    return {"variant": variant, "schema": f"{variant}-v1", "sources": sources, "code": code}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def release_dir(variant, run_id=None):
    root = C.ARTIFACTS_DIR / variant
    if run_id is None:
        pointer = root / "latest.json"
        if not pointer.exists():
            raise ContractError("No v1 release; retrain legacy artifacts")
        run_id = json.loads(pointer.read_text())["run_id"]
    if Path(run_id).name != run_id or run_id in (".", ".."):
        raise ContractError("Invalid run id")
    path = root / "runs" / run_id
    if not (path / "metadata.json").exists():
        raise ContractError("Incomplete release")
    return path


def load_model(variant, run_id=None):
    import joblib
    path = release_dir(variant, run_id)
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    for name, digest in metadata["artifact_sha256"].items():
        if Path(name).name != name or sha256(path / name) != digest:
            raise ContractError(f"Release checksum mismatch: {name}")
    return joblib.load(path / "best_model.joblib"), path

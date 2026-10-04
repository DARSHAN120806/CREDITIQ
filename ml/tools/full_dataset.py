"""Read-only source audit and gated, training-only Full dataset build.

Kept outside creditiq_ml: pinned Lite source and provenance remain unchanged.
Exit 2 means the reports were produced but the Full contract is blocked.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ML_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_ROOT))
from creditiq_ml import config as C
from creditiq_ml.contracts import ContractError, FULL_FEATURES, HISTORY_GROUPS, LITE_FEATURES
from creditiq_ml.features import application_features, history_features, validate_features
from creditiq_ml.provenance import sha256, source_manifest, write_json

REQUIRED = {
    "bureau": "SK_ID_CURR SK_ID_BUREAU DAYS_CREDIT DAYS_AVAILABLE CREDIT_ACTIVE CREDIT_DAY_OVERDUE AMT_CREDIT_SUM AMT_CREDIT_SUM_DEBT AMT_CREDIT_SUM_OVERDUE".split(),
    "bureau_balance": "SK_ID_BUREAU MONTHS_BALANCE DAYS_AVAILABLE STATUS".split(),
    "previous_application": "SK_ID_CURR SK_ID_PREV DAYS_DECISION DAYS_AVAILABLE NAME_CONTRACT_STATUS".split(),
    "installments_payments": "SK_ID_CURR SK_ID_PREV NUM_INSTALMENT_NUMBER NUM_INSTALMENT_VERSION PAYMENT_ID DAYS_ENTRY_PAYMENT AMT_PAYMENT DAYS_AVAILABLE".split(),
    "pos_cash_balance": "SK_ID_CURR SK_ID_PREV MONTHS_BALANCE DAYS_AVAILABLE SK_DPD NAME_CONTRACT_STATUS".split(),
    "credit_card_balance": "SK_ID_CURR SK_ID_PREV MONTHS_BALANCE DAYS_AVAILABLE SK_DPD NAME_CONTRACT_STATUS AMT_BALANCE AMT_CREDIT_LIMIT_ACTUAL".split(),
    "installment_schedule": "SK_ID_CURR SK_ID_PREV NUM_INSTALMENT_NUMBER NUM_INSTALMENT_VERSION DAYS_INSTALMENT AMT_INSTALMENT DAYS_AVAILABLE".split(),
}


def paths_for(raw):
    files = {p.name.lower(): p for p in raw.glob("*.csv")}
    return {key: next((files[n.lower()] for n in names if n.lower() in files), None)
            for key, names in C.FILES.items()} | {"installment_schedule": files.get("installment_schedule.csv")}


def preflight(raw, paths):
    blockers = []
    manifest_path = raw / "adapter_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    try:
        source_manifest("full")
    except ContractError as exc:
        blockers.append(str(exc))
    for gate in ("annuity_monthly_verified", "category_mapping_verified", "cash_product_verified",
                 "schedule_complete", "schedule_versions_resolved", "payment_identity_verified", "availability_verified"):
        if manifest.get(gate) is not True:
            blockers.append(f"Unverified gate: {gate}")
    for key in HISTORY_GROUPS:
        item = manifest.get("sources", {}).get(key, {})
        if item.get("state") not in ("COMPLETE", "CONFIRMED_EMPTY") or not item.get("evidence"):
            blockers.append(f"No complete/confirmed-empty source evidence: {key}")
    for key, columns in REQUIRED.items():
        path = paths.get(key)
        if path is None:
            blockers.append(f"Missing source: {key}")
        else:
            missing = sorted(set(columns) - set(pd.read_csv(path, nrows=0).columns))
            if missing:
                blockers.append(f"{key}: missing columns {', '.join(missing)}")
    return manifest, blockers


def profile_sources(paths, eligible, out, chunksize):
    """Raw row coverage, not certified as-of history coverage; bounded CSV reads."""
    owners = None
    if paths.get("bureau"):
        b = pd.read_csv(paths["bureau"], usecols=["SK_ID_BUREAU", "SK_ID_CURR"])
        if b.SK_ID_BUREAU.isna().any() or b.SK_ID_BUREAU.duplicated().any():
            raise ContractError("Bureau ownership mapping has missing/duplicate account keys")
        owners = b.set_index("SK_ID_BUREAU").SK_ID_CURR
    coverage, columns, distributions = [], [], {}
    for key in HISTORY_GROUPS:
        path = paths.get(key)
        if path is None:
            coverage.append({"source": key, "state": "MISSING", "raw_row_coverage_pct": None})
            continue
        print(f"Profiling {path.name}", flush=True)
        header = pd.read_csv(path, nrows=0).columns
        selected = [c for c in REQUIRED[key] if c in header]
        if key == "installments_payments":
            selected += [c for c in ("DAYS_INSTALMENT", "AMT_INSTALMENT") if c in header]
        counts, missing, invalid, negative = Counter(), Counter(), Counter(), Counter()
        minimum, maximum, sums, valid_n, categories = {}, {}, Counter(), Counter(), {}
        rows = orphan = future = 0
        for chunk in pd.read_csv(path, usecols=selected, chunksize=chunksize,
                                 dtype={c: "string" for c in selected if c in ("STATUS", "NAME_CONTRACT_STATUS", "CREDIT_ACTIVE", "PAYMENT_ID")}):
            rows += len(chunk)
            ids = chunk.SK_ID_CURR if "SK_ID_CURR" in chunk else chunk.SK_ID_BUREAU.map(owners) if owners is not None else pd.Series(np.nan, index=chunk.index)
            orphan += int(ids.isna().sum())
            counts.update(ids[ids.isin(eligible)].value_counts().to_dict())
            event_col = {"bureau": "DAYS_CREDIT", "bureau_balance": "MONTHS_BALANCE", "previous_application": "DAYS_DECISION",
                         "installments_payments": "DAYS_ENTRY_PAYMENT", "pos_cash_balance": "MONTHS_BALANCE", "credit_card_balance": "MONTHS_BALANCE"}[key]
            if event_col in chunk:
                future += int(pd.to_numeric(chunk[event_col], errors="coerce").gt(0).sum())
            for col in selected:
                s = chunk[col]
                missing[col] += int(s.isna().sum())
                if col in ("STATUS", "NAME_CONTRACT_STATUS", "CREDIT_ACTIVE"):
                    categories.setdefault(col, Counter()).update(s.dropna().astype(str).value_counts().to_dict())
                elif col != "PAYMENT_ID":
                    nums = pd.to_numeric(s, errors="coerce")
                    finite = nums[np.isfinite(nums)]
                    invalid[col] += int((s.notna() & ~np.isfinite(nums)).sum())
                    negative[col] += int(finite.lt(0).sum())
                    if len(finite):
                        minimum[col] = min(minimum.get(col, float("inf")), float(finite.min()))
                        maximum[col] = max(maximum.get(col, float("-inf")), float(finite.max()))
                        sums[col] += float(finite.sum())
                        valid_n[col] += len(finite)
        for col in selected:
            columns.append({"source": key, "column": col, "rows": rows, "missing_pct": 100 * missing[col] / rows if rows else None,
                            "invalid_numeric_count": invalid[col], "negative_numeric_count": negative[col],
                            "min": minimum.get(col), "max": maximum.get(col),
                            "mean": sums[col] / valid_n[col] if valid_n[col] else None})
        distribution = pd.Series([counts.get(i, 0) for i in sorted(eligible)], dtype="int64")
        coverage.append({"source": key, "state": "OBSERVED_NOT_VERIFIED", "raw_rows": rows,
                         "eligible_applicants": len(eligible), "applicants_with_rows": len(counts),
                         "raw_row_coverage_pct": 100 * len(counts) / len(eligible) if eligible else None,
                         "unmapped_or_missing_owner_rows": orphan, "future_event_rows": future,
                         "rows_per_eligible_applicant_p50": float(distribution.quantile(.5)) if eligible else None,
                         "rows_per_eligible_applicant_p95": float(distribution.quantile(.95)) if eligible else None})
        distributions[key] = {c: dict(v) for c, v in categories.items()}
    pd.DataFrame(coverage).to_csv(out / "source_coverage.csv", index=False)
    pd.DataFrame(columns).to_csv(out / "source_column_quality.csv", index=False)
    write_json(out / "source_categories.json", distributions)
    return coverage


def feature_quality(frame, out):
    rows, distributions = [], {}
    groups = {c: k for k, cols in HISTORY_GROUPS.items() for c in cols}
    for col in FULL_FEATURES:
        present = col in frame
        s = frame[col] if present else pd.Series(dtype="float64")
        n = len(frame)
        known = int(s.notna().sum())
        item = {"feature": col, "source_group": groups.get(col, "application"),
                "status": "GENERATED" if present else "BLOCKED_NOT_GENERATED", "rows": n,
                "missing_pct": 100 * (n - known) / n if n else None,
                "coverage_pct": 100 * known / n if n else None}
        if present and pd.api.types.is_numeric_dtype(s):
            finite = s[np.isfinite(s)]
            item["nonfinite_nonnull_count"] = int((s.notna() & ~np.isfinite(s)).sum())
            if len(finite):
                item.update({"min": float(finite.min()), "mean": float(finite.mean()), "max": float(finite.max()),
                             **{f"p{q}": float(finite.quantile(q / 100)) for q in (1, 25, 50, 75, 99)}})
                # Near-constant ratios can span fewer than 20 representable floats.
                edges = np.unique(np.linspace(float(finite.min()), float(finite.max()), 21))
                hist, edges = np.histogram(finite, bins=edges if len(edges) > 1 else 1)
                distributions[col] = {"counts": hist.tolist(), "edges": edges.tolist()}
        elif present:
            distributions[col] = s.value_counts(dropna=False).to_dict()
        rows.append(item)
    pd.DataFrame(rows).to_csv(out / "feature_quality.csv", index=False)
    write_json(out / "feature_distributions.json", distributions)


def build(raw, out, chunksize=250000):
    raw, out = Path(raw).resolve(), Path(out).resolve()
    if not raw.is_dir() or chunksize < 1:
        raise ValueError("Raw directory must exist and chunksize must be positive")
    if raw == out or raw in out.parents or out == ML_ROOT or out in ML_ROOT.parents:
        raise ValueError("Output must be a separate directory, outside raw sources")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output directory must be empty; choose a new build directory")
    out.mkdir(parents=True, exist_ok=True)
    old_raw = C.RAW_DIR
    C.RAW_DIR = raw
    try:
        paths = paths_for(raw)
        source_paths = [p for key, p in paths.items() if p and key != "application_test"]
        source_paths += [raw / "adapter_manifest.json"] if (raw / "adapter_manifest.json").exists() else []
        source_stats = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in source_paths}
        print("Fingerprinting source files (read-only)", flush=True)
        inputs = {p.name: sha256(p) for p in source_paths}
        code = {p.name: sha256(p) for p in (ML_ROOT / "creditiq_ml").glob("*.py")}
        manifest, blockers = preflight(raw, paths)
        if paths.get("application_train") is None:
            raise ContractError("Missing application_train.csv")
        # The existing Lite gate permits ONLY the application features under research assumptions.
        source_manifest("lite")
        app = pd.read_csv(paths["application_train"])
        if "TARGET" not in app or app.TARGET.isna().any() or not app.TARGET.isin([0, 1]).all():
            raise ContractError("Training TARGET must be present, binary and nonmissing")
        source_rows = len(app)
        frame, exclusions = application_features(app.assign(IS_TRAIN=1), return_exclusions=True)
        del app
        if frame.empty:
            raise ContractError("No eligible training applications")
        frame = frame.sort_values("SK_ID_CURR").reset_index(drop=True)
        pd.DataFrame(exclusions, columns=["id", "reason"]).to_csv(out / "excluded_applications.csv", index=False)
        coverage = profile_sources(paths, set(frame.SK_ID_CURR), out, chunksize)
        if not blockers:
            try:
                # Existing canonical code owns all aggregation and relationship validation.
                tables = {k: pd.read_csv(paths[k], dtype={"STATUS": str} if k == "bureau_balance" else None) for k in HISTORY_GROUPS}
                schedule = pd.read_csv(paths["installment_schedule"])
                history = history_features(frame.SK_ID_CURR.tolist(), tables, schedule, manifest)
                candidate = frame.merge(history, on="SK_ID_CURR", how="left", validate="one_to_one")
                candidate[FULL_FEATURES] = validate_features(candidate, "full")
                frame = candidate
            except (ContractError, ValueError, KeyError) as exc:
                blockers.append(f"Canonical Full aggregation/validation failed: {exc}")
        ready = not blockers
        filename = "full_features.parquet" if ready else "application_features_ONLY_NOT_FULL.parquet"
        frame.to_parquet(out / filename, index=False)
        feature_quality(frame, out)
        # Source mutations during a build invalidate publication, rather than silently changing provenance.
        if any((p.stat().st_size, p.stat().st_mtime_ns) != source_stats[str(p)] for p in source_paths):
            raise ContractError("Input changed during build; discard output and rerun")
        generated = len(set(FULL_FEATURES) & set(frame.columns))
        result = {"status": "FULL_CONTRACT_VALIDATED" if ready else "BLOCKED", "training_ready": ready,
                  "release_ready": False, "mode": "RESEARCH_ONLY", "synthetic": manifest.get("synthetic", False),
                  "source_application_rows": source_rows, "eligible_rows": len(frame), "excluded_rows": len(exclusions),
                  "required_features": len(FULL_FEATURES), "generated_features": generated,
                  "unavailable_features": [c for c in FULL_FEATURES if c not in frame],
                  "dataset": filename, "dataset_sha256": sha256(out / filename), "blockers": blockers,
                  "input_sha256": inputs, "canonical_source_sha256": code, "builder_sha256": sha256(Path(__file__)),
                  "runtime": {"python": sys.version.split()[0], "pandas": pd.__version__, "numpy": np.__version__},
                  "source_manifest": manifest, "competition_test_included": False,
                  "training_performed": False,
                  "interpretation": "Raw row coverage is not verified as-of coverage. Blocked features have no distributions; 100% unavailable does not mean observed nulls. Training-ready means dataset contract only, not production readiness."}
        write_json(out / "build_manifest.json", result)
        report = ["# Full feature dataset readiness", "", f"**Status: {result['status']}; training_ready={str(ready).lower()}; release_ready=false.**", "",
                  f"Generated {generated}/{len(FULL_FEATURES)} features for {len(frame):,} eligible training applicants; {len(exclusions):,} excluded from {source_rows:,} source rows.",
                  "Competition test is excluded. No training, imputation, calibration or model changes were performed.", "",
                  "## Contract blockers", ""] + ([f"- {b}" for b in blockers] or ["None in canonical dataset validation; model evaluation has not been performed."])
        report += ["", "## Files and interpretation", "", f"- {filename}: {'validated Full features' if ready else 'application-only diagnostic dataset, NOT a Full training dataset'}.",
                   "- feature_quality.csv: one row per 60-feature contract entry; non-null coverage, missingness, quantiles and status.",
                   "- feature_distributions.json: numeric histograms/category counts for generated features only.",
                   "- source_coverage.csv: raw history presence among eligible applicants, not evidence of completeness or cutoff availability.",
                   "- source_column_quality.csv and source_categories.json: streamed raw input distributions, missingness, invalid numeric and negative counts; negative relative dates are expected, not inherently errors.",
                   "- excluded_applications.csv: unchanged application adapter exclusions.",
                   "- build_manifest.json: all blockers, assumptions, source/code/output hashes and environment versions.", "",
                   "## Observed raw source coverage", "", "| Source | Eligible applicants with rows | Coverage |", "|---|---:|---:|"]
        for row in coverage:
            value = row.get("raw_row_coverage_pct")
            report.append(f"| {row['source']} | {row.get('applicants_with_rows', 'unknown')} | {value:.2f}% |" if value is not None else f"| {row['source']} | unknown | unknown |")
        report += ["", "## Next action", "", "Provide audited per-source availability/completeness evidence and a normalized adapter manifest accepted by the existing Full policy. Provide payment identity/reversal reconciliation and the effective contractual schedule, including never-paid obligations. Do not fabricate dates, IDs or verification flags. Rerun into a new output directory. Until then retain Lite and do not train Full.",
                   "", "The supplied payment rows alone cannot establish never-paid obligations. User-declared Installment Intelligence snapshots do not supply historical verification. Raw source profiling does not certify all relational keys, duplicates, effective versions or as-of semantics; canonical validation runs only after gates pass."]
        (out / "FULL_FEATURE_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        print(f"{result['status']}: {generated}/60 features; report: {out / 'FULL_FEATURE_REPORT.md'}", flush=True)
        return result
    finally:
        C.RAW_DIR = old_raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunksize", type=int, default=250000)
    args = parser.parse_args()
    try:
        outcome = build(args.raw_dir, args.output_dir, args.chunksize)
    except (ContractError, ValueError, OSError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")
    sys.exit(0 if outcome["training_ready"] else 2)

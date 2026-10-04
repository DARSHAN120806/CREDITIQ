"""Exploratory Data Analysis. Writes plots + tables to reports/eda and a JSON seed for the future analytics dashboard."""
from __future__ import annotations
import json
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from . import config as C
from .io import load, exists

log = logging.getLogger(__name__)
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})


def _rate_by(df, col, min_count=200, top=None, sort_rate=True):
    g = df.groupby(col, dropna=False, observed=True)[C.TARGET].agg(default_rate="mean", count="size").reset_index()
    g = g[g["count"] >= min_count]
    if sort_rate:
        g = g.sort_values("default_rate", ascending=False)
    key = g[col]
    g[col] = key.astype(object).where(key.notna(), "MISSING").astype(str)
    return g.head(top) if top else g


def run_eda():
    out = C.REPORTS_DIR / "eda"
    out.mkdir(parents=True, exist_ok=True)
    app = load("application_train")
    summary = {}

    # 1. overview ---------------------------------------------------------
    summary["rows"], summary["columns"] = map(int, app.shape)
    summary["duplicate_ids"] = int(app[C.ID_COL].duplicated().sum())
    summary["default_rate"] = float(app[C.TARGET].mean())
    summary["class_counts"] = app[C.TARGET].value_counts().to_dict()
    summary["imbalance_ratio"] = float((app[C.TARGET] == 0).sum() / (app[C.TARGET] == 1).sum())
    app.dtypes.astype(str).rename("dtype").to_csv(out / "dtypes.csv")
    app.describe(include="all").T.to_csv(out / "describe.csv")

    # 2. missing values ---------------------------------------------------
    miss = app.isna().mean().sort_values(ascending=False)
    miss[miss > 0].rename("missing_frac").to_csv(out / "missing_values.csv")
    summary["columns_over_50pct_missing"] = int((miss > 0.5).sum())
    top = miss.head(30)[::-1]
    plt.figure(figsize=(8, 8)); plt.barh(top.index, top.values, color="#4f46e5")
    plt.title("Top 30 columns by missing fraction"); plt.tight_layout()
    plt.savefig(out / "missing_values.png"); plt.close()

    # 3. data quality / outliers -----------------------------------------
    q = {}
    if "DAYS_EMPLOYED" in app:
        q["days_employed_placeholder_365243"] = int((app["DAYS_EMPLOYED"] == 365243).sum())
    for col in ["AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "AMT_GOODS_PRICE", "CNT_CHILDREN"]:
        if col in app:
            q1, q3 = app[col].quantile([.25, .75]); iqr = q3 - q1
            q[col] = {"iqr_outliers": int(((app[col] < q1 - 1.5 * iqr) | (app[col] > q3 + 1.5 * iqr)).sum()),
                      "max": float(app[col].max()), "p99": float(app[col].quantile(.99))}
    if "CODE_GENDER" in app:
        q["gender_XNA_rows"] = int((app["CODE_GENDER"] == "XNA").sum())
    summary["data_quality"] = q

    # 4. relational coverage ---------------------------------------------
    cov = {}
    base = set(app[C.ID_COL])
    for key in ["bureau", "previous_application", "installments_payments", "credit_card_balance", "pos_cash_balance"]:
        if exists(key):
            ids = set(load(key, usecols=[C.ID_COL])[C.ID_COL].unique())
            cov[key] = round(len(base & ids) / len(base), 4)
    summary["train_customers_with_history_frac"] = cov

    # 5. target + distributions ------------------------------------------
    plt.figure(figsize=(4, 4))
    vc = app[C.TARGET].value_counts().sort_index()
    plt.bar(["No default (0)", "Default (1)"], vc.values, color=["#16a34a", "#dc2626"])
    plt.title("Target distribution"); plt.tight_layout(); plt.savefig(out / "target_distribution.png"); plt.close()

    age = -app["DAYS_BIRTH"] / 365.25
    fig, ax = plt.subplots(2, 2, figsize=(10, 7))
    ax[0, 0].hist(age, 40, color="#4f46e5"); ax[0, 0].set_title("Age (years)")
    ax[0, 1].hist(np.log10(app["AMT_INCOME_TOTAL"].clip(lower=1)), 40, color="#0ea5e9"); ax[0, 1].set_title("log10 Annual income")
    ax[1, 0].hist(app["AMT_CREDIT"], 40, color="#f59e0b"); ax[1, 0].set_title("Credit amount")
    ax[1, 1].hist(app["AMT_ANNUITY"].dropna(), 40, color="#10b981"); ax[1, 1].set_title("Annuity")
    plt.tight_layout(); plt.savefig(out / "numeric_distributions.png"); plt.close()

    # 6. default rate by segment (also feeds the Recharts dashboards) ----
    seed = {}
    cat_cols = [c for c in ["NAME_EDUCATION_TYPE", "OCCUPATION_TYPE", "NAME_INCOME_TYPE", "CODE_GENDER",
                            "NAME_FAMILY_STATUS", "NAME_HOUSING_TYPE", "FLAG_OWN_REALTY", "NAME_CONTRACT_TYPE"] if c in app]
    fig, axes = plt.subplots(len(cat_cols), 1, figsize=(9, 3.2 * len(cat_cols)))
    for ax, col in zip(np.atleast_1d(axes), cat_cols):
        g = _rate_by(app, col)
        ax.barh(g[col][::-1], g["default_rate"][::-1], color="#4f46e5")
        ax.axvline(summary["default_rate"], color="red", ls="--", lw=1)
        ax.set_title(f"Default rate by {col}")
        seed[col] = g.to_dict("records")
    plt.tight_layout(); plt.savefig(out / "default_rate_by_category.png"); plt.close()

    app["AGE_BIN"] = pd.cut(age, [18, 25, 30, 35, 40, 45, 50, 55, 60, 70], right=False)
    app["INCOME_BIN"] = pd.qcut(app["AMT_INCOME_TOTAL"], 10, duplicates="drop")
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    for a, col in zip(ax, ["AGE_BIN", "INCOME_BIN"]):
        g = _rate_by(app, col, min_count=1, sort_rate=False)
        a.bar(range(len(g)), g["default_rate"], color="#4f46e5"); a.set_xticks(range(len(g)))
        a.set_xticklabels(g[col], rotation=60, ha="right", fontsize=7); a.set_title(f"Default rate by {col}")
        seed[col] = g.to_dict("records")
    plt.tight_layout(); plt.savefig(out / "default_rate_age_income.png"); plt.close()

    # 7. EXT_SOURCE + correlations ---------------------------------------
    ext = [c for c in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"] if c in app]
    if ext:
        fig, ax = plt.subplots(1, len(ext), figsize=(4.5 * len(ext), 3.5))
        for a, c in zip(np.atleast_1d(ax), ext):
            for t, colr in [(0, "#16a34a"), (1, "#dc2626")]:
                a.hist(app.loc[app[C.TARGET] == t, c].dropna(), 40, alpha=.5, density=True, color=colr, label=f"TARGET={t}")
            a.set_title(c); a.legend()
        plt.tight_layout(); plt.savefig(out / "ext_source_by_target.png"); plt.close()

    corr = app.select_dtypes("number").drop(columns=[C.TARGET], errors="ignore").corrwith(app[C.TARGET]).dropna()
    corr = corr.reindex(corr.abs().sort_values(ascending=False).index)
    corr.head(40).rename("corr_with_target").to_csv(out / "top_correlations.csv")
    t = corr.head(20)[::-1]
    plt.figure(figsize=(8, 7)); plt.barh(t.index, t.values, color=["#dc2626" if v > 0 else "#16a34a" for v in t.values])
    plt.title("Top 20 numeric correlations with TARGET"); plt.tight_layout(); plt.savefig(out / "top_correlations.png"); plt.close()

    json.dump(summary, open(out / "eda_summary.json", "w"), indent=2, default=str)
    json.dump(seed, open(out / "analytics_seed.json", "w"), indent=2, default=str)
    log.info("EDA complete -> %s", out)
    return summary

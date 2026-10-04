"""Generate isolated, internally consistent SYNTHETIC fixtures; never overwrite real data."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd


def generate(out, n=2000, n_test=200):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output directory must be empty; do not mix synthetic and real data")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(7)
    ids = np.arange(100000, 100000 + n + n_test)
    size = len(ids)
    income = rng.lognormal(12, .5, size)
    credit = income * rng.uniform(.5, 5, size)
    family = rng.randint(1, 6, size)
    tenure = rng.randint(0, 15 * 365, size)
    app = pd.DataFrame({"SK_ID_CURR": ids, "NAME_CONTRACT_TYPE": "Cash loans",
          "DAYS_BIRTH": -rng.randint(25 * 365, 65 * 365, size), "DAYS_EMPLOYED": -tenure,
          "AMT_INCOME_TOTAL": income, "AMT_CREDIT": credit, "AMT_ANNUITY": credit / 36,
          "AMT_GOODS_PRICE": credit, "CNT_FAM_MEMBERS": family,
          "CNT_CHILDREN": [rng.randint(0, k) for k in family],
          "NAME_INCOME_TYPE": rng.choice(["Working", "Pensioner", "Commercial associate"], size),
          "NAME_EDUCATION_TYPE": rng.choice(["Secondary / secondary special", "Higher education"], size),
          "OCCUPATION_TYPE": rng.choice(["Laborers", "Managers", None], size),
          "NAME_HOUSING_TYPE": rng.choice(["House / apartment", "With parents", None], size)})
    app.loc[app.NAME_INCOME_TYPE.eq("Pensioner"), "DAYS_EMPLOYED"] = 365243
    target = (rng.rand(n) < .10 + .15 * (credit[:n] / income[:n] > 3)).astype(int)
    app.iloc[:n].assign(TARGET=target).to_csv(out / "application_train.csv", index=False)
    app.iloc[n:].to_csv(out / "application_test.csv", index=False)
    bureau = pd.DataFrame({"SK_ID_CURR": ids, "SK_ID_BUREAU": ids + 1000000,
        "DAYS_CREDIT": -365, "DAYS_AVAILABLE": -1, "CREDIT_ACTIVE": "Active",
        "CREDIT_DAY_OVERDUE": rng.choice([0, 0, 10], size),
        "AMT_CREDIT_SUM": credit, "AMT_CREDIT_SUM_DEBT": credit * .5, "AMT_CREDIT_SUM_OVERDUE": 0.0})
    bureau.to_csv(out / "bureau.csv", index=False)
    pd.DataFrame({"SK_ID_BUREAU": ids + 1000000, "MONTHS_BALANCE": -1, "DAYS_AVAILABLE": -1,
                  "STATUS": rng.choice(["0", "1", "C", "X"], size)}).to_csv(out / "bureau_balance.csv", index=False)
    previous = pd.DataFrame({"SK_ID_CURR": ids, "SK_ID_PREV": ids + 2000000, "DAYS_DECISION": -200,
                             "DAYS_AVAILABLE": -200, "NAME_CONTRACT_STATUS": "Approved"})
    previous.to_csv(out / "previous_application.csv", index=False)
    card_previous = previous.assign(SK_ID_PREV=ids + 3000000)
    pd.concat([previous, card_previous], ignore_index=True).to_csv(out / "previous_application.csv", index=False)
    schedules, payments = [], []
    for customer, loan in zip(ids, ids + 2000000):
        for number, due in enumerate([-90, -60, -30], 1):
            base = {"SK_ID_CURR": int(customer), "SK_ID_PREV": int(loan),
                    "NUM_INSTALMENT_NUMBER": number, "NUM_INSTALMENT_VERSION": 1,
                    "DAYS_INSTALMENT": due, "AMT_INSTALMENT": 100.0}
            schedules.append({**base, "DAYS_AVAILABLE": -200})
            if number == 1:
                for part, day in enumerate([due - 2, due + 2]):
                    payments.append({**base, "PAYMENT_ID": f"{loan}-{number}-{part}", "DAYS_ENTRY_PAYMENT": day,
                                     "DAYS_AVAILABLE": day, "AMT_PAYMENT": 50.0})
            elif number == 2:
                payments.append({**base, "PAYMENT_ID": f"{loan}-{number}-0", "DAYS_ENTRY_PAYMENT": due - 1,
                                 "DAYS_AVAILABLE": due - 1, "AMT_PAYMENT": 100.0})
            # number 3 is a contractual, never-paid installment.
    pd.DataFrame(schedules).to_csv(out / "installment_schedule.csv", index=False)
    pd.DataFrame(payments).to_csv(out / "installments_payments.csv", index=False)
    pd.DataFrame({"SK_ID_CURR": ids, "SK_ID_PREV": ids + 2000000, "MONTHS_BALANCE": -1,
        "DAYS_AVAILABLE": -1, "SK_DPD": rng.choice([0, 5, 20], size), "NAME_CONTRACT_STATUS": "Active",
        "CNT_INSTALMENT": 12, "CNT_INSTALMENT_FUTURE": 9}).to_csv(out / "POS_CASH_balance.csv", index=False)
    pd.DataFrame({"SK_ID_CURR": ids, "SK_ID_PREV": ids + 3000000, "MONTHS_BALANCE": -1,
        "DAYS_AVAILABLE": -1, "SK_DPD": rng.choice([0, 0, 30], size), "NAME_CONTRACT_STATUS": "Active",
        "AMT_BALANCE": rng.uniform(0, 12000, size), "AMT_CREDIT_LIMIT_ACTUAL": 10000.0}).to_csv(out / "credit_card_balance.csv", index=False)
    sources = ["bureau", "bureau_balance", "previous_application", "installments_payments", "pos_cash_balance", "credit_card_balance"]
    manifest = {"synthetic": True, "currency": "XXX", "evidence": "Synthetic generator; not real-data verification",
                "annuity_monthly_verified": True, "category_mapping_verified": True, "cash_product_verified": True,
                "schedule_complete": True, "schedule_versions_resolved": True, "payment_identity_verified": True,
                "availability_verified": True, "sources": {k: {"state": "COMPLETE", "evidence": "generated fixture"} for k in sources}}
    (out / "adapter_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="data/raw_synth")
    parser.add_argument("--rows", type=int, default=2000)
    args = parser.parse_args()
    print(generate(args.output, args.rows))


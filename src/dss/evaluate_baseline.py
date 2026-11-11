"""DSS module 1 - first evaluation: baselines vs. models, chronological 80/20 split.

Split (by purchase date, delivered orders with a known late flag, window 01/2017-08/2018):
    train      01/2017-03/2018   fit models
    validation 04/2018-05/2018   calibrate probabilities (isotonic), choose thresholds
    test       06/2018-08/2018   final evaluation  (train+validation = 80%, test = 20%)
A random 80/20 split is also run, only to show why it must not be used.

Outputs: src/dss/results/{comparison.csv, per_month.csv, thresholds.csv, tree_rules.txt, summary.json}
Usage: python -m src.dss.evaluate_baseline
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

from .features import CAT, NUM, build_features

OUT = Path(__file__).resolve().parent / "results"
X_COLS = NUM + CAT


def recall_at_top(y, p, frac=0.10):
    k = max(1, int(round(len(p) * frac)))
    idx = np.argsort(-np.asarray(p), kind="stable")[:k]
    y = np.asarray(y)
    return y[idx].sum() / y.sum(), y[idx].mean()          # recall, precision within the top k


def metrics(name, y, p, split="time"):
    r10, prec10 = recall_at_top(y, p, 0.10)
    r5, _ = recall_at_top(y, p, 0.05)
    return {"split": split, "model": name, "n": len(y), "positives": int(np.sum(y)),
            "prevalence": round(float(np.mean(y)), 4),
            "pr_auc": round(average_precision_score(y, p), 4), "roc_auc": round(roc_auc_score(y, p), 4),
            "recall_top5": round(r5, 4), "recall_top10": round(r10, 4), "precision_top10": round(prec10, 4),
            "brier": round(brier_score_loss(y, np.clip(p, 0, 1)), 4)}


def make_models():
    onehot = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), CAT)])
    ordinal = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), NUM),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                               encoded_missing_value=-1), CAT)])
    cat_idx = list(range(len(NUM), len(NUM) + len(CAT)))
    return {
        "logistic_regression": make_pipeline(onehot, LogisticRegression(max_iter=3000, class_weight="balanced")),
        "decision_tree_d4": make_pipeline(ordinal, DecisionTreeClassifier(
            max_depth=4, min_samples_leaf=200, class_weight="balanced", random_state=42)),
        "hist_gradient_boosting": make_pipeline(ordinal, HistGradientBoostingClassifier(
            learning_rate=0.05, max_iter=300, max_leaf_nodes=31, l2_regularization=1.0, min_samples_leaf=100,
            categorical_features=cat_idx, class_weight="balanced", random_state=42)),
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = build_features()
    d = df[df.is_late.notna() & df.purchase_date.between("2017-01-01", "2018-08-31")].copy()
    d["is_late"] = d.is_late.astype(int)
    train = d[d.purchase_date < "2018-04-01"]
    val = d[(d.purchase_date >= "2018-04-01") & (d.purchase_date < "2018-06-01")]
    test = d[d.purchase_date >= "2018-06-01"]
    print(f"orders: train {len(train)} ({train.is_late.mean():.2%} late), val {len(val)} "
          f"({val.is_late.mean():.2%}), test {len(test)} ({test.is_late.mean():.2%}); "
          f"train+val share = {(len(train) + len(val)) / len(d):.1%}")

    rows, preds = [], {}
    rng = np.random.default_rng(42)
    preds["random"] = rng.random(len(test))
    preds["baseline_route_history"] = test.route_hist_late.to_numpy()
    preds["baseline_seller_history"] = test.seller_hist_late.to_numpy()
    preds["baseline_max(route,seller)"] = np.maximum(test.route_hist_late, test.seller_hist_late).to_numpy()
    fitted = {}
    for name, mdl in make_models().items():
        mdl.fit(train[X_COLS], train.is_late)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(
            mdl.predict_proba(val[X_COLS])[:, 1], val.is_late)
        preds[name] = iso.predict(mdl.predict_proba(test[X_COLS])[:, 1])
        fitted[name] = (mdl, iso)
    for name, p in preds.items():
        rows.append(metrics(name, test.is_late, p))

    # Model refit on the full 80% (train + validation), ranking metrics on the 20% test
    trval = pd.concat([train, val])
    hgb80 = make_models()["hist_gradient_boosting"].fit(trval[X_COLS], trval.is_late)
    rows.append(metrics("hist_gradient_boosting_refit_80pct", test.is_late,
                        hgb80.predict_proba(test[X_COLS])[:, 1]))

    # Counter-example: random 80/20 split (NOT valid for time-ordered data)
    tr_r, te_r = train_test_split(d, test_size=0.2, random_state=42, stratify=d.is_late)
    hgb_r = make_models()["hist_gradient_boosting"].fit(tr_r[X_COLS], tr_r.is_late)
    rows.append(metrics("hist_gradient_boosting", te_r.is_late, hgb_r.predict_proba(te_r[X_COLS])[:, 1],
                        split="random_80_20"))
    comp = pd.DataFrame(rows)
    comp.to_csv(OUT / "comparison.csv", index=False)

    # Per test month (drift) for the main candidates
    pm = []
    for month, g in test.groupby(test.purchase_date.dt.to_period("M")):
        idx = test.index.get_indexer(g.index)
        for name in ["baseline_route_history", "baseline_max(route,seller)", "hist_gradient_boosting"]:
            r = metrics(name, g.is_late, preds[name][idx])
            r["month"] = str(month)
            pm.append(r)
    pd.DataFrame(pm).to_csv(OUT / "per_month.csv", index=False)

    # Threshold table for the best time-split model (by PR-AUC)
    best = comp[comp.split.eq("time") & comp.model.isin(fitted)].sort_values("pr_auc").iloc[-1].model
    p, y = preds[best], test.is_late.to_numpy()
    th = []
    for t in np.round(np.arange(0.05, 0.55, 0.05), 2):
        flag = p >= t
        tp = int((flag & (y == 1)).sum())
        th.append({"threshold": t, "flagged": int(flag.sum()), "flagged_pct": round(flag.mean(), 4),
                   "tp": tp, "precision": round(tp / max(flag.sum(), 1), 4), "recall": round(tp / y.sum(), 4)})
    pd.DataFrame(th).to_csv(OUT / "thresholds.csv", index=False)

    tree = fitted["decision_tree_d4"][0]
    (OUT / "tree_rules.txt").write_text(export_text(tree[-1], feature_names=X_COLS), encoding="utf-8")
    summary = {"p0_train": round(df.attrs["p0"], 4), "best_time_split_model": best,
               "n_train": len(train), "n_val": len(val), "n_test": len(test)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    pd.set_option("display.width", 200)
    print(comp.drop(columns=["n"]).to_string(index=False))
    print(pd.DataFrame(pm)[["month", "model", "positives", "prevalence", "pr_auc", "roc_auc", "recall_top10"]]
          .to_string(index=False))
    print(pd.DataFrame(th).to_string(index=False))


if __name__ == "__main__":
    main()

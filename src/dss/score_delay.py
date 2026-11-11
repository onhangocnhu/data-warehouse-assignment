"""DSS - score the orders handed over to the carrier in the test months, write dss.* and backtest.

Decision supported: when the seller hands an order over to the carrier, should the platform act on it
(warn the customer, offer a voucher, upgrade the shipping)? For each test month M (06, 07, 08/2018),
as a monthly production run would do:
  1. training data = orders purchased before M whose estimated date has passed (outcome known);
  2. the most recent 60 days of that data calibrate the probabilities (isotonic regression);
  3. orders handed over in month M are scored; each day the riskiest orders are flagged:
       RED = top 5% of the day, YELLOW = next 10% (capacity policy), GREEN = the rest;
     orders already past their estimated date at handover are RED by rule (certainly late);
  4. three human-readable reasons and a recommended action are attached.
Then the policies are backtested on the known outcomes (capacity curve, confusion matrix and
expected-cost policy).

Outputs: dss.model_registry, dss.delay_risk_score,
         src/dss/results/{scores.csv, capacity_curve.csv, policy_backtest.csv, confusion.csv, importance.csv}
Usage:   python -m src.dss.score_delay
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score

from src.etl.config import DSN
from .evaluate_models import CAT, FEATURE_SETS, TEST_MONTHS, RankEnsemble, score
from .features import build_features

RES = Path(__file__).resolve().parent / "results"
CAL_DAYS = 60
RED_PCT, YELLOW_PCT = 0.05, 0.15
STAGE = "handover"

# Cost assumptions for the expected-cost policy (BRL per order); the dashboard lets the user change them
# (what-if). A late order costs support time, a voucher and part of the customer's future value;
# the intervention is contacting the customer and offering a voucher.
COST = {"late": 30.0, "intervene": 8.0, "effect": 0.4}
LOW_REVIEW_ON_TIME, LOW_REVIEW_LATE = 0.093, 0.624      # share of 1-2 star reviews (OLAP, section 3.3)

ACTIONS = {
    "RED": "Chủ động báo khách về khả năng trễ, tặng voucher; đề xuất chuyển gói vận chuyển nhanh",
    "YELLOW": "Theo dõi hành trình hằng ngày, sẵn sàng liên hệ khách",
}
CERTAIN_ACTION = "Đơn đã quá ngày giao dự kiến khi bàn giao: liên hệ khách ngay, tặng voucher xin lỗi"


def stage_setup(specs):
    cols = sorted({c for s in specs for c in FEATURE_SETS[s["features"]]})
    algo = "hist_gradient_boosting" if len(specs) == 1 else "rank_ensemble_" + "_".join(s["algo"] for s in specs)
    return {STAGE: dict(cols=cols, algo=algo, specs=specs, time="carrier_date")}


def ensemble_importance(model, sample, cols, n_repeats=5, seed=1):
    """Permutation importance of the ensemble: drop in PR-AUC when one feature is shuffled."""
    rng = np.random.default_rng(seed)
    base = average_precision_score(sample.label, model.score_batch(sample))
    out = []
    for c in cols:
        drops = []
        for _ in range(n_repeats):
            s = sample.copy()
            s[c] = rng.permutation(s[c].to_numpy())
            drops.append(base - average_precision_score(s.label, model.score_batch(s)))
        out.append(np.mean(drops))
    return out


def reasons(row, ref, stage):
    """Up to three reasons, ranked by how far the order is from a normal order (ratio to reference)."""
    c = []
    if row.route_late_90d > 1.5 * ref["p"]:
        c.append((row.route_late_90d / ref["p"], f"Tuyến {row.route} trễ {row.route_late_90d:.0%} trong 90 ngày qua"))
    if row.seller_hist_n >= 10 and row.seller_late_90d > 1.5 * ref["p"]:
        c.append((row.seller_late_90d / ref["p"], f"Người bán trễ {row.seller_late_90d:.0%} trong 90 ngày qua"))
    if row.global_late_7d > 1.3 * ref["p"]:
        c.append((row.global_late_7d / ref["p"], f"Toàn sàn đang trễ {row.global_late_7d:.0%} trong 7 ngày qua"))
    if row.slack_days < ref["slack_p10"]:
        text = (f"Ngày hứa giao chỉ dư {row.slack_days:.0f} ngày so với thời gian giao thường lệ của tuyến"
                if row.slack_days >= 0.5 else
                f"Ngày hứa giao sớm hơn thời gian giao thường lệ của tuyến {abs(row.slack_days):.0f} ngày"
                if row.slack_days <= -0.5 else "Ngày hứa giao sát với thời gian giao thường lệ của tuyến")
        c.append((1 + (ref["slack_p10"] - row.slack_days) / 5, text))
    if row.platform_load_ratio > 1.4:
        c.append((row.platform_load_ratio, f"Lượng đơn toàn sàn gấp {row.platform_load_ratio:.1f} lần bình thường"))
    if row.days_to_black_friday <= 7:
        c.append((2.0, "Đặt hàng trong tuần Black Friday"))
    if row.distance_km > ref["dist_p90"]:
        c.append((row.distance_km / ref["dist_p90"], f"Khoảng cách giao xa ({row.distance_km:,.0f} km)".replace(",", ".")))
    if stage == "handover":
        if row.days_left_at_handover < ref["left_p10"]:
            c.append((1 + (ref["left_p10"] - row.days_left_at_handover) / 3,
                      f"Chỉ còn {row.days_left_at_handover:.0f} ngày tới hạn giao khi bàn giao vận chuyển"))
        if row.handling_vs_seller > 2:
            c.append((1 + row.handling_vs_seller / 3,
                      f"Người bán chuẩn bị hàng chậm hơn thường lệ {row.handling_vs_seller:.0f} ngày"))
    c.sort(key=lambda x: -x[0])
    out = [t for _, t in c[:3]] or ["Nhiều yếu tố rủi ro nhỏ cùng lúc (tuyến, người bán, thời điểm đặt) theo đánh giá của mô hình"]
    return out + [None] * (3 - len(out))


def run_stage(d, stage, cfg, month):
    start = pd.Period(month, "M").start_time
    known = d[(d.purchase_date < start) & (d.estimated_date < start)]
    cal_from = start - pd.Timedelta(days=CAL_DAYS)
    fit_part, cal_part = known[known.estimated_date < cal_from], known[known.estimated_date >= cal_from]
    cols = cfg["cols"]
    # calibration map learned from an ensemble that has not seen the calibration slice; the ensemble
    # score is a mean percentile rank, so the calibration slice is scored as one batch like a month
    cal_eval = cal_part[~(cal_part.days_left_at_handover < 0)]
    m_cal = RankEnsemble(cfg["specs"]).fit(fit_part, fit_part.label)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(m_cal.score_batch(cal_eval), cal_eval.label)
    model = RankEnsemble(cfg["specs"]).fit(known, known.label)

    test = d[d.ym == month].copy()
    if stage == "handover":
        test = test[test.carrier_date.notna()].copy()
    test["certain"] = (test.days_left_at_handover < 0) if stage == "handover" else False
    test["raw_score"] = 1.0
    test.loc[~test.certain, "raw_score"] = model.score_batch(test[~test.certain])
    test["p_late"] = 1.0
    test.loc[~test.certain, "p_late"] = iso.predict(test.loc[~test.certain, "raw_score"])
    test["decision_date"] = test[cfg["time"]].dt.date
    test["risk_rank_pct"] = test.groupby("decision_date").raw_score.rank(ascending=False, pct=True, method="first")
    test["risk_level"] = np.select([test.certain | (test.risk_rank_pct <= RED_PCT), test.risk_rank_pct <= YELLOW_PCT],
                                   ["RED", "YELLOW"], "GREEN")
    ref = {"p": known.label.mean(), "slack_p10": known.slack_days.quantile(0.10),
           "dist_p90": known.distance_km.quantile(0.90),
           "left_p10": known.days_left_at_handover.quantile(0.10) if stage == "handover" else 0}
    rs = [reasons(r, ref, stage) if lvl != "GREEN" else [None] * 3
          for r, lvl in zip(test.itertuples(), test.risk_level)]
    test[["reason_1", "reason_2", "reason_3"]] = pd.DataFrame(rs, index=test.index)
    test.loc[test.certain, "reason_1"] = "Đã quá ngày giao dự kiến khi bàn giao vận chuyển"
    test["recommended_action"] = [CERTAIN_ACTION if cert else ACTIONS.get(lvl)
                                  for cert, lvl in zip(test.certain, test.risk_level)]
    test["stage"] = stage
    version = f"{stage}_{cfg['algo']}_{month}"
    test["model_version"] = version
    ev = test[~test.certain]
    metrics = score(ev.label, ev.raw_score)
    reg = dict(model_version=version, stage=stage, algorithm=cfg["algo"], train_rows=len(known),
               train_until=start.date(), test_month=month, pr_auc=metrics["pr_auc"], roc_auc=metrics["roc_auc"],
               recall_top10=metrics["recall_top10"],
               params=json.dumps({"ensemble": cfg["specs"], "calibration_days": CAL_DAYS}, default=str))
    imp = None
    if month == TEST_MONTHS[-1]:
        sample = ev.sample(min(4000, len(ev)), random_state=1)
        imp = pd.DataFrame({"stage": stage, "feature": cols + CAT,
                            "importance": ensemble_importance(model, sample, cols + CAT)})
    return test, reg, imp


def capacity_curve(scores):
    rows = []
    for stage, g in scores.groupby("stage"):
        total_late = g.label.sum()
        for k in np.arange(0.01, 0.31, 0.01):
            flagged = g.certain | (g.risk_rank_pct <= k)
            rows.append({"stage": stage, "capacity_pct": round(k * 100), "flagged": int(flagged.sum()),
                         "late_caught": int(g.label[flagged].sum()), "recall": g.label[flagged].sum() / total_late,
                         "precision": g.label[flagged].mean()})
    return pd.DataFrame(rows)


def ev_policy(g, late, intervene, effect):
    """Intervene when p * late * effect > intervene. Returns flagged, caught, net benefit, avoided low reviews."""
    threshold = intervene / (late * effect)
    flagged = g.certain | (g.p_late >= threshold)
    caught = g.label[flagged].sum()
    net = caught * late * effect - flagged.sum() * intervene
    return dict(threshold=threshold, flagged=int(flagged.sum()), flagged_pct=flagged.mean(), late_caught=int(caught),
                recall=caught / g.label.sum(), precision=g.label[flagged].mean() if flagged.any() else 0,
                net_benefit_brl=net, low_reviews_avoided=caught * effect * (LOW_REVIEW_LATE - LOW_REVIEW_ON_TIME))


def write_db(scores, registry):
    cols = ["order_id", "stage", "model_version", "decision_date", "p_late", "risk_rank_pct", "risk_level",
            "reason_1", "reason_2", "reason_3", "recommended_action", "label"]
    with psycopg.connect(DSN) as conn:
        conn.execute("TRUNCATE dss.delay_risk_score")
        conn.execute("DELETE FROM dss.model_registry")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO dss.model_registry (model_version, stage, algorithm, train_rows, train_until, params, "
                "test_month, pr_auc, roc_auc, recall_top10) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(r["model_version"], r["stage"], r["algorithm"], r["train_rows"], r["train_until"], r["params"],
                  r["test_month"], round(r["pr_auc"], 4), round(r["roc_auc"], 4), round(r["recall_top10"], 4))
                 for r in registry])
            with cur.copy("COPY dss.delay_risk_score (order_id, stage, model_version, decision_date, p_late, "
                          "risk_rank_pct, risk_level, reason_1, reason_2, reason_3, recommended_action, "
                          "actual_is_late) FROM STDIN") as cp:
                def txt(v):
                    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v
                for r in scores[cols].itertuples(index=False):
                    cp.write_row([r.order_id, r.stage, r.model_version, r.decision_date, round(float(r.p_late), 4),
                                  round(float(r.risk_rank_pct), 4), r.risk_level, txt(r.reason_1), txt(r.reason_2),
                                  txt(r.reason_3), txt(r.recommended_action), int(r.label)])


def main():
    cfg = json.loads((RES / "best_config.json").read_text(encoding="utf-8"))
    specs = cfg.get("final", cfg["ensemble"])
    df = build_features()
    d = df[df.label.notna() & df.purchase_date.between("2017-01-01", "2018-08-31") & df.carrier_date.notna()].copy()
    d["label"] = d.label.astype(int)
    d["ym"] = d.purchase_date.dt.to_period("M").astype(str)

    parts, registry, imps = [], [], []
    for stage, cfg in stage_setup(specs).items():
        for month in TEST_MONTHS:
            t, reg, imp = run_stage(d, stage, cfg, month)
            parts.append(t)
            registry.append(reg)
            if imp is not None:
                imps.append(imp)
            print(f"{stage:<9} {month}: n={len(t)}, late={t.label.sum()}, ROC={reg['roc_auc']:.3f}, "
                  f"recall@10={reg['recall_top10']:.3f}, red={int((t.risk_level == 'RED').sum())}")
    scores = pd.concat(parts)
    write_db(scores, registry)

    keep = ["order_id", "stage", "ym", "decision_date", "p_late", "raw_score", "risk_rank_pct", "risk_level",
            "certain", "label", "reason_1", "reason_2", "reason_3", "route"]
    scores[keep].to_csv(RES / "scores.csv", index=False)
    pd.concat(imps).to_csv(RES / "importance.csv", index=False)
    cap = capacity_curve(scores)
    cap.to_csv(RES / "capacity_curve.csv", index=False)

    g, c = scores, COST
    pol, conf = [], []
    for name, mask in [("Mức ĐỎ (top 5%)", g.risk_level == "RED"), ("ĐỎ + VÀNG (top 15%)", g.risk_level != "GREEN")]:
        caught = g.label[mask].sum()
        pol.append({"policy": name, "flagged": int(mask.sum()), "flagged_pct": mask.mean(),
                    "late_caught": int(caught), "recall": caught / g.label.sum(), "precision": g.label[mask].mean(),
                    "net_benefit_brl": caught * c["late"] * c["effect"] - mask.sum() * c["intervene"],
                    "low_reviews_avoided": caught * c["effect"] * (LOW_REVIEW_LATE - LOW_REVIEW_ON_TIME)})
        tp, fp = int((mask & (g.label == 1)).sum()), int((mask & (g.label == 0)).sum())
        fn, tn = int((~mask & (g.label == 1)).sum()), int((~mask & (g.label == 0)).sum())
        prec, rec = tp / (tp + fp), tp / (tp + fn)
        conf.append({"cut": name, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec,
                     "f1": 2 * prec * rec / (prec + rec), "accuracy": (tp + tn) / len(g)})
    r = ev_policy(g, c["late"], c["intervene"], c["effect"])
    pol.append({"policy": "Chi phí kỳ vọng", **{k: r[k] for k in
                ["flagged", "flagged_pct", "late_caught", "recall", "precision", "net_benefit_brl",
                 "low_reviews_avoided"]}, "threshold": r["threshold"]})
    pd.DataFrame(pol).to_csv(RES / "policy_backtest.csv", index=False)
    pd.DataFrame(conf).to_csv(RES / "confusion.csv", index=False)
    pd.set_option("display.width", 220)
    print(pd.DataFrame(pol).round(3).to_string(index=False))
    print(pd.DataFrame(conf).round(4).to_string(index=False))
    print(cap[cap.capacity_pct.isin([5, 10, 15, 20, 30])].round(3).to_string(index=False))


if __name__ == "__main__":
    main()

"""Export reusable CSV data, manuscript tables, and Figure 1 from archived results."""
from pathlib import Path
import argparse
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def export(study, output):
    run = study / "run_20261025"
    sys.path.insert(0, str(run))
    from common import parse
    metrics = load(study / "assessment/report_metrics.json")
    revision = load(study / "revision_analysis/results/revision_analysis.json")
    episodes = [json.loads(line) for line in (run / "inputs/episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    choices, offers = [], []
    for e in episodes:
        raw = load(run / "results/attempts" / (e["episode_id"] + ".json"))
        status, choice = parse(raw, e)
        selected = e["profiles"].get(choice, {})
        labels = {value: key for key, value in e["display_map"].items()}
        base = {key: e.get(key, "") for key in ("episode_id", "case_id", "pair_id", "module", "split", "repeat", "mandate", "target_seconds")}
        base.update(status=status, physical_choice=choice, displayed_choice=labels.get(choice, choice),
                    fee_usd=selected.get("fee", ""), success_probability=selected.get("success_probability", ""),
                    time_seconds=selected.get("time_seconds", ""), principal_return_usd=selected.get("refund", ""),
                    retention_days=selected.get("retention_days", ""))
        choices.append(base)
        for physical, offer in e["profiles"].items():
            offers.append({"episode_id": e["episode_id"], "physical_offer": physical,
                "displayed_label": labels[physical], "column_position": e["position"].index(physical) + 1,
                "fee_usd": offer["fee"], "success_probability": offer["success_probability"],
                "time_seconds": offer["time_seconds"], "principal_return_usd": offer["refund"],
                "retention_days": offer["retention_days"],
                "expected_expenditure_usd": 1 + float(offer["fee"]) - (1-float(offer["success_probability"]))*float(offer["refund"]),
                "selected": physical == choice})
    assert len(choices) == 1280 and len(offers) == 2560
    write_csv(output / "data/choices.csv", choices)
    write_csv(output / "data/offers.csv", offers)
    predictions = []
    for row in load(run / "analysis/predictions.json"):
        predictions.append({**{k: v for k, v in row.items() if k != "probabilities"},
                            **dict(zip(("probability_alpha", "probability_beta", "probability_decline"), row["probabilities"]))})
    write_csv(output / "data/withheld_predictions.csv", predictions)
    selected = []
    for r in metrics["per_cell"]:
        a = r["mean_selected_attributes"]
        selected.append({"mandate": r["mandate"], "target_seconds": r["target_seconds"], "choices": r["n"],
                         "declines": r["declines"], "fee_cents": a["fee"]*100,
                         "success_percent": a["success_probability"]*100, "time_seconds": a["time_seconds"],
                         "principal_return_cents": a["refund"]*100, "retention_days": a["retention_days"]})
    write_csv(output / "tables/table_3_selected_attributes.csv", selected)
    write_csv(output / "tables/table_4_prediction_overall.csv", [
        {**r, "accuracy_percent": r["correct"] / r["n"] * 100} for r in metrics["prediction_comparison"]])
    write_csv(output / "tables/tables_C1_C2_prediction_by_condition.csv", [
        {"model": r["model"], **cell} for r in metrics["prediction_scores"] for cell in r["by_cell"]])
    write_csv(output / "tables/table_C3_success_switching.csv", [
        {"mandate": r["mandate"], "target_seconds": r["target_seconds"], "category": r["category"],
         "premium_usd": level["premium_usd"], "reference_choices": level["choice_counts"].get("alpha", 0),
         "higher_success_choices": level["choice_counts"].get("beta", 0),
         "decline_choices": level["choice_counts"].get("DECLINE", 0), "unanimous": level["unanimous"]}
        for r in metrics["fine_reliability"] for level in r["levels"]])
    write_csv(output / "tables/table_C4_fee_sensitivity.csv", [
        {k: r[k] for k in ("specification", "mandate", "target_seconds", "penalty", "all_full_fee_slopes_negative", "all_conditional_fee_slopes_negative", "heldout_log_loss", "share_baseline_log_loss", "beats_share_baseline")}
        for r in metrics["fee_gates"]])
    write_csv(output / "tables/table_C6_target_satisfaction.csv", [
        {k: v for k, v in row.items() if k != "entries"} for row in revision["target_satisfaction"]])
    compensation = []
    for boot in revision["compensation_bootstrap"]:
        point = next(r for r in revision["compensation_point_checks"] if r["specification"] == "linear_fee"
                     and r["conditional"] == boot["conditional"] and r["penalty"] == boot["penalty"])
        compensation.append({"fit": "conditional" if boot["conditional"] else "full", "penalty": boot["penalty"],
                             "fee_gradient_per_usd": point["fee_gradients_per_usd"][0],
                             "premium_cents": point["unrestricted_fee_premium_usd"]*100,
                             "interval_low_cents": boot["percentile_95_usd"][0]*100,
                             "interval_high_cents": boot["percentile_95_usd"][1]*100,
                             "interior_resamples": boot["interior"], "finite_resamples": boot["finite"], "draws": boot["draws"]})
    write_csv(output / "tables/table_C7_compensation.csv", compensation)
    write_csv(output / "tables/refund_probes.csv", [
        {**{k: v for k, v in r.items() if k != "choices"}, "choices": "|".join(r["choices"])} for r in metrics["refund_probes"]])
    write_csv(output / "tables/repetition_diagnostics.csv", [
        {**r, "calls_per_set": "|".join(map(str, r["calls_per_set"]))} for r in metrics["repetition"]])
    figure_rows = []
    for kind, key, denominator in (("mandate", "mandate_changes", 192), ("target", "target_changes", 96)):
        for r in metrics[key]:
            rs = r["pair_resampling"]
            figure_rows.append({"comparison": kind, "mandate": r["mandate"], "changes": r["changes"],
                               "paired_choices": denominator, "change_percent": rs["mean"]*100,
                               "interval_low_percent": rs["pair_resampling_95_percentile"][0]*100,
                               "interval_high_percent": rs["pair_resampling_95_percentile"][1]*100})
    write_csv(output / "tables/figure_1_data.csv", figure_rows)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.labelsize": 10,
                         "xtick.labelsize": 9, "ytick.labelsize": 10, "svg.hashsalt": "agent-ce-figure-1"})
    fig, ax = plt.subplots(figsize=(6.5, 3.55))
    positions = [7, 6, 5, 2.5, 1.5, .5, -.5]
    for y, row in zip(positions, figure_rows):
        mean, low, high = (row[k] for k in ("change_percent", "interval_low_percent", "interval_high_percent"))
        color, marker = ("#174A7E", "o") if row["comparison"] == "mandate" else ("#9A4F17", "s")
        ax.errorbar(mean, y, xerr=[[mean-low], [high-mean]], fmt=marker, color=color, markersize=5, capsize=3, elinewidth=1.3)
        ax.text(52, y, f'{mean:.1f}% ({row["changes"]}/{row["paired_choices"]})', va="center", fontsize=9.1, clip_on=False)
    ax.set_yticks(positions, [row["mandate"] for row in figure_rows])
    ax.set_ylim(-1.25, 8.2)
    ax.set_xlim(0, 50)
    ax.set_xticks(range(0, 51, 10))
    ax.set_xlabel("Choices changed (%)", labelpad=6)
    ax.text(0, 8.05, "Mandate change from Balanced", fontsize=10, fontweight="bold", va="center")
    ax.text(0, 3.65, "Completion target from 5 to 60 seconds", fontsize=10, fontweight="bold", va="center")
    ax.grid(axis="x", color="#E3E3E3", linewidth=.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, pad=7)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#8A8A8A")
    fig.subplots_adjust(left=.25, right=.79, top=.97, bottom=.16)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    fig.savefig(figures / "figure_1_choice_changes.png", dpi=350, facecolor="white")
    fig.savefig(figures / "figure_1_choice_changes.svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)
    csv_count = sum(len(list((output / sub).glob("*.csv"))) for sub in ("data", "tables"))
    print(json.dumps({"choices": len(choices), "offers": len(offers), "predictions": len(predictions),
                      "csv_files": csv_count, "figure_formats": ["png", "svg"]}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=ROOT / "study")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    export(args.study.resolve(), args.output.resolve())

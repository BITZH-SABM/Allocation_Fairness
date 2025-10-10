"""
结果可视化脚本
读取 results/simulation_results_*.json，导出CSV并生成折线/分面图
"""
import os
import glob
import json
from typing import Dict, Any, List

import pandas as pd
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns

# 配置中文字体，避免标题显示为空格
matplotlib.rcParams['axes.unicode_minus'] = False

# 动态选择可用的中文字体，若不可用则退化为英文标题
FONT_PROP = None
_CANDIDATE_FONTS = [
    'Microsoft YaHei', 'SimHei', 'SimSun', 'NSimSun', 'FangSong', 'KaiTi',
    'PingFang SC', 'Hiragino Sans GB', 'Source Han Sans CN', 'Noto Sans CJK SC',
    'WenQuanYi Zen Hei', 'Arial Unicode MS'
]
for name in _CANDIDATE_FONTS:
    try:
        prop = fm.FontProperties(family=name)
        path = fm.findfont(prop, fallback_to_default=False)
        if os.path.exists(path):
            FONT_PROP = prop
            break
    except Exception:
        continue

def _title(text_zh: str, fallback_en: str):
    if FONT_PROP is not None:
        plt.title(text_zh, fontproperties=FONT_PROP)
    else:
        plt.title(fallback_en)


def load_latest_results(results_dir: str = "results") -> (Dict[str, Any], str):
    files = sorted(glob.glob(os.path.join(results_dir, "simulation_results_*.json")))
    if not files:
        raise FileNotFoundError("未找到结果文件，请先运行 simulation_runner.py 以生成结果。")
    latest = files[-1]
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data, latest


def export_long_tables(data: Dict[str, Any], out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    dist_results: List[Dict[str, Any]] = data.get("distribution_results", [])
    eval_results: List[Dict[str, Any]] = data.get("evaluation_results", [])
    agents: List[Dict[str, Any]] = data.get("agents", [])
    id2name = {a["id"]: a.get("family_name", str(a["id"])) for a in agents}

    # rounds.csv
    rows_rounds = []
    for r in dist_results:
        rows_rounds.append({
            "round": r.get("round"),
            "method": r.get("method_name", r.get("distribution_method")),
            "total_grain": r.get("resources", {}).get("grain", 0.0),
        })
    df_rounds = pd.DataFrame(rows_rounds)
    rounds_csv = os.path.join(out_dir, "rounds.csv")
    df_rounds.to_csv(rounds_csv, index=False)

    # allocations_long.csv（allocation/effective_input/production 需要从 eval 与 dist 合并）
    rows_alloc = []
    # 构建按轮的 outcome map
    round_to_outcome = {}
    for r, e in zip(dist_results, eval_results):
        round_to_outcome[r.get("round")] = e.get("layered_statistics", {})
    # production（结果层）也可从 dist_results 的 "productions" 读
    for r in dist_results:
        rnd = r.get("round")
        allocation = r.get("distribution", {})
        production = r.get("productions", {})
        # effective_input 只能从 eval 的 layered_statistics 重建
        eff_layer = round_to_outcome.get(rnd, {}).get("effective_input", {})
        for aid_str, res in allocation.items():
            aid = int(aid_str)
            rows_alloc.append({
                "round": rnd,
                "agent_id": aid,
                "family": id2name.get(aid, str(aid)),
                "allocation": float(res.get("grain", 0.0)),
                "effective_input": float(eff_layer.get("total", {}).get("mean", 0.0)),  # 占位：后续细化
                "production": float(production.get(aid, {}).get("grain", 0.0))
            })
    # 注意：effective_input 上面用了 layer 的 total.mean 作为占位，若要每户级有效投入，需在结果中保存 per-agent 的有效投入。
    df_alloc = pd.DataFrame(rows_alloc)
    alloc_csv = os.path.join(out_dir, "allocations_long.csv")
    df_alloc.to_csv(alloc_csv, index=False)

    # satisfaction.csv
    rows_sat = []
    for e in eval_results:
        rnd = e.get("round")
        for ae in e.get("agent_evaluations", []):
            rows_sat.append({
                "round": rnd,
                "agent_id": ae.get("agent_id"),
                "family": ae.get("family_name"),
                "value_type": ae.get("value_type"),
                "score": ae.get("fairness_score")
            })
    df_sat = pd.DataFrame(rows_sat)
    sat_csv = os.path.join(out_dir, "satisfaction.csv")
    df_sat.to_csv(sat_csv, index=False)

    # layered_stats.csv
    rows_layer = []
    for e in eval_results:
        rnd = e.get("round")
        layered = e.get("layered_statistics", {}) or {}
        for layer_name, stats in layered.items():
            if not stats:
                continue
            t = stats.get("total", {})
            rows_layer.append({
                "round": rnd,
                "layer": layer_name,
                "mean": t.get("mean"),
                "variance": t.get("variance"),
                "std_dev": t.get("std_dev"),
                "gini": t.get("gini")
            })
    df_layer = pd.DataFrame(rows_layer)
    layer_csv = os.path.join(out_dir, "layered_stats.csv")
    df_layer.to_csv(layer_csv, index=False)

    return {
        "rounds": rounds_csv,
        "allocations_long": alloc_csv,
        "satisfaction": sat_csv,
        "layered_stats": layer_csv
    }


def plot_figures(csv_paths: Dict[str, str], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    sns.set_style("whitegrid")

    # 图1：每轮总资源
    df_rounds = pd.read_csv(csv_paths["rounds"])
    plt.figure(figsize=(7,4))
    sns.lineplot(data=df_rounds, x="round", y="total_grain")
    _title("每轮总资源", "Total resources per round")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "total_resources.png"))
    plt.close()

    # 图2：满意度（平均）
    df_sat = pd.read_csv(csv_paths["satisfaction"]) if os.path.exists(csv_paths["satisfaction"]) else pd.DataFrame()
    if not df_sat.empty:
        df_sat_mean = df_sat.groupby("round", as_index=False)["score"].mean()
        plt.figure(figsize=(7,4))
        sns.lineplot(data=df_sat_mean, x="round", y="score")
        plt.ylim(0,5)
        _title("每轮平均满意度", "Average satisfaction per round")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "avg_satisfaction.png"))
        plt.close()

    # 图3：三层指标（分面：layer）
    df_layer = pd.read_csv(csv_paths["layered_stats"]) if os.path.exists(csv_paths["layered_stats"]) else pd.DataFrame()
    if not df_layer.empty:
        for metric in ["mean", "variance", "std_dev", "gini"]:
            plt.figure(figsize=(8,5))
            sns.lineplot(data=df_layer, x="round", y=metric, hue="layer")
            _title(f"三层指标: {metric}", f"Layered metrics: {metric}")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"layered_{metric}.png"))
            plt.close()


def main():
    # 读取最新结果文件
    data, file_path = load_latest_results()
    # 基于结果文件名创建专属子目录，如 results/simulation_results_YYYYMMDD_HHMMSS
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_dir = os.path.join(os.path.dirname(file_path), base)
    os.makedirs(out_dir, exist_ok=True)
    # 导出CSV并绘图到同一文件夹
    paths = export_long_tables(data, out_dir=out_dir)
    plot_figures(paths, out_dir=out_dir)
    print(f"图表与CSV已生成到 {out_dir}")


if __name__ == "__main__":
    main()



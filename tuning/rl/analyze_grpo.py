#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "matplotlib",
# ]
# ///
"""
analyze_grpo.py — Parse GRPO training logs and generate progress charts.

Usage:
    uv run tuning/rl/analyze_grpo.py tuning/rl/grpo_training_run1.log          # from raw log file
    uv run tuning/rl/analyze_grpo.py tuning/rl/log_history.json                # from trainer JSON
    uv run tuning/rl/analyze_grpo.py tuning/rl/grpo_training_run1.log --save   # save PNG instead of showing

Download JSON from Modal volume:
    modal volume get grpo-checkpoints log_history.json tuning/rl/log_history.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_raw_log(path: str) -> list[dict]:
    """Parse metric dicts from raw training log output."""
    with open(path) as f:
        content = f.read()

    entries = []
    step = 0
    for match in re.finditer(r"\{'loss'.*?\}", content):
        d = {}
        for kv in re.finditer(r"'([^']+)': '([^']+)'", match.group()):
            try:
                d[kv.group(1)] = float(kv.group(2))
            except ValueError:
                d[kv.group(1)] = kv.group(2)
        step += 1
        d["step"] = step
        entries.append(d)
    return entries


def parse_json_log(path: str) -> list[dict]:
    """Parse trainer.state.log_history JSON."""
    with open(path) as f:
        data = json.load(f)

    # Handle both raw list and trainer_state.json format
    if isinstance(data, dict) and "log_history" in data:
        data = data["log_history"]

    # Filter to only step entries (skip eval entries)
    return [d for d in data if "reward" in d or "loss" in d]


def load_metrics(path: str) -> list[dict]:
    """Auto-detect format and load."""
    if path.endswith(".json"):
        return parse_json_log(path)
    return parse_raw_log(path)


def print_summary(metrics: list[dict]):
    """Print text summary table."""
    if not metrics:
        print("No metrics found!")
        return

    total = len(metrics)
    print(f"\n{'='*70}")
    print(f"GRPO Training Summary — {total} steps")
    print(f"{'='*70}")

    # Segment into ranges
    if total <= 20:
        segments = [(1, total)]
    else:
        seg_size = max(total // 6, 10)
        segments = []
        start = 1
        while start <= total:
            end = min(start + seg_size - 1, total)
            segments.append((start, end))
            start = end + 1

    def avg(lst, key):
        vals = [d.get(key, 0) for d in lst if key in d]
        return sum(vals) / len(vals) if vals else 0

    print(f"\n{'Steps':>12} | {'Format':>8} | {'Accuracy':>8} | {'Hallucin':>8} | {'Reward':>8} | {'Loss':>8}")
    print("-" * 72)
    for s, e in segments:
        sl = metrics[s - 1 : e]
        fmt = avg(sl, "rewards/format_reward_func/mean")
        acc = avg(sl, "rewards/accuracy_reward_func/mean")
        hal = avg(sl, "rewards/hallucination_penalty_func/mean")
        rew = avg(sl, "reward")
        loss = avg(sl, "loss")
        print(f"  {s:>4}-{e:<5} | {fmt:>8.3f} | {acc:>8.3f} | {hal:>8.3f} | {rew:>8.3f} | {loss:>8.4f}")

    # Overall stats
    rewards = [d.get("reward", 0) for d in metrics if "reward" in d]
    fmt_vals = [d.get("rewards/format_reward_func/mean", 0) for d in metrics if "rewards/format_reward_func/mean" in d]
    acc_vals = [d.get("rewards/accuracy_reward_func/mean", 0) for d in metrics if "rewards/accuracy_reward_func/mean" in d]

    print(f"\n{'Key Stats':}")
    print(f"  Overall avg reward:    {sum(rewards)/len(rewards):.3f}")
    print(f"  First 10 avg reward:   {sum(rewards[:10])/min(10,len(rewards)):.3f}")
    print(f"  Last 10 avg reward:    {sum(rewards[-10:])/min(10,len(rewards)):.3f}")
    print(f"  Best step:             {max(rewards):.3f} (step {rewards.index(max(rewards))+1})")
    print(f"  Worst step:            {min(rewards):.3f} (step {rewards.index(min(rewards))+1})")

    if fmt_vals:
        print(f"  Avg format reward:     {sum(fmt_vals)/len(fmt_vals):.3f} / 2.0")
    if acc_vals:
        print(f"  Avg accuracy reward:   {sum(acc_vals)/len(acc_vals):.3f} / 3.0")

    # Step times
    times = [d.get("step_time", 0) for d in metrics if "step_time" in d]
    if times:
        total_time = sum(times)
        print(f"\n  Total time:  {total_time/3600:.1f} hours ({total_time:.0f}s)")
        print(f"  Avg step:    {total_time/len(times):.1f}s")


def plot_charts(metrics: list[dict], save_path: str | None = None):
    """Generate matplotlib charts."""
    import matplotlib.pyplot as plt
    import matplotlib

    if save_path:
        matplotlib.use("Agg")

    steps = [d.get("step", i + 1) for i, d in enumerate(metrics)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("GRPO Training Progress", fontsize=14, fontweight="bold")

    window = max(len(steps) // 30, 5)

    def smooth(values, w):
        if len(values) < w:
            return values
        smoothed = []
        for i in range(len(values)):
            start = max(0, i - w + 1)
            smoothed.append(sum(values[start : i + 1]) / (i - start + 1))
        return smoothed

    # --- Chart 1: Total Reward ---
    ax = axes[0][0]
    rewards = [d.get("reward", 0) for d in metrics]
    ax.plot(steps, rewards, alpha=0.3, color="tab:blue", linewidth=0.8)
    ax.plot(steps, smooth(rewards, window), color="tab:blue", linewidth=2, label=f"Reward (smoothed {window})")
    ax.set_title("Total Reward")
    ax.set_xlabel("Step")
    ax.set_ylabel("Reward")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Chart 2: Reward Components ---
    ax = axes[0][1]
    fmt = [d.get("rewards/format_reward_func/mean", 0) for d in metrics]
    acc = [d.get("rewards/accuracy_reward_func/mean", 0) for d in metrics]
    hal = [d.get("rewards/hallucination_penalty_func/mean", 0) for d in metrics]

    ax.plot(steps, smooth(fmt, window), linewidth=2, label="Format (max 2.0)", color="tab:green")
    ax.plot(steps, smooth(acc, window), linewidth=2, label="Accuracy (max 3.0)", color="tab:orange")
    ax.plot(steps, smooth(hal, window), linewidth=2, label="Hallucination (min -2.0)", color="tab:red")
    ax.set_title("Reward Components")
    ax.set_xlabel("Step")
    ax.set_ylabel("Score")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

    # --- Chart 3: Loss ---
    ax = axes[1][0]
    losses = [d.get("loss", 0) for d in metrics]
    ax.plot(steps, losses, alpha=0.3, color="tab:purple", linewidth=0.8)
    ax.plot(steps, smooth(losses, window), color="tab:purple", linewidth=2, label=f"Loss (smoothed {window})")
    ax.set_title("Training Loss")
    ax.set_xlabel("Step")
    ax.set_ylabel("Loss")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Chart 4: Entropy + Completion Length ---
    ax = axes[1][1]
    entropy = [d.get("entropy", 0) for d in metrics]
    comp_len = [d.get("completions/mean_length", 0) for d in metrics]

    color1 = "tab:cyan"
    ax.plot(steps, smooth(entropy, window), linewidth=2, label="Entropy", color=color1)
    ax.set_ylabel("Entropy", color=color1)
    ax.tick_params(axis="y", labelcolor=color1)

    ax2 = ax.twinx()
    color2 = "tab:brown"
    ax2.plot(steps, smooth(comp_len, window), linewidth=2, label="Completion Length", color=color2, linestyle="--")
    ax2.set_ylabel("Avg Completion Length", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)

    ax.set_title("Entropy & Completion Length")
    ax.set_xlabel("Step")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved to: {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Analyze GRPO training logs")
    parser.add_argument("log_file", help="Path to raw log file or JSON log history")
    parser.add_argument("--save", action="store_true", help="Save chart as PNG instead of displaying")
    parser.add_argument("--no-chart", action="store_true", help="Print summary only, skip charts")
    args = parser.parse_args()

    metrics = load_metrics(args.log_file)
    print(f"Loaded {len(metrics)} steps from {args.log_file}")

    print_summary(metrics)

    if not args.no_chart:
        save_path = None
        if args.save:
            save_path = str(Path(args.log_file).with_suffix(".png"))
        plot_charts(metrics, save_path=save_path)


if __name__ == "__main__":
    main()

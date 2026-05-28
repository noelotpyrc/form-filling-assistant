#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "safetensors",
#     "torch",
#     "tabulate",
#     "packaging",
# ]
# ///
"""
analyze_model.py — Compare LoRA adapters and generate model understanding reports.

Compares two LoRA adapters (e.g. SFT vs GRPO) and produces:
  1. Architecture map: layer types and LoRA targets
  2. Per-layer effective weight change (||B @ A||)
  3. Per-layer drift between adapters (L2, relative change, cosine similarity)
  4. Summary by component type (self_attn vs linear_attn vs MLP)

Usage:
    # Compare SFT adapter against GRPO adapter
    uv run tuning/rl/analyze_model.py \\
        ~/work/models/qwen35-08b-dspy-format-lora \\
        /tmp/grpo_lora/grpo-extractor-lora

    # Single adapter analysis (effective weight norms only)
    uv run tuning/rl/analyze_model.py \\
        ~/work/models/qwen35-08b-dspy-format-lora

    # Save report to file
    uv run tuning/rl/analyze_model.py \\
        ~/work/models/qwen35-08b-dspy-format-lora \\
        /tmp/grpo_lora/grpo-extractor-lora \\
        --save tuning/rl/model_comparison_report.txt

    # JSON output for programmatic use
    uv run tuning/rl/analyze_model.py \\
        ~/work/models/qwen35-08b-dspy-format-lora \\
        /tmp/grpo_lora/grpo-extractor-lora \\
        --json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import torch
from safetensors.torch import load_file
from tabulate import tabulate


# --- Qwen3.5-0.8B architecture map ---
# 24 layers total:
#   - 6 self_attn layers: 3, 7, 11, 15, 19, 23
#   - 18 linear_attn (Gated DeltaNet) layers: all others
#   - 24 MLP blocks (one per layer)
SELF_ATTN_LAYERS = {3, 7, 11, 15, 19, 23}
TOTAL_LAYERS = 24

# LoRA module types and what they control
MODULE_ROLES = {
    "q_proj": "query projection — what to attend to",
    "k_proj": "key projection — what to match against",
    "v_proj": "value projection — what information to extract",
    "o_proj": "output projection — how to combine attention results",
    "gate_proj": "MLP gate — controls information flow",
    "up_proj": "MLP up-projection — expands representation",
    "down_proj": "MLP down-projection — compresses back",
    "in_proj_qkv": "linear_attn QKV input projection",
    "in_proj_z": "linear_attn gate (z) projection",
    "in_proj_b": "linear_attn beta projection",
    "in_proj_a": "linear_attn alpha projection",
}

# Component-level descriptions
COMPONENT_DESCRIPTIONS = {
    "self_attn": (
        "Standard self-attention (6 layers at positions 3,7,11,15,19,23). "
        "Handles complex reasoning, long-range dependencies, and relational "
        "understanding between distant tokens. Most impactful for connecting "
        "user text to field schemas."
    ),
    "linear_attn": (
        "Gated DeltaNet linear attention (18 layers). Efficient local pattern "
        "recognition with O(n) complexity. Handles token-level patterns, "
        "format compliance, and local syntactic structure."
    ),
    "mlp": (
        "Feed-forward networks (24 layers, one per layer). Stores factual "
        "knowledge and learned transformations. Acts as the model's 'memory' "
        "for patterns learned during training."
    ),
}


def parse_lora_keys(tensors: dict[str, torch.Tensor]) -> dict:
    """Parse LoRA tensor keys into structured layer info.

    Returns dict keyed by (layer_idx, component, module) with A and B matrices.
    """
    layers = {}

    for key, tensor in tensors.items():
        # Pattern: base_model.model.model.model.layers.X.COMPONENT.MODULE.lora_{A,B}.weight
        # or:      base_model.model.model.layers.X.COMPONENT.MODULE.lora_{A,B}.weight
        m = re.search(
            r"layers\.(\d+)\.([\w.]+)\.([\w]+)\.lora_([AB])\.weight", key
        )
        if not m:
            continue

        layer_idx = int(m.group(1))
        component_path = m.group(2)
        module = m.group(3)
        ab = m.group(4)

        # Classify component
        if "self_attn" in component_path or "attention" in component_path:
            if layer_idx in SELF_ATTN_LAYERS:
                component = "self_attn"
            else:
                component = "linear_attn"
        elif "mlp" in component_path or "feed_forward" in component_path:
            component = "mlp"
        else:
            component = component_path

        entry_key = (layer_idx, component, module)
        if entry_key not in layers:
            layers[entry_key] = {"layer": layer_idx, "component": component, "module": module}
        layers[entry_key][ab] = tensor

    return layers


def compute_effective_weight(A: torch.Tensor, B: torch.Tensor) -> dict:
    """Compute effective LoRA weight change: ΔW = B @ A."""
    # A: (rank, in_features), B: (out_features, rank)
    dW = B.float() @ A.float()
    norm = torch.norm(dW).item()
    frob = norm  # Frobenius norm
    max_val = torch.max(torch.abs(dW)).item()
    mean_abs = torch.mean(torch.abs(dW)).item()
    return {
        "frobenius_norm": frob,
        "max_abs": max_val,
        "mean_abs": mean_abs,
        "shape": list(dW.shape),
        "rank": A.shape[0],
    }


def compute_drift(
    A1: torch.Tensor, B1: torch.Tensor,
    A2: torch.Tensor, B2: torch.Tensor,
) -> dict:
    """Compute drift between two LoRA adapters at the same position."""
    dW1 = (B1.float() @ A1.float()).flatten()
    dW2 = (B2.float() @ A2.float()).flatten()

    diff = dW2 - dW1
    l2 = torch.norm(diff).item()
    norm1 = torch.norm(dW1).item()
    relative = (l2 / norm1 * 100) if norm1 > 1e-10 else float("inf")
    cosine = torch.nn.functional.cosine_similarity(
        dW1.unsqueeze(0), dW2.unsqueeze(0)
    ).item()

    return {
        "l2_distance": l2,
        "relative_change_pct": relative,
        "cosine_similarity": cosine,
        "base_norm": norm1,
        "new_norm": torch.norm(dW2).item(),
    }


def get_attn_type(layer_idx: int) -> str:
    """Get the attention type for a given layer index."""
    return "self_attn" if layer_idx in SELF_ATTN_LAYERS else "linear_attn"


def build_architecture_map() -> list[dict]:
    """Build Qwen3.5-0.8B architecture map."""
    arch = []
    for i in range(TOTAL_LAYERS):
        attn_type = get_attn_type(i)
        attn_modules = (
            ["q_proj", "k_proj", "v_proj", "o_proj"]
            if attn_type == "self_attn"
            else ["in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "o_proj"]
        )
        arch.append({
            "layer": i,
            "attn_type": attn_type,
            "attn_modules": attn_modules,
            "mlp_modules": ["gate_proj", "up_proj", "down_proj"],
        })
    return arch


def analyze_single(adapter_path: str) -> dict:
    """Analyze a single LoRA adapter."""
    safetensors_path = Path(adapter_path) / "adapter_model.safetensors"
    if not safetensors_path.exists():
        raise FileNotFoundError(f"No adapter_model.safetensors in {adapter_path}")

    config_path = Path(adapter_path) / "adapter_config.json"
    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    tensors = load_file(str(safetensors_path))
    layers = parse_lora_keys(tensors)

    results = []
    for key, info in sorted(layers.items()):
        if "A" in info and "B" in info:
            ew = compute_effective_weight(info["A"], info["B"])
            results.append({
                "layer": info["layer"],
                "component": info["component"],
                "module": info["module"],
                "attn_type": get_attn_type(info["layer"]),
                **ew,
            })

    return {
        "adapter_path": str(adapter_path),
        "config": {
            "rank": config.get("r"),
            "lora_alpha": config.get("lora_alpha"),
            "base_model": config.get("base_model_name_or_path"),
            "peft_type": config.get("peft_type"),
        },
        "num_lora_pairs": len(results),
        "num_params": sum(t.numel() for t in tensors.values()),
        "layers": results,
    }


def analyze_comparison(adapter1_path: str, adapter2_path: str) -> dict:
    """Compare two LoRA adapters."""
    t1 = load_file(str(Path(adapter1_path) / "adapter_model.safetensors"))
    t2 = load_file(str(Path(adapter2_path) / "adapter_model.safetensors"))

    layers1 = parse_lora_keys(t1)
    layers2 = parse_lora_keys(t2)

    # Find common keys
    common = set(layers1.keys()) & set(layers2.keys())

    results = []
    for key in sorted(common):
        info1, info2 = layers1[key], layers2[key]
        if "A" in info1 and "B" in info1 and "A" in info2 and "B" in info2:
            ew1 = compute_effective_weight(info1["A"], info1["B"])
            ew2 = compute_effective_weight(info2["A"], info2["B"])
            drift = compute_drift(info1["A"], info1["B"], info2["A"], info2["B"])
            results.append({
                "layer": info1["layer"],
                "component": info1["component"],
                "module": info1["module"],
                "attn_type": get_attn_type(info1["layer"]),
                "adapter1_norm": ew1["frobenius_norm"],
                "adapter2_norm": ew2["frobenius_norm"],
                **drift,
            })

    only_in_1 = set(layers1.keys()) - set(layers2.keys())
    only_in_2 = set(layers2.keys()) - set(layers1.keys())

    return {
        "adapter1_path": str(adapter1_path),
        "adapter2_path": str(adapter2_path),
        "common_pairs": len(results),
        "only_in_adapter1": len(only_in_1),
        "only_in_adapter2": len(only_in_2),
        "layers": results,
    }


def summarize_by_component(layers: list[dict], mode: str = "single") -> dict:
    """Aggregate stats by component type."""
    groups = defaultdict(list)
    for entry in layers:
        groups[entry["component"]].append(entry)

    summary = {}
    for comp, entries in sorted(groups.items()):
        if mode == "single":
            norms = [e["frobenius_norm"] for e in entries]
            summary[comp] = {
                "count": len(entries),
                "avg_norm": sum(norms) / len(norms),
                "max_norm": max(norms),
                "min_norm": min(norms),
                "total_norm": sum(norms),
                "description": COMPONENT_DESCRIPTIONS.get(comp, ""),
            }
        else:  # comparison
            rel = [e["relative_change_pct"] for e in entries]
            cos = [e["cosine_similarity"] for e in entries]
            l2 = [e["l2_distance"] for e in entries]
            summary[comp] = {
                "count": len(entries),
                "avg_relative_change_pct": sum(rel) / len(rel),
                "max_relative_change_pct": max(rel),
                "avg_cosine_similarity": sum(cos) / len(cos),
                "min_cosine_similarity": min(cos),
                "avg_l2_distance": sum(l2) / len(l2),
                "description": COMPONENT_DESCRIPTIONS.get(comp, ""),
            }

    return summary


def summarize_by_layer(layers: list[dict], mode: str = "single") -> list[dict]:
    """Aggregate stats by layer index."""
    by_layer = defaultdict(list)
    for entry in layers:
        by_layer[entry["layer"]].append(entry)

    result = []
    for layer_idx in sorted(by_layer.keys()):
        entries = by_layer[layer_idx]
        attn_type = get_attn_type(layer_idx)

        if mode == "single":
            norms = [e["frobenius_norm"] for e in entries]
            result.append({
                "layer": layer_idx,
                "attn_type": attn_type,
                "num_modules": len(entries),
                "total_norm": sum(norms),
                "avg_norm": sum(norms) / len(norms),
                "max_norm": max(norms),
            })
        else:
            rel = [e["relative_change_pct"] for e in entries]
            cos = [e["cosine_similarity"] for e in entries]
            result.append({
                "layer": layer_idx,
                "attn_type": attn_type,
                "num_modules": len(entries),
                "avg_relative_change_pct": sum(rel) / len(rel),
                "max_relative_change_pct": max(rel),
                "avg_cosine_similarity": sum(cos) / len(cos),
                "min_cosine_similarity": min(cos),
            })

    return result


# --- Report formatting ---

def format_single_report(analysis: dict) -> str:
    """Format a single-adapter analysis as a text report."""
    lines = []
    lines.append("=" * 80)
    lines.append("LoRA ADAPTER ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append(f"Adapter:    {analysis['adapter_path']}")
    cfg = analysis["config"]
    lines.append(f"Base model: {cfg.get('base_model', 'unknown')}")
    lines.append(f"LoRA rank:  {cfg.get('rank', '?')}  alpha: {cfg.get('lora_alpha', '?')}")
    lines.append(f"LoRA pairs: {analysis['num_lora_pairs']}  params: {analysis['num_params']:,}")
    lines.append("")

    # Architecture map
    lines.append("─" * 80)
    lines.append("ARCHITECTURE MAP (Qwen3.5-0.8B)")
    lines.append("─" * 80)
    arch = build_architecture_map()
    arch_table = []
    for layer in arch:
        marker = "★" if layer["attn_type"] == "self_attn" else " "
        arch_table.append([
            f"{marker} {layer['layer']:2d}",
            layer["attn_type"],
            ", ".join(layer["attn_modules"]),
            ", ".join(layer["mlp_modules"]),
        ])
    lines.append(tabulate(
        arch_table,
        headers=["Layer", "Attn Type", "Attn Modules", "MLP Modules"],
        tablefmt="simple",
    ))
    lines.append("  ★ = standard self-attention layer (6 of 24)")
    lines.append("")

    # Per-layer summary
    lines.append("─" * 80)
    lines.append("PER-LAYER EFFECTIVE WEIGHT CHANGE  ||ΔW|| = ||B @ A||")
    lines.append("─" * 80)
    layer_summary = summarize_by_layer(analysis["layers"], mode="single")
    layer_table = []
    for ls in layer_summary:
        bar = "█" * int(ls["total_norm"] / max(l["total_norm"] for l in layer_summary) * 30)
        layer_table.append([
            f"{ls['layer']:2d}",
            ls["attn_type"],
            ls["num_modules"],
            f"{ls['total_norm']:.4f}",
            f"{ls['avg_norm']:.4f}",
            f"{ls['max_norm']:.4f}",
            bar,
        ])
    lines.append(tabulate(
        layer_table,
        headers=["Layer", "Type", "#Mod", "Total ||ΔW||", "Avg ||ΔW||", "Max ||ΔW||", "Relative"],
        tablefmt="simple",
    ))
    lines.append("")

    # Component summary
    lines.append("─" * 80)
    lines.append("SUMMARY BY COMPONENT TYPE")
    lines.append("─" * 80)
    comp_summary = summarize_by_component(analysis["layers"], mode="single")
    for comp, stats in comp_summary.items():
        lines.append(f"\n  {comp.upper()} ({stats['count']} modules)")
        lines.append(f"  {stats['description']}")
        lines.append(f"    Avg ||ΔW||:   {stats['avg_norm']:.6f}")
        lines.append(f"    Max ||ΔW||:   {stats['max_norm']:.6f}")
        lines.append(f"    Total ||ΔW||: {stats['total_norm']:.6f}")
    lines.append("")

    # Top changed modules
    lines.append("─" * 80)
    lines.append("TOP 15 MOST CHANGED MODULES")
    lines.append("─" * 80)
    top = sorted(analysis["layers"], key=lambda x: x["frobenius_norm"], reverse=True)[:15]
    top_table = []
    for t in top:
        top_table.append([
            f"layer.{t['layer']}.{t['component']}.{t['module']}",
            t["attn_type"],
            f"{t['frobenius_norm']:.6f}",
            f"{t['mean_abs']:.8f}",
        ])
    lines.append(tabulate(
        top_table,
        headers=["Module Path", "Attn Type", "||ΔW||", "Mean |ΔW|"],
        tablefmt="simple",
    ))
    lines.append("")

    return "\n".join(lines)


def format_comparison_report(comparison: dict) -> str:
    """Format a two-adapter comparison as a text report."""
    lines = []
    lines.append("=" * 90)
    lines.append("LoRA ADAPTER COMPARISON REPORT")
    lines.append("=" * 90)
    lines.append(f"Adapter 1 (base): {comparison['adapter1_path']}")
    lines.append(f"Adapter 2 (new):  {comparison['adapter2_path']}")
    lines.append(f"Common pairs: {comparison['common_pairs']}")
    if comparison["only_in_adapter1"]:
        lines.append(f"Only in adapter 1: {comparison['only_in_adapter1']}")
    if comparison["only_in_adapter2"]:
        lines.append(f"Only in adapter 2: {comparison['only_in_adapter2']}")
    lines.append("")

    # Per-layer drift
    lines.append("─" * 90)
    lines.append("PER-LAYER DRIFT (adapter1 → adapter2)")
    lines.append("─" * 90)
    layer_summary = summarize_by_layer(comparison["layers"], mode="comparison")
    layer_table = []
    max_rel = max(l["avg_relative_change_pct"] for l in layer_summary) if layer_summary else 1
    for ls in layer_summary:
        bar_len = int(ls["avg_relative_change_pct"] / max_rel * 30) if max_rel > 0 else 0
        bar = "█" * bar_len
        layer_table.append([
            f"{ls['layer']:2d}",
            ls["attn_type"],
            ls["num_modules"],
            f"{ls['avg_relative_change_pct']:.3f}%",
            f"{ls['max_relative_change_pct']:.3f}%",
            f"{ls['avg_cosine_similarity']:.6f}",
            bar,
        ])
    lines.append(tabulate(
        layer_table,
        headers=["Layer", "Type", "#Mod", "Avg Drift%", "Max Drift%", "Avg CosSim", "Relative"],
        tablefmt="simple",
    ))
    lines.append("")

    # Component summary
    lines.append("─" * 90)
    lines.append("DRIFT BY COMPONENT TYPE")
    lines.append("─" * 90)
    comp_summary = summarize_by_component(comparison["layers"], mode="comparison")
    for comp, stats in comp_summary.items():
        lines.append(f"\n  {comp.upper()} ({stats['count']} modules)")
        lines.append(f"  {COMPONENT_DESCRIPTIONS.get(comp, '')}")
        lines.append(f"    Avg relative change: {stats['avg_relative_change_pct']:.4f}%")
        lines.append(f"    Max relative change: {stats['max_relative_change_pct']:.4f}%")
        lines.append(f"    Avg cosine sim:      {stats['avg_cosine_similarity']:.6f}")
        lines.append(f"    Min cosine sim:      {stats['min_cosine_similarity']:.6f}")
    lines.append("")

    # Top 15 most drifted
    lines.append("─" * 90)
    lines.append("TOP 15 MOST DRIFTED MODULES")
    lines.append("─" * 90)
    top = sorted(comparison["layers"], key=lambda x: x["relative_change_pct"], reverse=True)[:15]
    top_table = []
    for t in top:
        top_table.append([
            f"layer.{t['layer']}.{t['component']}.{t['module']}",
            t["attn_type"],
            f"{t['relative_change_pct']:.4f}%",
            f"{t['cosine_similarity']:.6f}",
            f"{t['l2_distance']:.6f}",
        ])
    lines.append(tabulate(
        top_table,
        headers=["Module Path", "Attn Type", "Rel Change%", "Cosine Sim", "L2 Dist"],
        tablefmt="simple",
    ))
    lines.append("")

    # Bottom 15 least drifted
    lines.append("─" * 90)
    lines.append("TOP 15 LEAST DRIFTED MODULES")
    lines.append("─" * 90)
    bottom = sorted(comparison["layers"], key=lambda x: x["relative_change_pct"])[:15]
    bottom_table = []
    for t in bottom:
        bottom_table.append([
            f"layer.{t['layer']}.{t['component']}.{t['module']}",
            t["attn_type"],
            f"{t['relative_change_pct']:.4f}%",
            f"{t['cosine_similarity']:.6f}",
        ])
    lines.append(tabulate(
        bottom_table,
        headers=["Module Path", "Attn Type", "Rel Change%", "Cosine Sim"],
        tablefmt="simple",
    ))
    lines.append("")

    # Interpretation
    lines.append("─" * 90)
    lines.append("INTERPRETATION")
    lines.append("─" * 90)
    if comp_summary:
        most_changed = max(comp_summary.items(), key=lambda x: x[1]["avg_relative_change_pct"])
        least_changed = min(comp_summary.items(), key=lambda x: x[1]["avg_relative_change_pct"])
        lines.append(f"  Most changed component:  {most_changed[0]} (avg {most_changed[1]['avg_relative_change_pct']:.4f}%)")
        lines.append(f"  Least changed component: {least_changed[0]} (avg {least_changed[1]['avg_relative_change_pct']:.4f}%)")

        avg_all = sum(e["relative_change_pct"] for e in comparison["layers"]) / len(comparison["layers"])
        avg_cos = sum(e["cosine_similarity"] for e in comparison["layers"]) / len(comparison["layers"])
        lines.append(f"  Overall avg drift:       {avg_all:.4f}%")
        lines.append(f"  Overall avg cosine sim:  {avg_cos:.6f}")

        if avg_all < 0.1:
            lines.append("  → Very small changes — early training or conservative learning rate")
        elif avg_all < 1.0:
            lines.append("  → Moderate changes — healthy RL fine-tuning range")
        elif avg_all < 5.0:
            lines.append("  → Significant changes — substantial policy shift")
        else:
            lines.append("  → Large changes — check for training instability")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and compare LoRA adapters with architecture-aware reports"
    )
    parser.add_argument(
        "adapter1",
        help="Path to first LoRA adapter directory (e.g. SFT adapter)",
    )
    parser.add_argument(
        "adapter2",
        nargs="?",
        help="Path to second LoRA adapter directory (e.g. GRPO adapter). If omitted, single-adapter analysis.",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="Save report to file instead of printing",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON data instead of formatted report",
    )
    args = parser.parse_args()

    if args.adapter2:
        # Comparison mode
        print(f"Comparing adapters...")
        print(f"  Adapter 1: {args.adapter1}")
        print(f"  Adapter 2: {args.adapter2}")

        comparison = analyze_comparison(args.adapter1, args.adapter2)

        if args.json:
            # Convert non-serializable types
            output = json.dumps(comparison, indent=2, default=str)
            if args.save:
                Path(args.save).write_text(output)
                print(f"JSON saved to: {args.save}")
            else:
                print(output)
        else:
            # Also run single analysis on both for context
            a1 = analyze_single(args.adapter1)
            report = format_single_report(a1)
            report += "\n\n"
            report += format_comparison_report(comparison)

            if args.save:
                Path(args.save).write_text(report)
                print(f"Report saved to: {args.save}")
            else:
                print(report)
    else:
        # Single adapter mode
        print(f"Analyzing adapter: {args.adapter1}")
        analysis = analyze_single(args.adapter1)

        if args.json:
            output = json.dumps(analysis, indent=2, default=str)
            if args.save:
                Path(args.save).write_text(output)
                print(f"JSON saved to: {args.save}")
            else:
                print(output)
        else:
            report = format_single_report(analysis)
            if args.save:
                Path(args.save).write_text(report)
                print(f"Report saved to: {args.save}")
            else:
                print(report)


if __name__ == "__main__":
    main()

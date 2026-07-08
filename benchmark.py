"""
benchmark.py
Runs a fixed battery of prompts against qwen3:8b, times each one, and
writes a Markdown report (benchmark_report.md) summarizing latency and
token throughput. Useful as evidence/appendix in a project writeup.

Usage:
    python benchmark.py
"""

import statistics
import datetime

from qwen_client import chat, is_ollama_running, is_model_pulled, MODEL_NAME

TASKS = [
    ("Arithmetic reasoning",
     "What is 17 * 24 - 138 / 6? Show your work.", True),
    ("Logic puzzle",
     "If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops "
     "definitely Lazzies? Explain.", True),
    ("Code generation",
     "Write a Python one-liner to reverse a linked list iteratively (with a short explanation).", False),
    ("Summarization",
     "Summarize in one sentence: The Ottoman Empire was a transcontinental empire "
     "that controlled much of Southeast Europe, West Asia, and North Africa between "
     "the 14th and early 20th centuries.", False),
    ("Translation",
     "Translate 'Actions speak louder than words' into French and Japanese.", False),
    ("Creative writing",
     "Write a 3-line haiku about autumn leaves.", False),
]


def run_benchmark():
    if not is_ollama_running():
        print("❌ Ollama server not reachable. Start it with `ollama serve`.")
        return
    if not is_model_pulled(MODEL_NAME):
        print(f"❌ Model not found. Run `ollama pull {MODEL_NAME}` first.")
        return

    rows = []
    for name, prompt, think in TASKS:
        print(f"Running: {name} (thinking={think}) ...")
        result = chat([{"role": "user", "content": prompt}], think=think, temperature=0.3)
        tok_s = None
        if result.completion_tokens and result.elapsed_s > 0:
            tok_s = result.completion_tokens / result.elapsed_s
        rows.append({
            "task": name,
            "elapsed_s": round(result.elapsed_s, 2),
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "tokens_per_sec": round(tok_s, 1) if tok_s else None,
            "answer_preview": result.answer.strip().replace("\n", " ")[:160],
        })

    times = [r["elapsed_s"] for r in rows]
    write_report(rows, times)
    print("\n✅ Report written to benchmark_report.md")


def write_report(rows, times):
    lines = []
    lines.append(f"# Qwen3:8B Benchmark Report")
    lines.append(f"\nGenerated: {datetime.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"\nModel: `{MODEL_NAME}` served locally via Ollama\n")

    lines.append("| Task | Time (s) | Prompt tok | Completion tok | Tok/s | Answer preview |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['task']} | {r['elapsed_s']} | {r['prompt_tokens']} | "
            f"{r['completion_tokens']} | {r['tokens_per_sec']} | {r['answer_preview']}... |"
        )

    lines.append("\n## Summary")
    lines.append(f"- Average latency: **{statistics.mean(times):.2f}s**")
    lines.append(f"- Fastest task: **{min(times):.2f}s**")
    lines.append(f"- Slowest task: **{max(times):.2f}s**")

    with open("benchmark_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_benchmark()

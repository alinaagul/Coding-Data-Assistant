"""
cli_demo.py
Terminal walkthrough of Qwen3:8B's capabilities — no browser needed.

Usage:
    python cli_demo.py            # run all demos
    python cli_demo.py --only code,translation
"""

import argparse
import json
import sys
import textwrap

from qwen_client import chat, json_extract, is_ollama_running, is_model_pulled, MODEL_NAME


def banner(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def show(result):
    if result.thinking:
        print("\n--- thinking ---")
        print(textwrap.indent(result.thinking.strip(), "  "))
        print("--- end thinking ---\n")
    print(result.answer.strip())
    print(f"\n[{result.elapsed_s:.1f}s | prompt_tokens={result.prompt_tokens} "
          f"completion_tokens={result.completion_tokens}]")


def demo_chat():
    banner("1. General chat")
    result = chat([{"role": "user", "content": "In two sentences, what makes Qwen3 different from Qwen2.5?"}],
                   think=False, temperature=0.5)
    show(result)


def demo_reasoning():
    banner("2. Step-by-step reasoning")
    q = ("Three friends split a restaurant bill of $87.50 evenly, then one of them "
         "pays an extra $12 tip on top of their share. How much did that friend pay in total?")
    result = chat([{"role": "user", "content": q}], think=True, temperature=0.2)
    show(result)


def demo_code():
    banner("3. Code generation")
    prompt = "Write a Python function `is_prime(n)` with docstring, type hints, and 3 doctest examples."
    result = chat([{"role": "user", "content": prompt}], think=False, temperature=0.3)
    show(result)


def demo_translation():
    banner("4. Translation (English -> Urdu)")
    prompt = "Translate to Urdu: 'Knowledge shared is knowledge multiplied.'"
    result = chat([{"role": "user", "content": prompt}], think=False, temperature=0.3)
    show(result)


def demo_summarize():
    banner("5. Summarization")
    text = (
        "Large language models are trained on vast text corpora and learn statistical "
        "patterns of language, which lets them generate coherent text, answer questions, "
        "translate languages, and write code. Recent open-weight models like Qwen3 add "
        "a 'thinking' mode where the model can reason step by step before answering, "
        "improving performance on math and logic tasks, while also supporting a fast "
        "'non-thinking' mode for latency-sensitive chat use cases."
    )
    prompt = f"Summarize in one sentence:\n\n{text}"
    result = chat([{"role": "user", "content": prompt}], think=False, temperature=0.2)
    show(result)


def demo_json():
    banner("6. Structured JSON extraction")
    schema = '{"product": string, "quantity": number, "urgency": "low"|"medium"|"high"}'
    text = "We urgently need 200 units of the model-X sensor shipped by Friday."
    data = json_extract(text, schema)
    print(json.dumps(data, indent=2))


DEMOS = {
    "chat": demo_chat,
    "reasoning": demo_reasoning,
    "code": demo_code,
    "translation": demo_translation,
    "summarize": demo_summarize,
    "json": demo_json,
}


def main():
    parser = argparse.ArgumentParser(description="Qwen3:8B CLI capability demo")
    parser.add_argument("--only", type=str, default=None,
                         help="comma-separated subset of: " + ",".join(DEMOS.keys()))
    args = parser.parse_args()

    if not is_ollama_running():
        print("❌ Ollama server not reachable. Start it with `ollama serve`.")
        sys.exit(1)
    if not is_model_pulled(MODEL_NAME):
        print(f"❌ Model not found. Run `ollama pull {MODEL_NAME}` first.")
        sys.exit(1)

    selected = args.only.split(",") if args.only else list(DEMOS.keys())
    for name in selected:
        if name not in DEMOS:
            print(f"Unknown demo '{name}', skipping.")
            continue
        DEMOS[name]()


if __name__ == "__main__":
    main()

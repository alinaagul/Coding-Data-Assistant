# Qwen3:8B Capability Showcase

A self-contained project that demonstrates the capabilities of **Qwen3 8B**,
running fully locally through **Ollama** — no cloud API keys, no data leaving
your machine.

It ships three ways to explore the model:

| File | What it is |
|---|---|
| `app.py` | Interactive Streamlit web app with 7 demo tabs |
| `cli_demo.py` | Terminal walkthrough of the same capabilities |
| `benchmark.py` | Times a battery of prompts and writes `benchmark_report.md` |

## Capabilities demonstrated

1. **General chat** — multi-turn conversation with streaming responses
2. **Reasoning mode** — Qwen3's `<think>` chain-of-thought, shown in a
   collapsible box, applied to math/logic word problems
3. **Code generation** — writes and explains code in multiple languages
4. **Translation** — multilingual translation with nuance notes
5. **Summarization** — long-form text condensed to bullets/paragraph/brief
6. **Structured JSON extraction** — free text → schema-constrained JSON,
   useful for data pipelines
7. **Function/tool calling** — model decides when to call a defined tool
   (mock weather function) and uses the result to answer

## 1. Prerequisites

- [Ollama](https://ollama.com/download) installed and running
- Python 3.9+
- ~6–8 GB free disk space and RAM/VRAM for the 8B model (quantized)

## 2. Pull the model

```bash
ollama pull qwen3:8b
```

Verify it's available:

```bash
ollama list
```

Ollama should already be running as a background service after install. If
not, start it manually:

```bash
ollama serve
```

## 3. Set up the project

```bash
cd qwen3-8b-showcase
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Run it

**Web app (recommended):**

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

**Terminal demo:**

```bash
python cli_demo.py
# or run a subset:
python cli_demo.py --only code,translation,json
```

**Benchmark report:**

```bash
python benchmark.py
# writes benchmark_report.md with per-task latency and tokens/sec
```

## Project structure

```
qwen3-8b-showcase/
├── app.py                    # Streamlit demo app (7 tabs)
├── cli_demo.py                # Terminal version of the demos
├── benchmark.py                # Latency/throughput benchmark -> markdown report
├── qwen_client.py              # Ollama wrapper: chat, streaming, thinking-tag parsing, JSON mode
├── sample_data/
│   └── sample_article.txt      # Sample text for the summarizer tab
├── requirements.txt
└── README.md
```

## How the "thinking mode" toggle works

Qwen3 can run in two modes:

- **Thinking mode** (`think=True`): the model reasons step by step inside
  `<think>...</think>` tags before producing its final answer. Better for
  math, logic, and multi-step tasks; slower and more verbose.
- **Non-thinking mode** (`think=False`): answers directly. Faster, better
  for simple chat, translation, or formatting-sensitive tasks like JSON
  extraction.

`qwen_client.py` requests this via Ollama's `think` option when available,
and falls back to prefixing the prompt with `/think` / `/no_think` on older
Ollama client versions. The wrapper then splits the raw response into
`thinking` and `answer` so the UI can show the reasoning trace separately
from the final answer.

## Extending the project

Ideas if you want to expand this for a course/portfolio submission:

- Swap the mock `get_weather` tool in the Function Calling tab for a real
  API (e.g. Open-Meteo) to show end-to-end tool use.
- Add a RAG tab: chunk a PDF, embed with a local embedding model
  (e.g. `nomic-embed-text` via Ollama), retrieve top-k chunks, and feed them
  to Qwen3 as context.
- Log every benchmark run's `benchmark_report.md` over time to chart
  performance across hardware or quantization levels (e.g. `qwen3:8b` vs
  `qwen3:8b-q4_K_M`).
- Add a "compare models" tab that runs the same prompt against `qwen3:8b`
  and another locally pulled model side by side.

## Troubleshooting

- **"Ollama server not reachable"** — run `ollama serve` in a terminal and
  keep it open, or check it's running as a system service.
- **"Model not found"** — run `ollama pull qwen3:8b`.
- **Slow responses** — the 8B model needs a decent GPU or Apple Silicon for
  good speed; on CPU-only machines expect much slower generation. Consider
  a quantized tag such as `qwen3:8b-q4_K_M` for lighter hardware.
- **`think` not supported error** — update Ollama: `ollama upgrade` (or
  reinstall the latest version); the wrapper falls back automatically but
  the built-in reasoning toggle works best on recent releases.

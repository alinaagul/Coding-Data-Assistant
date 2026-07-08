"""
Qwen3:8B Capability Showcase — Streamlit App
Run with:  streamlit run app.py

Requires a local Ollama server with `qwen3:8b` pulled:
    ollama pull qwen3:8b
    ollama serve   (usually already running as a background service)
"""

import json
import time

import streamlit as st

from qwen_client import (
    MODEL_NAME,
    chat,
    chat_stream,
    is_ollama_running,
    is_model_pulled,
    json_extract,
)

st.set_page_config(page_title="Qwen3:8B Showcase", page_icon="🧠", layout="wide")

# ---------------------------------------------------------------- sidebar ---
with st.sidebar:
    st.title("🧠 Qwen3:8B Showcase")
    st.caption("Local capability demo, served via Ollama")

    ollama_ok = is_ollama_running()
    model_ok = is_model_pulled(MODEL_NAME) if ollama_ok else False

    st.write("**Ollama server:**", "✅ running" if ollama_ok else "❌ not reachable")
    st.write("**qwen3:8b pulled:**", "✅ yes" if model_ok else "❌ no")

    if not ollama_ok:
        st.error("Start Ollama first: `ollama serve`")
    elif not model_ok:
        st.warning("Run `ollama pull qwen3:8b` in a terminal, then refresh.")

    st.divider()
    think_mode = st.toggle("Enable thinking mode", value=True,
                            help="Qwen3 will expose its chain-of-thought in a collapsible box.")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
    st.divider()
    st.caption("Tabs demonstrate: chat, reasoning, code, translation, "
               "summarization, structured JSON extraction, and tool calling.")

TABS = st.tabs([
    "💬 Chat",
    "🧩 Reasoning",
    "💻 Code Assistant",
    "🌍 Translation",
    "📝 Summarizer",
    "🗂️ JSON Extraction",
    "🛠️ Function Calling",
])


def render_response(result, container):
    if result.thinking:
        with container.expander("🧠 Model's reasoning trace", expanded=False):
            st.markdown(result.thinking)
    container.markdown(result.answer)
    container.caption(
        f"⏱ {result.elapsed_s:.1f}s · prompt_tokens={result.prompt_tokens} "
        f"· completion_tokens={result.completion_tokens}"
    )


# ------------------------------------------------------------------ Chat ---
with TABS[0]:
    st.subheader("General Conversation")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask Qwen3 anything...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_text = ""
            for chunk in chat_stream(
                st.session_state.chat_history, think=think_mode, temperature=temperature
            ):
                full_text += chunk
                placeholder.markdown(full_text)
        st.session_state.chat_history.append({"role": "assistant", "content": full_text})

# ------------------------------------------------------------- Reasoning ---
with TABS[1]:
    st.subheader("Multi-step Reasoning / Math")
    st.caption("Try a logic puzzle or word problem and watch the thinking trace.")
    default_q = (
        "A farmer has 17 sheep. All but 9 die. How many are left? "
        "Then: if the remaining sheep each need 2.5 liters of water per day, "
        "how many liters are needed for a week?"
    )
    reasoning_q = st.text_area("Problem", value=default_q, height=100)
    if st.button("Solve", key="reasoning_btn"):
        with st.spinner("Thinking..."):
            result = chat(
                [{"role": "user", "content": reasoning_q}],
                think=True,
                temperature=0.2,
            )
        render_response(result, st)

# --------------------------------------------------------- Code Assistant --
with TABS[2]:
    st.subheader("Code Generation & Explanation")
    col1, col2 = st.columns(2)
    with col1:
        lang = st.selectbox("Language", ["Python", "JavaScript", "Rust", "SQL", "Go"])
        task = st.text_area(
            "Describe what you want",
            value="Write a function that checks if a string is a valid palindrome, "
                  "ignoring spaces, punctuation, and capitalization. Include tests.",
            height=120,
        )
        gen_btn = st.button("Generate code")
    with col2:
        if gen_btn:
            prompt = f"Write {lang} code for the following task. Include comments.\n\nTask: {task}"
            with st.spinner("Generating..."):
                result = chat([{"role": "user", "content": prompt}],
                               think=think_mode, temperature=temperature)
            render_response(result, st)

# ----------------------------------------------------------- Translation ---
with TABS[3]:
    st.subheader("Multilingual Translation")
    col1, col2 = st.columns(2)
    with col1:
        src_text = st.text_area("Text to translate", value="The early bird catches the worm.")
        target_lang = st.selectbox(
            "Target language",
            ["Urdu", "Arabic", "Mandarin Chinese", "Spanish", "French", "German", "Japanese"],
        )
        translate_btn = st.button("Translate")
    with col2:
        if translate_btn:
            prompt = (
                f"Translate the following text into {target_lang}. "
                f"Then give a brief note on any idiom/nuance lost in translation.\n\n{src_text}"
            )
            with st.spinner("Translating..."):
                result = chat([{"role": "user", "content": prompt}],
                               think=False, temperature=0.3)
            render_response(result, st)

# ------------------------------------------------------------ Summarizer ---
with TABS[4]:
    st.subheader("Long-form Summarization")
    default_doc = ""
    try:
        with open("sample_data/sample_article.txt", "r", encoding="utf-8") as f:
            default_doc = f.read()
    except FileNotFoundError:
        pass

    doc_text = st.text_area("Paste text to summarize", value=default_doc, height=220)
    style = st.radio("Summary style", ["3 bullet points", "one paragraph", "executive brief"], horizontal=True)
    if st.button("Summarize"):
        prompt = f"Summarize the following text as {style}:\n\n{doc_text}"
        with st.spinner("Summarizing..."):
            result = chat([{"role": "user", "content": prompt}], think=False, temperature=0.3)
        render_response(result, st)

# -------------------------------------------------------- JSON Extraction --
with TABS[5]:
    st.subheader("Structured Data Extraction")
    st.caption("Qwen3 extracts structured JSON from free text — useful for pipelines/RAG.")
    schema = st.text_area(
        "JSON schema hint",
        value='{"name": string, "email": string|null, "company": string|null, "intent": string}',
        height=80,
    )
    free_text = st.text_area(
        "Unstructured text",
        value="Hi, this is Ayesha Khan from BrightSoft Ltd. I'm reaching out because "
              "we'd like a quote for 50 licenses. You can reach me at ayesha@brightsoft.example.",
        height=120,
    )
    if st.button("Extract JSON"):
        with st.spinner("Extracting..."):
            try:
                data = json_extract(free_text, schema)
                st.json(data)
            except json.JSONDecodeError as e:
                st.error(f"Model did not return valid JSON: {e}")

# ------------------------------------------------------- Function Calling --
with TABS[6]:
    st.subheader("Tool / Function Calling")
    st.caption("Qwen3 decides when to call a defined tool and with what arguments.")

    def get_weather(city: str) -> dict:
        # Mock tool — swap in a real API call if desired.
        fake_data = {"karachi": 34, "islamabad": 29, "lahore": 31, "london": 18, "new york": 22}
        return {"city": city, "temp_c": fake_data.get(city.lower(), 25)}

    tools_def = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current temperature in Celsius for a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name"}},
                    "required": ["city"],
                },
            },
        }
    ]

    tool_query = st.text_input("Ask something that needs the weather tool",
                                value="What's the weather like in Lahore right now?")
    if st.button("Run with tools"):
        messages = [{"role": "user", "content": tool_query}]
        with st.spinner("Thinking about which tool to use..."):
            result = chat(messages, think=think_mode, temperature=0.2, tools=tools_def)

        if result.tool_calls:
            st.write("**Model requested tool call(s):**")
            for call in result.tool_calls:
                fn = call["function"]["name"]
                args = call["function"]["arguments"]
                st.code(json.dumps({"function": fn, "arguments": args}, indent=2))
                if fn == "get_weather":
                    tool_result = get_weather(**args if isinstance(args, dict) else json.loads(args))
                    st.write("Tool result:", tool_result)

                    followup = messages + [
                        {"role": "assistant", "content": "", "tool_calls": result.tool_calls},
                        {"role": "tool", "content": json.dumps(tool_result)},
                    ]
                    final = chat(followup, think=False, temperature=0.2)
                    st.markdown("**Final answer:**")
                    st.markdown(final.answer)
        else:
            render_response(result, st)

# ⚡ Autonomous-HDL

> An autonomous multi-agent system for end-to-end Verilog/HDL code generation, verification, and simulation — powered by **CrewAI**, **Google Gemini**, **OpenAI GPT**, and a locally-hosted **Verilog-finetuned GGUF model**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-streaming-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-multi--agent-orange)](https://www.crewai.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google)](https://aistudio.google.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT-412991?logo=openai)](https://platform.openai.com/)
[![HuggingFace](https://img.shields.io/badge/🤗%20Model-autonomusHDL-yellow)](https://huggingface.co/Vishvjit2001/autonomusHDL)
[![Iverilog](https://img.shields.io/badge/Simulator-Icarus%20Verilog-red)](http://iverilog.icarus.com/)

---

## 📖 Overview

**Autonomous-HDL** is a fully agentic pipeline that takes a plain-English Verilog design problem and autonomously:

1. 📐 **Plans** the hardware architecture
2. 🧩 **Decomposes** the design into subtasks/modules
3. 💻 **Generates** synthesizable Verilog for each submodule
4. 🔗 **Merges** all submodules into a complete RTL design
5. 🧪 **Writes** a SystemVerilog testbench
6. ✅ **Simulates** the design using Icarus Verilog (`iverilog`)

The system supports **three interchangeable LLM backends** — Google Gemini, OpenAI GPT, and a locally-hosted Verilog-finetuned GGUF model — giving you flexibility between cloud APIs and fully local inference.

All steps stream output in real-time via a FastAPI server with Server-Sent Events (SSE), and include a built-in web UI to monitor and interact with running jobs.

---

## 🏗️ Architecture

```
User Prompt (Natural Language)
        │
        ▼
┌───────────────────┐
│   FastAPI Server  │  ← REST + SSE streaming
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────┐
│              CrewAI Pipeline              │
│                                           │
│  [Planner] → [Subtask Generator]          │
│      → [Verilog Coder × N]                │
│          → [Merger] → [Testbench Writer]  │
│              → [Icarus Verilog Runner]    │
└───────────┬───────────────────────────────┘
            │  LLM calls (choose one or mix)
            ▼
┌─────────────────────────────────────────────────────┐
│                   LLM Backends                      │
│                                                     │
│  ① Google Gemini       (cloud, fast)                │
│  ② OpenAI GPT          (cloud, powerful)            │
│  ③ autonomusHDL GGUF   (local, Verilog-specialized) │
│     Qwen2.5-Coder-14B fine-tuned on HDL datasets    │
└─────────────────────────────────────────────────────┘
         │
         ▼
  Verified Verilog Output + Simulation Logs
```

**Language breakdown:** Python (80.8%) · HTML (18.3%) · SystemVerilog (0.9%)

---

## ✨ Features

- 🤖 **Fully autonomous** — one prompt triggers the entire design pipeline
- 🔀 **Multi-LLM support** — swap between Gemini, GPT, and local GGUF at will
- 🏠 **Local inference option** — run completely offline with the [autonomusHDL GGUF model](https://huggingface.co/Vishvjit2001/autonomusHDL), no API key needed
- 📡 **Real-time streaming** — watch agent outputs live via SSE
- 🔁 **Human-in-the-loop** — pause, review, and accept/reject intermediate outputs
- 🧪 **Auto-verification** — built-in Icarus Verilog simulation
- 🌐 **Web UI** — browser-based interface for managing and monitoring runs
- 🗂️ **Knowledge base** — domain knowledge folder to guide agent reasoning

---

## 🧠 LLM Backends

Autonomous-HDL supports three backends that can be configured per-run or globally via `.env`:

| Backend | Type | Best For | Requires |
|---|---|---|---|
| **Google Gemini** | Cloud API | Fast iteration, large context | `GEMINI_API_KEY` |
| **OpenAI GPT** | Cloud API | High reasoning quality | `OPENAI_API_KEY` |
| **autonomusHDL (GGUF)** | Local (llama.cpp) | Offline use, Verilog-specialized | Downloaded GGUF model |

> 💡 **Tip:** The local **autonomusHDL** model is a Qwen2.5-Coder-14B finetuned specifically on Verilog/HDL datasets, making it highly accurate for RTL code generation without any cloud dependency.

➡️ [Download the model from Hugging Face](https://huggingface.co/Vishvjit2001/autonomusHDL)

---

## 📁 Project Structure

```
Autonomous-HDL/
├── knowledge/              # Domain knowledge fed to agents
├── src/
│   └── vgen/
│       ├── run_api.py      # FastAPI entrypoint
│       ├── crew.py         # CrewAI crew and agent definitions
│       ├── tasks.py        # Task definitions for each pipeline stage
│       └── ...
├── testbench.sv            # Example SystemVerilog testbench
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata (uv-compatible)
├── uv.lock                 # Locked dependency versions
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [Icarus Verilog](http://iverilog.icarus.com/) (`iverilog`)
- At least one of: a Gemini API key, an OpenAI API key, or the downloaded autonomusHDL GGUF model

### 1. Clone the repository

```bash
git clone https://github.com/vishvjit18/Autonomous-HDL.git
cd Autonomous-HDL
```

### 2. Install dependencies

Using `pip`:

```bash
pip install -r requirements.txt
```

Or using [`uv`](https://github.com/astral-sh/uv) (recommended, faster):

```bash
uv sync
```

### 3. Install Icarus Verilog

```bash
# Ubuntu / Debian
sudo apt-get install iverilog

# macOS
brew install icarus-verilog
```

### 4. Configure environment variables

Create a `.env` file in the project root and add the keys for whichever backends you want to use:

```env
# --- Cloud Backends (add one or both) ---
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# --- Local GGUF Backend ---
# Path to your downloaded autonomusHDL GGUF model file
GGUF_MODEL_PATH=/path/to/qwen2.5_coder_14b_instruct_verilog_finetuned_q8.gguf
```

> You only need to set the keys for the backends you intend to use.

### 5. (Optional) Download the local GGUF model

If you want to use the local Verilog-finetuned model:

```bash
# Install huggingface_hub CLI
pip install huggingface_hub

# Download the Q8 model (15.7 GB, highest quality)
huggingface-cli download Vishvjit2001/autonomusHDL \
  qwen2.5_coder_14b_instruct_verilog_finetuned_q8.gguf \
  --local-dir ./models

# Or the Q3_K_L model (7.9 GB, lighter)
huggingface-cli download Vishvjit2001/autonomusHDL \
  "Qwen2.5 coder-14B-Q3_K_L.gguf" \
  --local-dir ./models
```

### 6. Run the server

```bash
python -m vgen.run_api
```

The server will start at **http://localhost:8000**.

---

## 🌐 Web Interface

Open **http://localhost:8000** in your browser to access the built-in web UI. From there you can:

- Submit a new Verilog design problem
- Select your preferred LLM backend (Gemini / GPT / Local GGUF)
- Monitor streaming agent output in real-time
- Accept or override intermediate outputs

---

## 📡 API Reference

### `POST /run` — Start a new run

**Request body:**
```json
{
  "problem": "Design a 4-bit synchronous up-counter with synchronous reset.",
  "run_type": "full"
}
```

**`run_type` options:**

| Value | Description |
|---|---|
| `full` | Complete end-to-end pipeline |
| `planning` | Architecture planning only |
| `subtasks` | Subtask decomposition only |
| `merging` | Merge pre-generated submodules |
| `testbench` | Testbench generation only |
| `iverilog` | Simulate existing Verilog with iverilog |

**Response:**
```json
{
  "run_id": "run_20240512_143022",
  "status": "starting",
  "message": "Run run_20240512_143022 started"
}
```

---

### `GET /run/{run_id}` — Get run status

Returns the current status and output of a specific run.

---

### `GET /run/{run_id}/stream` — Stream run output (SSE)

Streams live agent output as Server-Sent Events.

```javascript
const eventSource = new EventSource(`http://localhost:8000/run/${runId}/stream`);

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

---

### `POST /run/{run_id}/input` — Provide input or accept output

Submit human feedback mid-run, or pass an empty string to accept and continue.

```json
{ "input": "" }
```

---

### `GET /runs` — List all runs

Returns a list of all run IDs with their statuses.

---

## 💻 Python Client Example

```python
import requests

# Start a new run
response = requests.post(
    "http://localhost:8000/run",
    json={
        "problem": "Design a parameterized N-bit shift register with serial in, parallel out.",
        "run_type": "full"
    }
)

run_id = response.json()["run_id"]
print(f"Run started: {run_id}")

# Poll for status
status = requests.get(f"http://localhost:8000/run/{run_id}").json()
print(status)
```

---

## 🔌 Choosing a Backend

| Scenario | Recommended Backend |
|---|---|
| Fast prototyping with internet access | Gemini |
| High-complexity designs needing strong reasoning | OpenAI GPT |
| Offline / air-gapped environments | autonomusHDL GGUF (local) |
| Maximum Verilog-specific accuracy | autonomusHDL GGUF (finetuned) |
| Cost-sensitive production use | Gemini or local GGUF |

---

## 📋 Notes

- Full pipeline runs may take **several minutes** depending on design complexity and backend
- The `knowledge/` folder can be extended with domain-specific Verilog guidelines to improve agent output
- Human-in-the-loop input can be provided at any stage via the `/run/{run_id}/input` endpoint
- All streaming output is chunked in real-time — no waiting for the full result
- The local GGUF model requires sufficient RAM/VRAM (8 GB+ for Q3_K_L, 16 GB+ for Q8)

---

## 🤝 Contributing

Contributions are welcome! To get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push and open a Pull Request

---

## 📜 License

This project is open-source. See [LICENSE](LICENSE) for details.

---

## 👤 Author

**Vishvjit** — [@vishvjit18](https://github.com/vishvjit18)

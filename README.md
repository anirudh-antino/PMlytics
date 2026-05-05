# PMlytics

Local web app that asks natural-language questions about your product or funnel data and turns them into read-only SQL/Mongo plans, charts, and short reports.  

## Run locally

**Prerequisites:** **Python 3.10 or newer**.

From the repository root:

**macOS / Linux** — copy and run:

```bash
python3 -m venv venv
source venv/bin/activate
python3 install_deps.py
python3 app.py
```

**Windows** (Command Prompt):

```bat
python -m venv venv
venv\Scripts\activate.bat
python install_deps.py
python app.py
```

**Windows** (PowerShell) — same steps; use `venv\Scripts\Activate.ps1` instead of `activate.bat` if you prefer. If activation is blocked by policy, open Command Prompt and use the block above:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python install_deps.py
python app.py
```

Then open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** 

## LLM (pick one)

**Recommended (often free tier):** [Google AI Studio](https://aistudio.google.com/) → create a Gemini API key → paste in **Settings** in the app.  
**Alternatives:** OpenAI or Anthropic keys in **Settings** — same flow.

## Database (pick one)

Connect **PostgreSQL**, **MySQL**, or **MongoDB** from the **Connections** screen (connection string or host/port/db/user). Use a read-only user or a staging database if you want extra safety.

## Demo

**Video:** *[placeholder — add link when ready]*
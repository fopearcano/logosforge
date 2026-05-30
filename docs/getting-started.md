# Getting Started

This guide gets Logosforge running and walks you through creating your first
project.

---

## Requirements

- **Python 3.10+** and `pip`
- Optionally, a local or cloud **AI provider** (Logosforge is fully usable without
  one — the AI features simply stay idle)

The only runtime dependencies are PySide6, SQLModel, and certifi (plus a Cocoa
binding on macOS). See `requirements.txt`.

---

## Install & run

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

`run.py` launches the desktop app. On first run it creates a working database
(`storyplanner.db`) in the current directory and a default *"My Story"* project,
and lands you on the **Projects** view.

**Run the tests:**

```bash
python -m pytest tests/
```

---

## Connect an AI provider (optional)

Open **Settings → AI Provider** and choose one of:

- **LM Studio** or **Ollama** — fully local, no API key, nothing leaves your
  machine. Start the local server, point Logosforge at its endpoint (defaults:
  `http://localhost:1234/v1` and `http://localhost:11434/v1`), and pick a model.
- **OpenAI / Anthropic / OpenRouter** — cloud. Enter an API key (or set the
  `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` environment
  variable) and select a model.

Use **Test** to verify the connection. See [configuration.md](configuration.md)
for the full provider reference.

---

## Create your first project

1. From **Projects**, create a new project. In the **New Project** dialog set a
   title, pick a [**Narrative Engine**](narrative-engines.md) (Novel, Screenplay,
   Graphic Novel, Stage Script, or Series), and accept or change the suggested
   [**Writing Format**](writing-formats.md).
2. Open **Manuscript** and start writing. Press **Ctrl+Shift+F** for distraction-
   free **focus mode**; type **`/`** at the start of a line for the command palette.
3. Build the world in **PSYKE** (the Story Bible): add characters, places, objects,
   themes, and lore. Names you use in the manuscript become clickable and hover-
   previewed, and the [Auto-Link](auto_link.md) banner will suggest new entries as
   you write.
4. Shape the structure with the **Outline**, **Plot**, **Timeline**, and **Graph**
   views — all of which adapt to your engine.
5. When you want feedback or generation, open the **Assistant** (or **Chat**). It
   reasons from your outline, Story Bible, notes, and graph, and never changes your
   text without you clicking **Apply / Replace / Insert**.

---

## Where your work lives

Your working data is the local SQLite database; **Save / Save As** writes a
portable `*.json` project file you can back up, sync, or version-control.
Logosforge auto-saves atomically, keeps timestamped version snapshots, and is safe
to store in a cloud-synced folder. See [data-model.md](data-model.md).

---

## Next steps

- [User Guide](user-guide.md) — a tour of every view and menu.
- [Narrative Engines](narrative-engines.md) and [Writing Formats](writing-formats.md)
  — the two core axes.
- [AI Assistant](ai-assistant.md), [PSYKE](psyke.md), and
  [QUANTUM Outliner](quantum-outliner.md) — the headline features.
- The full [documentation index](README.md).

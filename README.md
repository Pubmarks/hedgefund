# Agentic Hedgefund

**Inspired from [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/pdf/2412.20138)**

Agentic processes can run a trading firm as a coordinated multi-agent pipeline: specialized LLM analysts (fundamental, sentiment, news, technical) gather and report on market signals in parallel; bull and bear researchers debate those findings to surface a balanced view; a trader synthesizes the debate into buy/sell decisions with sizing and timing; a risk team challenges the plan from aggressive, neutral, and conservative angles; and a fund manager approves the final trade—using structured reports for reliable handoffs and short natural-language debates where deeper reasoning is needed, so the whole loop stays explainable and closer to how real desks collaborate.

## Fork and Play

Fork this repo, open the **Actions** tab, and run **Ticker research**. Enter a stock ticker (e.g. `AAPL`) and start the workflow. GitHub Actions runs the full multi-agent pipeline in the cloud, posts the final report to the job summary, and uploads the research files as artifacts, downloadable as .zip. No local install, Docker, or API wiring required: defaults use free OpenCode models, so you can fork and run from the browser alone.

### Customise (Optional)

For more control, open your fork’s **Settings → Secrets and variables → Actions**.

**Secrets** (sensitive keys):

| Name | Purpose |
| --- | --- |
| `OPENCODE_API_KEY` | Auth for OpenCode; optional with the free `opencode/big-pickle` default, required for paid providers |
| `FRED_API_KEY` | Macro data from FRED; set this for fuller news/macro analyst reports |

**Variables** (non-secret model config, OpenCode `provider/model` format):

| Name | Role | Default |
| --- | --- | --- |
| `HEDGEFUND_QUICK_MODEL` | Fast / lighter reasoning | `opencode/big-pickle` |
| `HEDGEFUND_DEEP_MODEL` | Deeper analysis | `opencode/big-pickle` |
| `HEDGEFUND_EPIC_MODEL` | Highest-stakes reasoning | `opencode/big-pickle` |

After saving, re-run **Ticker research**. The workflow injects these into the container automatically—no code or image changes needed.

## Advanced

### Run locally

You need [uv](https://docs.astral.sh/uv/) and Python ≥ 3.11. OpenCode runs via the SDK in subprocess mode by default (`opencode acp`)—no separate server required.

```bash
git clone https://github.com/<you>/hedgefund.git
cd hedgefund
cp .env.example .env   # fill OPENCODE_API_KEY / FRED_API_KEY as needed
uv sync --frozen
uv run --frozen python main.py AAPL
```

Useful flags:

```bash
uv run --frozen python main.py AAPL -d 2024-06-01          # trade date
uv run --frozen python main.py AAPL -o summary.md          # custom output path
uv run --frozen python main.py AAPL --debate-rounds 2      # bull/bear rounds
uv run --frozen python main.py AAPL --risk-rounds 2        # risk discussion rounds
```

The report lands at `out/<TICKER>/final-report.md` (plus per-agent markdown under that folder). Model tiers and keys use the same env vars as Actions (`HEDGEFUND_*_MODEL`, `OPENCODE_API_KEY`, `FRED_API_KEY`); set them in `.env` or your shell. Leave `OPENCODE_SERVER_URL` unset unless you want an external `opencode serve`.

### Develop further

Layout:

| Path | Role |
| --- | --- |
| `main.py` | CLI entrypoint |
| `pipeline.py` | Orchestrates the four phases and stitches `final-report.md` |
| `phases/` | Phase runners (reports → debate → trader → risk) |
| `agents/` | Role prompts and agent logic (analysts, researchers, trader, risk, managers) |
| `config.py` | Defaults and env-driven model/path settings |
| `agent.py` | OpenCode session helpers |
| `opencode.json` | OpenCode agent permissions and default model |
| `memory/` | Memory log / reflection used across runs |

Typical loop: edit an agent prompt or phase under `agents/` / `phases/`, re-run `uv run --frozen python main.py <TICKER>`, inspect intermediate files under `out/<TICKER>/`. Bump debate or risk rounds from the CLI while iterating. When you change dependencies, update `pyproject.toml` and refresh the lock with `uv lock`, then `uv sync --frozen`. To ship a container for Actions, push to `main` (or run **Publish image**) so GHCR gets a new `latest` tag for **Ticker research**.

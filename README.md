# Pricer

AI-driven multi-agent deal analyzer for Indian ecommerce, with dynamic price
estimation and autonomous deal intelligence.

Pricer scans deal feeds, extracts product information, estimates a fair price
using several models, calculates the potential discount, stores deal history,
and displays results in a Gradio dashboard.

## Features

- Automated scanning of Indian ecommerce deal sources
- RSS feed parsing and product-detail extraction
- AI-powered INR price prediction
- Local Llama inference through Ollama
- Remote fine-tuned Llama inference through Modal
- Random Forest price estimation from product embeddings
- Ensemble model combining independent price estimates
- Historical deal memory
- Optional Pushover notifications
- Optional Twilio SMS notifications
- Gradio dashboard with logs, deal tables, and vector visualization

## Deal sources

The scanner currently uses feeds from:

- DesiDime
- Amazon India
- Flipkart
- Reliance Digital
- Tata Cliq
- Croma
- Ajio
- Myntra
- Nykaa
- Reddit India deal communities

Feed definitions and scraping logic are in
[deals.py](app/agents/deals.py).

## Architecture

```text
Gradio dashboard
        |
        v
DealAgentFramework
        |
        v
PlanningAgent
   |         |          |
   v         v          v
Scanner   Ensemble   Messaging
Agent     Agent      Agent
             |
       +-----+------+
       |            |
       v            v
  Specialist     Frontier
  Agent          Agent
  (Modal)        (Ollama)
       |
       v
  Random Forest
  Agent
```

### Scanner Agent

Fetches RSS entries, scrapes product pages, cleans descriptions, extracts
prices, and selects promising deals using structured model output.

### Specialist Agent

Calls the fine-tuned pricing model deployed on Modal. Its integration is in
[specialist_agent.py](app/agents/specialist_agent.py).

### Frontier Agent

Uses the local `llama3.2` model through Ollama's OpenAI-compatible API. Its
integration is in [frontier_agent.py](app/agents/frontier_agent.py).

### Random Forest Agent

Encodes a product description with
`sentence-transformers/all-MiniLM-L6-v2` and predicts a price using the
serialized model in `models/random_forest_model.pkl`.

### Ensemble Agent

Combines specialist, frontier, and Random Forest predictions using
`models/ensemble_model.pkl`.

### Planning Agent

Ranks analyzed deals by estimated discount, stores the best result, and
triggers a notification when the discount exceeds the configured threshold.

## Repository layout

```text
app/
  agents/
    agent.py                  Shared agent logging base class
    deals.py                  Feed scraping and Pydantic deal models
    scanner_agent.py          Deal discovery and selection
    specialist_agent.py       Modal fine-tuned model client
    frontier_agent.py         Local Ollama model client
    random_forest_agent.py    Local Random Forest model client
    ensemble_agent.py         Prediction aggregation
    planning_agent.py         Deal ranking and orchestration
    messaging_agent.py        Pushover/Twilio notifications
  core/
    deal_agent_framework.py   ChromaDB, memory, and agent lifecycle
  services/
    modal_pricer_service.py   Modal GPU deployment definition
  ui/
    dashboard.py              Gradio dashboard entry point
  utils/
    log_formatting.py         Dashboard log formatting
data/
  train.pkl                  Training examples
  test.pkl                   Evaluation examples
  memory.json                Runtime deal history
models/
  random_forest_model.pkl    Random Forest artifact
  ensemble_model.pkl         Required ensemble artifact
products_vectorstore/        Persistent ChromaDB product embeddings
notebooks/                    Training, evaluation, and tutorial notebooks
archive/
  community_contributions/   Alternative implementations
  checkpoints/                Jupyter-generated checkpoints
  legacy/                     Older scripts and experiments
```

## Requirements

- Windows, macOS, or Linux
- Python 3.11 recommended
- Ollama
- A local `llama3.2` Ollama model
- Python dependencies used by the application
- `random_forest_model.pkl`
- `ensemble_model.pkl`
- ChromaDB data in `products_vectorstore/`
- Modal account and Hugging Face access for the specialist model

## Local setup

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
```

If the virtual environment has not been created:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the application dependencies in the activated environment. The
repository currently does not contain a root `requirements.txt`; use the
dependencies imported by the application or create one for your deployment.

## Environment variables

Create a local `.env` file in the repository root. Never commit it.

```env
OPENAI_API_KEY=your_openai_key
HF_TOKEN=your_huggingface_token
PUSHOVER_USER=your_pushover_user
PUSHOVER_TOKEN=your_pushover_token
```

The local Ollama integration uses:

```text
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

These values may be set in the PowerShell session instead of `.env`:

```powershell
$env:OPENAI_BASE_URL="http://localhost:11434/v1"
$env:OPENAI_API_KEY="ollama"
```

## Start Ollama

Install Ollama from [ollama.com](https://ollama.com), then run it in a
separate terminal:

```powershell
ollama serve
ollama pull llama3.2
```

## Run the dashboard

Run this command from the repository root:

```powershell
python -m app.ui.dashboard
```

Then open the local Gradio URL shown in the terminal, usually
`http://127.0.0.1:7860`.

The dashboard cannot initialize the full ensemble until
`models/ensemble_model.pkl` exists.

## Model artifacts

The model files are generated artifacts and are not source code:

```text
models/random_forest_model.pkl
models/ensemble_model.pkl
```

The training and evaluation workflow is documented in
[train_random_forest_and_ensemble.ipynb](notebooks/train_random_forest_and_ensemble.ipynb).

The repository currently includes the training and test datasets and the
Random Forest artifact. The ensemble artifact must also be generated before
the full dashboard can run.

Pickle files should be loaded only from trusted sources. They can execute code
when deserialized.

## Modal fine-tuned model

The Modal service is defined in
[modal_pricer_service.py](app/services/modal_pricer_service.py). It uses:

```text
Base model:     meta-llama/Meta-Llama-3.1-8B
Fine-tuned:     ed-donner/pricer-2024-09-13_13.04.39
```

The fine-tuned model is hosted on
[Hugging Face](https://huggingface.co/ed-donner/pricer-2024-09-13_13.04.39).
Modal downloads it when the GPU container starts.

Authenticate with Modal:

```powershell
modal token new
```

Create the Modal secret expected by the service:

```powershell
modal secret create hf-secret HF_TOKEN=hf_your_token_here
```

Deploy from the repository root:

```powershell
modal deploy -m app.services.modal_pricer_service
```

The Hugging Face token in the local `.env` is not automatically available to
Modal. The token must be stored as the `hf-secret` Modal secret.

## Notifications

Pushover notifications are enabled by default in
[messaging_agent.py](app/agents/messaging_agent.py). Set valid
`PUSHOVER_USER` and `PUSHOVER_TOKEN` values before using them.

Twilio SMS support is present but disabled by default. Enable it only after
configuring the Twilio credentials in `.env`.

## Training notebooks and archived material

The `notebooks/` directory contains the original training, RAG, visualization,
Modal, and dashboard experiments. They are useful for reproducing artifacts but
are not required for normal dashboard startup.

The `archive/` directory contains checkpoints, legacy scripts, and community
variants. These files are retained for reference and are not part of the
default application runtime.

## Troubleshooting

### `FileNotFoundError: ensemble_model.pkl`

Create the ensemble artifact and place it at:

```text
models/ensemble_model.pkl
```

### `401` or `403` from Hugging Face

Accept the Meta Llama license, verify the Hugging Face token has read access,
and recreate the Modal `hf-secret`.

### Modal cannot find `Pricer`

Deploy the service from the repository root:

```powershell
modal deploy -m app.services.modal_pricer_service
```

### Ollama connection refused

Start Ollama and verify that `llama3.2` is installed:

```powershell
ollama serve
ollama list
```

## Author

Developed by Aditya Adi and Anirudh C.

# Food AI Intelligence

A full-stack starter for uncertainty-aware, multimodal food and nutrition analysis. The project includes a responsive React dashboard, a FastAPI service, SQLite persistence, vision-AI image analysis (configured through a backend secret), multilingual AI chat, goals, meal journal/history, browser speech recognition, portion what-if controls, and an interactive relationship graph.

> **Honest implementation status:** This is a runnable starter, not a clinically validated nutrition product. The backend vision and chat integrations call a real OpenAI-compatible API only when `OPENAI_API_KEY` is configured. They return explicit errors when configuration/API calls fail; there are no fake AI success responses. The bundled food reference table is intentionally small and transparent. It is **not** a complete import of IFCT 2017, USDA FoodData Central, or any of the linked image datasets. Unmatched foods are returned without fabricated nutrition values.

## Stack

- Frontend: React, TypeScript, Vite, Recharts, Lucide
- Backend: Python, FastAPI, Pydantic, SQLite, Pillow, OpenAI SDK
- Persistence: SQLite meals, goals, settings and starter food reference table

## Requirements

- Node.js 20+ and npm
- Python 3.11+
- An API key for the selected vision/chat provider (optional for the dashboard/database; required for actual AI analysis and chat)

## Run on Windows (VS Code, step by step)

**Important:** the backend entry file is `backend/main.py`, so the correct Uvicorn target is `main:app` when the terminal is inside `backend`. Do **not** use `app.main:app` for this project; there is no `app` package.

1. In VS Code, choose **File → Open Folder…** and open this exact project folder: `Food_AI_Intelligence_Starter\food-ai-intelligence` (the folder containing `README.md`, `backend`, and `frontend`).
2. Choose **Terminal → New Terminal**. The terminal should be at the project root.
3. Start the backend in this terminal:

```powershell
cd .\backend
py -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Open backend/.env in VS Code and set OPENAI_API_KEY if using live AI
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

   Keep this terminal running. Visit http://127.0.0.1:8000/docs to confirm the API is reachable. In **Command Prompt (CMD)**, use `if not exist .env copy .env.example .env` instead of the PowerShell `if` command above.

4. Open a **second terminal** with **Terminal → New Terminal**. From the project root run:

```powershell
cd .\frontend
npm install
npm run dev
```

5. Open the local URL printed by Vite, usually http://localhost:5173.

You can also double-click `start-backend.bat` and `start-frontend.bat` from the project root after dependencies have been installed. These scripts do not install packages automatically.

### Troubleshooting

- `ModuleNotFoundError: No module named 'app'`: you used the wrong target. Change to the `backend` folder and run `py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`.
- `uvicorn is not recognized`: use `py -m uvicorn ...`, not the bare `uvicorn` command.
- `Copy-Item is not recognized`: you are in CMD, not PowerShell. Use `if not exist .env copy .env.example .env` in CMD.
- `npm` is not recognized: install Node.js 20+ and reopen VS Code.
- API docs work but AI scan/chat reports that AI is not configured: verify `backend/.env`, save it, and restart the backend. Never share the API key or commit `.env`.

## Environment variables

See `backend/.env.example`. Keep the real `.env` out of source control. Never put provider keys in Vite variables or frontend source.

## Implemented in this starter

- Independent pages for Dashboard, Scan Food, Voice Input, Meal Journal, Health Goals, History, Knowledge Graph, AI Chat Assistant, and Settings
- New premium navy-sidebar interface, responsive layout, light/dark theme, English/Hindi/Hinglish interface strings
- Real image upload bytes sent to backend; MIME, size, image decode, dimensions and model output are validated
- Vision response parser, multi-item list, visible ingredient fields, confidence, portion interval, assumptions, clarification questions
- Food lookup against a small SQLite starter table; portion-based nutrition calculation only for a matched record; unmatched records have null nutrition rather than invented values
- SQLite CRUD for meals, goals and settings; API endpoints for food lookup and weekly aggregates
- Editable detected primary label and portion, manual journal entry, meal deletion, goal editing
- Browser speech-recognition support with editable transcript and typed fallback
- AI chat endpoint with language and bounded saved-meal context
- Interactive knowledge graph component; current graph nodes/edges are illustrative examples and should be replaced with verified imported data for research use
- API health/status endpoint, errors and tests for CRUD, persistence, validation and invalid upload type

## Important remaining work before a production/judged release

1. **Nutrition data import:** Import approved IFCT 2017 data for supported Indian foods and USDA FoodData Central records with IDs, preparation states, source versions, units and license/attribution notes. Current seed table is deliberately small and some recipe foods are generic estimates, not official IFCT records.
2. **Image datasets:** The supplied links are food-image datasets, not nutrition composition databases. Build a reproducible dataset loader/model-training pipeline only after verifying terms and redistribution rights. Khana is described as non-commercial research/educational use and does not own image copyrights; Food-101 image terms restrict uses beyond scientific fair use unless rights are negotiated; Food-530 README says access is by request/agreement. Check each source's current terms before using in a public/commercial app.
3. **Thali localization/segmentation:** The current vision prompt returns individual food candidates, but does not draw pixel-accurate masks/bounding boxes. A real segmentation/detection model and UI overlay are required for reliable per-item boxes over the image.
4. **Portion accuracy:** Portion estimates from one RGB photo are uncertain. Calibrate with user-confirmed serving size, known plate reference, depth/multiple views or scale measurements. Do not present confidence as validated model accuracy.
5. **Meal analysis save semantics:** Review each item and database match before saving. This starter saves a single primary item from the analysis UI; multi-item transaction editing/saving should be added for complete mixed-thali journaling.
6. **Security:** Add authentication/authorization before exposing the API outside localhost, rate limits, CSRF policy if cookie auth is introduced, upload scanning, request logging with sensitive-data minimization, retention controls, backups and deployment secrets management.
7. **Localization:** The primary navigation and key dashboard strings are localized; review all labels and error messages for full Hindi/Hinglish localization.
8. **Automated UI tests and actual API smoke test:** Run the build and backend tests below. A successful build does not verify a live API key or recognition quality; test a labelled, held-out image set.

## Test commands

Backend (from `backend` after dependencies install):

```powershell
pytest -q
```

Frontend (from `frontend`):

```powershell
npm run build
```

No test should claim model accuracy from a handful of screenshots. Create a labelled held-out set including pomegranate, apple, banana, pizza, roti, rice, dal, sabzi, paneer, dosa, idli, salads and mixed Indian thalis. Report per-class precision/recall and nutrition error separately.

## Supplied data references and notes

- Khana: https://khana.omkarprabhu.in/ — 131k+ images, 80 Indian food dishes; site describes non-commercial research/education terms and notes it does not own image copyright.
- Massive Indian Food Dataset: https://www.kaggle.com/datasets/anshulmehtakaggl/themassiveindianfooddataset — verify Kaggle license and image rights before redistribution/training.
- Food-530: https://github.com/yyqgood/Food-530-dataset — 530 categories / 392,183 images described; README says download is available by request/agreement.
- NUFood: https://www.cs.is.i.nagoya-u.ac.jp/opensource/nufood/ — review current dataset license and intended usage before ingestion.
- Food-101: https://data.vision.ee.ethz.ch/cvl/vision2/datasets_extra/food-101/ — 101 classes; image copyright terms require care beyond scientific fair use.
- TurkishFoods-15: https://huggingface.co/datasets/yunusserhat/TurkishFoods-15 — Hugging Face card lists Apache-2.0 for that dataset version; retain citation and verify card before use.
- Research paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC10096622/ — use for literature review, not as a food composition table unless the paper explicitly provides suitable data.

Image classification datasets help identify food classes; they do not by themselves provide calories, macros, portion weights, ingredients, or validated recipes.

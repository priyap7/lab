# Project status and verification

## Fixes included
- Corrected backend startup target: run `uvicorn main:app` from the `backend` directory. This project has `backend/main.py`, not an `app` package.
- Added Windows startup helper scripts at the project root.
- Added `frontend/src/vite-env.d.ts` for Vite's `import.meta.env` types.
- Kept API secrets out of the archive; only `.env.example` is included.
- Removed generated caches and partial `node_modules` from the deliverable. Run `npm install` in `frontend` on your computer.

## Verified in this environment
- Backend tests: `python -m pytest -q` — 5 passed.

## Still not verified / requires your machine or credentials
- Frontend production build could not be verified: dependencies were missing and `npm install` timed out in this environment. Install dependencies with Node.js 20+ and run `npm run build`.
- Live OpenAI vision/chat calls require a valid secret in `backend/.env`; live API behavior was not tested. Do not paste API keys into chat.
- The nutrition table is a small starter subset, not a complete IFCT 2017/USDA import. Image segmentation/bounding boxes and clinically validated nutrition accuracy are not implemented.
- This is a local starter, not a production-ready clinical product. Review README's remaining work before public deployment.

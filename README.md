# LabelLens AI

LabelLens AI reviews the text visible in a packaged-food label photo, compares it with a user-defined preference profile, and links findings to source wording. It is deliberately cautious: a missing match is not proof of safety, and incomplete or unreadable label sections remain unknown.

## What it does

- Upload JPEG, PNG, or WebP photos up to the configured limit, with drag-and-drop, preview, replacement, and removal.
- Send images from the backend to a configurable xAI Grok vision model using the Responses API. The browser never receives the provider key.
- Validate structured extraction with Pydantic, keep exact source wording, and require nutrition values and units to be supported by their quoted label text before comparison. Unsupported fields are marked unknown or partially readable instead of being presented as confirmed.
- Assess image readability and flag visible issues such as blur, glare, curved packaging, obstruction, cropping, and perspective distortion. Uncertain fields remain unresolved rather than being completed from context.
- Compare allergens, curated ingredient synonyms, precautionary cross-contact wording, dietary-pattern uncertainty, and nutrition thresholds with matching units and serving bases.
- Review quoted evidence and field confidence, request a clearer photo when needed, manually confirm or correct ingredient/allergen text, and rerun comparisons without another image request.
- Store preferences in browser local storage only when the user opts in. Uploaded photos are not persisted by this application.

## Prerequisites

- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- An xAI API key for live analysis. The default model is `grok-4.7`; choose a model available to your xAI account that supports image input and JSON output.

The app can run without provider credentials. The backend health endpoint then reports `configuration_required`, and image analysis returns a clear configuration error rather than sample results. Frontend and deterministic comparison tests use mocked provider output and do not need paid API access.

## Setup: Windows PowerShell

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set the provider values:

```dotenv
XAI_API_KEY=your-server-side-key
XAI_VISION_MODEL=grok-4.7
MAX_UPLOAD_MB=10
FRONTEND_ORIGIN=http://localhost:5173
REQUESTS_PER_MINUTE=12
```

Start the API in the activated backend terminal:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). Check backend readiness at `http://127.0.0.1:8000/api/health`.

## Setup: macOS / Linux

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Set the same environment values above, then start the backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Tests and build

```powershell
# From backend, with its virtual environment activated
python -m pytest -q

# From frontend
npm test
npm run build
```

Provider tests are mocked. They cover curved and blurry label assessments, incomplete transcription, unreadable or low-confidence fields, missing source text, conservative comparisons, and re-comparison after user corrections. For one manual live-provider check, configure the backend environment, start both services, upload a clear photo showing an ingredient list, choose a restriction such as milk, and verify that the finding quotes the visible wording. Try a cropped, curved, or blurry image too; it should ask for confirmation or a clearer image rather than treating missing text as absent.

## API

- `GET /api/health` reports readiness, whether provider configuration is present, and the configured upload limit; it never returns secrets.
- `POST /api/analyze-label` accepts multipart `image` and a JSON-string `profile` form field.
- `POST /api/compare` accepts previously extracted `label` data and a revised `profile`, and does not call the vision provider.

The backend serves the OpenAPI page at `/docs` during local development.

## Configuration and provider changes

- `XAI_API_KEY`: server-side xAI credential. Never expose it to the frontend.
- `XAI_VISION_MODEL`: model name for the xAI endpoint (default `grok-4.7`); select a model whose current documentation confirms image input and JSON output support.
- `MAX_UPLOAD_MB`: upload size ceiling (default 10 MB).
- `FRONTEND_ORIGIN`: allowed browser origin (default `http://localhost:5173`). Set this to the deployed frontend origin in production.
- `REQUESTS_PER_MINUTE`: per-client in-memory safeguard for image analysis (default 12).

Provider calls live in `backend/app/services/vision_provider.py`; the OpenAI-compatible Python client is configured for xAI's `https://api.x.ai/v1` API. Preserve the `LabelData` validation contract when changing providers. Never put credentials in frontend variables or source control. For production, terminate TLS, configure an explicit frontend origin, use a shared rate limiter, and review provider retention terms.

## Privacy, limitations, and safety

Images are sent to the backend's configured AI provider for analysis. The app does not save images or create user accounts. Preferences are stored in this browser only after opt-in. The provider may process images under its own service terms; do not upload sensitive material unless those terms are acceptable.

This is an aid for reading labels, not medical advice or a product safety certification. Image-quality assessment is performed by the configured vision model; it is not a deterministic blur meter, OCR completeness proof, or guarantee that every curved, obscured, or small-print section was detected. The image can omit package sections, OCR/vision can make mistakes, ingredient sources may be ambiguous, and manufacturing cross-contact may not be disclosed. Missing extracted text is not proof that an ingredient or allergen is absent. Confirm unresolved fields against the original package, and contact the manufacturer for decisions involving serious allergies or strict dietary requirements. User corrections are compared as supplied; the app cannot independently verify them.

## Current scope

The first version uses an in-memory rate limit, no database, and deterministic rules plus curated synonyms. User-defined dietary patterns are surfaced as unknown rather than interpreted speculatively. The comparison engine intentionally does not convert nutrition values across serving bases. The frontend uses a small custom CSS design system; no component framework is required.

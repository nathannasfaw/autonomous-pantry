# Autonomous Pantry

Autonomous Pantry is a pantry-aware cooking assistant that combines pantry scanning, persistent pantry storage, recipe generation, and shopping-cart suggestions in one local web app.

The project is built as a React frontend with a FastAPI backend. A user can scan pantry items with the camera, store them in SQLite, refresh the app without losing that pantry data, and then ask for recipes based on what is already on hand.

This is a working prototype designed for local development and demos. Core flows work, but there are still rough edges and limitations that are listed below.

## Project Overview

### What the app does

Autonomous Pantry helps answer everyday kitchen questions such as:

- What ingredients do I already have?
- What can I cook with my pantry?
- What ingredients am I missing for a recipe?
- What should I add to a shopping cart?

### Key features

- Camera-based pantry scanning
- YOLO object detection for pantry items
- Claude-assisted crop identification for better food labeling
- Persistent pantry storage with SQLite
- Pantry data shared across new chat sessions using a stable `client_id`
- Chat-based recipe generation and meal suggestions
- Pantry-aware ingredient gap analysis
- Shopping-cart recommendations for missing items
- Editable pantry UI for add, update, and delete
- Recipe image scraping from recipe source pages when available

### Problem it solves

Most recipe tools and meal planners do not know what is already in your kitchen. Autonomous Pantry tries to bridge that gap by keeping pantry state at the center of recipe and grocery decisions.

## Architecture Overview

### Frontend

The frontend is located in `frontend/` and uses:

- React 18
- Vite
- Tailwind CSS

The frontend handles:

- the chat interface
- pantry browsing and editing
- camera scan flow
- recipe and cart rendering
- browser-level `client_id` persistence

### Backend

The backend is located in `backend/` and uses:

- FastAPI
- Pydantic
- Anthropic SDK
- PyTorch
- Ultralytics YOLO

The backend handles:

- chat session creation
- pantry routes
- scan confirmation and persistence
- recipe intent detection
- recipe lookup and validation
- pantry-to-recipe gap analysis
- cart recommendation
- recipe source-page image extraction

### Database

The app uses SQLite for pantry persistence.

SQLite stores pantry items by `client_id`, so pantry data stays available across:

- page refreshes
- new chat sessions
- backend restarts

## How It Works

### 1. Scanning an item

1. The user opens the scanner in the frontend.
2. The backend runs YOLO on the captured frame.
3. The backend sends cropped detections through a second identification step.
4. The confirmed pantry items are sent to the pantry update route.
5. The backend writes those items to SQLite.
6. The pantry panel refreshes from the database.

Important rule:

- a pantry scan is a data update, not a chat message

### 2. Pantry persistence

The frontend stores a stable `client_id` in browser local storage.

When a new chat starts:

- the frontend sends `client_id` to the backend
- the backend creates a new conversation id
- the backend loads pantry items tied to that `client_id`

This means a new conversation still uses the same pantry.

### 3. Chat interaction and recipe generation

1. The user sends a message in chat.
2. The backend checks if the message is an explicit recipe or meal request.
3. If not, the system does not enter recipe generation.
4. If yes, the backend normalizes the dish query.
5. The backend asks Claude for structured recipe data.
6. The backend validates the recipe before using it.
7. The backend compares recipe ingredients against pantry items.
8. Missing ingredients go through gap analysis and recommendation scoring.
9. The frontend renders the recipe and the shopping cart.

### 4. Separation between pantry updates and chat

Pantry updates use `/pantry/*` routes.

Chat uses `/chat/*` routes.

That separation is intentional so:

- scans do not appear as visible chat acknowledgements by default
- pantry persistence is independent from conversation history
- recipe generation only runs on explicit user intent

## Project Structure

```text
autonomous-pantry/
├── backend/
│   ├── app/
│   │   ├── data/
│   │   ├── models/
│   │   ├── routes/
│   │   └── services/
│   ├── main.py
│   └── requirements.txt
└── frontend/
    ├── src/
    ├── package.json
    └── vite.config.js
```

### Important backend files

- `backend/main.py`
  - FastAPI entrypoint
  - loads environment variables
  - registers routes
  - initializes SQLite and the recommendation model

- `backend/app/routes/chat.py`
  - starts chat sessions
  - handles recipe and cart conversation flow

- `backend/app/routes/pantry.py`
  - handles scan, crop identification, pantry fetch, and pantry update routes

- `backend/app/services/pantry_store.py`
  - SQLite persistence layer for pantry items

- `backend/app/services/session_manager.py`
  - in-memory conversation session state
  - links sessions to persisted pantry data

- `backend/app/services/llm_service.py`
  - recipe request parsing
  - query normalization
  - structured recipe lookup
  - validation and fallback behavior

- `backend/app/services/gap_analysis.py`
  - computes missing ingredients based on pantry contents

- `backend/app/services/nn_service.py`
  - PyTorch-based cart recommendation logic

- `backend/app/services/recipe_image_service.py`
  - tries to extract image metadata from recipe pages

### Important frontend files

- `frontend/src/App.jsx`
  - main layout and tabs

- `frontend/src/hooks/useChat.js`
  - starts sessions
  - stores browser `client_id`
  - sends chat messages

- `frontend/src/hooks/usePantry.js`
  - pantry fetch and update logic

- `frontend/src/components/CameraModal.jsx`
  - live scan interface

- `frontend/src/components/RecipeCard.jsx`
  - recipe display
  - only shows an image section when an image URL exists

## Environment Setup

Create a `.env` file in:

```bash
backend/.env
```

### Required environment variables

- `ANTHROPIC_API_KEY`
  - required for recipe lookup, crop identification, and chat reasoning

### Example `.env`

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Notes:

- The backend can start without this key, but LLM-powered features will fail.
- SQLite does not require separate database credentials.

## Running the Project

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- Anthropic API key

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd autonomous-pantry
```

If your repo root contains this folder inside another project, instead run:

```bash
cd c:\Users\natha\Projects\fintech_project\autonomous-pantry
```

### 2. Install backend dependencies

Windows:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `.env`

Create `backend/.env`:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 4. Start the backend

From `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

### 5. Install frontend dependencies

Open a second terminal:

```bash
cd frontend
npm install
```

### 6. Start the frontend

From `frontend/`:

```bash
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

### 7. Try the app

Suggested test flow:

1. Open the app in the browser
2. Scan a pantry item or add one manually
3. Refresh the page and confirm the pantry still exists
4. Ask for a recipe such as:
   - `I want to make orange chicken`
   - `What can I make with my pantry?`
5. Review the recipe and shopping cart output

## Database

The app uses SQLite.

### Database file

The database is created automatically at:

```text
backend/app/data/pantry.db
```

### Pantry table contents

The `pantry_items` table stores:

- `id`
- `client_id`
- `item_name`
- `quantity`
- `unit`
- `category`
- `confidence`
- `scanned_at`
- `updated_at`

### Persistence model

- the browser stores a stable `client_id`
- the backend loads pantry data for that `client_id`
- pantry items are stored in SQLite instead of only in session memory

This allows pantry state to persist across:

- refreshes
- new chats
- backend restarts

## Current Limitations / Known Issues

### Recipe generation

- recipe lookup depends on LLM output and web search quality
- some recipe pages are difficult to parse consistently
- some requests still need retry handling before a valid structured recipe is returned
- API rate limits can affect repeated recipe requests

### Images

- recipe images are only shown if the recipe payload already includes an image URL or if the source page exposes `og:image` or `twitter:image`
- some recipe sites block scraping with `403 Forbidden`
- if no image is available, the UI hides the image section

### Ingredient matching

- pantry-to-recipe matching is heuristic-based
- unit conversion is limited
- ingredient naming can still mismatch in edge cases

### Pantry scanning

- scan quality depends on camera angle, lighting, and framing
- crop identification improves labels but is still imperfect
- false positives and low-confidence detections can still happen

### State and scale

- conversation sessions are still stored in memory
- there is no authentication or user account system
- pantry data is keyed by browser `client_id`, not a real user identity
- there is no production deployment setup or background job system

### Ordering

- the order/cart flow is a prototype
- `instacart_stub.py` is not a real grocery integration

## Future Improvements

- Replace SQLite with Postgres for multi-user deployments
- Add authentication and real user accounts
- Move session state to Redis or a database
- Improve ingredient normalization and unit conversion
- Add stronger recipe retrieval and schema validation
- Improve food detection accuracy
- Add automated tests for pantry, chat, and recipe flows
- Improve the mobile and camera UX
- Add a real checkout integration

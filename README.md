# 🏆 Tournament Poster Extraction API

A production-ready REST API built with **FastAPI** and the official **Google Gemini Python SDK (`google-genai`)** that analyzes sports tournament and event poster images and extracts structured, clean JSON data using multimodal AI.

---

## 🚀 Features

- **Direct Multimodal Extraction**: Powered by Google Gemini Vision (default `gemini-2.5-flash`), analyzing poster typography, hierarchy, dates, logos, and QR codes directly without brittle OCR pre-processing.
- **Strict Structured JSON Output**: Validated with Pydantic schemas for reliable schema adherence and type safety.
- **Smart Date Parsing**: Normalizes tournament, registration, and auction dates to ISO `YYYY-MM-DD` while distinguishing between event dates, auction dates, and registration deadlines.
- **Comprehensive Sports Event Schema**:
  - **Tournament**: Name, normalized sport, format, season, organizer.
  - **Dates**: Start date, end date, explicit registration deadline, auction date.
  - **Location**: Venue, address, city, state, country (extracted only when explicitly stated or reliably determined).
  - **Registration**: Available flag, registration methods array (`["Call", "WhatsApp", "QR Code", ...]`), QR presence, registration URL, fee, contact person, contact numbers array, email.
  - **Auction**: Required flag, auction date, venue, address.
  - **Participation**: Number of teams, number of players, eligibility, team requirements, player requirements.
  - **Fees**: Dedicated breakdown for registration fee, team fee, player fee, auction fee with currency preserved.
  - **Prizes**: First prize, second prize, third prize, and special individual awards in `other_prizes`.
  - **Additional Information**: Useful rules, selection procedures, overs/match format, and instructions (slogans are excluded).
  - **Extraction Quality**: Approximate confidence score between 0.0 and 1.0 and `fields_needing_review`.
- **Production Validation & Error Handling**:
  - Validates image MIME types (`image/jpeg`, `image/png`, `image/webp`)
  - File size limits (configurable via `MAX_FILE_SIZE_MB`)
  - Rejects empty / corrupted files
  - Safe error responses without exposing secrets or API keys
- **Interactive API Documentation**: Automatic Swagger UI at `/docs` and ReDoc at `/redoc`.
- **Configurable CORS**: Supports single origin, comma-separated lists, or wildcard.

---

## 📁 Project Structure

```
tournament-poster-api/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application, routes, CORS & validation
│   ├── models.py                # Pydantic schemas for request/response validation
│   └── services/
│       ├── __init__.py
│       └── gemini_service.py    # Google Gemini Vision integration & structured prompt
├── tests/
│   ├── __init__.py
│   └── test_api.py              # Unit & integration tests with pytest & TestClient
├── .env.example                 # Example environment variables
├── .env                         # Local environment configuration (git ignored)
├── .gitignore                   # Git ignore patterns
├── render.yaml                  # Render Blueprint configuration
├── requirements.txt             # Project dependencies
└── README.md                    # Documentation
```

---

## 🛠️ Prerequisites

- **Python 3.11+** installed
- **Render Account** (Free tier on [render.com](https://render.com))
- **Render CLI** (`render.cli`)
- **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

---

## ⚙️ Local Setup & Installation

### 1. Clone or Open the Repository

```bash
cd "d:/Shreyansh PC/Project/Tournament API Key"
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Local Environment Variables

Create your `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and supply your Gemini API key:

```ini
GEMINI_API_KEY=AIzaSy...your_actual_key_here
GEMINI_MODEL=gemini-2.5-flash
ALLOWED_ORIGINS=*
MAX_FILE_SIZE_MB=10
```

---

## 🏃 Running the API Locally

Start the development server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- **Root**: `http://localhost:8000/`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

---

## ☁️ Deploying to Render (Free Tier)

### 1. Render CLI Installation

**Windows (via WinGet):**
```powershell
winget install render.cli
```

### 2. Authenticate Render CLI

```bash
render login
```
*(This opens your browser to authenticate with your Render account).*

### 3. Connect Git Repository

Render deploys web services from Git (GitHub or GitLab):

```bash
git add .
git commit -m "Initial commit for Render deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

### 4. Deploy via Render Blueprint / CLI

Render uses the included [`render.yaml`](file:///d:/Shreyansh%20PC/Project/Tournament%20API%20Key/render.yaml) to automatically configure:
- **Service Type**: Web Service (`python`)
- **Plan**: Free
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

Deploy using:
```bash
render blueprints launch
```
Or create a Web Service directly linked to your GitHub repo on Render.

### 5. Set Environment Variable in Render

In your Render service settings / dashboard:
1. Navigate to **Environment**.
2. Add environment variable:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: `YOUR_ACTUAL_GEMINI_API_KEY`
3. Save changes (Render will automatically re-deploy).

---

## 📖 API Endpoints

### 1. `GET /`
Returns basic status information.

**Response (200 OK):**
```json
{
  "message": "Tournament Poster Extraction API",
  "status": "running"
}
```

---

### 2. `GET /health`
Liveness and health check endpoint.

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

---

### 3. `POST /extract`
Extracts structured tournament information from an uploaded poster image.

- **Content-Type**: `multipart/form-data`
- **Request Field**:
  - `poster`: Image file (`.jpeg`, `.jpg`, `.png`, `.webp`)

#### Example `curl` Request:

```bash
curl -X POST "https://<RENDER_SERVICE_URL>/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "poster=@/path/to/tournament_poster.png"
```

#### Example JSON Response (200 OK):

```json
{
  "tournament": {
    "name": "Apex Premier League 2026",
    "sport": "Cricket",
    "format": "Turf Box Cricket Tournament",
    "season": "Season 4",
    "organizer": "Apex Sports Club"
  },
  "dates": {
    "start_date": "2026-11-29",
    "end_date": "2026-12-05",
    "registration_deadline": "2026-11-20",
    "auction_date": "2026-11-25"
  },
  "location": {
    "venue": "Skyline Turf Arena",
    "address": "Opposite Tech Park, Outer Ring Road",
    "city": "Bengaluru",
    "state": "Karnataka",
    "country": "India"
  },
  "registration": {
    "available": true,
    "methods": [
      "WhatsApp",
      "QR Code"
    ],
    "qr_code_present": true,
    "registration_url": null,
    "registration_fee": "₹5,000 per team",
    "contact_person": "Rahul Sharma",
    "contact_numbers": [
      "9876543210",
      "9123456789"
    ],
    "email": "contact@apexsports.com"
  },
  "auction": {
    "required": true,
    "date": "2026-11-25",
    "venue": "Grand Orchid Hall",
    "address": "Indiranagar, Bengaluru"
  },
  "participation": {
    "number_of_teams": 16,
    "number_of_players": 100,
    "eligibility": "Only Maheshwari Samaj members can participate",
    "team_requirements": "Minimum 8 players per team",
    "player_requirements": "Aadhaar Card copy required"
  },
  "fees": {
    "registration_fee": "₹500",
    "team_fee": "₹5,000",
    "player_fee": "₹500",
    "auction_fee": "₹1,000"
  },
  "prizes": {
    "first_prize": "₹50,000",
    "second_prize": "₹25,000",
    "third_prize": null,
    "other_prizes": [
      "Man of the Match - ₹1,000",
      "Best Bowler - Trophy",
      "Player of the Tournament"
    ]
  },
  "additional_information": [
    "100 players will be selected through auction",
    "10 overs per match with red tennis ball"
  ],
  "extraction": {
    "confidence": 0.95,
    "fields_needing_review": []
  }
}
```

---

## 📮 Postman Configuration

To test `POST /extract` against local or deployed Render instance:

1. **Method**: `POST`
2. **URL**: `https://<RENDER_SERVICE_URL>/extract` (or `http://localhost:8000/extract`)
3. **Body Tab**:
   - Select **form-data**
   - In the **KEY** column, type `poster`
   - Change type from **Text** to **File**
   - In the **VALUE** column, click **Select Files** and choose your tournament poster image (`.jpg`, `.png`, or `.webp`)
4. **Headers**: Automatically set by Postman for `multipart/form-data`.
5. Click **Send**. No API key is required in Postman; the key is securely kept on Render.

---

## 🧪 Running Tests

Execute the test suite using `pytest`:

```bash
pytest -v
```

All 17 unit and integration tests validate schema conformity, MIME checks, file size constraints, error handlers, and extraction logic without needing live API calls.

# Bulk Email Enrichment Platform

A production-grade, asynchronous microservice platform and web dashboard for bulk domain resolution, email permutation generation, and multi-stage deliverability verification.

---

## 📁 Project Directory Organization

```text
email-enrichment-puppet/
├── backend/                  # FastAPI Application, Repositories, Providers & Services
├── frontend/                 # React + Vite + TypeScript Web Dashboard
├── docs/                     # Architecture specifications & system design docs
├── uploads/                  # Temporary storage for user-uploaded CSV files (auto-managed)
├── exports/                  # Generated enriched CSV result files available for download
├── logs/                     # Application, worker, queue, and debug log files
├── temp/                     # Transient processing files (safe to clear anytime)
└── tests/                    # Automated testing suite
    ├── unit/                 # Pytest unit tests
    ├── integration/          # API & route integration tests
    └── fixtures/             # Version-controlled static test fixtures
        └── csv/              # Sample CSV datasets for testing bulk uploads
            ├── valid_companies.csv
            ├── missing_company_column.csv
            ├── empty.csv
            ├── duplicate_headers.csv
            └── large_dataset.csv  (5,000-row stress test dataset)
```

### Working Directory Details

* **`uploads/`**: Stores raw CSV files uploaded by users prior to asynchronous processing. (Contents git-ignored).
* **`exports/`**: Contains generated CSV result files ready for user download after job completion. (Contents git-ignored).
* **`logs/`**: Centralized log directory for FastAPI server, background worker pool, and queue execution trace logs. (Contents git-ignored).
* **`temp/`**: Working storage for temporary chunk files and transient data created during job execution. (Contents git-ignored).
* **`tests/fixtures/`**: Static test fixture datasets used by automated pytest suites. **Maintained in version control.**

---

## 🛠️ Tech Stack

### Backend
- **Python**: `3.12+` / `3.14`
- **Framework**: `FastAPI`
- **Server**: `Uvicorn`
- **Configuration & Validation**: `Pydantic v2` / `pydantic-settings`
- **Database Client**: `Supabase` (PostgreSQL)
- **Testing**: `pytest`, `pytest-asyncio`
- **Code Quality**: `Ruff`

### Frontend
- **Framework**: `React` with `TypeScript`
- **Build Tool**: `Vite`
- **Routing**: `React Router DOM v6`
- **Styling**: `Vanilla CSS` with custom Design Tokens

---

## 🚀 Running the Backend

1. Navigate to `backend/`:
   ```bash
   cd backend
   ```
2. Activate virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
3. Start the server:
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --http h11
   ```
4. Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 💻 Running the Frontend

1. Navigate to `frontend/`:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start dev server:
   ```bash
   npm run dev
   ```
4. Access web dashboard: [http://localhost:3000](http://localhost:3000)

---

## 🧪 Automated Tests

```bash
cd backend
.\venv\Scripts\python.exe -m pytest -v
```

# Development Setup

## Prerequisites

- Python 3.13
- Node.js
- npm
- Docker Desktop
- Git
- uv

---

## Clone

```powershell
git clone <repository-url>

cd Polaris
```

---

## Environment

Create a root `.env` file.

---

## Backend

```powershell
cd backend

uv sync

uv run uvicorn app.main:app --reload
```

API:

```
http://localhost:8000
```

---

## Frontend

```powershell
cd frontend

npm install

npm run dev
```

Frontend:

```
http://localhost:5173
```

---

## Docker

```powershell
docker compose up
```

---

## Running Tests

Backend

```powershell
uv run pytest
```
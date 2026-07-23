# Polaris

Polaris is a production-grade AI Engineering project focused on building an intelligent workflow orchestration platform using modern AI engineering practices.

## Tech Stack

### Backend
- Python 3.13
- FastAPI
- uv
- pytest

### Frontend
- React
- Vite
- JavaScript

### Database
- PostgreSQL 17
- pgvector

### Tooling
- Docker Compose
- GitHub Actions

---

## Project Structure

```text
backend/
frontend/
docs/
scripts/
tests/

docker-compose.yml
.env
```

---

## Getting Started

### Backend

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Docker

```powershell
docker compose up
```

---

## Running Tests

Backend

```powershell
uv run pytest
```

---

## License

MIT
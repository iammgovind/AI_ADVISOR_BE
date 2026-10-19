# FI backend

FastAPI API with JWT authentication, user management, and Swagger docs. Requires Python 3.10+.

## Setup

```powershell
cd d:\Py\FI_be
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY` plus your MySQL `MYSQL_PASSWORD`. Host/port default to `localhost:3306`, database `fi_be` (created automatically).

## Run

```powershell
uvicorn app.main:app --reload
```

- Health: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

Optional schema migrations:

```powershell
alembic upgrade head
```

On first run the app creates the `fi_be` MySQL database and tables if they do not exist. Tests still use in-memory SQLite.

## Auth in Swagger

1. `POST /api/v1/auth/register` with email + password (min 8 chars).
2. `POST /api/v1/auth/login` — use **email** in the `username` field.
3. Click **Authorize** and paste the `access_token`.
4. Call `GET /api/v1/users/me`.

Admin-only routes: `GET/PATCH/DELETE /api/v1/users`. Promote a user by setting `role` to `admin` in the database, or via `PATCH /api/v1/users/{id}` as an existing admin.

## Tests

```powershell
pytest
```

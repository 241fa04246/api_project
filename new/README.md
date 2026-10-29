# Library Management System

A small browser-based library application with a Python REST API and SQLite database. It uses Python's standard library only.

## Features

- Responsive landing page, member registration/login, dashboard, and searchable book catalog.
- Passwords stored as salted PBKDF2-HMAC-SHA256 hashes; JWT bearer tokens expire after one hour.
- Role-based access: members borrow/return books and view their own loans; admins manage the catalog and see all loans.
- `X-API-Key` validation on every `/api/*` endpoint.
- Input validation, parameterized SQL, bounded JSON requests, and transactional borrowing.
- Optional HTTPS with TLS 1.2 or newer.

## Project layout

```text
library-management-system/
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── books.html
│   ├── style.css
│   └── script.js
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── auth.py
│   ├── security.py
│   ├── book_routes.py
│   ├── borrow_routes.py
│   ├── requirements.txt
│   └── .env.example
├── tests/
│   ├── test_auth.py
│   ├── test_books.py
│   ├── test_borrowing.py
│   └── test_security.py
├── app.py
├── .gitignore
└── README.md
```

`backend/requirements.txt` documents that no third-party packages are needed. `.env.example` contains placeholders only: do not commit real API keys, JWT secrets, or TLS private keys.

## Run locally (PowerShell)

Stop any previously running copy of the server with **Ctrl+C** first. Then, from the project root:

```powershell
$env:LIBRARY_API_KEY = "replace-with-a-random-secret-at-least-16-chars"
$env:JWT_SECRET = "replace-with-a-different-random-secret-at-least-32-chars"
python .\app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The default server listens on loopback and uses HTTP for local development only. Database storage defaults to `library.db` in the project root; set `LIBRARY_DB` to change it.

For HTTPS, configure a certificate and private key before starting:

```powershell
$env:TLS_CERT_FILE = "C:\path\to\fullchain.pem"
$env:TLS_KEY_FILE = "C:\path\to\private-key.pem"
python .\app.py
```

Both TLS variables must be set together. For production, use a trusted certificate and TLS, protect secrets, restrict network access, and use an established production HTTP server or TLS-terminating reverse proxy.

The browser asks for the API key at registration/sign-in and keeps it in the tab's `sessionStorage` to call the API. This is suitable only for a local classroom/demo setup: a key delivered to browser code is not private and should not be used as a production client credential.

## Accounts and admin access

Registration always creates a member account; users cannot assign themselves admin access. To promote an existing user, stop the server and run:

```powershell
python .\app.py --promote reader1
```

Then start the server again and sign in to refresh the JWT with the new role. To demote an account, run `python .\app.py --demote reader1`. These commands use the configured `LIBRARY_DB` path if set, otherwise the project-root `library.db`.

## REST API

All `/api/*` routes require `X-API-Key: <LIBRARY_API_KEY>`. Authenticated requests additionally require `Authorization: Bearer <access_token>`. Request/response bodies are JSON.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health` | Public | Health check |
| POST | `/api/auth/register` | API key | Create member (`username`, `password`) |
| POST | `/api/auth/login` | API key | Login and receive a JWT |
| GET | `/api/auth/me` | Authenticated | Get the current account |
| GET | `/api/books?q=...` | API key | List/search books |
| GET | `/api/books/{id}` | API key | Get a book |
| POST | `/api/books` | Admin | Add a book (`title`, `author`, `isbn`, `year`, `copies`) |
| PUT/PATCH | `/api/books/{id}` | Admin | Replace/update a book |
| DELETE | `/api/books/{id}` | Admin | Delete a book |
| POST | `/api/books/{id}/borrow` | Member | Borrow an available copy |
| POST | `/api/books/{id}/return` | Authenticated | Return the caller's active loan |
| GET | `/api/loans` | Authenticated | List own loans (or all loans as admin) |

## Tests

Run the integration suite from the project root:

```powershell
python -m unittest discover -v
```

The suite covers authentication, password hashing, API-key and JWT checks, authorization, catalog validation and management, borrowing/returns, and loan privacy.

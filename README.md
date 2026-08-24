# api.dileepa.dev

This is the API for Dileepa's personal website ([dileepa.dev](https://dileepa.dev)), built with [FastAPI](https://fastapi.tiangolo.com/). It provides the data behind the main site, the admin dashboard, and the blog sync pipeline.

> [!NOTE]
> v2.0.0 migrates this API from NestJS to FastAPI. Both stacks are in the repository during the
> migration: `app/` is the FastAPI application and `src/` is the NestJS one still serving
> production. `src/` is deleted only after both consumers are verified against FastAPI and a
> rollback window has passed. See [TODO.md](TODO.md).

## Table of Contents

- [api.dileepa.dev](#apidileepadev)
  - [Table of Contents](#table-of-contents)
  - [Tools and Technologies](#tools-and-technologies)
  - [Installation](#installation)
  - [Running the App](#running-the-app)
    - [Development](#development)
    - [Production](#production)
    - [Scripts](#scripts)
  - [API Documentation](#api-documentation)
  - [Testing](#testing)
  - [Versioning](#versioning)
  - [Contributing](#contributing)
  - [Issues](#issues)
  - [Security](#security)
  - [License](#license)
  - [API Endpoints](#api-endpoints)
  - [Deployment](#deployment)
  - [Contact](#contact)

## Tools and Technologies

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) 0.141.x
- **Language:** [Python](https://www.python.org/) 3.13
- **Package Manager:** [uv](https://docs.astral.sh/uv/)
- **Validation:** [Pydantic](https://docs.pydantic.dev/) 2.13.x
- **Linting and Formatting:** [Ruff](https://docs.astral.sh/ruff/)
- **Type Checking:** [mypy](https://mypy-lang.org/) (strict)
- **Testing:** [pytest](https://docs.pytest.org/) with [httpx](https://www.python-httpx.org/)
- **Database:** [MongoDB](https://www.mongodb.com/) via the async
  [PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/) driver
- **Deployment:** [FastAPI Cloud](https://fastapicloud.com/)
- **Authentication:** [JWT](https://jwt.io/) access and refresh tokens
  ([PyJWT](https://pyjwt.readthedocs.io/)), password hashing with
  [pwdlib](https://frankie567.github.io/pwdlib/)
- **Authorization:** Role-based access control through FastAPI dependencies
- **Image Hosting:** [Cloudinary](https://cloudinary.com/)
- **Rate Limiting:** [SlowAPI](https://slowapi.readthedocs.io/)
- **Documentation:** OpenAPI, with Swagger UI and ReDoc served in development only

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/dileepadev/api.dileepa.dev.git
   cd api.dileepa.dev
   ```

2. Install dependencies. `uv` fetches Python 3.13 itself, so no separate
   install is needed:

   ```bash
   uv sync --all-groups
   ```

   Never `pip install` into this project — it would bypass the lockfile.

3. Copy the example environment file and update it with your configuration:

   ```bash
   cp .env.example .env
   # Then edit .env as needed
   ```

## Running the App

Run through the FastAPI CLI, not `uvicorn` directly.

### Development

```bash
uv run fastapi dev
```

The application will be available at `http://localhost:8000` (or the configured port in `.env`).

### Production

```bash
uv run fastapi run
```

### Scripts

Migration and operations scripts live in [`scripts/`](scripts). Every one that
writes takes `--apply`; without it they report what they would do and change
nothing.

```bash
# Confirm an existing bcrypt hash validates. Run this before the auth cutover.
uv run python -m scripts.verify_password_hash --email owner@dileepa.dev

# Backfill v1 documents into the v2.0.0 shape. Run to completion before cutover.
uv run python -m scripts.migrate_v1_documents --apply

# Rewrite the blog rows off blog.dileepa.dev. Back up and restore-test first.
uv run python -m scripts.migrate_blog_urls
uv run python -m scripts.migrate_blog_urls --apply
uv run python -m scripts.rollback_blog_urls --apply   # if it has to be undone

# Convert events into sessions. The events collection is never modified.
uv run python -m scripts.migrate_events_to_sessions --apply

# Create or update an account. There is no /users endpoint by design.
uv run python -m scripts.create_user --email owner@dileepa.dev --apply
```

## API Documentation

>[!IMPORTANT]
> Swagger UI and JSON OpenAPI is disabled in production. It is only available in development mode.  

- Swagger UI at [`/api`](http://localhost:8000/api)
- ReDoc at [`/api/redoc`](http://localhost:8000/api/redoc)
- OpenAPI JSON at [`/api-json`](http://localhost:8000/api-json)

The generated spec is the machine-readable version of
[`api-contract.md`](https://github.com/dileepadev/dileepadev/blob/main/docs/architecture/api-contract.md).
`dileepa-dev` and `admin-dileepa-dev` generate their typed clients from it, so
when the two disagree the spec wins and the document gets corrected.

## Testing

```bash
uv run pytest                      # the suite
uv run pytest --cov                # with coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The suite runs entirely offline: no live API keys, no real MongoDB, no network.
Storage is behind a repository interface with an in-memory implementation, and
Resend and Cloudinary are faked at their boundaries. A test that needs a secret
is a test that is wrong.

## Versioning

This project follows a versioning pattern similar to [Semantic Versioning](https://semver.org/) (SemVer) for managing releases. For detailed versioning information, see the [VERSIONING.md](VERSIONING.md) file.

## Contributing

Contributions are welcome! Please read the following before contributing:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [BRANCH_NAMING_GUIDELINES.md](BRANCH_NAMING_GUIDELINES.md)
- [COMMIT_MESSAGE_GUIDELINES.md](COMMIT_MESSAGE_GUIDELINES.md)
- [PULL_REQUEST_GUIDELINES.md](PULL_REQUEST_GUIDELINES.md)

## Issues

For any issues or feature requests, please use the [issue templates](.github/ISSUE_TEMPLATE) provided in the repository. You can also check the [CHANGELOG.md](CHANGELOG.md) for updates and changes.

## Security

If you discover any security vulnerabilities, please report them as described in [SECURITY.md](SECURITY.md).

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

## API Endpoints

Reads are public unless noted. Writes need an `admin` role. Collection endpoints
return `{ "items": [...], "total": n, "limit": n, "offset": n }`; errors return
`{ "error": { "code": "...", "message": "...", "details": null } }`.

| Endpoint | Public | Admin | Notes |
| --- | --- | --- | --- |
| `POST /auth/login` | — | ✓ | Returns an access and a refresh token |
| `POST /auth/refresh` | — | ✓ | |
| `GET /auth/profile` | — | ✓ | The signed-in user |
| `GET /about` | ✓ | CRUD | Singleton — no id in any path |
| `GET /experiences` | ✓ | CRUD | |
| `GET /educations` | ✓ | CRUD | |
| `GET /tools` | ✓ | CRUD | |
| `GET /communities` | ✓ | CRUD | |
| `GET /videos` | ✓ | CRUD | |
| `GET /projects` · `GET /projects/{slug}` | ✓ | CRUD | **New in v2.0.0** |
| `GET /sessions` · `GET /sessions/{slug}` | ✓ | CRUD | **New in v2.0.0** — supersedes `/events` |
| `GET /blogs` · `GET /blogs/{slug}` | ✓ | CRUD | Reshaped |
| `POST /blogs/sync` | — | API key | The blog repo's pipeline |
| `POST /uploads` | — | ✓ or API key | Cloudinary-backed |
| `GET /uploads` · `DELETE /uploads/{publicId}` | — | ✓ | |
| `POST /contact` | ✓ | — | Rate-limited harder than anything else |
| `GET /health` | ✓ | — | 503 when MongoDB is unreachable |
| `GET /version` | ✓ | — | |

Every collection also takes `PATCH /{resource}/order` for bulk reordering, and
`POST` / `PATCH /{id}` / `DELETE /{id}` for admin writes. `PATCH` is a partial
update: only the fields sent are changed.

### Deprecated, removed in v2.1.0

These exist so nothing breaks mid-migration. All three send `Deprecation`,
`Sunset` and `Link: rel="successor-version"` headers.

| Endpoint | Successor |
| --- | --- |
| `GET /events` | `GET /sessions` — sessions projected into the v1 shape, as a bare array |
| `POST /auth/sign-in` | `POST /auth/login` |
| `POST /upload` | `POST /uploads` |

## Deployment

Deployed to [FastAPI Cloud](https://fastapicloud.com/) with `fastapi deploy`.
`FASTAPI_CLOUD_TOKEN` and `FASTAPI_CLOUD_APP_ID` come from
`fastapi cloud setup-ci`; application configuration is set with
`fastapi cloud env set`, using `--secret` for anything sensitive. Secrets there
are write-only, so keep the authoritative copy in a password manager, and note
that a configuration change needs a redeploy to take effect.

`api.dileepa.dev` is attached **after** the first successful deployment — a
domain cannot be reserved ahead of a running app — with Zero Downtime Migration
enabled, so the certificate is issued while Vercel is still serving traffic.

## Contact

For any inquiries or feedback, please reach out to me via [email](mailto:contact@dileepa.dev) or through my [website](https://dileepa.dev).

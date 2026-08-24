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
  - [Environments](#environments)
  - [Running the App](#running-the-app)
    - [Development](#development)
    - [Production](#production)
    - [Scripts](#scripts)
  - [API Documentation](#api-documentation)
  - [HTTP request files](#http-request-files)
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
- **Documentation:** OpenAPI, rendered by [Scalar](https://scalar.com/) in development only

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

3. Copy the template for the environment you are working in and fill it in:

   ```bash
   cp .env.development.example .env.development
   ```

   Real `.env.*` files are gitignored. See [Environments](#environments).

## Environments

Every environment has its own file, and **only one of them is ever read**.
`ENVIRONMENT` names it:

| `ENVIRONMENT` | File read | Template (committed) |
| --- | --- | --- |
| `development` (default) | `.env.development` | `.env.development.example` |
| `production` | `.env.production` | `.env.production.example` |
| `staging` | `.env.staging` | — |

Nothing merges. Each file is complete on its own, so the value in front of you
is the value in effect — there is no second file quietly overriding it and no
precedence order to remember. Values shared between environments are duplicated
across the files on purpose: that duplication is the price of never having to
work out which file won.

Real environment variables still beat the file, so exporting one for a single
command is always the last word:

```bash
MONGODB_DB=scratch uv run fastapi dev
ENVIRONMENT=production uv run fastapi run
```

`ENVIRONMENT` is the one value that has to come from the process environment,
because it is what chooses the file. Setting it to one thing in the file and
exporting another makes the app refuse to start rather than load the wrong
cluster's credentials.

> [!NOTE]
> A plain `.env` is not read by anything. If you have one from an earlier
> layout, copy it to `.env.development` and delete it.

**The production deployment reads none of these files.** FastAPI Cloud holds its
own configuration, set with `fastapi cloud env set` and `--secret`. These files
are a local-development convenience; `.env.production` is for rehearsing a
release on your own machine.

Production is also checked at startup. The app refuses to boot with a
placeholder `JWT_SECRET`, a localhost database, a wildcard `CORS_ORIGINS`, or an
empty `BLOG_SYNC_API_KEY`, and logs a warning for a short signing secret or a
missing Resend or Cloudinary credential. See
[`app/core/config.py`](app/core/config.py).

## Running the App

Run through the FastAPI CLI, not `uvicorn` directly.

### Development

```bash
uv run fastapi dev
```

The application will be available at `http://localhost:8000` (or the configured
`PORT`). It reads `.env.development` and nothing else, and the startup line
names the environment and the database it connected to — worth reading before
you assume which data you are looking at.

### Production

```bash
uv run fastapi run
```

To run production mode locally, fill in `.env.production` and export the
environment so that file is the one loaded:

```bash
ENVIRONMENT=production uv run fastapi run
```

### Scripts

Migration and operations scripts live in [`scripts/`](scripts). Every one that
writes takes `--apply`; without it they report what they would do and change
nothing.

Each run prints the environment and the database it is about to open before it
touches anything:

```text
  ENVIRONMENT  production
  DATABASE     cluster0.example.mongodb.net/dileepa
  MODE         APPLY — writing changes
```

Applying against production additionally makes you type the database name back.
Pass `--yes` to skip that in a scripted run — and only then, since a script that
cannot be asked refuses rather than assuming consent.

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
> The reference and the OpenAPI JSON are both disabled in production. They are
> only available in development.

- API reference at [`/docs`](http://localhost:8000/docs), rendered by
  [Scalar](https://scalar.com/)
- OpenAPI JSON at [`/api-json`](http://localhost:8000/api-json)

Scalar replaces Swagger UI and ReDoc, which are both switched off. It loads its
bundle from a CDN, so `/docs` is served with its own Content-Security-Policy
allowing exactly that origin — the rest of the API keeps `default-src 'none'`.
Pin a different bundle with `SCALAR_JS_URL` if the CDN is not acceptable.

The generated spec is the machine-readable version of
[`api-contract.md`](https://github.com/dileepadev/dileepadev/blob/main/docs/architecture/api-contract.md).
`dileepa-dev` and `admin-dileepa-dev` generate their typed clients from it, so
when the two disagree the spec wins and the document gets corrected.

## HTTP request files

[`http/`](http) holds runnable requests for every endpoint, one file per router
module, for the VS Code [REST Client][rest-client] extension. Open a `.http`
file, pick the `development` or `production` environment in the status bar, and
send. Credentials are read from your shell, so nothing secret is committed.

[rest-client]: https://marketplace.visualstudio.com/items?itemName=humao.rest-client

They complement the test suite rather than repeat it: the suite proves the logic
offline, these exercise a real server over the wire. Each file ends with the
failure cases worth re-running after touching auth, validation or the error
envelope. [`http/README.md`](http/README.md) has the details, and
`tests/test_http_files.py` fails if a route ever has no request.

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
| `GET /` | ✓ | — | What this service is, and where the docs are |
| `GET /docs` | ✓ | — | The API reference. **Development only** |

Every collection also takes `PATCH /{resource}/order` for bulk reordering, and
`POST` / `PATCH /{id}` / `DELETE /{id}` for admin writes. `PATCH` is a partial
update: only the fields sent are changed.

### Removed from v1

v2.0.0 ships as a single cutover — the API and every consumer released
together — so there are no deprecated aliases and nothing waiting to be dropped
in a later version. These v1 paths return `404`; move callers to the successor.

| v1 endpoint | Successor |
| --- | --- |
| `GET /events` | `GET /sessions` — an `{ items, total, limit, offset }` envelope, not a bare array |
| `POST` `PATCH` `DELETE /events` | The equivalent `/sessions` route |
| `POST /auth/sign-in` | `POST /auth/login` — same body, same token shape |
| `POST /upload` | `POST /uploads` |
| `GET /upload` | `GET /uploads` |
| `DELETE /upload/{publicId}` | `DELETE /uploads/{publicId}` |

`tests/contract/test_v1_parity.py` records every one of these with its reason,
and fails if a v1 route is neither served nor listed there.

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

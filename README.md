# api.dileepa.dev

This is the API for Dileepa's personal website ([dileepa.dev](https://dileepa.dev)), built with [FastAPI](https://fastapi.tiangolo.com/). It provides the data behind the main site, the admin dashboard, and the blog sync pipeline.

**Production:** `https://api.dileepa.dev` — health check at
[`/health`](https://api.dileepa.dev/health).

> [!NOTE]
> v2.0.0 replaced the NestJS API with this one, and the cutover is complete.
> `api.dileepa.dev` is served by FastAPI Cloud; the NestJS `src/` tree, the Node toolchain and
> the Vercel deployment are all gone. See [Deployment](#deployment) for how it is deployed and
> [TODO.md](TODO.md) for what remains before the release is closed out.

## Table of Contents

- [api.dileepa.dev](#apidileepadev)
  - [Table of Contents](#table-of-contents)
  - [Tools and Technologies](#tools-and-technologies)
  - [Installation](#installation)
  - [Environments](#environments)
  - [Running the App](#running-the-app)
    - [`fastapi dev` and `fastapi run` are both local, and both development](#fastapi-dev-and-fastapi-run-are-both-local-and-both-development)
    - [Actually running as production](#actually-running-as-production)
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
    - [Removed from v1](#removed-from-v1)
  - [Deployment](#deployment)
    - [One app, one environment](#one-app-one-environment)
    - [Deploying](#deploying)
    - [Cutover status — done](#cutover-status--done)
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
   git clone https://github.com/dileepadev/api-dileepa-dev.git
   cd api-dileepa-dev
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

### `fastapi dev` and `fastapi run` are both local, and both development

The CLI command picks how the **server** runs. `ENVIRONMENT` picks which
**configuration** loads. They are independent, and only the second one decides
which database you are talking to:

```bash
uv run fastapi dev    # reload on;  ENVIRONMENT unset -> .env.development
uv run fastapi run    # reload off; ENVIRONMENT unset -> .env.development
```

`fastapi run` prints **"Starting FastAPI in production mode"**. That is the CLI
describing itself — no reload, production-shaped server — and it is not a
statement about your data. With `ENVIRONMENT` unset it is still reading
`.env.development` and still connected to the development database.

So the banner the application prints immediately below it is the one to read:

```text
──────────────────────────────────────────────────────────────────
  api.dileepa.dev 2.0.0

  Environment  development
  Database     cluster0.example.mongodb.net/development
  Docs         enabled at /docs
  Copy source  cluster0.example.mongodb.net/production

  ENVIRONMENT is 'development', so this process is not
  connected to production. Any "production mode" line above it is
  the FastAPI CLI describing the server, not this configuration.
──────────────────────────────────────────────────────────────────
```

The application is then available at `http://localhost:8000` (or the configured
`PORT`).

### Actually running as production

Fill in `.env.production` and export the environment, which is what selects the
file. Nothing else does:

```bash
ENVIRONMENT=production uv run fastapi run
```

The banner says `PRODUCTION` and that writes are live, `/docs` and `/api-json`
are gone, and the `/maintenance/*` routes are not registered at all. A
production process whose configuration is wrong refuses to start rather than
serving traffic — see `production_problems` in
[`app/core/config.py`](app/core/config.py).

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

# Recompute blogs.commentCount from the comments. Safe to run any time: it only
# writes a number it has just derived. This is also the backfill.
uv run python -m scripts.reconcile_comment_counts
uv run python -m scripts.reconcile_comment_counts --apply

# Rewrite the v1 events into the v2 shape, in place. Originals are copied to
# events_v1_backup first, so this is reversible.
uv run python -m scripts.migrate_events_v1_to_v2 --apply

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
| `GET /pillars` | ✓ | CRUD | **New in v2.0.0** — the six cards in the site's About section |
| `GET /speaking-topics` | ✓ | CRUD | **New in v2.0.0** — the talk themes on the site's speaker kit |
| `GET /projects` · `GET /projects/{slug}` | ✓ | CRUD | **New in v2.0.0** |
| `GET /events` · `GET /events/{slug}` | ✓ | CRUD | **Reshaped in v2.0.0** — same path, new model |
| `GET /blogs` · `GET /blogs/{slug}` | ✓ | CRUD | Reshaped |
| `POST /blogs/sync` | — | API key | The blog repo's pipeline |
| `GET /blogs/{slug}/engagement` | ✓ | — | View and reaction counts, plus this caller's own reaction |
| `POST /blogs/{slug}/views` | ✓ | — | De-duplicated per reader per 24h |
| `POST /blogs/{slug}/reactions` | ✓ | — | Set, change, or clear one reaction |
| `GET /blogs/{slug}/comments` | ✓ | — | The thread. **Never returns a commenter's email** |
| `POST /blogs/{slug}/comments` | ✓ | — | Live immediately; rate-limited and honeypotted |
| `POST /blogs/{slug}/comments/{id}/reactions` | ✓ | — | Same four reactions; works on replies too |
| `GET /comments` | — | ✓ | The moderation queue. **Not public** — it holds emails |
| `POST /comments` | — | ✓ | The owner's own reply, badged as the author |
| `PATCH /comments/{id}` · `DELETE /comments/{id}` | — | ✓ | Hide (reversible) or delete (permanent) |
| `POST /uploads` | — | ✓ or API key | Cloudinary-backed |
| `GET /uploads` · `DELETE /uploads/{publicId}` | — | ✓ | |
| `POST /contact` | ✓ | — | Rate-limited harder than anything else |
| `GET /api-links` | — | ✓ | The endpoint catalogue the admin renders. **New in v2.0.0** |
| `GET /health` | ✓ | — | 503 when MongoDB is unreachable |
| `GET /version` | ✓ | — | |
| `GET /` | ✓ | — | What this service is, and where the docs are |
| `GET /docs` | ✓ | — | The API reference. **Development only** |
| `GET /status` | — | ✓ | Environment, version and database — the admin header's status badge |
| `GET /maintenance/database` | — | ✓ | Both databases and their counts. **Development only** |
| `POST /maintenance/database/copy` | — | ✓ | Replace this database with a copy of the source. **Development only** |
| `POST /maintenance/database/clear` | — | ✓ | Empty this database. **Development only** |

Every collection also takes `PATCH /{resource}/order` for bulk reordering, and
`POST` / `PATCH /{id}` / `DELETE /{id}` for admin writes. `PATCH` is a partial
update: only the fields sent are changed.

**Development only** means the route is not registered at all when
`ENVIRONMENT=production` — `api.dileepa.dev` answers `404`, not `403`. For the
three `/maintenance` routes that is deliberate and load-bearing: they empty the
database the process is pointed at, and the strongest thing that can be said
about them on the production API is that they are not on it. See
[`app/routers/maintenance.py`](app/routers/maintenance.py) for the other four
guards, and `SOURCE_MONGODB_URI` in
[`.env.development.example`](.env.development.example) for the read-only Atlas
user the copy should read through.

Every collection also serves a single record at `GET /{resource}/{id}`. Where a
resource carries a slug the same route accepts either, which is why the rows
above name `{slug}` for projects, events and blogs and the seven profile
collections take an id. `/about` is the exception in both directions: it is a
singleton, so it has no id and no single-record route of its own.

`GET /api-json` serves the OpenAPI document behind `/docs`. Like the reference
itself it is registered only outside production.

**`order` sorts descending — higher values first.** The semantic every resource
inherited from v1's `index: -1`. An admin screen showing positions 1..N maps the
top row to the *highest* number; the admin does that inversion in one place
rather than the API changing a convention seven collections depend on.

**Engagement and comments are the only public writes** besides the contact form.
Neither collects an identity: both key on a salted hash of the caller's address,
which is enough to recognise a repeat and not enough to reconstruct who it was.
Detail in [`dileepadev/docs/architecture/api-contract.md`](https://github.com/dileepadev/dileepadev/blob/main/docs/architecture/api-contract.md).

### Removed from v1

v2.0.0 ships as a single cutover — the API and every consumer released
together — so there are no deprecated aliases and nothing waiting to be dropped
in a later version. These v1 paths return `404`; move callers to the successor.

| v1 endpoint | Successor |
| --- | --- |
| `GET /events` | Same path. An `{ items, total, limit, offset }` envelope rather than a bare array, over the v2 model |
| `POST` `PATCH` `DELETE /events/{id}` | The same verbs against `/events/{slug}` |
| `POST /auth/sign-in` | `POST /auth/login` — same body, same token shape |
| `POST /upload` | `POST /uploads` |
| `GET /upload` | `GET /uploads` |
| `DELETE /upload/{publicId}` | `DELETE /uploads/{publicId}` |

`tests/contract/test_v1_parity.py` records every one of these with its reason,
and fails if a v1 route is neither served nor listed there.

## Deployment

Deployed to [FastAPI Cloud](https://fastapicloud.com/) with `fastapi deploy`.
The CLI ships with `fastapi[standard]` — `fastapi-cloud-cli` is already in the
locked dependencies, so CI needs no extra install step.

### One app, one environment

**FastAPI Cloud has no preview deployments.** Per-pull-request environments are
not supported, and its GitHub integration only ever deploys the repository's
default branch — pushes to any other branch are ignored. There is no staging
copy of this service.

Every app does get a default `https://<app>.fastapicloud.dev` URL with TLS, live
the moment a deploy finishes, and that is what the build was verified against
before the domain was pointed at it. Once the custom domain is attached, that
default URL stops being the address to use — `https://api.dileepa.dev` is the
production endpoint, and the health check is
[`https://api.dileepa.dev/health`](https://api.dileepa.dev/health).

### Deploying

This repository does **not** use the GitHub integration. It deploys through
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml), which uses a
deploy token and runs on every push to `main`. `main` is the release branch, so
a merge into it is a release and the deploy follows it rather than waiting on
someone to press a button.

`workflow_dispatch` is kept for the redeploy a commit cannot trigger:
application configuration lives in FastAPI Cloud, not in this repository, so a
`fastapi cloud env set` takes effect only on the next deploy and leaves nothing
here to push. A `concurrency` group serialises runs — there is one app and one
environment, so two deploys at once would race on the same target, and a
queued deploy is better than a half-written one.

`FASTAPI_CLOUD_TOKEN` and `FASTAPI_CLOUD_APP_ID` come from
`fastapi cloud setup-ci`, which writes both repository secrets. Pass
`--branch` if the deploy branch should not be `main`. Both are set, and the
workflow has run green end to end from Actions.

The job declares `environment: production`, and that is the **only** deployment
environment this repository uses. The name is not cosmetic: GitHub's
[Deployments](https://github.com/dileepadev/api-dileepa-dev/deployments) page
groups by environment name, so a second name would split one service's history
across two headings. The workflow is also the only thing that writes a
deployment record — a `fastapi deploy` from a terminal deploys the app but
creates no entry there.

Application configuration is separate from those two, and is set with
`fastapi cloud env set`, using `--secret` for anything sensitive. Those values
are write-only once set, so keep the authoritative copy in a password manager.
**A configuration change needs a redeploy to take effect.**

### Cutover status — done

`api.dileepa.dev` is served by FastAPI Cloud. The certificate was issued by
Google Trust Services, and the Vercel deployment no longer receives traffic.

Verified against the live domain:

| Check | Result |
| --- | --- |
| `GET /health` | `{"status":"ok","checks":{"database":"up"}}` |
| `GET /version` | `2.0.0`, `production`, `fastapi` |
| Security headers | All eight present |
| `/docs`, `/api-json`, `/openapi.json`, `/redoc` | `404` — unregistered in production |
| CORS | An unlisted origin receives no `Access-Control-Allow-Origin` |
| Rate limiting | `429` with `Retry-After` past 60 requests a minute |
| Content | 18 blogs, 26 events, 9 communities, 8 tools, 6 videos, 4 experiences, 4 educations |

The `production` database was empty at cutover; every document was in
`development`, already migrated. It was populated by copying that database
across — 149 documents, 15 collections, `_id`s preserved, indexes recreated,
and `development` left unmodified so it remains a byte-for-byte fallback. The
three migration scripts were therefore never run against `production`; each
outcome they exist to produce was verified against the live API instead.

These were the steps, in the order they had to happen.

| # | Step | Why it is here |
| --- | --- | --- |
| 1 | Restore-tested MongoDB backup | `migrate_blog_urls.py` rewrites live rows |
| 2 | `scripts/migrate_v1_documents.py` against production | Every ported collection lacks `published`, `order`, `meta` and timestamps; sorting happens in MongoDB, so a half-migrated collection sorts wrongly |
| 3 | `migrate_events_v1_to_v2.py`, then `migrate_blog_urls.py` | Originals are copied to `events_v1_backup` first; both are idempotent |
| 4 | `scripts/verify_password_hash.py` against production | The test suite pins a hash generated here; this checks the owner's real one |
| 5 | `fastapi cloud env set` for every value in `.env.production.example` | A missing one either fails startup or degrades a feature |
| 6 | Deploy, and verify on the `.fastapicloud.dev` URL | The only chance to check the build against real data before it is the live API |
| 7 | Attach `api.dileepa.dev` with **Zero Downtime Migration** | The certificate is issued before traffic switches |
| 8 | Confirm both consumers, then delete the Vercel project | The site and the admin are the real acceptance test |

Steps 1 to 4 were satisfied by the copy described above rather than by running
the scripts. A domain cannot be reserved ahead of a running app, which is why
step 7 could not move earlier; the subdomain is a `CNAME` at `api` pointing to
the value FastAPI Cloud shows for the app. There was no rollback target once
the domain moved — the Vercel deployment was already paused — so step 8's
confirmation is what closes the migration out.

Startup refuses a misconfigured production: a placeholder `JWT_SECRET`, a
localhost `MONGODB_URI`, a wildcard `CORS_ORIGINS` or an empty
`BLOG_SYNC_API_KEY` each abort the boot rather than serve traffic. See
[`app/core/config.py`](app/core/config.py).

## Contact

For any inquiries or feedback, please reach out to me via [email](mailto:contact@dileepa.dev) or through my [website](https://dileepa.dev).

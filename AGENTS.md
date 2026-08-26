# AGENTS.md

Canonical instructions for AI coding agents working in this repository.

> This file is the **single source of truth**. `CLAUDE.md` and
> `.github/copilot-instructions.md` intentionally contain only tool-specific notes and point
> back here. Add shared rules **here only** — duplicating them causes drift and contradictory
> guidance.

## What this is

`api-dileepa-dev` is the backend at **[api.dileepa.dev](https://api.dileepa.dev)** — the data
source for the main website, the admin dashboard, and the blog sync pipeline.

Today it is **NestJS 11 + Mongoose + MongoDB**, deployed as Vercel serverless functions.
v2.0.0 migrates it to **FastAPI on Python 3.13**, and extends the data model with two new
resource — `projects` — plus reshaped `events` and `blogs`, the latter for a blog that now lives on
the main website instead of its own host.

This is an architectural migration, not a framework swap.

Currently on branch `feat/v2.0.0`. Version `1.2.0`; the target is `2.0.0`.

[TODO.md](TODO.md) holds this repo's slice. Issue **#13** holds the full scope. The
cross-repository roadmap lives in `dileepadev/TODO.md`.

## Layout

Both stacks are in the repository. `app/` is the FastAPI application, `src/` is the NestJS one
still serving production. Write new code in `app/`; touch `src/` only to keep production
working until the cutover.

### `app/` — FastAPI (v2.0.0)

| Path | What it holds |
| --- | --- |
| `app/main.py` | The application: lifespan, middleware, routers. The FastAPI CLI entrypoint |
| `app/core/config.py` | **Every** environment variable. Nothing else reads `os.environ` |
| `app/core/errors.py` | `ApiError` and the handlers producing `{ error: { code, message, details } }` |
| `app/core/security.py` | Password hashing and JWTs. The only module that knows about tokens |
| `app/core/deps.py` | Auth dependencies and the repository providers |
| `app/core/db.py` | The MongoDB client, collection names, and index creation |
| `app/models/` | Pydantic request and response models, camelCase on the wire |
| `app/repositories/` | `DocumentRepository`, with a Mongo and an in-memory implementation |
| `app/routers/crud.py` | The CRUD router factory the five ported resources are built from |
| `app/routers/` | One module per resource |
| `app/services/` | Resend and Cloudinary, the two outbound integrations, plus `reactions.py` — the toggle rule posts and comments share |
| `scripts/` | Migration and operations scripts. Every writer takes `--apply` |
| `tests/` | Offline suite. `tests/contract/` holds the v1 parity baseline |
| `http/` | Runnable requests, one file per router module. VS Code REST Client |

A resource with no behaviour of its own is a `crud_router(...)` call in
`app/routers/profile.py` and nothing else. Give it its own module when it needs something the
others do not — do not add a flag to the factory.

### `src/` — NestJS (v1.2.0, still serving production)

| Path | Status |
| --- | --- |
| `src/auth/` | JWT + local Passport strategies, RBAC guards, API-key guard |
| `src/users/` | User schema and service, bcrypt hashes |
| `src/{about,experiences,educations,tools,communities,videos}/` | Straight CRUD modules |
| `src/blogs/` | Includes `POST /blogs/sync`, upsert-by-slug, API-key guarded |
| `src/events/` | Thin. Reshaped in place under `app/routers/events.py`; the path is unchanged |
| `src/contact/` · `src/upload/` | Contact form via Resend; image upload |
| `src/common/filters/` | HTTP exception filter |

## Toolchain

**Current (NestJS):**

- Node + npm. `npm install`, then `npm run start:dev` (watch mode, port 3000).
- `npm run build` · `npm run start:prod` · `npm run lint` · `npm run test`
- Swagger UI at `/api`, OpenAPI JSON at `/api-json` — **development only**, disabled in
  production. Keep it that way. (FastAPI serves the reference at `/docs` instead; see below.)
- `.env.development` from `.env.development.example`.

**Target (FastAPI, v2.0.0):**

- Python 3.13 managed with `uv`. `uv sync`, then `uv run <cmd>`. Never `pip install`.
- Run with the FastAPI CLI, not `uvicorn` directly: `uv run fastapi dev` while developing,
  `uv run fastapi run` to serve.
- FastAPI **0.141.x**, Pydantic **2.13.x**, Uvicorn **0.52.x**.
- Passwords are hashed with **`pwdlib`**, not `passlib` — see Gotchas.
- The API reference is rendered by **Scalar** at `/docs`; Swagger UI and ReDoc are both off.
  The reference and the OpenAPI JSON at `/api-json` are **development only** — in production
  neither is registered, so the page cannot be reached and the spec it reads is not served.
- `ruff` for lint and format, `mypy` for types, `pytest` + `httpx` for tests.
- Async MongoDB driver against the **same cluster and the same collections**. No re-seed.
- **One env file per environment, and only one is ever read.** `ENVIRONMENT`
  names it: `.env.development`, `.env.production`, `.env.staging`. Nothing
  merges and there is no shared base — each file is complete, and values common
  to both are duplicated on purpose so no one has to work out which file won.
  A plain `.env` is read by nothing. Real environment variables still beat the
  file. `ENVIRONMENT` itself must come from the process environment, because it
  is what selects the file; a file that disagrees with it makes the app refuse
  to start. Deployments read no file at all. See `app/core/config.py`.
- **`Settings` resolves its env file in `__init__`, not in `model_config`.**
  `model_config` is evaluated once when the class is defined, which would bake
  in whatever `ENVIRONMENT` was at import time. Do not "simplify" it back.

Run both stacks side by side during the migration. Do not delete `src/` until both consumers
are verified against FastAPI in production and a rollback window has passed.

## Coding standards

- Match the style already in the file you're editing.
- Comments explain *why*, not *what*.
- Validation at the boundary — `class-validator` DTOs today, Pydantic models in v2.0.0. Never
  trust a request body that hasn't been through a model.
- Never return a raw Mongoose or Motor document. Map to a response model; a schema change must
  not silently become an API change.
- Errors are structured, not strings. v2.0.0 standardises on
  `{ error: { code, message, details } }` across every endpoint.
- List endpoints share one envelope and one pagination shape. Do not invent a second.
- Only the auth layer knows about tokens. Nothing downstream should parse a JWT.
- Every endpoint is documented — decorators today, docstrings and response models in FastAPI.

## Testing

- FastAPI: `uv run pytest`. NestJS: `npm run test` (Jest, `*.spec.ts`), `npm run test:e2e`.
- **The parity baseline lives in `tests/contract/test_v1_parity.py`.** It lists every v1.2.0
  route and fails if one is neither served nor recorded in `INTENTIONALLY_DROPPED` with a
  reason. Add to that dict deliberately; never to make a test pass.
- Keep tests offline. No live API keys, no real MongoDB, no network in a unit test. Storage is
  behind `DocumentRepository`, so tests use `InMemoryRepository`; Resend and Cloudinary are
  faked at their boundaries.
- When overriding a dependency in a test, the override must take **no parameters**. FastAPI
  reads a parameter default as a request field and Pydantic deep-copies it, so
  `lambda repo=repo: repo` silently hands every request its own copy.
- Auth is the highest-risk area — test token issue, refresh, expiry, and role enforcement
  explicitly, not incidentally.
- The suite sets `DOTENV_DISABLED=1` before importing the app. That is what keeps it offline
  on a machine with a populated `.env.development`; do not remove it to "make a test see real
  config".
- **`http/` is checked, not decorative.** `tests/test_http_files.py` fails if a route exists
  with no request in `http/`, and if `http/*.http` stops mirroring `app/routers/*.py`. A new
  endpoint gets its request in the same commit, like the README's endpoint table.

## Docs

- `README.md` carries the endpoint table. It must match reality; `tests/test_openapi.py` and
  `tests/contract/test_v1_parity.py` catch the code drifting, but not the README.
- Update the endpoint table and the data models in the same commit as the code.
- The generated OpenAPI spec is the machine-readable contract. When it and
  `dileepadev/docs/architecture/api-contract.md` disagree, the spec wins and the document gets
  corrected — not the other way round.
- `CHANGELOG.md` gets categorised entries at release time.

## Git workflow

- Branches: [BRANCH_NAMING_GUIDELINES.md](BRANCH_NAMING_GUIDELINES.md). `main` and `dev` are
  protected; never commit to them directly.
- Commits: [COMMIT_MESSAGE_GUIDELINES.md](COMMIT_MESSAGE_GUIDELINES.md) — if the work traces to
  a GitHub issue, reference it (`fixes #12`, `refs #12`); don't invent an issue number if none
  was given. v2.0.0 work traces to `refs #13`.
- PRs: [PULL_REQUEST_GUIDELINES.md](PULL_REQUEST_GUIDELINES.md)
- Versioning: [VERSIONING.md](VERSIONING.md) — SemVer.

## Secrets

- Real values live in `.env.<environment>`, all gitignored. The `.env.*.example` templates
  are committed and carry no real values. Never invert that.
- Nothing secret goes in `.vscode/settings.json`, which **is** committed. The REST Client
  environments there read credentials from the shell with `{{$processEnv …}}`.
- This repo holds the most sensitive configuration in the platform: `MONGODB_URI`,
  `JWT_SECRET`, `CLOUDINARY_API_SECRET`, `RESEND_API_KEY`, `BLOG_SYNC_API_KEY`. Treat every one
  as production-critical. (`SWAGGER_PASSWORD` is gone: FastAPI serves its own docs, and they
  stay disabled in production rather than password-protected.)
- **`JWT_SECRET`, `JWT_ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` must match the NestJS
  deployment through the cutover**, or every existing session is invalidated the moment traffic
  moves.
- Never log a secret, a token, or a full request body containing credentials.
- `CORS_ORIGINS` is an allowlist. Do not widen it to `*` to make something work locally.

## Gotchas

- **`projects` is net-new**, and now built end to end — API, admin screen, and site routes.
- **Comments are the one collection `crud_router` cannot build.** That helper's list route is
  public by design, and `/comments` holds email addresses, so its routes are written out with
  `CurrentUser` on every one of them, the list included. If you add a collection holding anything
  a person gave in confidence, check which door you are opening before reaching for the factory.
- **Engagement counters are server-owned.** `views` and `reactions` are absent from `BlogCreate`,
  `BlogUpdate` and `BlogSync` on purpose, so an admin edit or a content re-sync cannot overwrite
  them. `/blogs/sync` writes with `$set` over the fields it sends — adding one of these to that
  model would silently zero a counter on the next push.
- **`events` is far thinner than it looks** — `title`, `date` (string), `location`, `format`,
  `description`, `url`, `index`. No speakers, photos, recordings, slug, status, or structured
  time. `events` keeps its path and its collection name, and is a new model rather than a rename.
- **Blog rows store absolute `blog.dileepa.dev` URLs** in `link` and `bannerUrl`, written by the
  blog repo's sync script. All 18 become wrong when the blog moves. The rewrite is destructive:
  take a **verified, restore-tested backup**, dry-run first, and keep old values in a `legacy`
  field for one release.
- **Dates are strings everywhere in v1** — `event.date`, `blog.date`, `video.date`,
  `community.period`. Sorting and filtering do not work the way you'd assume. Events and blogs
  use real datetimes in v2.0.0; videos and communities keep their strings, because nothing sorts
  on them.
- **`scripts/migrate_v1_documents.py` runs to completion before traffic moves.** The API reads
  `index` as `order` and treats a missing `published` as published, so it is correct against an
  untouched database — but sorting happens in MongoDB, before that aliasing. A half-migrated
  collection sorts v2 documents above v1 ones.
- **bcrypt compatibility was the hard cutover risk, and it is settled.** Node `bcrypt` hashes
  validate under **`pwdlib[bcrypt]`**, verified against real Node output at cost 10 and 12, for
  both `$2a$` and `$2b$` prefixes. `pwdlib` is used rather than the `passlib[bcrypt]` this file
  originally named: passlib has been unmaintained since 2020 and breaks against bcrypt >= 4.1,
  and `pwdlib` is what the FastAPI security documentation now uses. Hashes are configured
  argon2id-first, so a legacy hash verifies and is rewritten on the next successful sign-in. No
  password reset is needed. `tests/test_auth.py` pins this against a real hash, and
  `scripts/verify_password_hash.py` checks a live account before cutover — **run it against the
  production database before moving traffic.**
- **Cloudinary is the image backend.** Azure Blob Storage is retired: it is gone from the
  FastAPI application, the README and the env templates. It still appears in stored URLs, which the
  blog image migration replaces separately.
- **Only `blogs` has a `slug`.** Nothing else has a stable public identifier. New resources
  (`projects`, `events`) must have one, unique and indexed.
- **The docs page has its own Content-Security-Policy.** Scalar loads its bundle from a CDN,
  and the API-wide `default-src 'none'` blanks the page. `_docs_csp()` in
  `app/core/rate_limit.py` allows exactly that one origin — do not "fix" a blank docs page by
  exempting the path from CSP altogether.
- **Production refuses to start when it is misconfigured.** `Settings.production_problems()`
  blocks a placeholder `JWT_SECRET`, a localhost database, a wildcard `CORS_ORIGINS`, and an
  empty `BLOG_SYNC_API_KEY`; `production_warnings()` only logs. The split matters:
  `JWT_SECRET` **length** is a warning on purpose, because the secret has to keep matching
  the NestJS deployment through the cutover and refusing the boot over it would take
  production down to fix a weakness that predates this service. The check runs in the
  lifespan, not in a validator, so tests can still build a production-shaped `Settings`.
- **The operations scripts confirm before writing to production.** `scripts/_common.py`
  prints the environment and database, then makes the operator type the database name back.
  `--yes` skips it for scripted runs; a non-interactive run without `--yes` refuses rather
  than assuming consent.
- **The rate limiter needs `RouterAwareSlowAPIMiddleware`, not slowapi's own.** slowapi finds a
  request's handler by walking `app.routes` for something with an `.endpoint`, but since
  FastAPI 0.141 `include_router` keeps routers nested as `_IncludedRouter`, which has none. It
  found nothing, treated every routed request as exempt, and applied `RATE_LIMIT_DEFAULT` to
  nothing — `/auth/login` included. It fails **open and silently**: no 429, no `X-RateLimit-*`.
  Per-route `@limiter.limit` decorators check inside the endpoint and were never affected,
  which is why `/contact` kept working and hid it. Related: the limiter is built with
  `key_style="endpoint"`, because slowapi's `url` default gives every distinct path its own
  budget and makes the limit on any parameterised route bypassable by varying the parameter.
  Build limiters through `make_limiter()` so tests share the real configuration.
- **Indexes are reconciled by key pattern, not by name.** Mongoose named the indexes it
  created after the field — `users.email_1`, `blogs.slug_1` — and both are already unique.
  Mongo rejects a second index over the same keys under a different name with
  `IndexOptionsConflict`, so `create_index` is not the no-op it looks like: against the real
  cluster it threw on every startup. `ensure_indexes` matches on the key pattern and reuses
  whatever is there. Do not "fix" a name mismatch by renaming or dropping a live unique index.
  An existing index that is *not* unique where the API needs one is a different matter and is
  warned about loudly — Mongo cannot add the constraint to an index that already exists.
- **There are no deprecated aliases, and no transitional surface.** v2.0.0 is a single
  cutover: the API and every consumer are released together, so `GET /events`,
  `POST /auth/sign-in` and `POST /upload` are gone rather than carried. Do not reintroduce one
  to make a consumer work — retarget the consumer. `tests/test_openapi.py` fails if any
  operation is published with `deprecated: true`, and `tests/contract/test_v1_parity.py`
  records each dropped v1 route with its successor.

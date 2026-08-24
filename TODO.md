# TODO

This file tracks tasks, improvements, and features planned for upcoming updates or releases of
this repository.

> [!NOTE]
> This is this repository's slice of the v2.0.0 migration. The cross-repository roadmap lives in
> [`dileepadev/TODO.md`](https://github.com/dileepadev/dileepadev/blob/main/TODO.md), and the full
> scope for this repo is in
> [issue #13](https://github.com/dileepadev/api-dileepa-dev/issues/13).

## v2.0.0 — NestJS to FastAPI

The backend moves from NestJS 11 on Vercel serverless to FastAPI on Python 3.13, hosted on
FastAPI Cloud, and gains two new resources. Architecture and rules are in [AGENTS.md](AGENTS.md).

This is an architectural migration, not a framework swap.

> [!WARNING]
> **This repository blocks both frontends.** Keep NestJS live and serving until FastAPI is
> verified in production. Do not delete `src/` to feel finished.

### Baseline ✅

- [x] Scaffold FastAPI 0.141.x on Python 3.13, managed with `uv` — `uv sync`, never `pip install`
- [x] `ruff` for lint and format, `mypy` for types, `pytest` + `httpx` for tests
- [x] Run through the FastAPI CLI — `uv run fastapi dev` and `uv run fastapi run`, not `uvicorn`
- [x] Async MongoDB driver against the **same cluster and the same collections**. No re-seed
- [x] Write contract tests against the current NestJS responses **first** — that is the parity
      baseline. `tests/contract/test_v1_parity.py` lists every v1.2.0 route and fails if one is
      neither served nor recorded as deliberately dropped, with a reason
- [ ] Stand FastAPI up alongside NestJS on a preview deployment

### Contract gaps — closed ✅

All four are decided and implemented; `api-contract.md` §10 records them.

- [x] **`/users` endpoints — there are none.** Accounts are seeded with
      `scripts/create_user.py`, run against the database directly. v1 never had a users endpoint
      either: `UsersService` only looked a user up by email. This is a single-owner platform, and
      user CRUD would be attack surface next to the password hashes for no benefit.
      `GET /auth/profile` covers "who am I"
- [x] **Admin write paths — `POST /{resource}`, `PATCH /{resource}/{id}`, `DELETE
      /{resource}/{id}`.** `PATCH` is a partial update: only the fields sent are changed. `about`
      is a singleton, so its writes take no id. Reads accept an id or a slug wherever a resource
      has one
- [x] **Reordering — bulk.** `PATCH /{resource}/order` takes `{ items: [{ id, order }] }`, one
      request per drag-and-drop commit. Declared before `/{id}` so `order` is not read as an id
- [x] **`draft` versus `published` — `published` gates visibility**, on blogs as on every other
      resource. `draft` is front-matter provenance. `/blogs/sync` maps `published = not draft` and
      refuses a `published` field in the body, so the front matter stays the one place an author
      decides whether a post is live

### Auth — the highest cutover risk

> [!WARNING]
> Getting this wrong locks the owner out of their own admin. Test before committing to the approach.

- [x] **Validate a real bcrypt hash under the chosen library.** Node `bcrypt` output verifies at
      cost 10 and 12, for both `$2a$` and `$2b$`. The library is **`pwdlib[bcrypt]`**, not
      `passlib[bcrypt]`: passlib has been unmaintained since 2020 and breaks against
      bcrypt >= 4.1. Configured argon2id-first, so a legacy hash verifies and is rewritten on the
      next successful sign-in. **No password reset is needed.** Pinned in `tests/test_auth.py`
- [ ] **Run `scripts/verify_password_hash.py` against the production database** before traffic
      moves. The test pins a hash generated here; this checks the owner's real one
- [x] JWT access + refresh; signing algorithm, secret handling and claim names (`sub`, `email`,
      `roles`) match v1 exactly. A token minted by NestJS carries no `type` claim and is read as
      an access token, so live sessions survive the cutover
- [x] Role-based dependency guards mirroring the current RBAC
- [x] API-key guard for `/blogs/sync` — same `x-api-key` header and environment variable as v1,
      so the blog repo's workflow needs no change
- [x] Test token issue, refresh, expiry, and role enforcement explicitly, not incidentally
- [ ] Rehearse the whole flow on staging before production

### Port existing modules

- [x] `users` · `auth`
- [x] `about` · `experiences` · `educations` · `tools` · `communities` · `videos`
- [x] `contact` (Resend) · `uploads` (Cloudinary)
- [x] Rate limiting via `slowapi`, security headers, CORS allowlist — never widen `CORS_ORIGINS`
      to `*`. Vercel preview hostnames are matched by pattern rather than enumerated
- [x] One list and pagination envelope; one error envelope `{ error: { code, message, details } }`
- [x] `GET /health`, `GET /version`. `/health` returns 503 when MongoDB is unreachable
- [x] Remove the second image backend — Cloudinary stays, Azure Blob code and config go

### New and changed resources

- [x] **`/projects`** — full model, CRUD, filters. Net-new; nothing existed
- [x] **`/sessions`** — speakers, photos, recordings, links, structured datetimes, slug, status.
      `status` is derived from `startAt` rather than stored, with an explicit `cancelled`
      respected; a field a human has to remember to update goes stale within a month
- [x] `/events` survives as a **deprecated alias** with `Deprecation`, `Sunset` and `Link`
      headers, returning sessions projected into the v1 shape as a bare array. Read-only.
      Remove it in v2.1.0, not before
- [x] `/blogs` reshaped — relative `path`, `banner: { url, alt }`, `tags`, `series`,
      `readingTimeMinutes`, real `publishedDate`
- [x] `/blogs/sync` retargeted — accepts a relative `path` and a Cloudinary banner URL
- [x] Every new resource gets a stable, unique, indexed `slug`
- [x] Dates become real datetimes on sessions and blogs. Videos and communities keep their
      strings, because nothing sorts on them

Two more aliases exist for the same reason `/events` does, and go at the same time:
`POST /auth/sign-in` → `POST /auth/login`, and `POST /upload` → `POST /uploads`.

### Data migration

> [!WARNING]
> The blog URL rewrite is destructive and touches live rows.

Scripts are written and default to dry-run. Running them against the live cluster is not done.

- [ ] **Take a verified, restore-tested MongoDB backup** — restore-tested, not just taken
- [x] Write the script rewriting the 18 blog rows off `blog.dileepa.dev` —
      `scripts/migrate_blog_urls.py`, with `scripts/rollback_blog_urls.py` to undo it
- [ ] Dry-run it and read the diff, then apply
- [x] Keep the old values in a `legacy` field for one release
- [x] Write `scripts/migrate_events_to_sessions.py`. It reads `events` and writes `sessions`,
      never modifying the source collection, so re-running is safe and `GET /events` keeps working
- [ ] Dry-run it; convert by hand anything it reports as an unparseable date
- [x] **`scripts/migrate_v1_documents.py`** — a gap the original plan missed. Every ported
      collection lacks `published`, `order`, `meta` and timestamps, and stores ordering as
      `index`. The API reads around all of that, but sorting happens in MongoDB, before the
      model's aliasing, so a half-migrated collection sorts wrongly
- [ ] **Run it to completion before traffic moves**

### Deployment

- [x] CI workflow — lint, format, types, tests, and the OpenAPI spec as an artifact
- [x] Deploy workflow, manual (`workflow_dispatch`) until the cutover is observed
- [x] Declare the entrypoint in `pyproject.toml` (`[tool.fastapi] entrypoint`)
- [ ] Run `fastapi cloud setup-ci` to mint the deploy token and write both repository secrets
- [ ] Deploy with `fastapi deploy`; `FASTAPI_CLOUD_TOKEN` and `FASTAPI_CLOUD_APP_ID` in CI
- [ ] Configuration through `fastapi cloud env set`, `--secret` for anything sensitive.
      Secrets are write-only — keep the authoritative copy in a password manager
- [ ] Environment changes need a redeploy to take effect
- [ ] **Attach `api.dileepa.dev` only after the first successful deployment** — a domain cannot be
      reserved ahead of a running app
- [ ] Add the domain with **Zero Downtime Migration** enabled, so the certificate is issued while
      Vercel still serves traffic. Subdomain is a `CNAME` at `api` →
      `<domain-id>.endpoints.fastapicloud.dev.`
- [ ] Confirm no CAA record on `dileepa.dev` blocks `pki.goog`
- [ ] Decide the plan before production traffic moves — Hobby is 0.1 vCPU / 512 MB shared, 1-day log
      retention, and one custom domain in total

### Testing

- [x] `uv run pytest` clean; contract tests green against FastAPI
- [x] Every v1.2.0 endpoint proven at parity, not assumed — and the six deliberate departures
      are recorded with reasons rather than discovered later
- [x] Auth proven against a real Node bcrypt hash; **no forced re-login**
- [ ] Auth end to end against the production database, before cutover
- [x] Tests stay offline — no live keys, no real MongoDB, no network in a unit test
- [x] `ruff check`, `ruff format --check` and `mypy` (strict) clean in CI

### Documentation and release

- [x] OpenAPI metadata — title, description, tags, contact, licence; docs disabled in production
- [x] Render the reference with **Scalar** at `/docs`; Swagger UI and ReDoc off. Neither the
      page nor `/api-json` is registered in production
- [x] Publish the OpenAPI spec so both frontends can generate typed clients — CI uploads
      `openapi.json` on every build
- [ ] Theme Scalar against the brand tokens
- [x] Fix the `README.md` endpoint table
- [x] `CHANGELOG.md`; version → `2.0.0` in `pyproject.toml`, which `/version` reads
- [ ] `VERSIONING.md` review
- [ ] Merge `feat/v2.0.0`; tag `v2.0.0`
- [ ] Close [issue #13](https://github.com/dileepadev/api-dileepa-dev/issues/13)

### Decommission — last, and only after both consumers are verified in production

- [ ] Cut `dileepa-dev` and `admin-dileepa-dev` over; observe through a rollback window
- [ ] Only then delete `src/`, `package.json`, `nest-cli.json`, and the Node toolchain
- [ ] Retire the Vercel deployment

## Later

- [ ] Remove the `/events` alias in v2.1.0
- [ ] Drop the `legacy` field from blog rows one release after the rewrite

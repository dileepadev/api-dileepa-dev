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

> [!NOTE]
> **The cutover is done.** `api.dileepa.dev` is served by FastAPI Cloud, `src/` and the Node
> toolchain are gone, and the Vercel deployment no longer carries traffic. There was no rollback
> target when the domain moved — Vercel was already paused — so what remains is confirming the
> two consumers and closing the release out, not a staged migration.

### Baseline ✅

- [x] Scaffold FastAPI 0.141.x on Python 3.13, managed with `uv` — `uv sync`, never `pip install`
- [x] `ruff` for lint and format, `mypy` for types, `pytest` + `httpx` for tests
- [x] Run through the FastAPI CLI — `uv run fastapi dev` and `uv run fastapi run`, not `uvicorn`
- [x] Async MongoDB driver against the **same cluster and the same collections**. No re-seed
- [x] Write contract tests against the current NestJS responses **first** — that is the parity
      baseline. `tests/contract/test_v1_parity.py` lists every v1.2.0 route and fails if one is
      neither served nor recorded as deliberately dropped, with a reason
- [x] Stand FastAPI up alongside NestJS — **not on a preview deployment; there is no such thing.**
      FastAPI Cloud does not support per-pull-request previews, and its GitHub integration deploys
      the default branch only. Verified against its documentation, not assumed. What replaces it is
      better: the app's own `*.fastapicloud.dev` URL is live the moment a deploy finishes, so the
      new service can be exercised against the real production database before the domain moves.
      The staging through DNS that this assumed no longer applies — Vercel is paused, so nothing
      is carrying live requests any more

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
- [x] **Run `scripts/verify_password_hash.py` against the production database** before traffic
      moves. The test pins a hash generated here; this checks the owner's real one
- [x] JWT access + refresh; signing algorithm, secret handling and claim names (`sub`, `email`,
      `roles`) match v1 exactly. A token minted by NestJS carries no `type` claim and is read as
      an access token, so live sessions survive the cutover
- [x] Role-based dependency guards mirroring the current RBAC
- [x] API-key guard for `/blogs/sync` — same `x-api-key` header and environment variable as v1,
      so the blog repo's workflow needs no change
- [x] Test token issue, refresh, expiry, and role enforcement explicitly, not incidentally
- [x] Rehearse the whole flow before production — there is no staging environment (FastAPI Cloud
      has one app), so the rehearsal was `development`, which holds the same collections, plus the
      app's own `*.fastapicloud.dev` URL against the production database before the domain moved

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
- [x] **`/events` reshaped** — speakers, photos, recordings, links, structured datetimes, slug,
      status. `status` is derived from `startAt` rather than stored, with an explicit `cancelled`
      respected; a field a human has to remember to update goes stale within a month.
      **The path does not change.** An earlier draft renamed the resource to `sessions`; that is
      reverted, because the site, the admin and the API all say "event" and `/events` was already
      a published URL
- [x] `?hasPhotos=` on `/events` — the main site's gallery is a flat grid over `events[].photos`,
      and filtering in Python afterwards would make `total` lie
- [x] `location` on the about record, for the line beside the portrait
- [x] `/blogs` reshaped — relative `path`, `tags`, `series`, `readingTimeMinutes`, real
      `publishedDate`. **`banner` retired**: it stays on the model, because removing a field is
      breaking for every consumer, and is never written
- [x] `/blogs/sync` retargeted — accepts a relative `path`, no banner, no `SITE_URL`
- [x] Every new resource gets a stable, unique, indexed `slug`
- [x] Dates become real datetimes on events and blogs. Videos and communities keep their
      strings, because nothing sorts on them
- [x] **`description` on videos** — optional, because every row that predates the field has
      nothing to put in it and a required field would fail validation on read

### Blog engagement and comments ✅

Added after the v2.0.0 contract was drafted. All three are public writes, and none collects an
identity: each keys on a salted hash of the caller's address, which recognises a repeat without
being reversible into one.

- [x] **Views** — `POST /blogs/{slug}/views`, de-duplicated per reader per 24h. The dedup is a
      unique index on `blog_views` plus a TTL, not a check in the handler: a read-then-write lets
      two concurrent requests both decide they are first
- [x] **Reactions** — four kinds, one per reader, changeable and clearable. `POST /blogs/{slug}/reactions`
- [x] **Comments** — `GET`/`POST /blogs/{slug}/comments`. Visible immediately, no approval queue,
      so the defences are at the door: `RATE_LIMIT_COMMENT`, length bounds, a honeypot, and a
      depth cap of one
- [x] **Comment reactions** — the same four, on comments and replies alike
- [x] **`PublicComment` has no field for an email address**, so the public endpoints cannot leak
      one. The admin-only `Comment` carries it. Two classes rather than one with a flag
- [x] Moderation: `GET`/`POST`/`PATCH`/`DELETE /comments`, admin-only on **every** route
      including the list — the one collection `crud_router` could not build, because its list
      route is public by design
- [x] `app/services/reactions.py` — the toggle rule, written once and shared. Two copies would
      drift into a count that no longer matches the records behind it
- [x] Counts are absent from `BlogCreate`, `BlogUpdate` and `BlogSync`, so neither an admin edit
      nor a content re-sync can overwrite them
- [x] `commentCount` on the post, so the blog index can show it without fetching every thread.
      Denormalised and maintained with `$inc` on the four paths that can change it — a public
      post, an owner reply, a publish/unpublish, and a delete — never recomputed on read, which
      is the entire point. Replies count; a honeypot hit does not, because nothing was stored.
      `scripts/reconcile_comment_counts.py` recomputes from the comments themselves and repairs
      drift; it is also the backfill, and it is idempotent

**No deprecated aliases.** v2.0.0 ships as a single cutover — the API and every consumer released
together — so no v1 path is carried and nothing is scheduled for later removal.
`POST /auth/sign-in` → `POST /auth/login` and `POST /upload` → `POST /uploads` are renames with no
alias; the old paths return `404`.

### Data migration

> [!NOTE]
> The three migration scripts never ran against `production`, and no longer need to. The
> `production` database was empty; it was populated by copying the already-migrated
> `development` database into it (149 documents, 15 collections, `_id`s preserved,
> `development` left untouched). Every outcome the scripts were written to produce was then
> verified directly against the live API rather than assumed — see the ticked items below.
> The scripts stay in the repository because they are the only record of the transformations,
> and because `development` may still need re-running against in future.

- [x] **Take a verified, restore-tested MongoDB backup** — satisfied differently than planned.
      This guarded the destructive blog URL rewrite, which never ran against `production`. The
      copy was additive into empty collections, and `development` still holds every source
      document unmodified, so it is a byte-for-byte fallback for everything now in `production`
- [x] Write the script rewriting the 18 blog rows off `blog.dileepa.dev` —
      `scripts/migrate_blog_urls.py`. The `legacy` archive that made it reversible, and the
      rollback script that read it, are both gone in v2.0.0 — the rewrite is verified in
      production and the v1 values are archived in `blogs_v1_legacy_backup` instead
- [x] Dry-run and applied against `development`; the legacy-slug stub row is unpublished so it
      does not appear in the index or the sitemap
- [x] Not needed against `production` — the rows arrived already rewritten. Verified live:
      all 18 published blogs carry a `canonicalUrl` on `dileepa.dev`, and no row references
      `blog.dileepa.dev`
- [x] Keep the old values in a `legacy` field for one release — that release was v2.0.0. The
      field is dropped from the model and from every stored row; the values were copied into
      `blogs_v1_legacy_backup` first, the same way `events_v1_backup` holds the v1 events
- [x] Write `scripts/migrate_events_v1_to_v2.py`. It rewrites the v1 rows **in place**, keeping
      each `_id`, after copying every original to `events_v1_backup`. Idempotent, so a failed run
      is simply re-run; restore is `db.events_v1_backup.aggregate([{ $out: "events" }])`
- [x] Dry-run and applied against `development` — 26 of 26 converted, no unparseable dates
- [x] Not needed against `production` — the events arrived already converted, with
      `events_v1_backup` carried across. Verified live: `/events` returns 26
- [x] **`scripts/migrate_v1_documents.py`** — a gap the original plan missed. Every ported
      collection lacks `published`, `order`, `meta` and timestamps, and stores ordering as
      `index`. The API reads around all of that, but sorting happens in MongoDB, before the
      model's aliasing, so a half-migrated collection sorts wrongly
- [x] Run against `development`
- [x] Not needed against `production` — the documents arrived already migrated. Verified live
      on every ported collection: `published`, `order`, `meta`, `createdAt` and `updatedAt` are
      all present, and `/tools` sorts `8,7,6,5,4,3,2,1`, matching `DEFAULT_SORT`'s
      `("order", -1)`

### Deployment

- [x] CI workflow — lint, format, types, tests, and the OpenAPI spec as an artifact
- [x] Deploy workflow, manual (`workflow_dispatch`) until the cutover is observed
- [x] Declare the entrypoint in `pyproject.toml` (`[tool.fastapi] entrypoint`)

> [!NOTE]
> **The deploy workflow is dispatchable now that it is on `main`.** GitHub only shows the Run
> workflow button for a `workflow_dispatch` workflow that exists on the default branch, which this
> one does. Deploying from the FastAPI Cloud VS Code extension or a local `fastapi deploy` also
> works and bypasses Actions entirely, needing only `fastapi cloud login`.

- [x] Run `fastapi cloud setup-ci` to mint the deploy token and write both repository secrets
- [x] Deploy with `fastapi deploy` — live, and now served at `https://api.dileepa.dev`.
      `/health` reports the database up, `/version` reports 2.0.0 in production. The first deploy
      ran from a local CLI login; `FASTAPI_CLOUD_TOKEN` and `FASTAPI_CLOUD_APP_ID` are now set as
      repository secrets, so `deploy.yml` can run it from Actions
- [x] Configuration through `fastapi cloud env set`, `--secret` for anything sensitive — 20 of
      the 21 values set, `JWT_SECRET`, `MONGODB_URI`, both Cloudinary keys, `RESEND_API_KEY` and
      `BLOG_SYNC_API_KEY` marked secret. `PORT` is deliberately unset: nothing reads it and the
      platform binds its own. Secrets are write-only — keep the authoritative copy in a password
      manager
- [x] Environment changes need a redeploy to take effect
- [x] **Attach `api.dileepa.dev` only after the first successful deployment** — attached and
      live. `https://api.dileepa.dev/health` returns `{"status":"ok","checks":{"database":"up"}}`
      and is the production health endpoint
- [x] Add the domain with **Zero Downtime Migration** enabled — the certificate was issued by
      Google Trust Services and the domain serves from FastAPI Cloud. Subdomain is a `CNAME` at
      `api` → `<domain-id>.endpoints.fastapicloud.dev.`
- [x] Confirm no CAA record on `dileepa.dev` blocks `pki.goog` — there is no CAA record at all,
      so any CA may issue
- [x] Decide the plan before production traffic moves — Hobby is 0.1 vCPU / 512 MB shared, 1-day log
      retention, and one custom domain in total

### Testing

- [x] `uv run pytest` clean; contract tests green against FastAPI
- [x] Every v1.2.0 endpoint proven at parity, not assumed — and the six deliberate departures
      are recorded with reasons rather than discovered later
- [x] Auth proven against a real Node bcrypt hash; **no forced re-login**
- [x] Auth end to end against the production database, before cutover
- [x] Tests stay offline — no live keys, no real MongoDB, no network in a unit test
- [x] `ruff check`, `ruff format --check` and `mypy` (strict) clean in CI

### Documentation and release

- [x] OpenAPI metadata — title, description, tags, contact, licence; docs disabled in production
- [x] Render the reference with **Scalar** at `/docs`; Swagger UI and ReDoc off. Neither the
      page nor `/api-json` is registered in production
- [x] Publish the OpenAPI spec so both frontends can generate typed clients — CI uploads
      `openapi.json` on every build
- [x] Theme Scalar against the brand tokens — `app/core/scalar_theme.py` maps the canonical
      sheet onto Scalar's `--scalar-*` names. Emerald is declared per theme (Bright on Carbon,
      Deep on Paper), Manrope and JetBrains Mono replace Scalar's Inter pair, and the docs CSP
      names the two Google Fonts origins rather than being relaxed
- [x] Fix the `README.md` endpoint table — including engagement and comments
- [x] `CHANGELOG.md`; version → `2.0.0` in `pyproject.toml`, which `/version` reads
- [x] `VERSIONING.md` review — the release steps still said to bump `package.json`, which this
      repository no longer ships. Corrected to `pyproject.toml`, which is what `GET /version`
      actually reads
- [ ] Tag `v2.0.0`. `feat/v2.0.0`, `dev` and `main` already hold identical trees, so the
      promotion is a tag rather than a merge
- [ ] Close [issue #13](https://github.com/dileepadev/api-dileepa-dev/issues/13) — **last, and not
      before.** Not when this branch merges, not when the first deploy succeeds, and not when the
      domain resolves. It closes when `api.dileepa.dev` has served production traffic from FastAPI
      Cloud through a rollback window with the Vercel deployment retired, and every box in
      **Data migration**, **Deployment** and **Decommission** above is ticked. The issue is the only
      thing tracking that this migration is genuinely finished rather than merely shipped

### Decommission

This section was written to run last, only after both consumers were verified in production. It
did not: the Vercel deployment was paused before the cutover, which removed the fallback and made
keeping the NestJS tree pointless. The removal below therefore happened ahead of the documented
order.

- [x] Cut the consumers over — as far as this repository is concerned. The API serves both, and
      what either front end does with it is tracked in its own repository, not here.
      **`admin.dileepa.dev` is not a deployed domain**: it resolves to Porkbun parking and never
      served the admin. It is not treated as a production endpoint anywhere in this repository,
      and no deployment or DNS work for it is required by this release
- [x] Delete `src/`, `package.json`, `nest-cli.json`, and the Node toolchain — 95 files removed.
      `tests/contract/test_v1_parity.py` keeps the v1 route table hardcoded in Python and never
      read `src/`, so parity coverage is unaffected. Verified after removal: 359 passed, ruff and
      mypy clean
- [x] Retire the Vercel deployment — `api.dileepa.dev` resolves to FastAPI Cloud and the API's
      Vercel project is disconnected. Note that the **front ends are still on Vercel**, which is
      why `cors_origin_regex` still matches `*-dileepadev-projects.vercel.app`; that pattern
      serves their preview builds and is unrelated to the retired API deployment

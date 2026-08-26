# Changelog

All notable changes to this project are documented in this file.

Changes are organized into the following categories:

- **Added:** New features or functionality introduced to the project.
- **Changed:** Modifications to existing functionality that do not add new features.
- **Fixed:** Bug fixes that resolve issues or correct unintended behavior.
- **Removed:** Features or components that have been removed from the project.

## [Unreleased]

### 2.0.0 — in progress on `feat/v2.0.0`

The backend moves from NestJS 11 on Vercel serverless to FastAPI on Python 3.13,
hosted on FastAPI Cloud, and gains two new resources. Both stacks are in the
repository during the migration; `src/` is deleted only after both consumers are
verified against FastAPI in production and a rollback window has passed.

#### Added - v2.0.0

- FastAPI 0.141.x application under `app/`, on Python 3.13 managed with `uv`.
  Ruff for lint and format, mypy in strict mode, pytest with httpx for tests.
- Async MongoDB access through PyMongo's async driver, against the same cluster
  and the same collections. Nothing is re-seeded.
- **`/projects`** — full model with slug, status, period, stack, gallery,
  metrics and SEO, plus CRUD and filters. Net-new; nothing existed before.
- **Blog engagement** — `GET /blogs/{slug}/engagement`, `POST /blogs/{slug}/views`
  and `POST /blogs/{slug}/reactions`. Views de-duplicate per reader per 24 hours
  through a unique index and a TTL on `blog_views`, not through a check in the
  handler: a read-then-write lets two concurrent requests both conclude they are
  the first, which is exactly how a view counter loses counts. Four reactions,
  one per reader, changeable and clearable.
- **Blog comments** — `GET`/`POST /blogs/{slug}/comments`, one level of replies,
  and `POST /blogs/{slug}/comments/{id}/reactions` carrying the same four
  reactions. Comments are visible the moment they are posted; there is no
  approval queue, so the defences are at the door — `RATE_LIMIT_COMMENT`, length
  bounds, a honeypot that answers 201 and stores nothing, and a depth cap that
  re-parents rather than rejects.
- **Comment moderation** — `GET`/`POST`/`PATCH`/`DELETE /comments`, admin-only on
  every route including the list. `PublicComment` has no field for an email
  address and so cannot serialise one; the admin-only `Comment` does. Two classes
  rather than one with a flag, because a field that is sometimes secret is a
  field that eventually gets returned by accident.
- `description` on videos. Optional: every row that predates the field has
  nothing to put in it, and a required field would fail validation on read.
- `?hasPhotos=` on `/events`, for the main site's event gallery. Expressed as a
  query rather than a fetch-and-filter, so `total` stays truthful and the
  gallery can be paged.
- `location` on the about record — free text, rendered beside the portrait as
  `"{title} · {location}"`.
- `GET /health` and `GET /version`. `/health` returns 503 when MongoDB is
  unreachable, so an uptime check does not have to read the body.
- `POST /auth/refresh` and `GET /auth/profile`, with refresh tokens alongside
  the existing access tokens.
- `PATCH /{resource}/order` on every collection, for bulk reordering. Without it
  a drag-and-drop in the admin costs one request per row.
- Contract tests that assert every v1.2.0 route is either still served or
  recorded as deliberately dropped with a reason.
- **`scripts/migrate_events_v1_to_v2.py`** — rewrites the v1 `events` documents
  into the v2 shape **in place**, keeping each `_id`, after copying every
  original to `events_v1_backup`. Idempotent: a row already in the v2 shape is
  recognised and skipped, so a failed run is simply re-run. Restoring is
  `db.events_v1_backup.aggregate([{ $out: "events" }])`.

#### Changed - v2.0.0

- **Collection endpoints return an envelope**, `{ items, total, limit, offset }`,
  rather than a bare array. One shape on every resource.
- **An empty collection is `200` with an empty list**, not `404`. v1 threw
  `NotFoundException` when a list came back empty, which made an empty section
  indistinguishable from a broken endpoint.
- **Errors return `{ error: { code, message, details } }`** on every endpoint,
  replacing `{ statusCode, timestamp, path, message }`. `code` is stable and
  machine-readable; `message` is written to be shown to a person.
- **Records expose `id`, not `_id`**, and never `__v`.
- **`index` is now `order`.** Same meaning — priority, higher sorts first — and
  the API reads either name, so it is correct against an unmigrated database.
  `scripts/migrate_v1_documents.py` performs the rename.
- **`/events` is reshaped, not replaced.** It keeps its path and its collection
  name and gains speakers, photos, recordings, slides, links, tags, a slug and
  structured timezone-aware datetimes. v1 carried seven flat fields — title, a
  free-text `date`, location, format, description, url, index — and none of the
  rest.

  An earlier draft of this migration renamed the resource to `sessions`, on the
  reasoning that a talk is a session *at* an event. That is reverted. The site,
  the admin and the person writing the records all say "event", `/events` was
  already a published URL, and a name nobody uses is a name that gets mistyped.

  `status` is **derived** from `startAt` rather than stored, so an event that has
  happened says so without anyone editing it. An explicit `cancelled` is
  respected — time passing does not un-cancel an event.
- **Blog posts carry a relative `path` and a composed `canonicalUrl`** instead
  of an absolute `link` on `blog.dileepa.dev`, a real `publishedDate` datetime
  instead of a date string, and `description` instead of `excerpt`. Old values
  are kept under `legacy` for one release.
- **Blog banners are retired.** Posts carry no image of their own; anything a
  post shows is an ordinary Markdown image in the body pointing at a URL. The
  `banner` field **stays on the model** — removing a field from a response is
  breaking for every consumer that reads it, and buys nothing — and is written
  by nothing. `scripts/migrate_blog_urls.py` clears it and archives the v1
  `bannerUrl` into `legacy`.
- `POST /blogs/sync` accepts a relative `path`, derives visibility from the
  front matter's `draft` rather than accepting `published` directly, and no
  longer accepts a banner.
- Password hashes are verified with `pwdlib` rather than `passlib`, which has
  been unmaintained since 2020 and breaks against bcrypt 4.1 and later. Existing
  Node `bcrypt` hashes validate unchanged and are rewritten to argon2id on the
  next successful sign-in. **No password reset is required.**
- **The API reference is rendered by [Scalar](https://scalar.com/) at `/docs`**, replacing
  Swagger UI and ReDoc, which are both switched off. In production neither the
  page nor the OpenAPI JSON at `/api-json` is registered, so the reference
  cannot be reached and the spec it reads is not served — the v1 posture, kept.
  `/docs` is served with its own Content-Security-Policy allowing exactly the
  Scalar CDN; the rest of the API keeps `default-src 'none'`.
- `GET /` returns `{ name, version, docs, website }` rather than the string
  `Hello World!`. `docs` is null in production rather than a dead link.

#### Removed - v2.0.0

- Azure Blob Storage. Cloudinary is the only image backend.
- **`POST /auth/sign-in`.** Use `POST /auth/login` — same body, same token
  shape, including v1's `access_token` field name.
- **`POST /upload`, `GET /upload`, `DELETE /upload/{publicId}`.** Use the
  `/uploads` equivalents.

#### Deprecated - v2.0.0

Nothing. v2.0.0 is a single cutover — the API and every consumer are released at
the same time — so no v1 path is carried behind a deprecation and nothing is
scheduled for removal in a later version. The v1 paths listed under *Removed*
return `404`.

`tests/contract/test_v1_parity.py` records every dropped v1 route with its
successor, and `tests/test_openapi.py` fails if any operation is ever published
with `deprecated: true`.

## [1.2.1] - 2026-03-02

### Fixed - v1.2.1

- Fix contact form CORS failure: add configurable `CORS_ORIGINS` environment variable and refactor `src/main.ts` to parse and use it with `app.enableCors`. Preserves localhost dev origins and falls back to production domains. (refs #10)
- Add `CORS_ORIGINS` to `.env.example` and document required production origin(s).
- Resolve 21 npm audit security vulnerabilities (including ReDoS and RCE risks) by adding safe `overrides` for transitive dependencies: `test-exclude`, `minimatch`, `multer`, `serialize-javascript`, and `ajv` in `package.json`. (refs #10)
- Verify test suite pass rate remains 100% after dependency adjustments.

## [1.2.0] - 2026-03-02

### Added - v1.2.0

- Introduce full CRUD operations (POST, PUT/PATCH, DELETE) across all feature modules.
- Implement JWT-based authentication infrastructure.
- Add authorization guards and Role-Based Access Control (RBAC) to secure non-public endpoints.
- Add image upload support for all relevant POST operations.
- Implement email support endpoints.
- Add blog synchronization endpoint protected by API key authentication.
- Implement a `priority` index to documents for custom sorting.
- Add support for loading Swagger UI assets from CDN to facilitate Vercel deployments.
- Configure project for deployment on Vercel.

### Changed - v1.2.0

- Upgrade NestJS framework to the latest stable version.
- Refactor project structure: Moved DTOs and Schemas to feature modules with updated import paths.
- Improve module, controller, and service organization following NestJS best practices.
- Standardize API error handling: Implemented global `ValidationPipe` and `HttpExceptionFilter`.
- Enforce stricter input validation and consistent error response formats.
- Remove deprecated `baseUrl` option from `tsconfig.json` to prepare for TypeScript 7.0.

## [1.1.0] - 2026-01-14

### Added - v1.1.0

- Add social media and other relevant external links to the `/about` endpoint for better representation.

### Changed - v1.1.0

- Update the `description` field in the `/about` endpoint to support an array of multiple descriptive entries, allowing for more detailed and modular content.
- Refactor the DTO (Data Transfer Object) structure to follow `camelCase` naming conventions for consistency with frontend standards.
- Update MongoDB queries to return data ordered by date for improved relevance.

## [1.0.0] - 2026-01-13

### Added - v1.0.0

- Set up initial project structure using [NestJS](https://nestjs.com/) and [TypeScript](https://www.typescriptlang.org/) running on [Node.js](https://nodejs.org/).
- Built and tested the following RESTful API endpoints:
  - `/about` – Provides general profile information about me.
  - `/experiences` – Returns a list of my professional work experiences and roles.
  - `/educations` – Displays my academic background including degrees and institutions.
  - `/events` – Lists upcoming or past events, talks, or appearances I’ve been part of.
  - `/videos` – Links to video content such as talks, tutorials, or interviews I’ve done.
  - `/blogs` – Returns metadata or summaries of blog posts I’ve written.
  - `/communities` – Tech communities I've volunteered with, both currently and in the past.
  - `/tools` – Lists the tools, frameworks, and technologies I currently work with.
- Configured database using [MongoDB](https://www.mongodb.com/) with [Mongoose](https://mongoosejs.com/) ODM. Seeded initial data and connected it to API endpoints.
- Implemented image upload and delivery via [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/).
- Generated interactive API documentation using [Swagger](https://swagger.io/) and [Swagger UI](https://swagger.io/tools/swagger-ui/).
- Deployed application to production using [Azure App Service](https://azure.microsoft.com/en-us/services/app-service/) with optional CI/CD.
- Integrated code linting and formatting with [ESLint](https://eslint.org/) and [Prettier](https://prettier.io/).
- Managed dependencies using [npm](https://www.npmjs.com/).

<!-- e.g., -->
<!-- Unreleased -->
<!-- v2.0.0 -->
<!-- v1.1.0 -->
<!-- v1.0.0 -->
<!-- v0.0.1 -->

[Unreleased]: https://github.com/dileepadev/api-dileepa-dev/branches
[1.0.0]: https://github.com/dileepadev/api-dileepa-dev/releases/tag/1.0.0
[1.1.0]: https://github.com/dileepadev/api-dileepa-dev/releases/tag/1.1.0
[1.2.0]: https://github.com/dileepadev/api-dileepa-dev/releases/tag/1.2.0
[1.2.1]: https://github.com/dileepadev/api-dileepa-dev/releases/tag/1.2.1

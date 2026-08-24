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
- **`/sessions`** — speakers, photos, recordings, slides, links, structured
  timezone-aware datetimes, slug and derived status. Supersedes `/events`.
- `GET /health` and `GET /version`. `/health` returns 503 when MongoDB is
  unreachable, so an uptime check does not have to read the body.
- `POST /auth/refresh` and `GET /auth/profile`, with refresh tokens alongside
  the existing access tokens.
- `PATCH /{resource}/order` on every collection, for bulk reordering. Without it
  a drag-and-drop in the admin costs one request per row.
- Contract tests that assert every v1.2.0 route is either still served or
  recorded as deliberately dropped with a reason.

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
- **Blog posts carry a relative `path` and a composed `canonicalUrl`** instead
  of an absolute `link` on `blog.dileepa.dev`, a `banner: { url, alt }` instead
  of `bannerUrl`, a real `publishedDate` datetime instead of a date string, and
  `description` instead of `excerpt`. Old values are kept under `legacy` for one
  release.
- `POST /blogs/sync` accepts a relative `path` and a Cloudinary banner URL, and
  derives visibility from the front matter's `draft` rather than accepting
  `published` directly.
- Password hashes are verified with `pwdlib` rather than `passlib`, which has
  been unmaintained since 2020 and breaks against bcrypt 4.1 and later. Existing
  Node `bcrypt` hashes validate unchanged and are rewritten to argon2id on the
  next successful sign-in. **No password reset is required.**
- Interactive docs move to `/api` (Swagger UI), `/api/redoc` and `/api-json`,
  still disabled in production.

#### Removed - v2.0.0

- Azure Blob Storage. Cloudinary is the only image backend.
- Write access to `/events`. It survives read-only, as an alias over sessions.

#### Deprecated - v2.0.0

Removed in v2.1.0, not before, and only once no consumer calls them. All three
send `Deprecation`, `Sunset` and `Link: rel="successor-version"` headers.

- `GET /events` — use `GET /sessions`.
- `POST /auth/sign-in` — use `POST /auth/login`.
- `POST /upload` — use `POST /uploads`.

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

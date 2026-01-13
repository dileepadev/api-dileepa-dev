# Changelog

All notable changes to this project are documented in this file.

Changes are organized into the following categories:

- **Added:** New features or functionality introduced to the project.
- **Changed:** Modifications to existing functionality that do not add new features.
- **Fixed:** Bug fixes that resolve issues or correct unintended behavior.
- **Removed:** Features or components that have been removed from the project.

## [Unreleased]

- Changes for the next release are available in development branches.

## [1.0.0] - 2026-01-13

### Added

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

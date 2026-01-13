# api.dileepa.dev

This is the API for Dileepa's personal website ([dileepa.dev](https://dileepa.dev)), built with [NestJS](https://nestjs.com/). It provides various endpoints to access information about Dileepa and other related data.

## Tech Stack

* **Framework:** [NestJS](https://nestjs.com/)
* **Language:** [TypeScript](https://www.typescriptlang.org/)
* **Runtime:** [Node.js](https://nodejs.org/)
* **Package Manager:** [npm](https://www.npmjs.com/)
* **Linting:** [ESLint](https://eslint.org/)
* **Formatting:** [Prettier](https://prettier.io/)
* **Database:** [MongoDB](https://www.mongodb.com/) (using [Mongoose](https://mongoosejs.com/))
* **Deployment:** [Azure App Service](https://azure.microsoft.com/en-us/services/app-service/)
* **Image Hosting:** [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/)
* **Documentation:** [Swagger](https://swagger.io/) (using [Swagger UI](https://swagger.io/tools/swagger-ui/))

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/api.dileepa.dev.git 
   cd api.dileepa.dev
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

## Running the App

### Development

To run the application in development mode with file watching:

```bash
npm run start:dev
```

The application will be available at `http://localhost:3000` (or the configured port).

### Production

To build and run the application in production mode:

```bash
npm run build
npm run start:prod
```

## Linting and Formatting

To lint the codebase:

```bash
npm run lint
```

To format the codebase using Prettier:

```bash
npm run format
```

## Contributing

Contributions are welcome! Please follow the guidelines outlined in [CONTRIBUTING.md](CONTRIBUTING.md) and adhere to the [Code of Conduct](CODE_OF_CONDUCT.md). Also, review the [Branch Naming](BRANCH_NAMING_GUIDELINES.md), [Commit Message](COMMIT_MESSAGE_GUIDELINES.md), and [Pull Request](PULL_REQUEST_GUIDELINES.md) guidelines.

## Security

If you discover any security vulnerabilities, please report them as described in [SECURITY.md](SECURITY.md).

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

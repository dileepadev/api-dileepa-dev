# api.dileepa.dev

This is the API for Dileepa's personal website ([dileepa.dev](https://dileepa.dev)), built with [NestJS](https://nestjs.com/). It provides various endpoints to access information about Dileepa and other related data.

## Table of Contents

- [api.dileepa.dev](#apidileepadev)
  - [Table of Contents](#table-of-contents)
  - [Tools and Technologies](#tools-and-technologies)
  - [Installation](#installation)
  - [Running the App](#running-the-app)
    - [Development](#development)
    - [Production](#production)
  - [API Documentation](#api-documentation)
  - [Testing](#testing)
  - [Versioning](#versioning)
  - [Contributing](#contributing)
  - [Issues](#issues)
  - [Security](#security)
  - [License](#license)
  - [API Endpoints](#api-endpoints)
  - [Deployment on Azure](#deployment-on-azure)
  - [Contact](#contact)

## Tools and Technologies

- **Framework:** [NestJS](https://nestjs.com/)
- **Language:** [TypeScript](https://www.typescriptlang.org/)
- **Runtime:** [Node.js](https://nodejs.org/)
- **Package Manager:** [npm](https://www.npmjs.com/)
- **Linting:** [ESLint](https://eslint.org/)
- **Formatting:** [Prettier](https://prettier.io/)
- **Version Control:** [Git](https://git-scm.com/)
- **Database:** [MongoDB](https://www.mongodb.com/) (using [Mongoose](https://mongoosejs.com/))
- **Deployment:** [Azure App Service](https://azure.microsoft.com/en-us/services/app-service/)
- **Image Hosting:** [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/)
- **Documentation:** [Swagger](https://swagger.io/) (using [Swagger UI](https://swagger.io/tools/swagger-ui/))

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/dileepadev/api.dileepa.dev.git
   cd api.dileepa.dev
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Copy the example environment file and update it with your configuration:

   ```bash
   cp .env.example .env
   # Then edit .env as needed
   ```

## Running the App

### Development

To run the application in development mode with file watching:

```bash
npm run start:dev
```

The application will be available at `http://localhost:3000` (or the configured port in `.env`).

### Production

To build and run the application in production mode:

```bash
npm run build
npm run start:prod
```

## API Documentation

Swagger UI is available at [`/api`](http://localhost:3000/api) once the app is running. (e.g., `http://localhost:3000/api`)

## Testing

To run tests:

```bash
npm run test
```

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

| Endpoint      | Description                                           |
|---------------|-------------------------------------------------------|
| `/about`      | Provides general profile information about me.        |
| `/experiences`| Returns a list of my professional work experiences.   |
| `/educations` | Displays my academic background, including degrees.   |
| `/events`     | Lists upcoming and past events, talks, or appearances.|
| `/videos`     | Links to video content such as talks or tutorials.    |
| `/blogs`      | Returns metadata or summaries of blog posts.          |
| `/communities`| Tech communities I've volunteered with.               |
| `/tools`      | Lists the tools, frameworks, and technologies I use.  |

## Deployment on Azure

This project is designed for deployment on Azure App Service and uses Azure Blob Storage for image hosting. For deployment instructions, see the [official Azure documentation](https://docs.microsoft.com/en-us/azure/app-service/quickstart-nodejs?tabs=windows).

## Contact

For any inquiries or feedback, please reach out to me via [email](mailto:contact@dileepa.dev) or through my [website](https://dileepa.dev).

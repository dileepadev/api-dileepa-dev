import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import helmet from 'helmet';
import fs from 'fs';
import path from 'path';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.use(helmet());

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );
  app.useGlobalFilters(new HttpExceptionFilter());

  const pkgJsonPath = path.resolve(process.cwd(), 'package.json');
  let appVersion = '0.0.0';
  try {
    const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8')) as {
      version?: string;
    };
    appVersion = pkg.version ?? appVersion;
  } catch (err) {
    console.warn('Could not read package.json for version:', err);
  }
  const isDev = process.env.NODE_ENV !== 'production';

  const config = new DocumentBuilder()
    .setTitle('api.dileepa.dev')
    .setDescription(
      "This API provides access to Dileepa Bandara's personal and other related data.",
    )
    .setContact('Dileepa Bandara', 'https://dileepa.dev', 'contact@dileepa.dev')
    .setLicense(
      'MIT',
      'https://github.com/dileepadev/api-dileepa-dev/blob/main/LICENSE',
    )
    .setVersion(appVersion)
    .addBearerAuth(
      {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        name: 'JWT',
        description: 'Enter JWT token',
        in: 'header',
      },
      'JWT-auth',
    )
    .build();

  if (isDev) {
    const documentFactory = () => SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('api', app, documentFactory);
    console.log('Swagger UI enabled at /api');
  } else {
    console.log('Swagger UI is disabled in production.');
  }

  // Enable CORS
  const corsOrigins = process.env.CORS_ORIGINS?.split(',') || [];
  app.enableCors({
    origin: isDev
      ? [
          'http://localhost:3000',
          'http://localhost:3001',
          'http://localhost:3002',
          ...corsOrigins,
        ]
      : corsOrigins.length > 0
        ? corsOrigins
        : ['https://dileepa.dev', 'https://www.dileepa.dev'],
    credentials: true,
  });

  await app.listen(process.env.PORT ?? 3000);
}

bootstrap().catch((err) => {
  console.error('Error starting server:', err);
  process.exit(1);
});

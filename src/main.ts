import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  const config = new DocumentBuilder()
    .setTitle('api.dileepa.dev')
    .setDescription(
      "This API provides access to Dileepa Bandara's personal and other related data.",
    )
    .setContact('Dileepa Bandara', 'https://dileepa.dev', 'contact@dileepa.dev')
    .setLicense(
      'MIT',
      'https://github.com/dileepadev/api.dileepa.dev/blob/main/LICENSE',
    )
    .setVersion('1.0.0')
    .build();
  const documentFactory = () => SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api', app, documentFactory);

  await app.listen(process.env.PORT ?? 3000);
}

bootstrap().catch((err) => {
  console.error('Error starting server:', err);
  process.exit(1);
});

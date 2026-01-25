import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AboutModule } from './about/about.module';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { ExperiencesModule } from './experiences/experiences.module';
import { EducationsModule } from './educations/educations.module';
import { EventsModule } from './events/events.module';
import { VideosModule } from './videos/videos.module';
import { BlogsModule } from './blogs/blogs.module';
import { CommunitiesModule } from './communities/communities.module';
import { ToolsModule } from './tools/tools.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { APP_GUARD } from '@nestjs/core';
import { JwtAuthGuard } from './auth/guards/jwt-auth.guard';
import { RolesGuard } from './auth/guards/roles.guard';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    MongooseModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => {
        let uri = configService.get<string>('MONGODB_URI') || '';
        // Fix common connection string typo that causes "No write concern mode" error
        if (uri.includes('majority/?authMechanism')) {
          uri = uri.replace(
            'majority/?authMechanism',
            'majority&authMechanism',
          );
        }
        return {
          uri,
        };
      },
      inject: [ConfigService],
    }),
    AuthModule,
    UsersModule,
    AboutModule,
    ExperiencesModule,
    EducationsModule,
    EventsModule,
    VideosModule,
    BlogsModule,
    CommunitiesModule,
    ToolsModule,
  ],
  controllers: [AppController],
  providers: [
    AppService,
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard,
    },
    {
      provide: APP_GUARD,
      useClass: RolesGuard,
    },
  ],
})
export class AppModule {}

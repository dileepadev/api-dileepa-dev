import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Request } from 'express';

/**
 * Guard that validates requests using a static API key.
 *
 * Expects the key in the `x-api-key` header.
 * Validates against the `BLOG_SYNC_API_KEY` environment variable.
 *
 * Use on endpoints that need machine-to-machine authentication
 * (e.g., CI/CD pipelines, GitHub Actions) without user-based JWT auth.
 */
@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(private readonly configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<Request>();
    const apiKey = request.headers['x-api-key'] as string;

    if (!apiKey) {
      throw new UnauthorizedException('Missing x-api-key header');
    }

    const validKey = this.configService.get<string>('BLOG_SYNC_API_KEY');

    if (!validKey) {
      throw new UnauthorizedException('API key not configured on server');
    }

    if (apiKey !== validKey) {
      throw new UnauthorizedException('Invalid API key');
    }

    return true;
  }
}

import { Controller, Request, Post, UseGuards } from '@nestjs/common';
import { LocalAuthGuard } from './guards/local-auth.guard';
import { AuthService } from './auth.service';
import { SignInDto } from './dto/signin.dto';
import { Public } from './decorators/public.decorator';
import { ApiBody, ApiTags } from '@nestjs/swagger';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Public()
  @UseGuards(LocalAuthGuard)
  @Post('sign-in')
  @ApiBody({ type: SignInDto })
  signIn(
    @Request()
    req: {
      user: { userId: string; email: string; roles: string[] };
    },
  ) {
    return this.authService.signIn(req.user);
  }
}

import { Injectable, UnauthorizedException } from '@nestjs/common';
import { UsersService } from '../users/users.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { SignInDto } from './dto/signin.dto';

@Injectable()
export class AuthService {
  constructor(
    private usersService: UsersService,
    private jwtService: JwtService,
  ) {}

  async validateUser(
    email: string,
    pass: string,
  ): Promise<{ userId: string; email: string; roles: string[] }> {
    const user = await this.usersService.findOne(email);

    if (!user) {
      // No user with that email
      throw new UnauthorizedException('User not found');
    }

    if (user.isActive === false) {
      // Account exists but is disabled
      throw new UnauthorizedException('Account disabled');
    }

    const passwordMatches = await bcrypt.compare(pass, user.passwordHash);

    if (!passwordMatches) {
      // Wrong password
      throw new UnauthorizedException('Invalid credentials');
    }

    return {
      userId: user._id.toString(),
      email: user.email,
      roles: user.roles,
    };
  }

  signIn(user: { userId: string; email: string; roles: string[] }) {
    const payload = { email: user.email, sub: user.userId, roles: user.roles };
    return {
      access_token: this.jwtService.sign(payload),
    };
  }

  async validateUserByCredentials(signInDto: SignInDto) {
    // validateUser now throws specific UnauthorizedExceptions on failure
    const user = await this.validateUser(signInDto.email, signInDto.password);
    return this.signIn(user);
  }
}

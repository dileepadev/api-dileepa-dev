import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsNotEmpty, IsString } from 'class-validator';

export class CreateContactDto {
  @ApiProperty({
    description: 'Name of the sender',
    example: 'John Doe',
  })
  @IsString()
  @IsNotEmpty()
  readonly name: string;

  @ApiProperty({
    description: 'Email of the sender',
    example: 'john@example.com',
  })
  @IsEmail()
  @IsNotEmpty()
  readonly email: string;

  @ApiProperty({
    description: 'Subject of the message',
    example: 'Project Inquiry',
  })
  @IsString()
  @IsNotEmpty()
  readonly subject: string;

  @ApiProperty({
    description: 'Message content',
    example: 'Hi, I would like to discuss a project with you.',
  })
  @IsString()
  @IsNotEmpty()
  readonly message: string;
}

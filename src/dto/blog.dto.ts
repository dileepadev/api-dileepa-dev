import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class BlogDto {
  @ApiProperty({
    description: 'The title of the blog post',
    example: 'Introduction to Artificial Intelligence',
  })
  @IsString()
  readonly title: string;

  @ApiProperty({
    description: 'The publication date of the blog post',
    example: '2025-10-01',
  })
  @IsString()
  readonly date: string;

  @ApiProperty({
    description: 'A short excerpt of the blog post',
    example: 'This blog post introduces the basics of AI...',
  })
  @IsString()
  readonly excerpt: string;

  @ApiProperty({
    description: 'The link to the blog post',
    example: 'https://blog.dileepa.dev/680e72e34fd7c6eea2de7cd7',
  })
  @IsString()
  readonly link: string;
}

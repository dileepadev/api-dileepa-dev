import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class EventDto {
  @ApiProperty({
    description: 'The title of the event',
    example: 'Introduction to Azure',
  })
  @IsString()
  readonly title: string;

  @ApiProperty({
    description: 'The date of the event',
    example: '2024-02-24',
  })
  @IsString()
  readonly date: string;

  @ApiProperty({
    description: 'The location of the event',
    example: 'NIBM Colombo',
  })
  @IsString()
  readonly location: string;

  @ApiProperty({
    description: 'The format of the event',
    example: 'In-Person',
  })
  @IsString()
  readonly format: string;

  @ApiProperty({
    description: 'A description of the event',
    example:
      'A beginner-friendly workshop to introduce the fundamentals of Azure cl…',
  })
  @IsString()
  readonly description: string;
}

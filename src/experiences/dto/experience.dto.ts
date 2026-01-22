import {
  IsString,
  IsUrl,
  IsArray,
  ArrayNotEmpty,
  ValidateNested,
} from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';

class LogoDto {
  @ApiProperty({
    description: 'URL to the logo for light mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/companies/rsl-light.svg',
  })
  @IsUrl()
  readonly light: string;

  @ApiProperty({
    description: 'URL to the logo for dark mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/companies/rsl-dark.svg',
  })
  @IsUrl()
  readonly dark: string;
}

export class ExperienceDto {
  @ApiProperty({
    description: 'The job title.',
    example: 'Associate AI Engineer',
  })
  @IsString()
  readonly title: string;

  @ApiProperty({
    description: 'The name of the company.',
    example: 'Random Software Ltd.',
  })
  @IsString()
  readonly company: string;

  @ApiProperty({
    description: 'Optional URL for the company.',
    example: 'https://randomsoftware.net',
  })
  @IsUrl()
  readonly url?: string;

  @ApiProperty({
    description: 'The period of employment.',
    example: 'Jan 2023 - Present',
  })
  @IsString()
  readonly period: string;

  @ApiProperty({
    description: 'Description of the role and responsibilities.',
    example:
      'Developed and maintained web applications using NestJS and Angular.',
  })
  @IsString()
  readonly description: string;

  @ApiProperty({
    description: 'List of technologies used.',
    example: ['NestJS', 'Angular', 'TypeScript', 'MongoDB'],
    type: [String],
  })
  @IsArray()
  @ArrayNotEmpty()
  @IsString({ each: true })
  readonly technologies: string[];

  @ApiProperty({
    description: 'Experience logo URLs',
    type: LogoDto,
  })
  @ValidateNested()
  @Type(() => LogoDto)
  readonly logo: LogoDto;
}

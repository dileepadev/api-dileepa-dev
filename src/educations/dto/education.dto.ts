import { IsString, IsUrl, ValidateNested } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';

class LogoDto {
  @ApiProperty({
    description: 'URL to the logo for light mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/Institutions/nibm.svg',
  })
  @IsUrl()
  readonly light: string;

  @ApiProperty({
    description: 'URL to the logo for dark mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/Institutions/nibm.svg',
  })
  @IsUrl()
  readonly dark: string;
}

export class EducationDto {
  @ApiProperty({
    description: 'The name of the course or degree.',
    example: 'BSc (Hons) in Computing',
  })
  @IsString()
  readonly course: string;

  @ApiProperty({
    description: 'The name of the institution.',
    example: 'National Institute of Business Management (NIBM)',
  })
  @IsString()
  readonly institution: string;

  @ApiProperty({
    description: 'The period of study.',
    example: '2019 - 2020',
  })
  @IsString()
  readonly period: string;

  @ApiProperty({
    description: 'Optional description about the education.',
    example: 'Specialized in Software Engineering.',
  })
  @IsString()
  readonly description?: string;

  @ApiProperty({
    description: 'Optional URL for the institution or course.',
    example: 'https://nibm.lk',
  })
  @IsUrl()
  readonly url?: string;

  @ApiProperty({
    description: 'Education logo URLs',
    type: LogoDto,
  })
  @ValidateNested()
  @Type(() => LogoDto)
  readonly logo: LogoDto;
}

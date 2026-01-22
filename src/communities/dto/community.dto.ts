import {
  IsString,
  IsBoolean,
  IsOptional,
  ValidateNested,
  IsUrl,
} from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';

class LogoDto {
  @ApiProperty({
    description: 'URL to the logo for light mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/communities/nibmcs.svg',
  })
  @IsUrl()
  readonly light: string;

  @ApiProperty({
    description: 'URL to the logo for dark mode',
    example:
      'https://dileepadev.blob.core.windows.net/images/communities/nibmcs.svg',
  })
  @IsUrl()
  readonly dark: string;
}

export class CommunityDto {
  @ApiProperty({
    description: 'The name of the community',
    example: 'NIBM Computer Society',
  })
  @IsString()
  readonly name: string;

  @ApiProperty({
    description: 'The role held in the community',
    example: 'Founding Member & President',
  })
  @IsString()
  readonly role: string;

  @ApiProperty({
    description: 'The period of involvement',
    example: 'Oct 2022 - Dec 2023',
  })
  @IsString()
  readonly period: string;

  @ApiProperty({
    description: 'A description of the community involvement',
    example:
      'Led the society in organizing events, workshops, and meetups to foster…',
  })
  @IsString()
  readonly description: string;

  @ApiProperty({
    description: 'Community logo URLs',
    type: LogoDto,
  })
  @ValidateNested()
  @Type(() => LogoDto)
  readonly logo: LogoDto;

  @ApiProperty({
    description: 'Whether currently involved',
    example: true,
  })
  @IsBoolean()
  @IsOptional()
  readonly current?: boolean;
}

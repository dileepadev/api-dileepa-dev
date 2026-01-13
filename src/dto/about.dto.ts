import { ApiProperty } from '@nestjs/swagger';
import { IsString, IsObject, ValidateNested, IsUrl } from 'class-validator';
import { Type } from 'class-transformer';

class ImagesDto {
  @ApiProperty({
    description: 'URL for the profile image in PNG format',
    example: 'https://dileepadev.blob.core.windows.net/images/profile.png',
  })
  @IsUrl()
  readonly profile_png: string;

  @ApiProperty({
    description: 'URL for the profile image in WEBP format',
    example: 'https://dileepadev.blob.core.windows.net/images/profile.webp',
  })
  @IsUrl()
  readonly profile_webp: string;

  @ApiProperty({
    description: 'URL for the banner image in WEBP format',
    example: 'https://dileepadev.blob.core.windows.net/images/banner.webp',
  })
  @IsUrl()
  readonly banner_webp: string;
}

export class AboutDto {
  @ApiProperty({
    description: 'The name of the person',
    example: 'Dileepa Bandara',
  })
  @IsString()
  readonly name: string;

  @ApiProperty({
    description: 'A short description about the person',
    example: "Hi! I'm an associate ai engineer focusing on...",
  })
  @IsString()
  readonly description: string;

  @ApiProperty({
    description: 'Contact email address',
    example: 'contact@dleepa.dev',
  })
  @IsString()
  readonly email: string;

  @ApiProperty({
    description: 'Job title',
    example: 'Associate AI Engineer',
  })
  @IsString()
  readonly title: string;

  @ApiProperty({
    description: 'URLs for profile and banner images',
    type: ImagesDto,
  })
  @IsObject()
  @ValidateNested()
  @Type(() => ImagesDto)
  readonly images: ImagesDto;
}

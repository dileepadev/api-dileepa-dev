import { ApiProperty } from '@nestjs/swagger';

export class UploadResponseDto {
  @ApiProperty({ description: 'The secure URL of the uploaded image' })
  url: string;

  @ApiProperty({
    description: 'The Cloudinary public ID of the uploaded image',
  })
  publicId: string;

  @ApiProperty({ description: 'Image width in pixels' })
  width: number;

  @ApiProperty({ description: 'Image height in pixels' })
  height: number;

  @ApiProperty({ description: 'Image format (e.g., jpg, png, webp)' })
  format: string;

  @ApiProperty({ description: 'File size in bytes' })
  bytes: number;
}

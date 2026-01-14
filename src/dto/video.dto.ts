import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class VideoDto {
  @ApiProperty({
    description: 'The title of the video',
    example: 'What is Azure AI',
  })
  @IsString()
  readonly title: string;

  @ApiProperty({
    description: 'The publication date of the video',
    example: '2025-02-24',
  })
  @IsString()
  readonly date: string;

  @ApiProperty({
    description: 'The link to the video',
    example: 'https://www.youtube.com/watch?v=YfrZkAx2Eao',
  })
  @IsString()
  readonly link: string;

  @ApiProperty({
    description: 'URL to the video thumbnail',
    example:
      'https://dileepadev.blob.core.windows.net/images/videos/v2p2e1_thumbnail.png',
  })
  @IsString()
  readonly thumbnail: string;
}

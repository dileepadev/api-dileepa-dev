import { IsNotEmpty, IsString, IsUrl, ValidateNested } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';

class LogoDto {
  @ApiProperty({
    description: 'URL to the image for light mode',
    example: 'https://dileepadev.blob.core.windows.net/images/tools/python.svg',
  })
  @IsUrl()
  readonly light: string;

  @ApiProperty({
    description: 'URL to the image for dark mode',
    example: 'https://dileepadev.blob.core.windows.net/images/tools/python.svg',
  })
  @IsUrl()
  readonly dark: string;
}

export class ToolDto {
  @ApiProperty({
    description: 'The name of the tool or technology.',
    example: 'Python',
  })
  @IsString()
  @IsNotEmpty()
  readonly name: string;

  @ApiProperty({
    description: 'Tools logo URLs',
    type: LogoDto,
  })
  @ValidateNested()
  @Type(() => LogoDto)
  readonly logo: LogoDto;
}

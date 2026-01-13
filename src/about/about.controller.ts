import { Controller, Get, NotFoundException } from '@nestjs/common';
import { AboutService } from './about.service';
import { AboutDto } from '../dto/about.dto';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';

@ApiTags('About')
@Controller('about')
export class AboutController {
  constructor(private readonly aboutService: AboutService) {}

  @Get()
  @ApiOperation({
    summary: 'Get information about the owner',
  })
  @ApiResponse({
    status: 200,
    description: 'Successfully retrieved about information.',
    type: AboutDto,
  })
  @ApiResponse({
    status: 404,
    description: 'About information not found.',
  })
  async findOne(): Promise<AboutDto> {
    const aboutInfo = await this.aboutService.findOne();
    if (!aboutInfo) {
      throw new NotFoundException('About information not found.');
    }
    return aboutInfo;
  }
}

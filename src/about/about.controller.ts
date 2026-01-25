import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Delete,
  NotFoundException,
} from '@nestjs/common';
import { AboutService } from './about.service';
import { AboutDto } from './dto/about.dto';
import { CreateAboutDto } from './dto/create-about.dto';
import { UpdateAboutDto } from './dto/update-about.dto';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
} from '@nestjs/swagger';
import { Public } from '../auth/decorators/public.decorator';
import { Roles } from '../auth/decorators/roles.decorator';

@ApiTags('about')
@ApiBearerAuth('JWT-auth')
@Controller('about')
export class AboutController {
  constructor(private readonly aboutService: AboutService) {}

  @Roles('admin')
  @Post()
  @ApiOperation({ summary: 'Create about information' })
  @ApiResponse({
    status: 201,
    description: 'About information created.',
    type: AboutDto,
  })
  create(@Body() createAboutDto: CreateAboutDto) {
    return this.aboutService.create(createAboutDto);
  }

  @Public()
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

  @Roles('admin')
  @Patch()
  @ApiOperation({ summary: 'Update about information' })
  @ApiResponse({
    status: 200,
    description: 'About information updated.',
    type: AboutDto,
  })
  @ApiResponse({
    status: 404,
    description: 'About information not found.',
  })
  async update(@Body() updateAboutDto: UpdateAboutDto) {
    return this.aboutService.update(updateAboutDto);
  }

  @Roles('admin')
  @Delete()
  @ApiOperation({ summary: 'Delete about information' })
  @ApiResponse({
    status: 200,
    description: 'About information deleted.',
    type: AboutDto,
  })
  @ApiResponse({
    status: 404,
    description: 'About information not found.',
  })
  async remove() {
    return this.aboutService.remove();
  }
}

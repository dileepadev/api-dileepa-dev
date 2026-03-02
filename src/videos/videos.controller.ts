import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Param,
  Delete,
  NotFoundException,
} from '@nestjs/common';
import { VideosService } from './videos.service';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
} from '@nestjs/swagger';
import { VideoDto } from './dto/video.dto';
import { CreateVideoDto } from './dto/create-video.dto';
import { UpdateVideoDto } from './dto/update-video.dto';
import { Public } from '../auth/decorators/public.decorator';
import { Roles } from '../auth/decorators/roles.decorator';

@ApiTags('videos')
@ApiBearerAuth('JWT-auth')
@Controller('videos')
export class VideosController {
  constructor(private readonly videosService: VideosService) {}

  @Roles('admin')
  @Post()
  @ApiOperation({ summary: 'Create a new video' })
  @ApiResponse({
    status: 201,
    description: 'The video has been successfully created.',
    type: VideoDto,
  })
  create(@Body() createVideoDto: CreateVideoDto) {
    return this.videosService.create(createVideoDto);
  }

  @Public()
  @Get()
  @ApiOperation({
    summary: 'Get all videos',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns an array of video objects.',
    type: [VideoDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No videos found.',
  })
  async findAll(): Promise<VideoDto[]> {
    const videos = await this.videosService.findAll();
    if (!videos || videos.length === 0) {
      throw new NotFoundException('No videos found.');
    }
    return videos;
  }

  @Public()
  @Get(':id')
  @ApiOperation({ summary: 'Get a specific video' })
  @ApiResponse({
    status: 200,
    description: 'Returns the video.',
    type: VideoDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Video not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.videosService.findOne(id);
  }

  @Roles('admin')
  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific video' })
  @ApiResponse({
    status: 200,
    description: 'The video has been successfully updated.',
    type: VideoDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Video not found.',
  })
  async update(
    @Param('id') id: string,
    @Body() updateVideoDto: UpdateVideoDto,
  ) {
    return this.videosService.update(id, updateVideoDto);
  }

  @Roles('admin')
  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific video' })
  @ApiResponse({
    status: 200,
    description: 'The video has been successfully deleted.',
    type: VideoDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Video not found.',
  })
  async remove(@Param('id') id: string) {
    return this.videosService.remove(id);
  }
}

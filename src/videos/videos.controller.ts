import { Controller, Get, NotFoundException } from '@nestjs/common';
import { VideosService } from './videos.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { VideoDto } from '../dto/video.dto';

@ApiTags('Videos')
@Controller('videos')
export class VideosController {
  constructor(private readonly videosService: VideosService) {}

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
}

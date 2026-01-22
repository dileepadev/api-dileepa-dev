import { Controller, Get, NotFoundException } from '@nestjs/common';
import { CommunitiesService } from './communities.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { CommunityDto } from '../dto/community.dto';

@ApiTags('Communities')
@Controller('communities')
export class CommunitiesController {
  constructor(private readonly communitiesService: CommunitiesService) {}

  @Get()
  @ApiOperation({
    summary: 'Get all communities',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns an array of community objects.',
    type: [CommunityDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No communities found.',
  })
  async findAll(): Promise<CommunityDto[]> {
    const communities = await this.communitiesService.findAll();
    if (!communities || communities.length === 0) {
      throw new NotFoundException('No communities found.');
    }
    return communities;
  }
}

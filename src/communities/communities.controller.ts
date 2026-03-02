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
import { CommunitiesService } from './communities.service';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
} from '@nestjs/swagger';
import { CommunityDto } from './dto/community.dto';
import { CreateCommunityDto } from './dto/create-community.dto';
import { UpdateCommunityDto } from './dto/update-community.dto';
import { Public } from '../auth/decorators/public.decorator';
import { Roles } from '../auth/decorators/roles.decorator';

@ApiTags('communities')
@ApiBearerAuth('JWT-auth')
@Controller('communities')
export class CommunitiesController {
  constructor(private readonly communitiesService: CommunitiesService) {}

  @Roles('admin')
  @Post()
  @ApiOperation({ summary: 'Create a new community' })
  @ApiResponse({
    status: 201,
    description: 'The community has been successfully created.',
    type: CommunityDto,
  })
  create(@Body() createCommunityDto: CreateCommunityDto) {
    return this.communitiesService.create(createCommunityDto);
  }

  @Public()
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

  @Public()
  @Get(':id')
  @ApiOperation({ summary: 'Get a specific community' })
  @ApiResponse({
    status: 200,
    description: 'Returns the community.',
    type: CommunityDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Community not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.communitiesService.findOne(id);
  }

  @Roles('admin')
  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific community' })
  @ApiResponse({
    status: 200,
    description: 'The community has been successfully updated.',
    type: CommunityDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Community not found.',
  })
  async update(
    @Param('id') id: string,
    @Body() updateCommunityDto: UpdateCommunityDto,
  ) {
    return this.communitiesService.update(id, updateCommunityDto);
  }

  @Roles('admin')
  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific community' })
  @ApiResponse({
    status: 200,
    description: 'The community has been successfully deleted.',
    type: CommunityDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Community not found.',
  })
  async remove(@Param('id') id: string) {
    return this.communitiesService.remove(id);
  }
}

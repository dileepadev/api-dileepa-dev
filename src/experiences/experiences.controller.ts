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
import { ExperiencesService } from './experiences.service';
import { ExperienceDto } from './dto/experience.dto';
import { CreateExperienceDto } from './dto/create-experience.dto';
import { UpdateExperienceDto } from './dto/update-experience.dto';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
} from '@nestjs/swagger';
import { Public } from '../auth/decorators/public.decorator';
import { Roles } from '../auth/decorators/roles.decorator';

@ApiTags('experiences')
@ApiBearerAuth('JWT-auth')
@Controller('experiences')
export class ExperiencesController {
  constructor(private readonly experiencesService: ExperiencesService) {}

  @Roles('admin')
  @Post()
  @ApiOperation({ summary: 'Create a new experience entry' })
  @ApiResponse({
    status: 201,
    description: 'The experience entry has been successfully created.',
    type: ExperienceDto,
  })
  create(@Body() createExperienceDto: CreateExperienceDto) {
    return this.experiencesService.create(createExperienceDto);
  }

  @Public()
  @Get()
  @ApiOperation({
    summary: 'Get all experience entries',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns all experience entries.',
    type: [ExperienceDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No experience entries found.',
  })
  async findAll(): Promise<ExperienceDto[]> {
    const experiences = await this.experiencesService.findAll();
    if (!experiences || experiences.length === 0) {
      throw new NotFoundException('No experience entries found.');
    }
    return experiences;
  }

  @Public()
  @Get(':id')
  @ApiOperation({ summary: 'Get a specific experience entry' })
  @ApiResponse({
    status: 200,
    description: 'Returns the experience entry.',
    type: ExperienceDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Experience entry not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.experiencesService.findOne(id);
  }

  @Roles('admin')
  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific experience entry' })
  @ApiResponse({
    status: 200,
    description: 'The experience entry has been successfully updated.',
    type: ExperienceDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Experience entry not found.',
  })
  async update(
    @Param('id') id: string,
    @Body() updateExperienceDto: UpdateExperienceDto,
  ) {
    return this.experiencesService.update(id, updateExperienceDto);
  }

  @Roles('admin')
  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific experience entry' })
  @ApiResponse({
    status: 200,
    description: 'The experience entry has been successfully deleted.',
    type: ExperienceDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Experience entry not found.',
  })
  async remove(@Param('id') id: string) {
    return this.experiencesService.remove(id);
  }
}

import { Controller, Get, NotFoundException } from '@nestjs/common';
import { ExperiencesService } from './experiences.service';
import { ExperienceDto } from './dto/experience.dto';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';

@ApiTags('Experiences')
@Controller('experiences')
export class ExperiencesController {
  constructor(private readonly experiencesService: ExperiencesService) {}

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
}

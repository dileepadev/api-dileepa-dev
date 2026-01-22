import { Controller, Get, NotFoundException } from '@nestjs/common';
import { EducationsService } from './educations.service';
import { EducationDto } from '../dto/education.dto';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';

@ApiTags('Educations')
@Controller('educations')
export class EducationsController {
  constructor(private readonly educationsService: EducationsService) {}

  @Get()
  @ApiOperation({
    summary: 'Get all education entries',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns all education entries.',
    type: EducationDto,
  })
  @ApiResponse({
    status: 404,
    description: 'No education entries found.',
  })
  async findAll(): Promise<EducationDto[]> {
    const educations = await this.educationsService.findAll();
    if (!educations || educations.length === 0) {
      throw new NotFoundException('No education entries found.');
    }
    return educations;
  }
}

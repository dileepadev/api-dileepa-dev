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
import { EducationsService } from './educations.service';
import { EducationDto } from './dto/education.dto';
import { CreateEducationDto } from './dto/create-education.dto';
import { UpdateEducationDto } from './dto/update-education.dto';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';

@ApiTags('Educations')
@Controller('educations')
export class EducationsController {
  constructor(private readonly educationsService: EducationsService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new education entry' })
  @ApiResponse({
    status: 201,
    description: 'The education entry has been successfully created.',
    type: EducationDto,
  })
  create(@Body() createEducationDto: CreateEducationDto) {
    return this.educationsService.create(createEducationDto);
  }

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

  @Get(':id')
  @ApiOperation({ summary: 'Get a specific education entry' })
  @ApiResponse({
    status: 200,
    description: 'Returns the education entry.',
    type: EducationDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Education entry not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.educationsService.findOne(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific education entry' })
  @ApiResponse({
    status: 200,
    description: 'The education entry has been successfully updated.',
    type: EducationDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Education entry not found.',
  })
  async update(
    @Param('id') id: string,
    @Body() updateEducationDto: UpdateEducationDto,
  ) {
    return this.educationsService.update(id, updateEducationDto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific education entry' })
  @ApiResponse({
    status: 200,
    description: 'The education entry has been successfully deleted.',
    type: EducationDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Education entry not found.',
  })
  async remove(@Param('id') id: string) {
    return this.educationsService.remove(id);
  }
}

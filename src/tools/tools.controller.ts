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
import { ToolsService } from './tools.service';
import { ToolDto } from './dto/tool.dto';
import { CreateToolDto } from './dto/create-tool.dto';
import { UpdateToolDto } from './dto/update-tool.dto';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
} from '@nestjs/swagger';
import { Public } from '../auth/decorators/public.decorator';
import { Roles } from '../auth/decorators/roles.decorator';

@ApiTags('tools')
@ApiBearerAuth('JWT-auth')
@Controller('tools')
export class ToolsController {
  constructor(private readonly toolsService: ToolsService) {}

  @Roles('admin')
  @Post()
  @ApiOperation({ summary: 'Create a new tool' })
  @ApiResponse({
    status: 201,
    description: 'The tool has been successfully created.',
    type: ToolDto,
  })
  create(@Body() createToolDto: CreateToolDto) {
    return this.toolsService.create(createToolDto);
  }

  @Public()
  @Get()
  @ApiOperation({
    summary: 'Get all tools',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns an array of tool objects.',
    type: [ToolDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No tools found.',
  })
  async findAll(): Promise<ToolDto[]> {
    const tools = await this.toolsService.findAll();
    if (!tools || tools.length === 0) {
      throw new NotFoundException('No tools found.');
    }
    return tools;
  }

  @Public()
  @Get(':id')
  @ApiOperation({ summary: 'Get a specific tool' })
  @ApiResponse({
    status: 200,
    description: 'Returns the tool.',
    type: ToolDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Tool not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.toolsService.findOne(id);
  }

  @Roles('admin')
  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific tool' })
  @ApiResponse({
    status: 200,
    description: 'The tool has been successfully updated.',
    type: ToolDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Tool not found.',
  })
  async update(@Param('id') id: string, @Body() updateToolDto: UpdateToolDto) {
    return this.toolsService.update(id, updateToolDto);
  }

  @Roles('admin')
  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific tool' })
  @ApiResponse({
    status: 200,
    description: 'The tool has been successfully deleted.',
    type: ToolDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Tool not found.',
  })
  async remove(@Param('id') id: string) {
    return this.toolsService.remove(id);
  }
}

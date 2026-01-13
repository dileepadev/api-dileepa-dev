import { Controller, Get, NotFoundException } from '@nestjs/common';
import { ToolsService } from './tools.service';
import { ToolDto } from '../dto/tool.dto';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';

@ApiTags('Tools')
@Controller('tools')
export class ToolsController {
  constructor(private readonly toolsService: ToolsService) {}

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
}

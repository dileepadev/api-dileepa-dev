import { Controller, Get, NotFoundException } from '@nestjs/common';
import { BlogsService } from './blogs.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { BlogDto } from './dto/blog.dto';

@ApiTags('Blogs')
@Controller('blogs')
export class BlogsController {
  constructor(private readonly blogsService: BlogsService) {}

  @Get()
  @ApiOperation({
    summary: 'Get all blog posts',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns an array of blog post objects.',
    type: [BlogDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No blog posts found.',
  })
  async findAll(): Promise<BlogDto[]> {
    const blogs = await this.blogsService.findAll();
    if (!blogs || blogs.length === 0) {
      throw new NotFoundException('No blog posts found.');
    }
    return blogs;
  }
}

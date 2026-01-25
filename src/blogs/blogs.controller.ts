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
import { BlogsService } from './blogs.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { BlogDto } from './dto/blog.dto';
import { CreateBlogDto } from './dto/create-blog.dto';
import { UpdateBlogDto } from './dto/update-blog.dto';

@ApiTags('Blogs')
@Controller('blogs')
export class BlogsController {
  constructor(private readonly blogsService: BlogsService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new blog post' })
  @ApiResponse({
    status: 201,
    description: 'The blog post has been successfully created.',
    type: BlogDto,
  })
  create(@Body() createBlogDto: CreateBlogDto) {
    return this.blogsService.create(createBlogDto);
  }

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

  @Get(':id')
  @ApiOperation({ summary: 'Get a specific blog post' })
  @ApiResponse({
    status: 200,
    description: 'Returns the blog post.',
    type: BlogDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Blog post not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.blogsService.findOne(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific blog post' })
  @ApiResponse({
    status: 200,
    description: 'The blog post has been successfully updated.',
    type: BlogDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Blog post not found.',
  })
  async update(@Param('id') id: string, @Body() updateBlogDto: UpdateBlogDto) {
    return this.blogsService.update(id, updateBlogDto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific blog post' })
  @ApiResponse({
    status: 200,
    description: 'The blog post has been successfully deleted.',
    type: BlogDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Blog post not found.',
  })
  async remove(@Param('id') id: string) {
    return this.blogsService.remove(id);
  }
}

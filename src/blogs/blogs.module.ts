import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { BlogsService } from './blogs.service';
import { Blog, BlogSchema } from '../schemas/blog.schema';
import { BlogsController } from './blogs.controller';

@Module({
  imports: [
    MongooseModule.forFeature([{ name: Blog.name, schema: BlogSchema }]),
  ],
  controllers: [BlogsController],
  providers: [BlogsService],
})
export class BlogsModule {}

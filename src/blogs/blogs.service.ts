import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Blog, BlogDocument } from '../schemas/blog.schema';
import { BlogDto } from 'src/dto/blog.dto';

@Injectable()
export class BlogsService {
  constructor(
    @InjectModel(Blog.name)
    private readonly blogModel: Model<BlogDocument>,
  ) {}

  async findAll(): Promise<BlogDto[]> {
    return this.blogModel
      .find()
      .sort({ sortDate: -1 })
      .select('-sortDate')
      .exec();
  }
}

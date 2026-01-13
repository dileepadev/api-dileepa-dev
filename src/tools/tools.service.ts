import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Tool, ToolDocument } from '../schemas/tool.schema';
import { ToolDto } from '../dto/tool.dto';

@Injectable()
export class ToolsService {
  constructor(
    @InjectModel(Tool.name)
    private readonly toolModel: Model<ToolDocument>,
  ) {}

  async findAll(): Promise<ToolDto[]> {
    return this.toolModel.find().exec();
  }
}

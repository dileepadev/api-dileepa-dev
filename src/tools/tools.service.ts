import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Tool, ToolDocument } from './schemas/tool.schema';
import { ToolDto } from './dto/tool.dto';
import { CreateToolDto } from './dto/create-tool.dto';
import { UpdateToolDto } from './dto/update-tool.dto';

@Injectable()
export class ToolsService {
  constructor(
    @InjectModel(Tool.name)
    private readonly toolModel: Model<ToolDocument>,
  ) {}

  async create(createToolDto: CreateToolDto): Promise<Tool> {
    const createdTool = new this.toolModel(createToolDto);
    return createdTool.save();
  }

  async findAll(): Promise<ToolDto[]> {
    return this.toolModel.find().exec();
  }

  async findOne(id: string): Promise<Tool> {
    const tool = await this.toolModel.findById(id).exec();
    if (!tool) {
      throw new NotFoundException(`Tool with ID ${id} not found`);
    }
    return tool;
  }

  async update(id: string, updateToolDto: UpdateToolDto): Promise<Tool> {
    const updatedTool = await this.toolModel
      .findByIdAndUpdate(id, updateToolDto, { new: true })
      .exec();
    if (!updatedTool) {
      throw new NotFoundException(`Tool with ID ${id} not found`);
    }
    return updatedTool;
  }

  async remove(id: string): Promise<Tool> {
    const deletedTool = await this.toolModel.findByIdAndDelete(id).exec();
    if (!deletedTool) {
      throw new NotFoundException(`Tool with ID ${id} not found`);
    }
    return deletedTool;
  }
}

import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Experience, ExperienceDocument } from './schemas/experience.schema';
import { ExperienceDto } from './dto/experience.dto';
import { CreateExperienceDto } from './dto/create-experience.dto';
import { UpdateExperienceDto } from './dto/update-experience.dto';

@Injectable()
export class ExperiencesService {
  constructor(
    @InjectModel(Experience.name)
    private experienceModel: Model<ExperienceDocument>,
  ) {}

  async create(createExperienceDto: CreateExperienceDto): Promise<Experience> {
    const createdExperience = new this.experienceModel(createExperienceDto);
    return createdExperience.save();
  }

  async findAll(): Promise<ExperienceDto[]> {
    return this.experienceModel
      .find()
      .sort({ sortDate: -1 })
      .select('-sortDate')
      .exec();
  }

  async findOne(id: string): Promise<Experience> {
    const experience = await this.experienceModel.findById(id).exec();
    if (!experience) {
      throw new NotFoundException(`Experience with ID ${id} not found`);
    }
    return experience;
  }

  async update(
    id: string,
    updateExperienceDto: UpdateExperienceDto,
  ): Promise<Experience> {
    const updatedExperience = await this.experienceModel
      .findByIdAndUpdate(id, updateExperienceDto, { new: true })
      .exec();
    if (!updatedExperience) {
      throw new NotFoundException(`Experience with ID ${id} not found`);
    }
    return updatedExperience;
  }

  async remove(id: string): Promise<Experience> {
    const deletedExperience = await this.experienceModel
      .findByIdAndDelete(id)
      .exec();
    if (!deletedExperience) {
      throw new NotFoundException(`Experience with ID ${id} not found`);
    }
    return deletedExperience;
  }
}

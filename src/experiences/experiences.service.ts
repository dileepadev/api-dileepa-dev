import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Experience, ExperienceDocument } from '../schemas/experience.schema';
import { ExperienceDto } from 'src/dto/experience.dto';

@Injectable()
export class ExperiencesService {
  constructor(
    @InjectModel(Experience.name)
    private experienceModel: Model<ExperienceDocument>,
  ) {}

  async findAll(): Promise<ExperienceDto[]> {
    return this.experienceModel.find().exec();
  }
}

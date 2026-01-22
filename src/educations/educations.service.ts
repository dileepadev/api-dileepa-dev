import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Education, EducationDocument } from './schemas/education.schema';
import { EducationDto } from './dto/education.dto';

@Injectable()
export class EducationsService {
  constructor(
    @InjectModel(Education.name)
    private educationModel: Model<EducationDocument>,
  ) {}

  async findAll(): Promise<EducationDto[]> {
    return this.educationModel
      .find()
      .sort({ sortDate: -1 })
      .select('-sortDate')
      .exec();
  }
}

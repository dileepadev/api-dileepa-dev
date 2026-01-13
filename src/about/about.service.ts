import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { About, AboutDocument } from '../schemas/about.schema';
import { AboutDto } from 'src/dto/about.dto';

@Injectable()
export class AboutService {
  constructor(
    @InjectModel(About.name)
    private aboutModel: Model<AboutDocument>,
  ) {}

  async findOne(): Promise<AboutDto | null> {
    return this.aboutModel.findOne().exec();
  }
}

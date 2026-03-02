import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { About, AboutDocument } from './schemas/about.schema';
import { AboutDto } from './dto/about.dto';
import { CreateAboutDto } from './dto/create-about.dto';
import { UpdateAboutDto } from './dto/update-about.dto';

@Injectable()
export class AboutService {
  constructor(
    @InjectModel(About.name)
    private aboutModel: Model<AboutDocument>,
  ) {}

  async create(createAboutDto: CreateAboutDto): Promise<About> {
    const createdAbout = new this.aboutModel(createAboutDto);
    return createdAbout.save();
  }

  async findOne(): Promise<AboutDto | null> {
    return this.aboutModel.findOne().exec();
  }

  async update(updateAboutDto: UpdateAboutDto): Promise<About> {
    const updatedAbout = await this.aboutModel
      .findOneAndUpdate({}, updateAboutDto, { new: true })
      .exec();
    if (!updatedAbout) {
      throw new NotFoundException('About information not found');
    }
    return updatedAbout;
  }

  async remove(): Promise<About> {
    const deletedAbout = await this.aboutModel.findOneAndDelete({}).exec();
    if (!deletedAbout) {
      throw new NotFoundException('About information not found');
    }
    return deletedAbout;
  }
}

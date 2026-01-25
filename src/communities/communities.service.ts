import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Community, CommunityDocument } from './schemas/community.schema';
import { CommunityDto } from './dto/community.dto';
import { CreateCommunityDto } from './dto/create-community.dto';
import { UpdateCommunityDto } from './dto/update-community.dto';

@Injectable()
export class CommunitiesService {
  constructor(
    @InjectModel(Community.name)
    private readonly communityModel: Model<CommunityDocument>,
  ) {}

  async create(createCommunityDto: CreateCommunityDto): Promise<Community> {
    const createdCommunity = new this.communityModel(createCommunityDto);
    return createdCommunity.save();
  }

  async findAll(): Promise<CommunityDto[]> {
    return this.communityModel
      .find()
      .sort({ sortDate: -1 })
      .select('-sortDate')
      .exec();
  }

  async findOne(id: string): Promise<Community> {
    const community = await this.communityModel.findById(id).exec();
    if (!community) {
      throw new NotFoundException(`Community with ID ${id} not found`);
    }
    return community;
  }

  async update(
    id: string,
    updateCommunityDto: UpdateCommunityDto,
  ): Promise<Community> {
    const updatedCommunity = await this.communityModel
      .findByIdAndUpdate(id, updateCommunityDto, { new: true })
      .exec();
    if (!updatedCommunity) {
      throw new NotFoundException(`Community with ID ${id} not found`);
    }
    return updatedCommunity;
  }

  async remove(id: string): Promise<Community> {
    const deletedCommunity = await this.communityModel
      .findByIdAndDelete(id)
      .exec();
    if (!deletedCommunity) {
      throw new NotFoundException(`Community with ID ${id} not found`);
    }
    return deletedCommunity;
  }
}

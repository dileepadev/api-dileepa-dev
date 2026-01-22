import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Community, CommunityDocument } from './schemas/community.schema';
import { CommunityDto } from './dto/community.dto';

@Injectable()
export class CommunitiesService {
  constructor(
    @InjectModel(Community.name)
    private readonly communityModel: Model<CommunityDocument>,
  ) {}

  async findAll(): Promise<CommunityDto[]> {
    return this.communityModel
      .find()
      .sort({ sortDate: -1 })
      .select('-sortDate')
      .exec();
  }
}

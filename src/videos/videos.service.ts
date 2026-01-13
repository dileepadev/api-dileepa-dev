import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Video, VideoDocument } from '../schemas/video.schema';
import { VideoDto } from 'src/dto/video.dto';

@Injectable()
export class VideosService {
  constructor(
    @InjectModel(Video.name)
    private readonly videoModel: Model<VideoDocument>,
  ) {}

  async findAll(): Promise<VideoDto[]> {
    return this.videoModel.find().exec();
  }
}

import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Event, EventDocument } from '../schemas/event.schema';
import { EventDto } from 'src/dto/event.dto';

@Injectable()
export class EventsService {
  constructor(
    @InjectModel(Event.name)
    private readonly eventModel: Model<EventDocument>,
  ) {}

  async findAll(): Promise<EventDto[]> {
    return this.eventModel.find().exec();
  }
}

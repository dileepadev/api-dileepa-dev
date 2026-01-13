import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { EventsService } from './events.service';
import { Event, EventSchema } from '../schemas/event.schema';
import { EventsController } from './events.controller';

@Module({
  imports: [
    MongooseModule.forFeature([{ name: Event.name, schema: EventSchema }]),
  ],
  controllers: [EventsController],
  providers: [EventsService],
})
export class EventsModule {}

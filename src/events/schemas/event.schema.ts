import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type EventDocument = Event & Document;

@Schema()
export class Event {
  @Prop({ required: true })
  title: string;

  @Prop({ required: true })
  date: string;

  @Prop({ required: true })
  location: string;

  @Prop({ required: true })
  format: string;

  @Prop({ required: true })
  description: string;
}

export const EventSchema = SchemaFactory.createForClass(Event);

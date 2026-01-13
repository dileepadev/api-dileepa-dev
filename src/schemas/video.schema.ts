import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type VideoDocument = Video & Document;

@Schema()
export class Video {
  @Prop({ required: true })
  title: string;

  @Prop({ required: true })
  views: string;

  @Prop({ required: true })
  date: string;

  @Prop({ required: true })
  link: string;

  @Prop({ required: true })
  thumbnail: string;
}

export const VideoSchema = SchemaFactory.createForClass(Video);

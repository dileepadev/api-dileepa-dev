import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type BlogDocument = Blog & Document;

@Schema()
export class Blog {
  @Prop({ required: true, unique: true })
  slug!: string;

  @Prop({ required: true })
  title!: string;

  @Prop({ required: true })
  date!: string;

  @Prop({ required: true })
  excerpt!: string;

  @Prop({ required: false, default: 0 })
  index!: number;

  @Prop({ required: true })
  link!: string;

  @Prop({ required: true })
  bannerUrl!: string;
}

export const BlogSchema = SchemaFactory.createForClass(Blog);

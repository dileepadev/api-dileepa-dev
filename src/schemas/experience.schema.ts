import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type ExperienceDocument = HydratedDocument<Experience>;

@Schema({ _id: false })
class Logo {
  @Prop({ required: true })
  light: string;

  @Prop({ required: true })
  dark: string;
}

@Schema({ collection: 'experiences', timestamps: true })
export class Experience {
  @Prop({ required: true })
  title: string;

  @Prop({ required: true })
  company: string;

  @Prop({ required: true })
  url: string;

  @Prop({ required: true })
  period: string;

  @Prop({ required: true })
  description: string;

  @Prop({ type: [String], required: true })
  technologies: string[];

  @Prop({ type: Logo, required: true })
  logo: Logo;
}

export const ExperienceSchema = SchemaFactory.createForClass(Experience);

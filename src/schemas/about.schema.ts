import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type AboutDocument = HydratedDocument<About>;

@Schema({ _id: false })
class Images {
  @Prop({ required: true })
  bannerWebp: string;

  @Prop({ required: true })
  profilePng: string;

  @Prop({ required: true })
  profileWebp: string;
}

const ImagesSchema = SchemaFactory.createForClass(Images);

@Schema({ _id: false })
class Links {
  @Prop({ required: true })
  website: string;

  @Prop({ required: true })
  email: string;

  @Prop({ required: true })
  github: string;

  @Prop({ required: true })
  linkedin: string;

  @Prop({ required: true })
  xtwitter: string;

  @Prop({ required: true })
  instagram: string;

  @Prop({ required: true })
  youtube: string;
}

const LinksSchema = SchemaFactory.createForClass(Links);

@Schema({ collection: 'about', timestamps: true })
export class About {
  @Prop({ required: true })
  name: string;

  @Prop({ required: true })
  title: string;

  @Prop({ required: true })
  tagline: string;

  @Prop({ required: true, type: [String] })
  description: string[];

  @Prop({ type: ImagesSchema, required: true })
  images: Images;

  @Prop({ type: LinksSchema, required: true })
  links: Links;

  @Prop({ required: true, type: [String] })
  connect: string[];
}

export const AboutSchema = SchemaFactory.createForClass(About);

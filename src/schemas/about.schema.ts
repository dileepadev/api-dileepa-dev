import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type AboutDocument = HydratedDocument<About>;

@Schema({ _id: false })
class Images {
  @Prop({ required: true })
  profile_png: string;

  @Prop({ required: true })
  profile_webp: string;

  @Prop({ required: true })
  banner_webp: string;
}

const ImagesSchema = SchemaFactory.createForClass(Images);

@Schema({ collection: 'about', timestamps: true })
export class About {
  @Prop({ required: true })
  name: string;

  @Prop({ required: true })
  description: string;

  @Prop({ required: true })
  email: string;

  @Prop({ required: true })
  title: string;

  @Prop({ type: ImagesSchema, required: true })
  images: Images;
}

export const AboutSchema = SchemaFactory.createForClass(About);

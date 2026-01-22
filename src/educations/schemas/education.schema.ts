import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type EducationDocument = HydratedDocument<Education>;

@Schema({ _id: false })
class Logo {
  @Prop({ required: true })
  light: string;

  @Prop({ required: true })
  dark: string;
}

@Schema({ collection: 'educations', timestamps: true })
export class Education {
  @Prop({ required: true })
  course: string;

  @Prop({ required: true })
  institution: string;

  @Prop({ required: true })
  period: string;

  @Prop({ required: true })
  description: string;

  @Prop({ required: true })
  url: string;

  @Prop({ type: Logo, required: true })
  logo: Logo;
}

export const EducationSchema = SchemaFactory.createForClass(Education);

import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type CommunityDocument = Community & Document;

@Schema({ _id: false })
class Logo {
  @Prop({ required: true })
  light: string;

  @Prop({ required: true })
  dark: string;
}

@Schema()
export class Community {
  @Prop({ required: true })
  name: string;

  @Prop({ required: true })
  role: string;

  @Prop({ required: true })
  period: string;

  @Prop({ required: true })
  description: string;

  @Prop({ type: Logo, required: true })
  logo: Logo;

  @Prop()
  current: boolean;
}

export const CommunitySchema = SchemaFactory.createForClass(Community);

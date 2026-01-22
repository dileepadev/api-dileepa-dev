import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document, HydratedDocument } from 'mongoose';

export type ToolDocument = HydratedDocument<Tool>;

@Schema({ _id: false })
class Logo {
  @Prop({ required: true })
  light: string;

  @Prop({ required: true })
  dark: string;
}

@Schema({ collection: 'tools', timestamps: true })
export class Tool {
  @Prop({ required: true, unique: true })
  name: string;

  @Prop({ type: Logo, required: true })
  logo: Logo;
}

export const ToolSchema = SchemaFactory.createForClass(Tool);

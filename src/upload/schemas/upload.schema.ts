import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

export type UploadDocument = Upload & Document;

@Schema({ timestamps: true })
export class Upload {
  @Prop({ required: true })
  url: string;

  @Prop({ required: true })
  publicId: string;

  @Prop({ required: true })
  folder: string;

  @Prop()
  fileName: string;

  @Prop()
  mimetype: string;

  @Prop()
  size: number;

  @Prop()
  width: number;

  @Prop()
  height: number;

  @Prop()
  format: string;
}

export const UploadSchema = SchemaFactory.createForClass(Upload);

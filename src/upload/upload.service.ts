import { Injectable, BadRequestException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import {
  v2 as cloudinary,
  UploadApiResponse,
  UploadApiErrorResponse,
} from 'cloudinary';
import 'multer';
import { Upload, UploadDocument } from './schemas/upload.schema';

@Injectable()
export class UploadService {
  constructor(
    private readonly configService: ConfigService,
    @InjectModel(Upload.name)
    private readonly uploadModel: Model<UploadDocument>,
  ) {
    cloudinary.config({
      cloud_name: this.configService.get<string>('CLOUDINARY_CLOUD_NAME'),
      api_key: this.configService.get<string>('CLOUDINARY_API_KEY'),
      api_secret: this.configService.get<string>('CLOUDINARY_API_SECRET'),
    });
  }

  async uploadImage(
    file: Express.Multer.File,
    folder?: string,
  ): Promise<UploadApiResponse> {
    if (!file) {
      throw new BadRequestException('No file provided');
    }

    const allowedMimeTypes: string[] = [
      'image/jpeg',
      'image/png',
      'image/webp',
      'image/gif',
      'image/svg+xml',
    ];

    const mimetype: string = file.mimetype;
    if (!allowedMimeTypes.includes(mimetype)) {
      throw new BadRequestException(
        `Invalid file type: ${mimetype}. Allowed types: ${allowedMimeTypes.join(', ')}`,
      );
    }

    const maxSize = 10 * 1024 * 1024; // 10 MB
    if (file.size > maxSize) {
      throw new BadRequestException(
        `File too large. Maximum size is ${String(maxSize / (1024 * 1024))} MB`,
      );
    }

    const folderName = folder || 'dileepa-dev';
    const uploadFolder = `api-dileepa-dev/${folderName}`;

    const result = await new Promise<UploadApiResponse>((resolve, reject) => {
      const uploadStream = cloudinary.uploader.upload_stream(
        {
          folder: uploadFolder,
          resource_type: 'image',
        },
        (
          error: UploadApiErrorResponse | undefined,
          result: UploadApiResponse | undefined,
        ) => {
          if (error) {
            reject(
              new BadRequestException(
                `Cloudinary upload failed: ${error.message}`,
              ),
            );
          } else {
            resolve(result as UploadApiResponse);
          }
        },
      );

      uploadStream.end(file.buffer);
    });

    // Save to database
    await this.uploadModel.create({
      url: result.secure_url,
      publicId: result.public_id,
      folder: uploadFolder,
      fileName: file.originalname,
      mimetype: file.mimetype,
      size: file.size,
      width: result.width,
      height: result.height,
      format: result.format,
    });

    return result;
  }

  async findAll(): Promise<Upload[]> {
    return this.uploadModel.find().sort({ createdAt: -1 }).exec();
  }

  async deleteImage(publicId: string): Promise<{ result: string }> {
    if (!publicId) {
      throw new BadRequestException('No public ID provided');
    }

    // Delete from database
    await this.uploadModel.findOneAndDelete({ publicId }).exec();

    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const result = await cloudinary.uploader.destroy(publicId);
    return result as { result: string };
  }
}

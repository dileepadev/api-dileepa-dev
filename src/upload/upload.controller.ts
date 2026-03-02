import {
  Controller,
  Post,
  Get,
  Delete,
  Param,
  UploadedFile,
  UseInterceptors,
  Body,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import {
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiTags,
  ApiConsumes,
  ApiBody,
} from '@nestjs/swagger';
import { UploadService } from './upload.service';
import { Roles } from '../auth/decorators/roles.decorator';
import { UploadResponseDto } from './dto/upload-response.dto';

@ApiTags('upload')
@ApiBearerAuth('JWT-auth')
@Controller('upload')
export class UploadController {
  constructor(private readonly uploadService: UploadService) {}

  @Roles('admin')
  @Post()
  @UseInterceptors(FileInterceptor('file'))
  @ApiConsumes('multipart/form-data')
  @ApiOperation({ summary: 'Upload an image to Cloudinary' })
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        file: {
          type: 'string',
          format: 'binary',
          description: 'Image file (JPEG, PNG, WebP, GIF, SVG)',
        },
        folder: {
          type: 'string',
          description:
            'Optional Cloudinary folder name (defaults to "dileepa-dev")',
        },
      },
      required: ['file'],
    },
  })
  @ApiResponse({
    status: 201,
    description: 'Image uploaded successfully.',
  })
  @ApiResponse({ status: 400, description: 'Invalid file or upload failed.' })
  @ApiResponse({ status: 401, description: 'Unauthorized.' })
  async uploadImage(
    @UploadedFile() file: Express.Multer.File,
    @Body('folder') folder?: string,
  ): Promise<UploadResponseDto> {
    const result = await this.uploadService.uploadImage(file, folder);
    return {
      url: result.secure_url,
      publicId: result.public_id,
      width: result.width,
      height: result.height,
      format: result.format,
      bytes: result.bytes,
    };
  }

  @Roles('admin')
  @Get()
  @ApiOperation({ summary: 'List all uploaded images' })
  @ApiResponse({ status: 200, description: 'Return all uploaded images.' })
  @ApiResponse({ status: 401, description: 'Unauthorized.' })
  async findAll() {
    return this.uploadService.findAll();
  }

  @Roles('admin')
  @Delete(':publicId')
  @ApiOperation({ summary: 'Delete an image from Cloudinary' })
  @ApiResponse({ status: 200, description: 'Image deleted successfully.' })
  @ApiResponse({ status: 400, description: 'Delete failed.' })
  @ApiResponse({ status: 401, description: 'Unauthorized.' })
  async deleteImage(@Param('publicId') publicId: string) {
    return this.uploadService.deleteImage(publicId);
  }
}

import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { EducationsService } from './educations.service';
import { Education, EducationSchema } from '../schemas/education.schema';
import { EducationsController } from './educations.controller';

@Module({
  imports: [
    MongooseModule.forFeature([
      { name: Education.name, schema: EducationSchema },
    ]),
  ],
  controllers: [EducationsController],
  providers: [EducationsService],
})
export class EducationsModule {}

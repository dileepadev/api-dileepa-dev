import {
  Injectable,
  InternalServerErrorException,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Resend } from 'resend';
import { CreateContactDto } from './dto/create-contact.dto';

@Injectable()
export class ContactService {
  private resend: Resend;
  private readonly logger = new Logger(ContactService.name);

  constructor(private configService: ConfigService) {
    const apiKey = this.configService.get<string>('RESEND_API_KEY');
    if (apiKey) {
      this.resend = new Resend(apiKey);
    } else {
      this.logger.warn(
        'RESEND_API_KEY is not defined. Email sending will fail.',
      );
    }
  }

  async create(createContactDto: CreateContactDto) {
    if (!this.resend) {
      throw new InternalServerErrorException('Email service is not configured');
    }

    const { name, email, subject, message } = createContactDto;
    const toEmail =
      this.configService.get<string>('CONTACT_EMAIL') || 'contact@dileepa.dev';
    const fromEmail =
      this.configService.get<string>('RESEND_FROM_EMAIL') ||
      'onboarding@resend.dev';

    try {
      const { data, error } = await this.resend.emails.send({
        from: fromEmail,
        to: [toEmail],
        subject: `[Contact Form] ${subject}`,
        html: `
          <h3>New Contact Form Submission</h3>
          <p><strong>Name:</strong> ${name}</p>
          <p><strong>Email:</strong> ${email}</p>
          <p><strong>Subject:</strong> ${subject}</p>
          <br/>
          <p><strong>Message:</strong></p>
          <p>${message}</p>
        `,
        replyTo: email,
      });

      if (error) {
        this.logger.error(`Failed to send email: ${error.message}`, error);
        throw new InternalServerErrorException('Failed to send email');
      }

      this.logger.log(`Email sent successfully: ${data?.id}`);
      return {
        success: true,
        message: 'Email sent successfully',
        id: data?.id,
      };
    } catch (err) {
      this.logger.error('Error sending email', err);
      throw new InternalServerErrorException(
        'Failed to process contact request',
      );
    }
  }
}

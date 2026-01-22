import { Controller, Get, NotFoundException } from '@nestjs/common';
import { EventsService } from './events.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { EventDto } from './dto/event.dto';

@ApiTags('Events')
@Controller('events')
export class EventsController {
  constructor(private readonly eventsService: EventsService) {}

  @Get()
  @ApiOperation({
    summary: 'Get all events',
  })
  @ApiResponse({
    status: 200,
    description: 'Returns an array of event objects.',
    type: [EventDto],
  })
  @ApiResponse({
    status: 404,
    description: 'No events found.',
  })
  async findAll(): Promise<EventDto[]> {
    const events = await this.eventsService.findAll();
    if (!events || events.length === 0) {
      throw new NotFoundException('No events found.');
    }
    return events;
  }
}

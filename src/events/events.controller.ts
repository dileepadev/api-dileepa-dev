import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Param,
  Delete,
  NotFoundException,
} from '@nestjs/common';
import { EventsService } from './events.service';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { EventDto } from './dto/event.dto';
import { CreateEventDto } from './dto/create-event.dto';
import { UpdateEventDto } from './dto/update-event.dto';

@ApiTags('Events')
@Controller('events')
export class EventsController {
  constructor(private readonly eventsService: EventsService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new event' })
  @ApiResponse({
    status: 201,
    description: 'The event has been successfully created.',
    type: EventDto,
  })
  create(@Body() createEventDto: CreateEventDto) {
    return this.eventsService.create(createEventDto);
  }

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

  @Get(':id')
  @ApiOperation({ summary: 'Get a specific event' })
  @ApiResponse({
    status: 200,
    description: 'Returns the event.',
    type: EventDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Event not found.',
  })
  async findOne(@Param('id') id: string) {
    return this.eventsService.findOne(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Update a specific event' })
  @ApiResponse({
    status: 200,
    description: 'The event has been successfully updated.',
    type: EventDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Event not found.',
  })
  async update(
    @Param('id') id: string,
    @Body() updateEventDto: UpdateEventDto,
  ) {
    return this.eventsService.update(id, updateEventDto);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete a specific event' })
  @ApiResponse({
    status: 200,
    description: 'The event has been successfully deleted.',
    type: EventDto,
  })
  @ApiResponse({
    status: 404,
    description: 'Event not found.',
  })
  async remove(@Param('id') id: string) {
    return this.eventsService.remove(id);
  }
}

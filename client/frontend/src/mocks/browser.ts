import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';
import { websocketHandlers } from './websocket';

export const worker = setupWorker(...handlers, ...websocketHandlers);

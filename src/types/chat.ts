export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinkingSteps?: string[];
  timestamp: Date;
}

export interface ChatRequest {
  query: string;
}

export interface ChatResponse {
  answer: string;
}

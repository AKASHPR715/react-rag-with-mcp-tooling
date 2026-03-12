const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function* streamChatMessage(query: string): AsyncIterator<{
  thinking?: string;
  answer_chunk?: string;
  answer?: string;
  error?: string;
}> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errorData.detail || 'Failed to connect to the tax advisor');
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('Readable stream not supported');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data;
          } catch (e) {
            console.error('Error parsing stream chunk:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('Streaming error:', error);
    yield { error: error instanceof Error ? error.message : 'Connection failed' };
  }
}

// Keep the old function for compatibility if needed, but mark as legacy
export async function sendChatMessage(query: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/tax-advisor/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  const data = await response.json();
  return data.answer;
}

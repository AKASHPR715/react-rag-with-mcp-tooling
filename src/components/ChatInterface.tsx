import React, { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { Send } from 'lucide-react';
import { Message } from '../types/chat';
import { streamChatMessage } from '../services/api';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { WelcomeScreen } from './WelcomeScreen';

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const queryText = query.trim();
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: queryText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      thinkingSteps: [],
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const stream = streamChatMessage(queryText);

      for await (const chunk of stream) {
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id === assistantMessageId) {
              const updatedMsg = { ...msg };

              if (chunk.thinking) {
                updatedMsg.thinkingSteps = [...(updatedMsg.thinkingSteps || []), chunk.thinking];
              }
              if (chunk.answer_chunk) {
                updatedMsg.content = updatedMsg.content + chunk.answer_chunk;
              }
              if (chunk.answer) {
                updatedMsg.content = chunk.answer;
              }
              if (chunk.error) {
                setError(chunk.error);
                updatedMsg.content = updatedMsg.content + `\n\n[Error: ${chunk.error}]`;
              }
              return updatedMsg;
            }
            return msg;
          })
        );
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: msg.content + `\n\nI apologize, but I encountered an error: ${errorMessage}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <header className="bg-white/80 backdrop-blur-lg border-b border-slate-200 px-6 py-4 shadow-sm z-10">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-800">Tax Advisor AI</h1>
          <p className="text-sm text-slate-600">Expert guidance on Indian taxation</p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6 font-sans">
          {messages.length === 0 ? (
            <WelcomeScreen onSuggestedQuery={handleSendMessage} />
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isLoading && <TypingIndicator />}
              <div ref={messagesEndRef} className="h-4" />
            </>
          )}
        </div>
      </div>

      <div className="border-t border-slate-200 bg-white/80 backdrop-blur-lg px-6 py-4 shadow-lg z-10">
        <div className="max-w-5xl mx-auto">
          {error && (
            <div className="mb-3 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 animate-fadeIn">
              {error}
            </div>
          )}

          <div className="flex gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask about tax deductions, exemptions, or filing..."
                className="w-full px-4 py-3 pr-12 rounded-xl border-2 border-slate-200 focus:border-blue-500 focus:outline-none resize-none transition-all duration-200 bg-white shadow-sm"
                rows={1}
                disabled={isLoading}
              />
            </div>

            <button
              onClick={() => handleSendMessage(inputValue)}
              disabled={!inputValue.trim() || isLoading}
              className="px-5 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 font-medium shadow-sm hover:shadow-md h-[46px]"
            >
              <Send size={18} />
              <span className="hidden sm:inline">Send</span>
            </button>
          </div>

          <p className="text-xs text-slate-500 mt-2 text-center">
            Press Enter to send • Shift + Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

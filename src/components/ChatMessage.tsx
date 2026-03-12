import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Message } from '../types/chat';
import { Bot, User, ChevronDown, ChevronUp, Brain } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(true);

  return (
    <div
      className={`flex gap-3 mb-6 animate-fadeIn ${isUser ? 'flex-row-reverse' : 'flex-row'
        }`}
    >
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser
            ? 'bg-blue-600 text-white'
            : 'bg-slate-100 text-blue-600 border border-slate-200'
          }`}
      >
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div
        className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'
          }`}
      >
        {/* Thinking Steps Section */}
        {!isUser && message.thinkingSteps && message.thinkingSteps.length > 0 && (
          <div className="mb-2 w-full max-w-lg">
            <button
              onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
              className="flex items-center gap-2 text-[11px] font-semibold text-slate-500 hover:text-blue-600 transition-colors bg-slate-50/80 px-2.5 py-1.5 rounded-lg border border-slate-100 shadow-sm"
            >
              <Brain size={14} className="text-blue-500" />
              <span className="uppercase tracking-wider">Thought Process ({message.thinkingSteps.length})</span>
              {isThinkingExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {isThinkingExpanded && (
              <div className="mt-2 ml-4 pl-3 border-l-2 border-blue-200 flex flex-col gap-1.5 animate-slideDown">
                {message.thinkingSteps.map((step, index) => (
                  <div key={index} className="text-[11px] text-slate-500 leading-relaxed">
                    • {step}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div
          className={`rounded-2xl px-4 py-3 shadow-md transition-all duration-300 ${isUser
              ? 'bg-blue-600 text-white rounded-tr-sm'
              : 'bg-white text-slate-800 border border-slate-100 rounded-tl-sm'
            }`}
        >
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap font-medium">
              {message.content}
            </p>
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-2 prose-li:my-1 prose-headings:my-2 prose-p:leading-relaxed text-slate-800">
              <ReactMarkdown>{message.content || 'Thinking...'}</ReactMarkdown>
            </div>
          )}
        </div>

        <span className="text-[10px] text-slate-400 mt-1.5 px-1 font-medium tracking-tight">
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </div>
  );
}

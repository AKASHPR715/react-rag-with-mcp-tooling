import { Bot } from 'lucide-react';

export function TypingIndicator() {
  return (
    <div className="flex gap-3 mb-6 animate-fadeIn">
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-slate-100 text-blue-600 border border-slate-200">
        <Bot size={18} />
      </div>

      <div className="flex flex-col items-start">
        <div className="rounded-2xl rounded-tl-sm px-4 py-3 bg-white border border-slate-200 shadow-sm">
          <div className="flex gap-1 items-center">
            <span className="text-sm text-slate-600">Tax Advisor is thinking</span>
            <div className="flex gap-1 ml-1">
              <span className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
              <span className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
              <span className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce"></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

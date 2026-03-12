import { Sparkles } from 'lucide-react';

interface WelcomeScreenProps {
  onSuggestedQuery: (query: string) => void;
}

const SUGGESTED_QUERIES = [
  'What is the limit for Section 80C?',
  'Can I claim NPS benefits?',
  'Explain Section 80D.',
];

export function WelcomeScreen({ onSuggestedQuery }: WelcomeScreenProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center animate-fadeIn">
        <div className="mb-6 flex justify-center">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-blue-700 rounded-2xl flex items-center justify-center shadow-lg">
            <Sparkles size={32} className="text-white" />
          </div>
        </div>

        <h1 className="text-3xl font-bold text-slate-800 mb-3">
          Tax Advisor AI
        </h1>
        <p className="text-slate-600 mb-8 text-lg">
          Your intelligent assistant for Indian tax queries. Ask me anything about tax deductions, exemptions, and filing.
        </p>

        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-4">
            Try asking
          </p>
          {SUGGESTED_QUERIES.map((query, index) => (
            <button
              key={index}
              onClick={() => onSuggestedQuery(query)}
              className="w-full px-6 py-4 bg-white border-2 border-slate-200 rounded-xl text-left text-slate-700 hover:border-blue-500 hover:bg-blue-50 transition-all duration-200 hover:shadow-md group"
            >
              <span className="text-sm font-medium group-hover:text-blue-700">
                {query}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

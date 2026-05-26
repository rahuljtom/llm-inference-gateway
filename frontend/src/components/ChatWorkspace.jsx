import { Terminal, Send, Activity } from 'lucide-react';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/atom-one-dark.css';
import { motion, AnimatePresence } from 'framer-motion';

marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  }
});

export function ChatWorkspace({
  messages,
  input,
  setInput,
  isStreaming,
  handleSend,
  messagesEndRef
}) {
  return (
    <main className="flex-1 flex flex-col min-w-0 bg-transparent relative z-0 h-full overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/40 pointer-events-none z-0" />
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6 z-10 custom-scrollbar">
        {messages.length === 0 && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="h-full flex flex-col items-center justify-center text-gray-500 space-y-4"
          >
            <div className="relative">
              <div className="absolute inset-0 bg-primary-500/20 blur-xl rounded-full" />
              <Terminal size={56} className="text-primary-500/50 relative z-10" />
            </div>
            <p className="font-mono text-sm tracking-widest uppercase text-gray-400">Awaiting payload dispatch</p>
          </motion.div>
        )}
        
        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div 
              key={i} 
              initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ duration: 0.3 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-3xl w-full rounded-2xl p-5 shadow-lg ${
                msg.role === 'user' 
                  ? 'bg-gradient-to-br from-primary-600/20 to-primary-900/10 border border-primary-500/30 text-blue-50' 
                  : 'glass-panel text-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-3 text-xs font-mono opacity-60">
                  <span className="flex items-center gap-1.5 font-semibold">
                    {msg.role === 'user' ? (
                      <><div className="w-1.5 h-1.5 rounded-full bg-primary-400" /> Client Payload</>
                    ) : (
                      <><div className="w-1.5 h-1.5 rounded-full bg-success" /> Provider Response</>
                    )}
                  </span>
                  {msg.role === 'assistant' && msg.duration > 0 && (
                    <div className="flex gap-4 text-[10px] items-center bg-black/40 px-3 py-1 rounded-full border border-white/5">
                      <span className="text-primary-400 font-bold">{msg.provider || 'router'}</span>
                      <span className="text-gray-400">{msg.duration}ms</span>
                      <span className="text-gray-400">{msg.tokens} tk</span>
                      <span className="text-success">{(msg.tokens / (msg.duration/1000)).toFixed(1)} tk/s</span>
                    </div>
                  )}
                </div>
                <div 
                  className="markdown-body text-sm text-gray-300"
                  dangerouslySetInnerHTML={{ 
                    __html: marked.parse(msg.content || (isStreaming && msg.role === 'assistant' ? '...' : '')) 
                  }}
                />
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      <div className="p-5 border-t border-white/10 bg-black/60 backdrop-blur-xl shrink-0 z-10">
        <div className="max-w-4xl mx-auto flex gap-4">
          <div className="flex-1 relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-primary-500 to-purple-600 rounded-xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="Enter prompt to dispatch through gateway..."
              className="relative w-full bg-[#0a0a0a] border border-white/10 rounded-xl px-5 py-4 text-sm text-gray-100 outline-none focus:border-primary-500/50 font-mono placeholder:text-gray-600 transition-colors shadow-inner"
            />
          </div>
          <button 
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="relative overflow-hidden bg-primary-600 hover:bg-primary-500 disabled:opacity-50 disabled:hover:bg-primary-600 text-white rounded-xl px-8 py-4 font-semibold transition-all flex items-center gap-2 text-sm shadow-[0_0_20px_rgba(37,99,235,0.3)] hover:shadow-[0_0_25px_rgba(59,130,246,0.5)] active:scale-95"
          >
            <Send size={16} className={isStreaming ? "animate-pulse" : ""} />
            <span className="tracking-wide">DISPATCH</span>
          </button>
        </div>
      </div>
    </main>
  );
}

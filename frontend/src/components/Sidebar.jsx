import { Settings, Sliders, Key, Zap } from 'lucide-react';

export function Sidebar({ config, setConfig }) {
  return (
    <aside className="w-72 glass-panel border-r border-white/5 flex flex-col p-6 space-y-8 shrink-0 z-10 h-full relative overflow-hidden">
      <div className="absolute top-0 right-0 w-[1px] h-full bg-gradient-to-b from-transparent via-primary-500/20 to-transparent"></div>
      
      <div>
        <h2 className="text-[11px] font-bold tracking-widest text-primary-400 uppercase mb-5 flex items-center gap-2">
          <Settings size={14} /> Routing Engine
        </h2>
        
        <div className="space-y-5">
          <div className="space-y-1.5">
            <label className="text-[10px] text-gray-500 font-mono font-bold tracking-wider uppercase flex items-center gap-1.5">
              <Sliders size={12} /> Mode
            </label>
            <div className="relative group">
              <select 
                value={config.routingMode} 
                onChange={e => setConfig({...config, routingMode: e.target.value})}
                className="w-full bg-black/50 border border-white/10 rounded-lg p-2.5 text-xs text-gray-200 outline-none focus:border-primary-500 focus:bg-black transition-all appearance-none cursor-pointer hover:border-white/20"
              >
                <option value="auto">Auto (Managed)</option>
                <option value="manual">Manual Override</option>
              </select>
              <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none text-gray-500 group-hover:text-gray-300">
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] text-gray-500 font-mono font-bold tracking-wider uppercase flex items-center gap-1.5">
              <Zap size={12} /> Primary Node
            </label>
            <div className="relative group">
              <select 
                value={config.primaryProvider} 
                onChange={e => setConfig({...config, primaryProvider: e.target.value})}
                className="w-full bg-black/50 border border-white/10 rounded-lg p-2.5 text-xs text-gray-200 outline-none focus:border-primary-500 focus:bg-black transition-all appearance-none cursor-pointer hover:border-white/20"
              >
                <option value="fast-chat">Groq (Llama 3)</option>
                <option value="gemini-chat">Gemini (1.5 Flash)</option>
                <option value="smart-chat">OpenAI (GPT-4o)</option>
                <option value="claude-chat">Anthropic (Claude 3.5)</option>
              </select>
              <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none text-gray-500 group-hover:text-gray-300">
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </div>
            </div>
          </div>

          {config.routingMode === 'auto' && (
            <div className="space-y-1.5 animate-in fade-in slide-in-from-top-2 duration-300">
              <label className="text-[10px] text-gray-500 font-mono font-bold tracking-wider uppercase flex items-center gap-1.5">
                <Zap size={12} className="text-warning" /> Fallback Node
              </label>
              <div className="relative group">
                <select 
                  value={config.fallbackProvider} 
                  onChange={e => setConfig({...config, fallbackProvider: e.target.value})}
                  className="w-full bg-black/50 border border-white/10 rounded-lg p-2.5 text-xs text-gray-200 outline-none focus:border-warning/50 focus:bg-black transition-all appearance-none cursor-pointer hover:border-white/20"
                >
                  <option value="">None</option>
                  <option value="gemini-chat">Gemini (1.5 Flash)</option>
                  <option value="smart-chat">OpenAI (GPT-4o)</option>
                  <option value="fast-chat">Groq (Llama 3)</option>
                </select>
                <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none text-gray-500 group-hover:text-gray-300">
                  <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-[10px] text-gray-500 font-mono font-bold tracking-wider uppercase flex items-center gap-1.5">
              <Key size={12} /> Authorization
            </label>
            <input 
              type="password" 
              placeholder="Override API Key (BYOK)..."
              value={config.apiKey}
              onChange={e => setConfig({...config, apiKey: e.target.value})}
              className="w-full bg-black/50 border border-white/10 rounded-lg p-2.5 text-xs text-gray-200 outline-none focus:border-primary-500 focus:bg-black transition-all font-mono placeholder:text-gray-600 hover:border-white/20"
            />
          </div>
        </div>
      </div>

      <div className="mt-auto pt-5 border-t border-white/5">
        <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono tracking-widest uppercase">
          <span className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-primary-500/50"></div>
            Core System
          </span>
          <span className="text-gray-400">v3.0.0</span>
        </div>
      </div>
    </aside>
  );
}

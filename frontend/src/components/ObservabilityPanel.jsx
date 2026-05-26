import { Activity, ArrowRight, ShieldCheck, Cpu } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

export function ObservabilityPanel({ metrics, activeFlow }) {
  const FlowNode = ({ label, active, icon: Icon }) => (
    <div className={`relative flex flex-col items-center justify-center p-3 rounded-xl border transition-all duration-500 overflow-hidden ${
      active 
        ? 'border-primary-500/50 bg-primary-500/10 text-primary-400 shadow-[0_0_15px_rgba(59,130,246,0.15)] scale-105' 
        : 'border-white/5 bg-black/40 text-gray-500 scale-100'
    }`}>
      {active && <div className="absolute inset-0 bg-gradient-to-r from-primary-500/0 via-primary-500/10 to-primary-500/0 anim-flow"></div>}
      <Icon size={16} className={`mb-1.5 ${active ? 'animate-pulse' : ''}`} />
      <span className="text-[10px] font-mono font-bold tracking-widest">{label}</span>
    </div>
  );

  return (
    <aside className="w-80 glass-panel border-l border-white/5 flex flex-col overflow-y-auto shrink-0 z-10 h-full relative custom-scrollbar">
      <div className="absolute top-0 left-0 w-[1px] h-full bg-gradient-to-b from-transparent via-purple-500/20 to-transparent"></div>
      
      <div className="p-6 border-b border-white/5">
        <h2 className="text-[11px] font-bold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-primary-400 uppercase flex items-center gap-2">
          <Activity size={14} className="text-purple-400" /> Telemetry Stream
        </h2>
      </div>
      
      <div className="p-6 space-y-10">
        {/* Infra Flow */}
        <div>
          <h3 className="text-[10px] font-mono font-bold tracking-wider text-gray-500 mb-4 uppercase">Request Pipeline</h3>
          <div className="flex justify-between items-center bg-black/30 rounded-2xl p-4 border border-white/5 shadow-inner">
            <FlowNode label="CLIENT" active={activeFlow === 'sending'} icon={Cpu} />
            <ArrowRight size={14} className={`transition-colors duration-300 ${activeFlow === 'sending' || activeFlow === 'streaming' ? 'text-primary-500 animate-pulse' : 'text-gray-700'}`} />
            <FlowNode label="GATEWAY" active={activeFlow === 'sending' || activeFlow === 'streaming'} icon={ShieldCheck} />
            <ArrowRight size={14} className={`transition-colors duration-300 ${activeFlow === 'streaming' ? 'text-primary-500 animate-pulse' : 'text-gray-700'}`} />
            <FlowNode label="LLM" active={activeFlow === 'streaming'} icon={Activity} />
          </div>
        </div>

        {/* Latency Chart */}
        <div>
          <h3 className="text-[10px] font-mono font-bold tracking-wider text-gray-500 mb-4 uppercase flex items-center justify-between">
            Latency (ms)
            <span className="text-primary-400 bg-primary-500/10 px-2 py-0.5 rounded text-[10px]">{metrics.avgLatency}ms avg</span>
          </h3>
          <div className="h-44 w-full bg-black/30 rounded-2xl border border-white/5 p-4 shadow-inner relative group">
            <div className="absolute -inset-1 bg-gradient-to-br from-primary-500/10 to-purple-600/10 rounded-2xl blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metrics.latencyHistory}>
                <defs>
                  <linearGradient id="colorMs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis width={30} fontSize={10} tick={{fill: '#52525b'}} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ background: 'rgba(10,10,10,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '12px', backdropFilter: 'blur(10px)' }}
                  itemStyle={{ color: '#60a5fa' }}
                />
                <Area type="monotone" dataKey="ms" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorMs)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Provider Health */}
        <div>
          <h3 className="text-[10px] font-mono font-bold tracking-wider text-gray-500 mb-4 uppercase">Provider Health</h3>
          <div className="space-y-3">
            {['Groq', 'Gemini', 'OpenAI', 'Anthropic'].map((p, idx) => (
              <div key={p} className="group flex items-center justify-between p-3 rounded-xl border border-white/5 bg-black/20 hover:bg-black/40 transition-colors">
                <span className="text-xs font-mono font-semibold text-gray-300 group-hover:text-white transition-colors">{p}</span>
                <div className="flex items-center gap-3 bg-black/50 px-2 py-1 rounded-md border border-white/5">
                  <span className="text-[10px] text-gray-400 font-mono">100% SLA</span>
                  <div className={`w-2 h-2 rounded-full shadow-[0_0_8px_currentColor] ${idx % 2 === 0 ? 'bg-success text-success' : 'bg-primary-400 text-primary-400'}`}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

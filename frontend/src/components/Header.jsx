import { Database, Server, Activity } from 'lucide-react';

export function Header({ metrics, isStreaming }) {
  return (
    <header className="h-16 glass-panel border-b border-white/5 flex items-center justify-between px-8 shrink-0 w-full z-20 shadow-sm relative">
      <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-primary-500/50 to-transparent"></div>
      
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3 w-3">
            {isStreaming && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>}
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isStreaming ? 'bg-primary-500 shadow-[0_0_8px_#3b82f6]' : 'bg-success shadow-[0_0_8px_#10b981]'}`}></span>
          </div>
          <span className="text-[13px] font-semibold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 uppercase">Gateway API</span>
        </div>
        
        <div className="h-5 w-px bg-white/10"></div>
        
        <div className="flex items-center gap-5 text-xs font-mono font-medium">
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-black/40 border border-white/5">
            <Database size={13} className={metrics.dbStatus === 'ok' ? 'text-success' : 'text-danger'} /> 
            <span className="text-gray-400">DB:</span>
            <span className={metrics.dbStatus === 'ok' ? 'text-success' : 'text-danger'}>{metrics.dbStatus.toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-black/40 border border-white/5">
            <Server size={13} className={metrics.redisStatus === 'ok' ? 'text-success' : 'text-danger'} /> 
            <span className="text-gray-400">Redis:</span>
            <span className={metrics.redisStatus === 'ok' ? 'text-success' : 'text-danger'}>{metrics.redisStatus.toUpperCase()}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-8 text-xs font-mono font-medium">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-gray-500" />
          <span className="text-gray-500">REQ:</span>
          <span className="text-gray-200 tabular-nums">{metrics.requestCount.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">AVG LATENCY:</span>
          <span className="text-primary-400 tabular-nums">{metrics.avgLatency}ms</span>
        </div>
      </div>
    </header>
  );
}

import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ChatWorkspace } from './components/ChatWorkspace';
import { ObservabilityPanel } from './components/ObservabilityPanel';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeFlow, setActiveFlow] = useState(null);
  
  const [config, setConfig] = useState({
    primaryProvider: 'fast-chat',
    fallbackProvider: 'gemini-chat',
    routingMode: 'auto',
    apiKey: ''
  });

  const [metrics, setMetrics] = useState({
    latencyHistory: Array(10).fill({ time: '', ms: 0 }),
    avgLatency: 0,
    requestCount: 0,
    dbStatus: 'ok',
    redisStatus: 'ok'
  });

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    
    const userMsg = { role: 'user', content: input, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);
    setActiveFlow('sending');

    const startTime = Date.now();
    let aiMsg = { role: 'assistant', content: '', timestamp: new Date().toISOString(), tokens: 0, duration: 0, provider: '' };
    setMessages(prev => [...prev, aiMsg]);

    try {
      const headers = { 
        'Content-Type': 'application/json',
        'Authorization': 'Bearer demo-key'
      };
      if (config.apiKey) headers['X-Provider-Api-Key'] = config.apiKey;
      if (config.routingMode === 'manual') headers['X-Provider'] = config.primaryProvider.split('-')[0];
      if (config.fallbackProvider && config.routingMode === 'auto') {
        headers['X-Gateway-Fallback'] = config.fallbackProvider.split('-')[0];
      }

      const response = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: config.primaryProvider,
          messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content })),
          stream: true
        })
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      setActiveFlow('streaming');

      let tokenCount = 0;
      let contentBuffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.error) {
                contentBuffer += `\n\n> **[System Error]:** ${parsed.error}`;
              }
              if (parsed.choices?.[0]?.delta?.content) {
                contentBuffer += parsed.choices[0].delta.content;
                tokenCount++;
              }
              if (parsed.model) {
                aiMsg.provider = parsed.model;
              }
              setMessages(prev => {
                const newMsgs = [...prev];
                newMsgs[newMsgs.length - 1] = {
                  ...aiMsg,
                  content: contentBuffer,
                  tokens: tokenCount,
                  duration: Date.now() - startTime
                };
                return newMsgs;
              });
            } catch (e) {
              // Ignore partial JSON
            }
          }
        }
      }
      
      const finalDuration = Date.now() - startTime;
      setMetrics(prev => ({
        ...prev,
        requestCount: prev.requestCount + 1,
        avgLatency: Math.floor((prev.avgLatency * prev.requestCount + finalDuration) / (prev.requestCount + 1)),
        latencyHistory: [...prev.latencyHistory.slice(1), { time: new Date().toLocaleTimeString(), ms: finalDuration }]
      }));
    } catch (err) {
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = `> **[Gateway Error]:** ${err.message}`;
        return newMsgs;
      });
    } finally {
      setIsStreaming(false);
      setActiveFlow(null);
    }
  };

  return (
    <div className="flex h-screen w-full font-sans bg-background text-gray-100 overflow-hidden">
      <Sidebar config={config} setConfig={setConfig} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header metrics={metrics} isStreaming={isStreaming} />
        <div className="flex-1 flex overflow-hidden">
          <ChatWorkspace 
            messages={messages} 
            input={input} 
            setInput={setInput} 
            isStreaming={isStreaming} 
            handleSend={handleSend}
            messagesEndRef={messagesEndRef}
          />
          <ObservabilityPanel metrics={metrics} activeFlow={activeFlow} />
        </div>
      </div>
    </div>
  );
}

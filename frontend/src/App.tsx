import { useState, useRef, useEffect } from 'react';
import { 
  Send, Bot, User, Loader2, Plus, MessageSquare, 
  Trash2, PanelLeftClose, PanelLeft, ChevronDown, 
  Copy, Check 
} from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([
    { id: '1', title: 'New chat', messages: [] }
  ]);
  const [currentSessionId, setCurrentSessionId] = useState('1');
  const [input, setInput] = useState('');
  const [userId, setUserId] = useState('garvi');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const currentSession = sessions.find(s => s.id === currentSessionId) || sessions[0];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession.messages, loading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  const createNewChat = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: 'New chat',
      messages: []
    };
    setSessions([newSession, ...sessions]);
    setCurrentSessionId(newSession.id);
  };

  const deleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (sessions.length === 1) return;
    const updated = sessions.filter(s => s.id !== id);
    setSessions(updated);
    if (currentSessionId === id) {
      setCurrentSessionId(updated[0].id);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const messageContent = textToSend || input;
    if (!messageContent.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: messageContent };
    const updatedMessages = [...currentSession.messages, userMessage];
    
    setSessions(sessions.map(s => {
      if (s.id === currentSessionId) {
        return {
          ...s,
          title: s.messages.length === 0 ? messageContent.slice(0, 30) + (messageContent.length > 30 ? '...' : '') : s.title,
          messages: updatedMessages
        };
      }
      return s;
    }));

    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const response = await fetch('https://self-learning-5b46.onrender.com/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageContent, user_id: userId }),
      });
      const data = await response.json();
      
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, { role: 'assistant', content: data.response }]
          };
        }
        return s;
      }));
    } catch (error) {
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, { role: 'assistant', content: 'Connection error. Please check your Render backend.' }]
          };
        }
        return s;
      }));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const suggestions = [
    { title: "Brainstorm ideas", prompt: "Help me brainstorm architectural concepts for a modern web application." },
    { title: "Write code snippet", prompt: "Write a clean, production-ready FastAPI endpoint with robust input validation." },
    { title: "Optimize routine", prompt: "Create an optimized daily productivity and coding routine schedule." },
    { title: "Explain concepts", prompt: "Explain how vector databases and long-term memory work in autonomous agents." },
  ];

  return (
    <div className="flex h-screen bg-white text-zinc-900 font-sans antialiased overflow-hidden selection:bg-amber-200 selection:text-zinc-900">
      
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-0'} bg-zinc-50 border-r border-zinc-200 flex flex-col transition-all duration-300 ease-in-out overflow-hidden shrink-0`}>
        <div className="p-3.5 flex items-center justify-between gap-2 border-b border-zinc-200">
          <button 
            onClick={createNewChat} 
            className="flex-1 bg-amber-400 hover:bg-amber-500 text-zinc-900 text-xs font-semibold py-2.5 px-3.5 rounded-xl flex items-center justify-center gap-2 transition-all duration-150 shadow-sm active:scale-[0.98]"
          >
            <Plus size={16} /> New chat
          </button>
          <button 
            onClick={() => setSidebarOpen(false)} 
            className="p-2.5 hover:bg-zinc-200/60 text-zinc-600 rounded-xl transition-colors duration-150"
            title="Close sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          <div className="px-3 py-1 text-[10px] font-bold tracking-wider uppercase text-zinc-400">History</div>
          {sessions.map(session => (
            <div 
              key={session.id} 
              onClick={() => setCurrentSessionId(session.id)}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer text-xs transition-all duration-150 ${session.id === currentSessionId ? 'bg-amber-50 text-zinc-900 font-medium border border-amber-200/60 shadow-sm' : 'text-zinc-600 hover:bg-zinc-100'}`}
            >
              <div className="flex items-center gap-2.5 truncate">
                <MessageSquare size={14} className={`${session.id === currentSessionId ? 'text-amber-500' : 'text-zinc-400'} shrink-0`} />
                <span className="truncate">{session.title}</span>
              </div>
              {sessions.length > 1 && (
                <button onClick={(e) => deleteSession(session.id, e)} className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-600 transition-opacity p-1 rounded">
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="p-3.5 border-t border-zinc-200 bg-white flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-amber-400 flex items-center justify-center font-bold text-xs text-zinc-900 shadow-sm">
            {userId.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 truncate">
            <input 
              type="text" 
              value={userId} 
              onChange={(e) => setUserId(e.target.value)} 
              className="bg-transparent text-xs font-semibold text-zinc-900 focus:outline-none w-full truncate cursor-pointer"
              title="Click to change User ID"
            />
            <span className="text-[10px] text-zinc-400 block tracking-wide">Active Profile</span>
          </div>
        </div>
      </aside>

      {/* Main Panel */}
      <main className="flex-1 flex flex-col bg-white relative min-w-0">
        
        {/* Header */}
        <header className="h-14 border-b border-zinc-200 flex items-center justify-between px-4 bg-white/80 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button 
                onClick={() => setSidebarOpen(true)} 
                className="p-2 hover:bg-zinc-100 text-zinc-600 rounded-xl transition-colors duration-150"
                title="Open sidebar"
              >
                <PanelLeft size={18} />
              </button>
            )}
            <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-zinc-100 rounded-xl cursor-pointer transition-colors duration-150 text-xs font-semibold text-zinc-800">
              <span>Leo Assistant</span>
              <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded-md border border-amber-200">v2</span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-xl bg-amber-400 flex items-center justify-center text-xs font-bold text-zinc-900 shadow-sm">
            {userId.charAt(0).toUpperCase()}
          </div>
        </header>

        {/* Message Viewport */}
        <div className="flex-1 overflow-y-auto px-4 py-8">
          {currentSession.messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center max-w-xl mx-auto text-center space-y-6 my-auto">
              <div className="w-14 h-14 rounded-2xl bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700 shadow-sm">
                <Bot size={28} />
              </div>
              <div className="space-y-1.5">
                <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">How can I help you today?</h1>
                <p className="text-xs text-zinc-500">Ask questions or run tasks with persistent session context.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left pt-2">
                {suggestions.map((item, idx) => (
                  <div 
                    key={idx} 
                    onClick={() => handleSendMessage(item.prompt)}
                    className="p-3.5 rounded-2xl border border-zinc-200 bg-zinc-50 hover:bg-amber-50/50 hover:border-amber-300 cursor-pointer transition-all duration-150 group"
                  >
                    <div className="text-xs font-semibold text-zinc-900 group-hover:text-amber-900 transition-colors">{item.title}</div>
                    <div className="text-[11px] text-zinc-500 truncate mt-1">{item.prompt}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6 w-full pb-6">
              {currentSession.messages.map((msg, index) => (
                <div key={index} className={`flex gap-4 w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-xl bg-amber-400 flex items-center justify-center text-zinc-950 shrink-0 mt-1 shadow-sm">
                      <Bot size={14} />
                    </div>
                  )}
                  <div className={`group relative max-w-[85%] text-xs md:text-sm leading-relaxed ${msg.role === 'user' ? 'bg-zinc-100 text-zinc-900 px-4 py-3 rounded-2xl rounded-br-sm border border-zinc-200' : 'text-zinc-800 py-1 w-full'}`}>
                    <div className="whitespace-pre-wrap font-normal">{msg.content}</div>
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400">
                        <button 
                          onClick={() => copyToClipboard(msg.content, index)} 
                          className="flex items-center gap-1.5 p-1 px-2 hover:bg-zinc-100 hover:text-zinc-900 rounded-lg transition-colors text-[11px]"
                          title="Copy text"
                        >
                          {copiedIndex === index ? <Check size={13} className="text-amber-600" /> : <Copy size={13} />}
                          <span>{copiedIndex === index ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-7 h-7 rounded-xl bg-zinc-900 flex items-center justify-center text-white shrink-0 mt-1 text-xs font-bold shadow-sm">
                      {userId.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex gap-4 max-w-3xl mx-auto w-full items-center text-zinc-400 text-xs animate-pulse">
                  <div className="w-7 h-7 rounded-xl bg-amber-400 flex items-center justify-center text-zinc-950 shrink-0 shadow-sm">
                    <Bot size={14} />
                  </div>
                  <div className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 px-4 py-3 rounded-2xl text-zinc-800 shadow-sm">
                    <Loader2 className="animate-spin text-amber-600" size={14} />
                    <span>Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-white border-t border-zinc-200">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="relative bg-zinc-50 rounded-2xl border border-zinc-300 focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-400/20 transition-all duration-150 shadow-sm">
              <textarea 
                ref={textareaRef}
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Message Leo..." 
                rows={1}
                className="w-full bg-transparent text-xs md:text-sm text-zinc-900 placeholder-zinc-400 px-4 pt-3.5 pb-12 focus:outline-none resize-none max-h-40"
              />
              <div className="absolute bottom-2.5 right-2.5 flex items-center gap-2">
                <button 
                  type="submit" 
                  disabled={!input.trim() || loading} 
                  className="bg-amber-400 hover:bg-amber-500 disabled:opacity-30 disabled:hover:bg-amber-400 text-zinc-950 p-2 rounded-xl transition-all duration-150 shadow-sm active:scale-95 font-medium"
                >
                  <Send size={15} />
                </button>
              </div>
            </form>
            <div className="text-center mt-2.5">
              <span className="text-[10px] text-zinc-400">Leo Assistant • Powered by LangGraph & Mem0</span>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
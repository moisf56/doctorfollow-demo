import React, { useState, useRef, useEffect } from 'react';
import { Send, Menu, X, Stethoscope, Sparkles, Mic, MicOff, ChevronDown, ChevronUp, Lock, User, AlertCircle, Database, GitBranch, Lightbulb } from 'lucide-react';

// API Configuration
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

console.log('API URL:', API_URL); // For debugging

// Login Component
const LoginPage = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // Create Basic Auth credentials
      const credentials = btoa(`${username}:${password}`);

      // Test login with /auth/login endpoint
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${credentials}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Store credentials securely
          sessionStorage.setItem('auth_credentials', credentials);
          sessionStorage.setItem('username', username);
          onLoginSuccess(credentials, username);
        } else {
          setError(data.message || 'Invalid credentials');
        }
      } else {
        setError('Invalid username or password');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Unable to connect to server. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-white/10 backdrop-blur-lg rounded-2xl mb-4 border border-white/20">
            <Stethoscope className="w-10 h-10 text-purple-300" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">DoctorFollow</h1>
          <p className="text-purple-200/70 text-sm">Medical AI Assistant - Secure Demo</p>
        </div>

        {/* Login Form */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 shadow-2xl">
          <h2 className="text-2xl font-semibold text-white mb-6 text-center">Sign In</h2>

          <form onSubmit={handleLogin} className="space-y-5">
            {/* Username Field */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-purple-200 mb-2">
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-purple-300/50" />
                </div>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-purple-300/30 focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent transition"
                  placeholder="Enter username"
                  required
                  autoFocus
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-purple-200 mb-2">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-purple-300/50" />
                </div>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-purple-300/30 focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent transition"
                  placeholder="Enter password"
                  required
                />
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-300 flex-shrink-0" />
                <p className="text-sm text-red-200">{error}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold rounded-lg shadow-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <Lock className="h-5 w-5" />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          {/* Demo Credentials Hint */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <p className="text-center text-xs text-purple-200/50">
              Demo credentials provided by your administrator
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-purple-200/40">
          <p>Powered by Medical RAG v3</p>
        </div>
      </div>
    </div>
  );
};

// Main Chat Component (existing code with authentication)
const DoctorFollowChat = ({ authCredentials, username, onLogout }) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState({});
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Initialize speech recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' ';
          } else {
            interimTranscript += transcript;
          }
        }

        if (finalTranscript) {
          setInputValue(prev => prev + finalTranscript);
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);
      };

      recognitionRef.current.onend = () => {
        setIsRecording(false);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const handleSend = async () => {
    if (inputValue.trim() === '' || isLoading) return;

    const userMessage = {
      id: messages.length + 1,
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentQuery = inputValue;
    setInputValue('');
    setIsLoading(true);

    const aiMessageId = messages.length + 2;
    const aiMessage = {
      id: aiMessageId,
      type: 'ai',
      content: '',
      thinking: '',
      answer: '',
      references: '',
      timestamp: new Date(),
      sources: [],
      isStreaming: true
    };

    setMessages(prev => [...prev, aiMessage]);

    try {
      const conversationHistory = messages.slice(-6).map(msg => ({
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content
      }));

      // Include authentication credentials in request
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${authCredentials}`, // Add auth header
        },
        body: JSON.stringify({
          query: currentQuery,
          conversation_history: conversationHistory
        })
      });

      if (response.status === 401) {
        // Authentication failed - logout
        alert('Session expired. Please login again.');
        onLogout();
        return;
      }

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            if (!jsonStr.trim()) continue;

            try {
              const event = JSON.parse(jsonStr);

              setMessages(prev => {
                const updated = [...prev];
                const msgIndex = updated.findIndex(m => m.id === aiMessageId);
                if (msgIndex === -1) return prev;

                const msg = { ...updated[msgIndex] };

                switch (event.type) {
                  case 'thinking_start':
                    msg.thinking = '';
                    break;
                  case 'thinking':
                    msg.thinking = (msg.thinking || '') + event.content;
                    break;
                  case 'thinking_end':
                    break;
                  case 'answer_start':
                    msg.answer = '';
                    break;
                  case 'answer':
                    msg.answer = (msg.answer || '') + event.content;
                    break;
                  case 'answer_end':
                    break;
                  case 'references':
                    msg.references = event.content;
                    break;
                  case 'sources':
                    msg.sources = event.data || [];
                    break;
                  case 'done':
                    msg.isStreaming = false;
                    let finalContent = '';
                    if (msg.thinking) {
                      finalContent += `<reasoning>${msg.thinking}</reasoning>\n\n`;
                    }
                    if (msg.answer) {
                      finalContent += `<answer>${msg.answer}</answer>`;
                    }
                    if (msg.references) {
                      finalContent += `\n\n---\n${msg.references}`;
                    }
                    msg.content = finalContent;
                    break;
                  case 'error':
                    msg.content = event.content;
                    msg.isStreaming = false;
                    break;
                }

                updated[msgIndex] = msg;
                return updated;
              });
            } catch (e) {
              console.error('Error parsing SSE:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => {
        const updated = [...prev];
        const msgIndex = updated.findIndex(m => m.id === aiMessageId);
        if (msgIndex !== -1) {
          updated[msgIndex] = {
            ...updated[msgIndex],
            content: `Error: ${error.message}`,
            isStreaming: false
          };
        }
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const toggleVoiceRecording = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in your browser.');
      return;
    }

    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const renderMessageContent = (message) => {
    if (message.isStreaming) {
      const hasThinking = message.thinking && message.thinking.length > 0;
      const hasAnswer = message.answer && message.answer.length > 0;
      const hasSources = message.sources && message.sources.length > 0;
      const isExpanded = expandedThinking[message.id];

      return (
        <div className="space-y-3">
          {hasThinking && (
            <div className="border border-purple-500/30 rounded-lg overflow-hidden bg-purple-900/10">
              <button
                onClick={() => setExpandedThinking(prev => ({
                  ...prev,
                  [message.id]: !prev[message.id]
                }))}
                className="w-full px-4 py-3 flex items-center justify-between bg-purple-900/20 hover:bg-purple-900/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></div>
                  <span className="text-sm font-medium text-purple-200">CLINICAL REASONING</span>
                </div>
                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-purple-300" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-purple-300" />
                )}
              </button>

              {isExpanded && (
                <div className="px-5 py-4 bg-purple-900/5">
                  <p className="text-xs leading-relaxed whitespace-pre-wrap text-purple-200/90 font-mono">
                    {message.thinking}
                  </p>
                </div>
              )}
            </div>
          )}

          {hasAnswer && (
            <div className="prose prose-invert max-w-none">
              <p className="text-sm leading-relaxed text-gray-100 whitespace-pre-wrap">
                {message.answer}
              </p>
            </div>
          )}

          {hasSources && (
            <div className="border-t border-gray-700 pt-3 mt-3">
              <p className="text-xs font-semibold text-gray-400 mb-2">REFERENCES</p>
              <div className="space-y-2">
                {message.sources.slice(0, 3).map((source, idx) => (
                  <div key={idx} className="text-xs text-gray-400 bg-gray-800/50 rounded p-2">
                    <p className="font-medium text-purple-300">Source {idx + 1} - Page {source.page_number}</p>
                    <p className="mt-1 line-clamp-2">{source.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    const hasReasoning = message.content.includes('<reasoning>');
    const reasoning = hasReasoning ? message.content.match(/<reasoning>(.*?)<\/reasoning>/s)?.[1] : null;
    const answer = message.content.match(/<answer>(.*?)<\/answer>/s)?.[1] || message.content;
    const hasSources = message.sources && message.sources.length > 0;
    const isExpanded = expandedThinking[message.id];

    return (
      <div className="space-y-3">
        {reasoning && (
          <div className="border border-purple-500/30 rounded-lg overflow-hidden bg-purple-900/10">
            <button
              onClick={() => setExpandedThinking(prev => ({
                ...prev,
                [message.id]: !prev[message.id]
              }))}
              className="w-full px-4 py-3 flex items-center justify-between bg-purple-900/20 hover:bg-purple-900/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-purple-400"></div>
                <span className="text-sm font-medium text-purple-200">CLINICAL REASONING</span>
              </div>
              {isExpanded ? (
                <ChevronUp className="w-4 h-4 text-purple-300" />
              ) : (
                <ChevronDown className="w-4 h-4 text-purple-300" />
              )}
            </button>

            {isExpanded && (
              <div className="px-5 py-4 bg-purple-900/5">
                <p className="text-xs leading-relaxed whitespace-pre-wrap text-purple-200/90 font-mono">
                  {reasoning}
                </p>
              </div>
            )}
          </div>
        )}

        <div className="prose prose-invert max-w-none">
          <p className="text-sm leading-relaxed text-gray-100 whitespace-pre-wrap">
            {answer.replace(/<[^>]*>/g, '')}
          </p>
        </div>

        {hasSources && (
          <div className="border-t border-gray-700 pt-3 mt-3">
            <p className="text-xs font-semibold text-gray-400 mb-2">REFERENCES</p>
            <div className="space-y-2">
              {message.sources.slice(0, 3).map((source, idx) => (
                <div key={idx} className="text-xs text-gray-400 bg-gray-800/50 rounded p-2">
                  <p className="font-medium text-purple-300">Source {idx + 1} - Page {source.page_number}</p>
                  <p className="mt-1 line-clamp-2">{source.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-indigo-900">
      {/* Header */}
      <header className="bg-gradient-to-r from-purple-800 to-blue-900 text-white p-4 shadow-lg border-b border-purple-500/30">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-white/10 p-2 rounded-lg backdrop-blur-sm">
              <Stethoscope className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold">DoctorFollow</h1>
              <p className="text-xs text-purple-200">Medical AI Assistant</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right mr-2">
              <p className="text-xs text-purple-200">Signed in as</p>
              <p className="text-sm font-medium">{username}</p>
            </div>
            <button
              onClick={onLogout}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition border border-white/20"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="container mx-auto max-w-4xl">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'} mb-4`}
            >
              <div
                className={`max-w-[80%] rounded-2xl p-4 shadow-lg ${
                  message.type === 'user'
                    ? 'bg-gradient-to-br from-purple-600 to-blue-600 text-white'
                    : 'bg-gray-800/90 backdrop-blur-sm text-gray-100 border border-gray-700'
                }`}
              >
                <div className="flex items-start gap-2 mb-2">
                  <div className={`text-xs font-semibold ${
                    message.type === 'user' ? 'text-purple-200' : 'text-purple-400'
                  }`}>
                    {message.type === 'user' ? '👨‍⚕️ You' : '🤖 AI Assistant'}
                  </div>
                  <div className="flex-1"></div>
                  <div className="text-xs opacity-70">
                    {formatTime(message.timestamp)}
                  </div>
                </div>

                <div className="mt-2">
                  {message.type === 'user' ? (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    renderMessageContent(message)
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-700 bg-gray-800/90 backdrop-blur-sm p-4">
        <div className="container mx-auto max-w-4xl">
          <div className="flex gap-2 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask a medical question..."
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                rows={3}
                disabled={isLoading}
              />
            </div>

            <button
              onClick={toggleVoiceRecording}
              className={`p-3 rounded-xl transition ${
                isRecording
                  ? 'bg-red-500 hover:bg-red-600'
                  : 'bg-gray-700 hover:bg-gray-600'
              } text-white`}
              title={isRecording ? 'Stop recording' : 'Start voice input'}
            >
              {isRecording ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
            </button>

            <button
              onClick={handleSend}
              disabled={isLoading || inputValue.trim() === ''}
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-xl transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isLoading ? (
                <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>

          <div className="mt-2 text-xs text-gray-500 text-center">
            Press Enter to send • Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
};

// Main App Component with Authentication Flow
function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authCredentials, setAuthCredentials] = useState(null);
  const [username, setUsername] = useState(null);

  // Check for existing session on mount
  useEffect(() => {
    const storedCredentials = sessionStorage.getItem('auth_credentials');
    const storedUsername = sessionStorage.getItem('username');

    if (storedCredentials && storedUsername) {
      setAuthCredentials(storedCredentials);
      setUsername(storedUsername);
      setIsAuthenticated(true);
    }
  }, []);

  const handleLoginSuccess = (credentials, user) => {
    setAuthCredentials(credentials);
    setUsername(user);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    sessionStorage.removeItem('auth_credentials');
    sessionStorage.removeItem('username');
    setAuthCredentials(null);
    setUsername(null);
    setIsAuthenticated(false);
  };

  return (
    <>
      {!isAuthenticated ? (
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      ) : (
        <DoctorFollowChat
          authCredentials={authCredentials}
          username={username}
          onLogout={handleLogout}
        />
      )}
    </>
  );
}

export default App;

import React, { useState, useEffect } from 'react';
import { knowledgeService } from '../../../api/knowledgeService';
import type { KnowledgeFile } from '../../../api/knowledgeService';
import { useChatbot } from '../../../hooks/useChatbot';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { GraphViewer } from './GraphViewer';

export const KnowledgeWorkspace: React.FC = () => {
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<KnowledgeFile | null>(null);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  
  // Reuse existing chatbot hook for the chat UI
  const { messages, isLoading: isChatLoading, sendMessage, sendDocumentMessage } = useChatbot();
  const [chatInput, setChatInput] = useState('');

  // Dragging states
  const [chatWidth, setChatWidth] = useState(400);
  const [isDragging, setIsDragging] = useState(false);

  // Document viewer states
  const [viewMode, setViewMode] = useState<'pdf' | 'markdown' | 'chunks' | 'graph'>('pdf');
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [chunksContent, setChunksContent] = useState<any[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] });
  const [activeSourceText, setActiveSourceText] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [isLoadingContent, setIsLoadingContent] = useState(false);

  useEffect(() => {
    if (!selectedFile) return;
    let currentPdfUrl: string | null = null;

    const loadContent = async () => {
      setIsLoadingContent(true);
      try {
        if (viewMode === 'pdf') {
          const url = await knowledgeService.getFileStreamUrl(selectedFile.id);
          setPdfUrl(url);
          currentPdfUrl = url;
        } else if (viewMode === 'markdown') {
          const md = await knowledgeService.getFileMarkdown(selectedFile.id);
          setMarkdownContent(md);
        } else if (viewMode === 'chunks') {
          const chunks = await knowledgeService.getFileChunks(selectedFile.id);
          setChunksContent(chunks);
        } else if (viewMode === 'graph') {
          const graph = await knowledgeService.getFileGraph(selectedFile.id);
          setGraphData(graph);
        }
      } catch (err) {
        console.error("Failed to load content", err);
      } finally {
        setIsLoadingContent(false);
      }
    };
    loadContent();

    return () => {
      if (currentPdfUrl) {
        URL.revokeObjectURL(currentPdfUrl);
      }
    };
  }, [selectedFile, viewMode]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const newWidth = window.innerWidth - e.clientX - 10; // offset
      if (newWidth > 250 && newWidth < window.innerWidth - 400) {
        setChatWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const handleSourceClick = (source: any) => {
    // Instead of relying on the backend chunk ID (which may not match), store the source text.
    // This lets the GraphViewer search and highlight nodes that appear in this text automatically.
    const text = source.full_content || source.content_snippet || '';
    setActiveSourceText(text);
    
    // Avoid stale closures: switch to markdown only if the graph view is not active
    setViewMode((prev) => prev === 'graph' ? 'graph' : 'markdown');
    
    // Still call setTimeout to highlight the markdown view in the background if the DOM is currently showing it
    setTimeout(() => {
      const fullNorm = (source.full_content || source.content_snippet || '')
        .replace(/[*_~`#>-]/g, '')
        .replace(/\s+/g, ' ')
        .toLowerCase()
        .trim();

      if (!fullNorm) return;

      const allElements = document.querySelectorAll('.prose *');
      const blockTags = ['P', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'TD', 'TH', 'BLOCKQUOTE'];
      
      // Step 1: collect all matching elements for the content
      const matches: { el: HTMLElement; index: number; textLen: number }[] = [];
      
      for (let i = 0; i < allElements.length; i++) {
        const el = allElements[i] as HTMLElement;
        if (!blockTags.includes(el.tagName)) continue;

        const textNorm = (el.textContent || '')
          .replace(/[*_~`#>-]/g, '')
          .replace(/\s+/g, ' ')
          .toLowerCase()
          .trim();
        
        // Condition: the text is more than 20 characters and remains contained within the chunk
        if (textNorm.length > 20 && fullNorm.includes(textNorm)) {
          matches.push({ el, index: i, textLen: textNorm.length });
        }
      }

      if (matches.length === 0) return;

      // Step 2: cluster nearby matching elements in the DOM
      // (because a chunk is a continuous block, while repeated headers/footers appear scattered)
      const clusters: (typeof matches)[] = [];
      let currentCluster = [matches[0]];

      for (let i = 1; i < matches.length; i++) {
        const prev = matches[i - 1];
        const curr = matches[i];
        // If two elements are within 5 DOM nodes of each other, treat them as the same block
        if (curr.index - prev.index <= 5) {
          currentCluster.push(curr);
        } else {
          clusters.push(currentCluster);
          currentCluster = [curr];
        }
      }
      clusters.push(currentCluster);

      // Step 3: select the cluster with the largest text size (likely the actual content rather than repeated header/footer text)
      let bestCluster = clusters[0];
      let maxScore = 0;
      for (const cluster of clusters) {
        const score = cluster.reduce((sum, item) => sum + item.textLen, 0);
        if (score > maxScore) {
          maxScore = score;
          bestCluster = cluster;
        }
      }

      // Step 4: scroll to the first element of the best cluster and highlight the entire cluster
      if (bestCluster.length > 0) {
        bestCluster[0].el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        bestCluster.forEach(({ el }) => {
          const originalBg = el.style.backgroundColor;
          const originalTransition = el.style.transition;
          el.style.transition = 'background-color 0.5s';
          el.style.backgroundColor = '#fef08a'; // yellow-200
          setTimeout(() => { 
            el.style.backgroundColor = originalBg; 
            setTimeout(() => { el.style.transition = originalTransition; }, 500);
          }, 2500);
        });
      }
    }, 400); // Wait 400ms for ReactMarkdown to render
  };

  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchFiles = async () => {
    try {
      const data = await knowledgeService.getFiles();
      setFiles(data);
      if (data.length > 0 && !selectedFile) {
        setSelectedFile(data[0]); // Auto-select first file
      }
    } catch (error) {
      console.error("Failed to fetch knowledge base files", error);
    }
  };

  useEffect(() => {
    const initFetch = async () => {
      setIsLoadingFiles(true);
      await fetchFiles();
      setIsLoadingFiles(false);
    };
    initFetch();
  }, []);

  // Polling for processing files
  useEffect(() => {
    const hasProcessingFiles = files.some(f => f.status === 'processing');
    if (hasProcessingFiles) {
      const interval = setInterval(() => {
        fetchFiles();
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [files]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsUploading(true);
    try {
      const newFile = await knowledgeService.uploadFile(file);
      setFiles(prev => [newFile, ...prev]);
      setSelectedFile(newFile);
    } catch (error) {
      console.error("Failed to upload file", error);
      alert("Failed to upload file. Please try again.");
    } finally {
      setIsUploading(false);
      // Reset input
      e.target.value = '';
    }
  };

  const handleDeleteFile = async (e: React.MouseEvent, fileId: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this document? This action cannot be undone.")) {
      return;
    }
    
    setDeletingId(fileId);
    try {
      await knowledgeService.deleteFile(fileId);
      setFiles(prev => prev.filter(f => f.id !== fileId));
      if (selectedFile?.id === fileId) {
        setSelectedFile(null);
      }
      setSelectedFileIds(prev => prev.filter(id => id !== fileId));
    } catch (error) {
      console.error("Failed to delete file", error);
      alert("Failed to delete file.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleFile = (e: React.ChangeEvent<HTMLInputElement>, fileId: string) => {
    if (e.target.checked) {
      setSelectedFileIds(prev => [...prev, fileId]);
    } else {
      setSelectedFileIds(prev => prev.filter(id => id !== fileId));
    }
  };

  const readyFileIds = selectedFileIds.filter(id => {
    const file = files.find(f => f.id === id);
    return file && file.status !== 'processing';
  });

  const canChat = readyFileIds.length > 0;

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading || !canChat) return;
    
    // Always use the dedicated RAG API in the Knowledge Workspace.
    // If no files are selected (selectedFileIds is empty), the backend will block the search.
    if (sendDocumentMessage) {
      // Make sure files still processing are not sent to the backend
      const readyFileIds = selectedFileIds.filter(id => {
        const file = files.find(f => f.id === id);
        return file && file.status !== 'processing';
      });
      sendDocumentMessage(chatInput, readyFileIds);
    }
    setChatInput('');
  };

  return (
    <div className="flex-1 flex bg-[#E8F1FF] font-sans relative w-full h-full overflow-hidden">
      
      {/* 1. INNER SIDEBAR: List of PDF files */}
      <aside className="w-[300px] shrink-0 bg-white m-2 rounded-2xl shadow-sm overflow-hidden flex flex-col border border-gray-100">
        <div className="p-5 flex items-center justify-between border-b border-gray-100 bg-gray-50/50">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Documents
          </h2>
          <div>
            <input 
              type="file" 
              id="upload-pdf" 
              accept="application/pdf" 
              className="hidden" 
              onChange={handleFileUpload} 
              disabled={isUploading}
            />
            <label 
              htmlFor="upload-pdf"
              className={`p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 hover:text-blue-600 transition-colors cursor-pointer flex items-center justify-center ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="Upload new PDF"
            >
              {isUploading ? (
                <svg className="animate-spin w-4 h-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
              )}
            </label>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {isLoadingFiles ? (
            <div className="text-center text-sm text-gray-500 py-4">Loading documents...</div>
          ) : files.length === 0 ? (
            <div className="text-center text-sm text-gray-500 py-4">No PDF files found.</div>
          ) : (
            files.map(file => (
              <div 
                key={file.id}
                className={`w-full flex items-center p-3 rounded-xl transition-all gap-3 ${
                  selectedFile?.id === file.id
                    ? 'bg-blue-50 border border-blue-200 shadow-sm'
                    : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                {/* Checkbox to include the file in the chat filter */}
                <input 
                  type="checkbox"
                  disabled={file.status === 'processing'}
                  checked={file.status !== 'processing' && selectedFileIds.includes(file.id)}
                  onChange={(e) => handleToggleFile(e, file.id)}
                  className={`w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 ${file.status === 'processing' ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
                  title={file.status === 'processing' ? 'File is processing...' : 'Include in chat filter'}
                />
                
                <button
                  onClick={() => setSelectedFile(file)}
                  className="flex-1 flex items-start gap-3 min-w-0 text-left"
                >
                  <div className={`mt-0.5 ${selectedFile?.id === file.id ? 'text-blue-600' : 'text-gray-400'}`}>
                    {file.status === 'processing' ? (
                      <svg className="w-5 h-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    ) : (
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" /></svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0 flex items-center gap-2">
                    <h3 className={`font-medium text-sm truncate ${selectedFile?.id === file.id ? 'text-blue-800' : 'text-gray-700'}`}>
                      {file.name}
                    </h3>
                    {file.status === 'processing' && (
                      <span className="text-[10px] bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full shrink-0">Processing</span>
                    )}
                  </div>
                </button>
                <button
                  onClick={(e) => handleDeleteFile(e, file.id)}
                  disabled={deletingId === file.id}
                  className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                  title="Delete document"
                >
                  {deletingId === file.id ? (
                    <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  )}
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* 2. CENTER SECTION: PDF Viewer */}
      <section className="flex-1 flex flex-col min-w-0 bg-white m-2 ml-0 rounded-2xl shadow-sm overflow-hidden border border-gray-100">
        <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800 truncate pr-4">
            {selectedFile ? selectedFile.name : 'Select a document'}
          </h2>
          {selectedFile && (
            <div className="flex bg-white rounded-lg p-1 border border-gray-200 shadow-sm text-sm">
              <button
                onClick={() => setViewMode('pdf')}
                className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'pdf' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                PDF
              </button>
              <button
                onClick={() => setViewMode('markdown')}
                className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'markdown' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                Markdown
              </button>
              <button
                onClick={() => setViewMode('chunks')}
                className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'chunks' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                Chunks
              </button>
              <button
                onClick={() => setViewMode('graph')}
                className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'graph' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                Graph
              </button>
            </div>
          )}
        </div>
        <div className="flex-1 bg-gray-100/50 relative">
          {isDragging && <div className="absolute inset-0 z-20 cursor-col-resize bg-transparent" />}
          {selectedFile ? (
            isLoadingContent ? (
              <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-20">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : viewMode === 'pdf' ? (
              pdfUrl ? (
                <iframe
                  src={pdfUrl}
                  className="w-full h-full border-0 absolute inset-0 z-10 bg-white"
                  title={selectedFile.name}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-gray-500 z-10">
                  <p>Loading PDF...</p>
                </div>
              )
            ) : viewMode === 'markdown' ? (
              <div className="absolute inset-0 z-10 overflow-auto bg-white p-8">
                <div className="max-w-4xl mx-auto prose prose-blue">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {markdownContent}
                  </ReactMarkdown>
                </div>
              </div>
            ) : viewMode === 'chunks' ? (
              <div className="absolute inset-0 z-10 overflow-auto bg-gray-50 p-6">
                <div className="max-w-4xl mx-auto space-y-4">
                  <h3 className="text-lg font-medium text-gray-800 mb-4">Database Chunks ({chunksContent.length})</h3>
                  {chunksContent.map((chunk, idx) => (
                    <div key={idx} className="bg-white p-4 rounded-xl shadow-sm border border-gray-200">
                      <div className="mb-2 text-xs text-gray-400 bg-gray-100 p-2 rounded-lg font-mono overflow-auto">
                        {JSON.stringify(chunk.metadata)}
                      </div>
                      <div className="text-sm text-gray-700 whitespace-pre-wrap font-serif">
                        {chunk.content}
                      </div>
                    </div>
                  ))}
                  {chunksContent.length === 0 && (
                    <div className="text-center text-gray-500 py-10">No chunks found in database.</div>
                  )}
                </div>
              </div>
            ) : (
              <div className="absolute inset-0 z-10 overflow-hidden bg-gray-50">
                <GraphViewer graphData={graphData} activeSourceText={activeSourceText} />
              </div>
            )
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-gray-400 z-10">
              <div className="text-center">
                <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <p>No document selected</p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Splitter */}
      <div 
        className="w-2 cursor-col-resize flex items-center justify-center hover:bg-blue-100 active:bg-blue-200 transition-colors z-10 mx-0.5 rounded-full"
        onMouseDown={() => setIsDragging(true)}
      >
        <div className="h-8 w-1 bg-gray-300 rounded-full" />
      </div>

      {/* 3. RIGHT SIDEBAR: Chat Section */}
      <aside 
        style={{ width: chatWidth }}
        className="shrink-0 bg-white m-2 ml-0 rounded-2xl shadow-sm flex flex-col border border-gray-100 overflow-hidden"
      >
        <div className="p-4 border-b border-gray-100 bg-gradient-to-r from-blue-600 to-indigo-600">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-100" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
            Ask AI Assistant
          </h2>
          <p className="text-xs text-blue-100 mt-1 opacity-80">
            {selectedFile ? `Chatting about ${selectedFile.name}` : 'Ready to help'}
          </p>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-gray-50/30">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4">
              <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-3">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </div>
              <p className="text-gray-500 text-sm">Ask any questions about the documents or farming processes!</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-[13px] prose prose-sm max-w-none ${
                  msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-none prose-invert' 
                    : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'
                }`}>
                  {msg.content ? (
                    <>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className={`mt-3 pt-3 border-t flex flex-wrap gap-2 ${msg.role === 'user' ? 'border-blue-400' : 'border-gray-100'}`}>
                          {msg.sources
                            .filter((src: any) => msg.content.includes(`[${src.id}]`))
                            .map((src: any) => (
                            <button
                              key={src.id}
                              onClick={() => handleSourceClick(src)}
                              className={`text-[11px] px-2 py-1 rounded border transition-colors cursor-pointer flex items-center gap-1 ${
                                msg.role === 'user' 
                                  ? 'bg-blue-700/50 text-blue-50 border-blue-500 hover:bg-blue-600' 
                                  : 'bg-blue-50 text-blue-600 hover:bg-blue-100 border-blue-100'
                              }`}
                              title={src.file_name}
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                              [{src.id}] Source
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="flex gap-1.5 items-center h-5 px-1">
                      {msg.statuses && msg.statuses.length > 0 ? (
                        <span className="text-gray-500 italic animate-pulse">{msg.statuses[msg.statuses.length - 1]}</span>
                      ) : (
                        <>
                          <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                          <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

        </div>

        {/* Chat Input */}
        <div className="p-3 bg-white border-t border-gray-100">
          <form onSubmit={handleSendChat} className="flex items-center bg-gray-50 border border-gray-200 rounded-xl px-2 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={!canChat || isChatLoading}
              placeholder={canChat ? "Ask a question..." : "Select a ready document to chat..."}
              className="flex-1 bg-transparent border-none py-3 px-2 text-sm text-gray-800 focus:outline-none focus:ring-0 placeholder-gray-400 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!chatInput.trim() || isChatLoading || !canChat}
              className={`p-2 rounded-lg transition-colors ${
                chatInput.trim() && !isChatLoading && canChat
                  ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm' 
                  : 'bg-transparent text-gray-300'
              }`}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>
            </button>
          </form>
        </div>
      </aside>

    </div>
  );
};

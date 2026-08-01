import React, { useEffect, useState, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface GraphViewerProps {
  graphData: { nodes: any[]; links: any[] };
  activeSourceText?: string | null;
}

export const GraphViewer: React.FC<GraphViewerProps> = ({ graphData, activeSourceText }) => {
  const fgRef = useRef<any>();
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight
      });
    }
    
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Zoom to fit when data changes
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        fgRef.current.zoomToFit(400, 50);
      }, 500);
    }
  }, [graphData]);

  const activeNodes = useMemo(() => {
    const set = new Set<string>();
    if (!activeSourceText || !graphData) return set;
    const contentNorm = activeSourceText.toLowerCase();
    graphData.nodes.forEach(node => {
      if (contentNorm.includes(node.id.toLowerCase())) {
        set.add(node.id);
      }
    });
    return set;
  }, [activeSourceText, graphData]);

  const activeLinks = useMemo(() => {
    const set = new Set<any>();
    if (activeNodes.size === 0 || !graphData) return set;
    graphData.links.forEach(link => {
      const sId = typeof link.source === 'object' ? link.source.id : link.source;
      const tId = typeof link.target === 'object' ? link.target.id : link.target;
      if (activeNodes.has(sId) && activeNodes.has(tId)) {
        set.add(link);
      }
    });
    return set;
  }, [activeNodes, graphData]);

  // Handle active chunk highlighting
  useEffect(() => {
    if (activeNodes.size > 0 && fgRef.current && graphData.nodes.length > 0) {
      const nodes = graphData.nodes.filter(n => activeNodes.has(n.id));
      if (nodes.length > 0) {
        const firstNode = nodes[0];
        if (firstNode.x && firstNode.y) {
          fgRef.current.centerAt(firstNode.x, firstNode.y, 1000);
          fgRef.current.zoom(3, 1000);
        }
      }
    }
  }, [activeNodes, graphData]);

  const getColorByLabel = (label: string) => {
    if (!label) return '#9ca3af';
    switch (label.toLowerCase().trim()) {
      case 'crop': return '#22c55e'; // teal-500
      case 'disease': return '#ef4444'; // red-500
      case 'pesticide': return '#eab308'; // yellow-500
      case 'fertilizer': return '#f97316'; // orange-500
      case 'location': return '#3b82f6'; // teal-500
      case 'farmingtechnique': return '#8b5cf6'; // violet-500
      case 'soiltype': return '#84cc16'; // lime-500
      case 'weathercondition': return '#06b6d4'; // cyan-500
      default: return '#9ca3af'; // gray-400
    }
  };

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 bg-gray-50 p-6">
        <svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
        <p>No knowledge graph data extracted for this document.</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-white relative" ref={containerRef}>
      <ForceGraph2D
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeLabel="id"
        nodeColor={(node: any) => {
          if (activeSourceText) {
            return activeNodes.has(node.id) ? getColorByLabel(node.label) : '#e5e7eb';
          }
          return getColorByLabel(node.label);
        }}
        nodeRelSize={6}
        linkColor={(link: any) => {
          if (activeSourceText) {
            return activeLinks.has(link) ? '#ef4444' : '#f3f4f6';
          }
          return '#94a3b8';
        }}
        linkWidth={(link: any) => (activeSourceText && activeLinks.has(link) ? 3 : 1)}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        nodeCanvasObjectMode={() => 'after'}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = node.id;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          
          // Draw text background
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);
          
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
          if (activeSourceText) {
            if (!activeNodes.has(node.id)) ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
          }
          
          ctx.fillRect(
            node.x - bckgDimensions[0] / 2, 
            node.y - bckgDimensions[1] / 2 + 10, 
            bckgDimensions[0], 
            bckgDimensions[1]
          );

          ctx.fillStyle = '#1f2937';
          if (activeSourceText) {
            if (!activeNodes.has(node.id)) ctx.fillStyle = '#9ca3af';
          }
          
          ctx.fillText(label, node.x, node.y + 10);
        }}
      />
      {/* Legend */}
      <div className="absolute top-4 left-4 bg-white/90 p-3 rounded-lg shadow-sm border border-gray-100 text-xs flex flex-col gap-1.5 pointer-events-none">
        <div className="font-semibold text-gray-700 mb-1">Entity Types</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#22c55e]"></div>Crop</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#ef4444]"></div>Disease</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#eab308]"></div>Pesticide</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#f97316]"></div>Fertilizer</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#3b82f6]"></div>Location</div>
        <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#8b5cf6]"></div>Farming Technique</div>
      </div>
    </div>
  );
};

// File icon utility using Seti UI icons
// Maps file extensions to Seti UI icons similar to VS Code

import { getIcon } from 'seti-icons';

// Enhanced Seti UI color theme mapping with better visibility and contrast
const setiTheme: Record<string, string> = {
  blue: '#4A9EFF',        // Brighter blue for better visibility on dark backgrounds
  grey: '#9CA3AF',         // Lighter grey for better contrast
  'grey-light': '#D1D5DB', // Even lighter grey
  green: '#10B981',        // Brighter green
  orange: '#F97316',       // Brighter orange
  pink: '#EC4899',         // Brighter pink
  purple: '#8B5CF6',       // Brighter purple
  red: '#EF4444',           // Brighter red
  white: '#F3F4F6',        // Light grey-white
  yellow: '#FBBF24',       // Brighter yellow
  ignore: '#6B7280',       // Medium grey
};

// Seti UI folder icon SVG (closed and open variants) with better visibility
// Closed folder: darker, more closed appearance
const folderIconClosed = '<svg viewBox="0 0 32 32" width="18" height="18"><path d="M27 9v16H5V9h22m0-2H5c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h22c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2z" fill="#90A4AE"/></svg>';

// Open folder: lighter color, shows open top with visible interior
const folderIconOpen = '<svg viewBox="0 0 32 32" width="18" height="18"><path d="M27 9v16H5V9h22m0-2H5c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h22c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2z" fill="#4A9EFF" opacity="0.8"/><path d="M5 9l3-6h6l-2 4h13v2H5z" fill="#4A9EFF"/><path d="M5 11h22v14H5V11z" fill="#4A9EFF" opacity="0.3"/></svg>';

/**
 * Apply color to SVG by adding fill attributes to path elements
 * Handles both direct paths and paths within <g> groups
 */
function applyColorToSvg(svg: string, color: string): string {
  // Add width and height if not present
  let processedSvg = svg;
  
  if (!processedSvg.includes('width=')) {
    processedSvg = processedSvg.replace(/<svg\s+/, '<svg width="18" height="18" ');
    if (!processedSvg.includes('width=')) {
      processedSvg = processedSvg.replace(/<svg>/, '<svg width="18" height="18">');
    }
  }
  
  // Replace all existing fill attributes
  processedSvg = processedSvg.replace(/fill="[^"]*"/gi, `fill="${color}"`);
  processedSvg = processedSvg.replace(/fill='[^']*'/gi, `fill="${color}"`);
  
  // Handle paths - add fill to all path elements that don't have it
  // This handles both self-closing paths (<path ... />) and regular paths (<path ...>)
  processedSvg = processedSvg.replace(/<path\s+([^>]*?)(\s*\/>|>)/gi, (match, attrs, closing) => {
    // Check if fill attribute already exists
    if (!attrs.includes('fill=')) {
      // Add fill before the closing tag
      return `<path ${attrs} fill="${color}"${closing}`;
    }
    return match;
  });
  
  return processedSvg;
}

export interface FileIconResult {
  svg: string;
  color: string;
}

export function getFileIcon(fileName: string, isDirectory: boolean, isExpanded?: boolean): FileIconResult {
  if (isDirectory) {
    // For directories, return folder icon with distinct open/closed states
    return {
      svg: isExpanded ? folderIconOpen : folderIconClosed,
      color: isExpanded ? '#4A9EFF' : '#90A4AE',
    };
  }

  try {
    const result = getIcon(fileName);
    // Convert color name to hex value with enhanced brightness
    const colorHex = setiTheme[result.color] || result.color;
    
    // Apply color to SVG - the SVG from seti-icons doesn't have fill, so we add it
    const coloredSvg = applyColorToSvg(result.svg, colorHex);
    
    return {
      svg: coloredSvg,
      color: colorHex,
    };
  } catch (error) {
    // Fallback to default icon if there's an error
    const fallbackSvg = '<svg viewBox="0 0 32 32" width="18" height="18"><path d="M6 2v28h20V10l-6-6H6zm2 2h10v6h6v18H8V4zm12 1.4L22.6 10H20V5.4z" fill="#9CA3AF"/></svg>';
    return {
      svg: fallbackSvg,
      color: '#9CA3AF',
    };
  }
}
// components/vmcp/CodeEditor.tsx

import { useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Save, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getFileIcon } from '@/utils/fileIcons';

interface CodeEditorProps {
  filePath: string | null;
  content: string;
  onChange: (content: string) => void;
  onSave: () => void;
  saving?: boolean;
  loading?: boolean;
  readOnly?: boolean;
  onCursorChange?: (line: number, column: number) => void;
}

function getLanguageFromPath(path: string | null): string {
  if (!path) return 'plaintext';

  const ext = path.split('.').pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    'py': 'python',
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'html': 'html',
    'css': 'css',
    'sh': 'shell',
    'bash': 'shell',
    'sql': 'sql',
    'xml': 'xml',
    'toml': 'toml',
    'ini': 'ini',
    'txt': 'plaintext',
  };

  return languageMap[ext || ''] || 'plaintext';
}

export default function CodeEditor({ filePath, content, onChange, onSave, saving = false, loading = false, readOnly = false, onCursorChange }: CodeEditorProps) {
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [cursorPosition, setCursorPosition] = useState({ line: 1, column: 1 });
  const editorRef = useRef<any>(null);

  useEffect(() => {
    setHasUnsavedChanges(false);
  }, [filePath]);

  // Update editor content when content prop or filePath changes
  useEffect(() => {
    if (editorRef.current) {
      const currentValue = editorRef.current.getValue();
      if (content !== undefined && currentValue !== content) {
        editorRef.current.setValue(content || '');
        setHasUnsavedChanges(false);
      }
    }
  }, [content, filePath]);

  // Track cursor position
  useEffect(() => {
    if (editorRef.current) {
      const updateCursorPosition = () => {
        const position = editorRef.current.getPosition();
        if (position) {
          const newPosition = {
            line: position.lineNumber,
            column: position.column,
          };
          setCursorPosition(newPosition);
          if (onCursorChange) {
            onCursorChange(newPosition.line, newPosition.column);
          }
        }
      };

      const disposable = editorRef.current.onDidChangeCursorPosition(updateCursorPosition);
      updateCursorPosition();

      return () => {
        disposable.dispose();
      };
    }
  }, [editorRef.current, onCursorChange]);

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      onChange(value);
      setHasUnsavedChanges(true);
    }
  };

  const handleSave = () => {
    onSave();
    setHasUnsavedChanges(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!readOnly && hasUnsavedChanges) {
          handleSave();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasUnsavedChanges, readOnly]);

  const language = getLanguageFromPath(filePath);
  const fileIcon = filePath ? getFileIcon(filePath, false) : null;
  const fileType = language.charAt(0).toUpperCase() + language.slice(1);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-card border-l border-border overflow-hidden">
      {filePath ? (
        <>
          {/* Header */}
          <div className="flex-shrink-0 border-b border-border px-4 py-1.5 flex items-center justify-between bg-muted/30">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {fileIcon && (
                <span
                  className="flex-shrink-0"
                  style={{
                    width: '18px',
                    height: '18px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}
                  dangerouslySetInnerHTML={{ __html: fileIcon.svg }}
                />
              )}
              <span className="text-sm font-medium truncate">{filePath}</span>
              {hasUnsavedChanges && (
                <span className="text-xs text-orange-500">•</span>
              )}
            </div>
            {!readOnly && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSave}
                disabled={saving || !hasUnsavedChanges}
                className="h-7 px-2 text-xs"
              >
                {saving ? (
                  <>
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-3 w-3 mr-1" />
                    Save
                  </>
                )}
              </Button>
            )}
          </div>

          {/* Editor Container - takes remaining space, scrollable */}
          <div className="flex-1 min-h-0 h-full relative overflow-hidden">
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-card z-10">
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Loading file...</p>
                </div>
              </div>
            ) : (
              <Editor
                height="100%"
                language={language}
                value={content || ''}
                onChange={handleEditorChange}
                theme="vs-dark"
                options={{
                  readOnly,
                  minimap: { enabled: true },
                  fontSize: 14,
                  wordWrap: 'on',
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                  tabSize: 2,
                  insertSpaces: true,
                  formatOnPaste: true,
                  formatOnType: true,
                }}
                onMount={(editor) => {
                  editorRef.current = editor;
                  // Set initial content when editor mounts
                  if (content) {
                    editor.setValue(content);
                  }
                }}
              />
            )}
          </div>
        </>
      ) : (
        /* Empty state - no file selected */
        <div className="flex-1 flex items-center justify-center min-h-0">
          <div className="text-center text-muted-foreground">
            <p className="text-sm">Select a file to view or edit</p>
          </div>
        </div>
      )}

    </div>
  );
}

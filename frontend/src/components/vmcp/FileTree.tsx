// components/vmcp/FileTree.tsx

import { useState } from 'react';
import { Folder, FolderOpen, ChevronRight, ChevronDown, Trash2, FilePlus, FolderPlus, Loader2, X } from 'lucide-react';
import { FileNode } from '@/types/vmcp';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { getFileIcon } from '@/utils/fileIcons';

interface FileTreeProps {
  files: FileNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDelete?: (path: string) => void;
  onUpload?: (files: FileList) => void;
  onCreateFile?: (path: string) => void;
  onCreateFolder?: (path: string) => void;
  loading?: boolean;
}

interface FileTreeNodeProps {
  node: FileNode;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDelete?: (path: string) => void;
  onCreateFile?: (path: string) => void;
  onCreateFolder?: (path: string) => void;
  level?: number;
}

function FileTreeNode({ node, selectedPath, onSelect, onDelete, onCreateFile, onCreateFolder, level = 0 }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(false); // Start collapsed by default
  const [isCreating, setIsCreating] = useState<'file' | 'folder' | null>(null);
  const [newName, setNewName] = useState('');
  const isSelected = selectedPath === node.path;
  const isDirectory = node.type === 'directory';
  const hasChildren = node.children && node.children.length > 0;
  const isHidden = node.name.startsWith('.');
  const fileIcon = getFileIcon(node.name, isDirectory, expanded);

  const handleClick = () => {
    if (isDirectory) {
      setExpanded(!expanded);
      // Don't select directories for editing
    } else {
      onSelect(node.path);
    }
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete && confirm(`Are you sure you want to delete ${node.name}?`)) {
      onDelete(node.path);
    }
  };

  const handleCreateFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsCreating('file');
    setNewName('');
  };

  const handleCreateFolder = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsCreating('folder');
    setNewName('');
  };

  const handleSubmitCreate = (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (newName.trim()) {
      const newPath = isDirectory ? `${node.path}/${newName.trim()}` : `${node.path}/../${newName.trim()}`;
      if (isCreating === 'file' && onCreateFile) {
        onCreateFile(newPath);
      } else if (isCreating === 'folder' && onCreateFolder) {
        onCreateFolder(newPath);
      }
    }
    setIsCreating(null);
    setNewName('');
  };

  const handleCancelCreate = (e?: React.FocusEvent<HTMLInputElement>) => {
    setIsCreating(null);
    setNewName('');
  };

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-1 px-2 py-1 hover:bg-muted/50 group",
          isSelected && "bg-primary/10 text-primary"
        )}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
      >
        {isDirectory ? (
          hasChildren ? (
            expanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground flex-shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
            )
          ) : (
            <div className="w-3 h-3 flex-shrink-0" />
          )
        ) : (
          <div className="w-3 h-3 flex-shrink-0" />
        )}

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
          title={node.name}
          dangerouslySetInnerHTML={{ __html: fileIcon.svg }}
        />

        <span
          className={cn(
            "flex-1 truncate text-sm",
            isHidden && "opacity-60"
          )}
        >
          {node.name}
        </span>

        {isDirectory && (onCreateFile || onCreateFolder) && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
            {onCreateFile && (
              <Button
                variant="ghost"
                size="sm"
                className="h-5 w-5 p-0"
                onClick={handleCreateFile}
                title="New File"
              >
                <FilePlus className="h-3 w-3" />
              </Button>
            )}
            {onCreateFolder && (
              <Button
                variant="ghost"
                size="sm"
                className="h-5 w-5 p-0"
                onClick={handleCreateFolder}
                title="New Folder"
              >
                <FolderPlus className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}

        {onDelete && (
          <Button
            variant="ghost"
            size="sm"
            className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100"
            onClick={handleDelete}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        )}
      </div>

      {isDirectory && expanded && (
        <div>
          {isCreating && (
            <div
              className="px-2 py-1"
              style={{ paddingLeft: `${(level + 1) * 16 + 8}px` }}
              onClick={(e) => e.stopPropagation()}
            >
              <form onSubmit={handleSubmitCreate} className="flex items-center gap-1">
                <span className="text-sm" style={{ color: isCreating === 'folder' ? '#90A4AE' : '#90A4AE', width: '16px', display: 'inline-block', textAlign: 'center' }}>
                  {isCreating === 'folder' ? '📁' : '📄'}
                </span>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onBlur={handleCancelCreate}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      handleCancelCreate();
                    } else if (e.key === 'Enter') {
                      e.preventDefault();
                      handleSubmitCreate(e);
                    }
                  }}
                  autoFocus
                  className="flex-1 text-sm px-1 py-0.5 border border-border rounded bg-background"
                  placeholder={isCreating === 'folder' ? 'Folder name' : 'File name'}
                  onClick={(e) => e.stopPropagation()}
                />
                <Button
                  type="submit"
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <X className="h-3 w-3" />
                </Button>
              </form>
            </div>
          )}
          {hasChildren && node.children!.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              selectedPath={selectedPath}
              onSelect={onSelect}
              onDelete={onDelete}
              onCreateFile={onCreateFile}
              onCreateFolder={onCreateFolder}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FileTree({
  files,
  selectedPath,
  onSelect,
  onDelete,
  onUpload,
  onCreateFile,
  onCreateFolder,
  loading
}: FileTreeProps) {
  const [dragOver, setDragOver] = useState(false);
  const [isCreating, setIsCreating] = useState<'file' | 'folder' | null>(null);
  const [newName, setNewName] = useState('');

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    if (onUpload && e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
    }
  };

  const handleCreateFile = () => {
    setIsCreating('file');
    setNewName('');
  };

  const handleCreateFolder = () => {
    setIsCreating('folder');
    setNewName('');
  };

  const handleSubmitCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (newName.trim()) {
      if (isCreating === 'file' && onCreateFile) {
        onCreateFile(newName.trim());
      } else if (isCreating === 'folder' && onCreateFolder) {
        onCreateFolder(newName.trim());
      }
    }
    setIsCreating(null);
    setNewName('');
  };

  return (
    <div
      className={cn(
        "w-64 border-r border-border flex-shrink-0 flex flex-col h-full min-h-0 bg-card",
        dragOver && "bg-primary/5"
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="flex-shrink-0 p-2 border-b border-border flex items-center justify-between bg-muted/30">
        <h3 className="text-xs font-semibold uppercase tracking-wider">Explorer</h3>
        <div className="flex items-center gap-1">
          {onCreateFile && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={handleCreateFile}
              title="New File"
            >
              <FilePlus className="h-3.5 w-3.5" />
            </Button>
          )}
          {onCreateFolder && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={handleCreateFolder}
              title="New Folder"
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            {isCreating && (
              <div className="p-2 border-b border-border">
                <form onSubmit={handleSubmitCreate} className="flex items-center gap-1">
                  <span className="text-sm" style={{ color: isCreating === 'folder' ? '#90A4AE' : '#90A4AE', width: '16px', display: 'inline-block', textAlign: 'center' }}>
                    {isCreating === 'folder' ? '📁' : '📄'}
                  </span>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    onBlur={() => {
                      setIsCreating(null);
                      setNewName('');
                    }}
                    autoFocus
                    className="flex-1 text-sm px-1 py-0.5 border border-border rounded bg-background"
                    placeholder={isCreating === 'folder' ? 'Folder name' : 'File name'}
                  />
                </form>
              </div>
            )}
            {files.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                <Folder className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No files yet</p>
                {onUpload && (
                  <p className="text-xs mt-2">Drag and drop files here</p>
                )}
              </div>
            ) : (
              <div className="p-1">
                {files.map((file) => (
                  <FileTreeNode
                    key={file.path}
                    node={file}
                    selectedPath={selectedPath}
                    onSelect={onSelect}
                    onDelete={onDelete}
                    onCreateFile={onCreateFile}
                    onCreateFolder={onCreateFolder}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

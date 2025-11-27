// components/vmcp/EmptySandboxState.tsx

import { Button } from '@/components/ui/button';
import { FolderOpen, Loader2 } from 'lucide-react';

interface EmptySandboxStateProps {
  onEnable: () => void;
  loading?: boolean;
}

export default function EmptySandboxState({ onEnable, loading = false }: EmptySandboxStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-0 flex-1 p-8">
      <div className="text-center max-w-md">
        <div className="mb-6 flex justify-center">
          <div className="h-20 w-20 rounded-full bg-muted flex items-center justify-center">
            <FolderOpen className="h-10 w-10 text-muted-foreground" />
          </div>
        </div>
        
        <h3 className="text-xl font-semibold text-foreground mb-2">
          Sandbox doesn't exist for this vMCP
        </h3>
        
        <p className="text-muted-foreground mb-6">
          Enable the sandbox to get an isolated Python environment with file management capabilities.
          You'll be able to create, edit, and execute files in a secure sandboxed directory.
        </p>
        
        <Button
          onClick={onEnable}
          disabled={loading}
          size="lg"
          className="min-w-[140px]"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Enabling...
            </>
          ) : (
            <>
              <FolderOpen className="h-4 w-4 mr-2" />
              Enable Now
            </>
          )}
        </Button>
      </div>
    </div>
  );
}


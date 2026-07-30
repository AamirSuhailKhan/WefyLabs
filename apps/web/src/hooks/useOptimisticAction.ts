'use client';

import { useState, useCallback } from 'react';

interface UseOptimisticActionOptions<T> {
  onSuccess?: (result: T) => void;
  onError?: (error: Error) => void;
}

export function useOptimisticAction<TState, TResult>(
  initialState: TState,
  asyncAction: (currentState: TState, payload: any) => Promise<TResult>,
  options: UseOptimisticActionOptions<TResult> = {}
) {
  const [state, setState] = useState<TState>(initialState);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (optimisticState: TState, payload?: any) => {
      const previousState = state;
      // 1. Immediately apply optimistic UI state update
      setState(optimisticState);
      setIsPending(true);
      setError(null);

      try {
        // 2. Perform background async API mutation
        const result = await asyncAction(optimisticState, payload);
        options.onSuccess?.(result);
        return result;
      } catch (err: any) {
        // 3. Rollback state to previous snapshot on error
        setState(previousState);
        const caughtError = err instanceof Error ? err : new Error(err?.message || 'Action failed');
        setError(caughtError);
        options.onError?.(caughtError);
        throw caughtError;
      } finally {
        setIsPending(false);
      }
    },
    [state, asyncAction, options]
  );

  return {
    state,
    setState,
    execute,
    isPending,
    error,
  };
}

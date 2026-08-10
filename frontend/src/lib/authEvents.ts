// A tiny event bus so lib/api.ts (a plain module, no React context access)
// can tell AuthProvider "the session could not be refreshed, sign the user
// out and show them why" without importing React state directly.
type Listener = (message: string) => void;

let listeners: Listener[] = [];

export function onSessionExpired(listener: Listener): () => void {
  listeners.push(listener);
  return () => {
    listeners = listeners.filter((l) => l !== listener);
  };
}

export function emitSessionExpired(message: string): void {
  listeners.forEach((l) => l(message));
}

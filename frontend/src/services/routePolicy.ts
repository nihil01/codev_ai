export type AppView = 'login' | 'workspace';

export function resolveAppView(_path: string, role: string | null): AppView {
  return role === null ? 'login' : 'workspace';
}

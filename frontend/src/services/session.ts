import type { CurrentUser, LoginResponse } from '../api';

export function saveSession(response: LoginResponse) {
  sessionStorage.setItem('token', response.token);
  sessionStorage.setItem(
    'user',
    JSON.stringify({
      user_id: response.user_id,
      email: response.email,
      role: response.role,
      company_id: response.company_id,
      ig_activated: false,
      wp_activated: false,
      ig_enabled: false,
      wp_enabled: false,
    }),
  );

  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

export function saveCurrentUser(user: CurrentUser) {
  sessionStorage.setItem('user', JSON.stringify(user));
  localStorage.removeItem('user');
}

export function loadStoredUser(): CurrentUser | null {
  const raw = sessionStorage.getItem('user') ?? localStorage.getItem('user');

  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as CurrentUser;

    return {
      user_id: parsed.user_id,
      email: parsed.email,
      role: parsed.role,
      company_id: parsed.company_id ?? null,
      ig_activated: parsed.ig_activated ?? false,
      wp_activated: parsed.wp_activated ?? false,
      ig_enabled: parsed.ig_enabled ?? false,
      wp_enabled: parsed.wp_enabled ?? false,
    };
  } catch {
    return null;
  }
}

export function clearSession() {
  sessionStorage.removeItem('token');
  sessionStorage.removeItem('user');
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

export function hasStoredToken() {
  return Boolean(sessionStorage.getItem('token') ?? localStorage.getItem('token'));
}
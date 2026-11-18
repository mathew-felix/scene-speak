const ADMIN_EMAIL = 'admin@gmail.com';
const ADMIN_PASSWORD = 'admin';

/** Temporary static login. Replace with a real backend later. */
export function isValidStaticLogin(email: string, password: string): boolean {
  return email.trim().toLowerCase() === ADMIN_EMAIL && password === ADMIN_PASSWORD;
}

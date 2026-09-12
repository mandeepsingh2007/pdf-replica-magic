export const AUTH_COOKIE = "tg_auth";

export const VALID_ID = "testid";
export const VALID_PASSWORD = "testpass";

export function validateCredentials(id: string, password: string): boolean {
  return id === VALID_ID && password === VALID_PASSWORD;
}

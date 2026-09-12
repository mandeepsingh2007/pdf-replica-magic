/** Next.js test generator login (session cleared on each visit). */
export const TEST_GENERATOR_LOGIN_URL =
  import.meta.env.VITE_TEST_GENERATOR_URL?.replace(/\/$/, "") ?? "http://localhost:3000/login";

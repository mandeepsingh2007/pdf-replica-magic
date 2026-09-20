const BACKEND_ORIGIN =
  process.env.BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type ServerSubject = {
  id: number;
  name: string;
  display_name: string;
  icon?: string | null;
};

export async function fetchSubjectsOnServer(
  track?: "hindi" | "english"
): Promise<{
  subjects: ServerSubject[];
  error: string | null;
}> {
  try {
    const qs = track ? `?track=${track}` : "";
    const res = await fetch(`${BACKEND_ORIGIN}/api/subjects${qs}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return {
        subjects: [],
        error: `Backend returned ${res.status} (${BACKEND_ORIGIN}). Redeploy Render after DB seed fix, or wake the API if it was sleeping.`,
      };
    }
    const subjects = (await res.json()) as ServerSubject[];
    return { subjects, error: null };
  } catch {
    return {
      subjects: [],
      error: `Cannot reach backend at ${BACKEND_ORIGIN}. Check BACKEND_URL on Vercel and Render service status.`,
    };
  }
}

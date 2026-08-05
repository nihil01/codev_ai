export async function readErrorResponse(response: Response): Promise<string> {
  const body = await response.text().catch(() => '');
  let detail = body.trim();

  if (detail) {
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown; message?: unknown };
      const candidate = parsed.detail ?? parsed.message;
      if (typeof candidate === 'string' && candidate.trim()) {
        detail = candidate.trim();
      }
    } catch {
      // Plain-text error bodies are valid and already contain the useful message.
    }
  }

  return `${response.status}${detail ? ` ${detail}` : ''}`;
}

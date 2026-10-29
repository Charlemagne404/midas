export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body.detail ?? 'Request failed';
    if (
      detail &&
      typeof detail === 'object' &&
      detail.code === 'SOURCE_OPERATION_BUSY' &&
      typeof detail.message === 'string'
    ) {
      const venue = typeof detail.venue === 'string' ? ` for ${detail.venue}` : '';
      const retryAfter = response.headers.get('Retry-After');
      const retryUnit = retryAfter === '1' ? 'second' : 'seconds';
      const retry = retryAfter ? ` Retry after ${retryAfter} ${retryUnit}.` : '';
      throw new Error(`Source capture busy${venue}: ${detail.message}.${retry}`);
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

export function requestError(error: unknown, fallback: string, useErrorMessage = false): string {
  if (error && typeof error === 'object' && 'data' in error) {
    const data = error.data
    if (data && typeof data === 'object') {
      if ('error' in data && typeof data.error === 'string' && data.error) return data.error
      if ('message' in data && typeof data.message === 'string' && data.message) return data.message
    }
  }
  return useErrorMessage && error instanceof Error && error.message ? error.message : fallback
}

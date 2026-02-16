/**
 * Namespace hook — reads tenant slug from URL path.
 */

import { useParams } from 'react-router'

export function useNamespace(): string | undefined {
  const { namespace } = useParams<{ namespace: string }>()
  return namespace
}

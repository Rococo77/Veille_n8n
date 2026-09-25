import { Resource } from '@angular/core';

import { problemMessage } from './problem';

/** resource.value() lève une exception en état d'erreur : on lit toujours via ce garde. */
export function valueOr<T>(resource: Resource<T>, fallback: T): T {
  return resource.hasValue() ? resource.value() : fallback;
}

export function errorOf(resource: Resource<unknown>): string | null {
  const error = resource.error();
  return error ? problemMessage((error as { cause?: unknown }).cause ?? error) : null;
}

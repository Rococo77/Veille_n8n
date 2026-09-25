import { HttpErrorResponse } from '@angular/common/http';

interface Problem {
  type?: string;
  title?: string;
  detail?: string;
  errors?: { loc: (string | number)[]; msg: string }[];
}

function asProblem(error: unknown): Problem | null {
  if (error instanceof HttpErrorResponse && error.error && typeof error.error === 'object') {
    return error.error as Problem;
  }
  return null;
}

export function problemCode(error: unknown): string | null {
  const type = asProblem(error)?.type;
  return type ? (type.split(':').pop() ?? null) : null;
}

/** Message affichable : jamais la réponse brute, seulement titre/détail prévus par l'API. */
export function problemMessage(error: unknown, fallback = 'Une erreur est survenue.'): string {
  if (error instanceof HttpErrorResponse && error.status === 0) {
    return 'Serveur injoignable. Vérifiez votre connexion.';
  }
  const problem = asProblem(error);
  if (!problem) return fallback;
  const first = problem.errors?.[0];
  if (first) {
    const field = first.loc.filter((part) => part !== 'body').join('.');
    return field ? `${field} : ${first.msg}` : first.msg;
  }
  return problem.detail ?? problem.title ?? fallback;
}

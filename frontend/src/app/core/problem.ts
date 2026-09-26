import { HttpErrorResponse } from '@angular/common/http';

interface FieldError {
  loc: (string | number)[];
  msg: string;
  type?: string;
}

interface Problem {
  type?: string;
  title?: string;
  detail?: string;
  errors?: FieldError[];
}

/** Noms de champs de l'API → libellés affichés dans les formulaires. */
const FIELD_LABELS: Record<string, string> = {
  name: 'Nom',
  url: 'URL du flux',
  email: 'Email',
  password: 'Mot de passe',
  new_password: 'Nouveau mot de passe',
  current_password: 'Mot de passe actuel',
  color: 'Couleur',
  description: 'Description',
  veille_type: 'Type de veille',
  theme_id: 'Thème',
  role: 'Rôle',
  code: 'Code',
};

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

/** Messages de validation Pydantic (anglais) reformulés ; sinon le message de l'API. */
function fieldMessage(error: FieldError): string {
  const field = error.loc.filter((part) => part !== 'body').at(-1);
  const label = typeof field === 'string' ? (FIELD_LABELS[field] ?? field) : null;
  const limit = error.msg.match(/\d+/)?.[0];
  let text: string;
  switch (error.type) {
    case 'missing':
      text = 'champ obligatoire';
      break;
    case 'string_too_short':
      text = limit ? `${limit} caractère${limit === '1' ? '' : 's'} minimum` : 'trop court';
      break;
    case 'string_too_long':
      text = limit ? `${limit} caractères maximum` : 'trop long';
      break;
    case 'string_pattern_mismatch':
      text = 'format invalide';
      break;
    case 'value_error':
      text = error.msg.replace(/^Value error,\s*/i, '');
      break;
    default:
      text = error.msg;
  }
  return label ? `${label} : ${text}` : text;
}

/** Message affichable : jamais la réponse brute, seulement titre/détail prévus par l'API. */
export function problemMessage(error: unknown, fallback = 'Une erreur est survenue.'): string {
  if (error instanceof HttpErrorResponse && error.status === 0) {
    return 'Serveur injoignable. Vérifiez votre connexion puis réessayez.';
  }
  if (error instanceof HttpErrorResponse && error.status >= 502 && error.status <= 504) {
    return 'Le serveur démarre ou ne répond pas. Réessayez dans une minute.';
  }
  const problem = asProblem(error);
  if (!problem) return fallback;
  const first = problem.errors?.[0];
  if (first) return fieldMessage(first);
  return problem.detail ?? problem.title ?? fallback;
}

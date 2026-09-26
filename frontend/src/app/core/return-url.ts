/**
 * Chemin de retour après reconnexion. N'accepte qu'un chemin interne : une URL absolue ou
 * protocol-relative (`//hote`, `/\hote`) ferait de la page de connexion une redirection ouverte.
 */
export function safeReturnPath(value: string | null | undefined): string | null {
  if (!value || value.length > 512) return null;
  if (!value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return null;
  if (value.startsWith('/connexion')) return null;
  return value;
}

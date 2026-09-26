import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';

import { AuthStore } from './auth.store';
import { Role } from './models';
import { safeReturnPath } from './return-url';

/**
 * Les gardes ne sont qu'un confort d'interface : chaque endpoint revérifie la session
 * et le rôle côté serveur. Un utilisateur qui contourne la garde n'obtient que des 401/403.
 */
export function requireRole(minimum: Role): CanMatchFn {
  return async (_route, segments) => {
    const auth = inject(AuthStore);
    const router = inject(Router);
    const me = auth.me() === undefined ? await auth.refresh() : auth.me();
    if (!me) {
      const retour = safeReturnPath('/' + segments.map((s) => s.path).join('/'));
      return router.createUrlTree(['/connexion'], {
        queryParams: retour && retour !== '/' ? { retour } : {},
      });
    }
    return auth.hasRole(minimum) ? true : router.parseUrl('/');
  };
}

export const guestOnly: CanMatchFn = async () => {
  // inject() n'est valide qu'avant le premier await : après, on est hors du contexte
  // d'injection (NG0203) et la navigation échoue en page blanche.
  const auth = inject(AuthStore);
  const router = inject(Router);
  const me = auth.me() === undefined ? await auth.refresh() : auth.me();
  return me ? router.parseUrl('/') : true;
};

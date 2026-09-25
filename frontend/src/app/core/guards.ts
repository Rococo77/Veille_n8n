import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';

import { AuthStore } from './auth.store';
import { Role } from './models';

/**
 * Les gardes ne sont qu'un confort d'interface : chaque endpoint revérifie la session
 * et le rôle côté serveur. Un utilisateur qui contourne la garde n'obtient que des 401/403.
 */
export function requireRole(minimum: Role): CanMatchFn {
  return async () => {
    const auth = inject(AuthStore);
    const router = inject(Router);
    const me = auth.me() === undefined ? await auth.refresh() : auth.me();
    if (!me) return router.parseUrl('/connexion');
    return auth.hasRole(minimum) ? true : router.parseUrl('/');
  };
}

export const guestOnly: CanMatchFn = async () => {
  const auth = inject(AuthStore);
  const me = auth.me() === undefined ? await auth.refresh() : auth.me();
  return me ? inject(Router).parseUrl('/') : true;
};

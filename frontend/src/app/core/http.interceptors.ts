import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthStore } from './auth.store';
import { problemCode } from './problem';
import { safeReturnPath } from './return-url';

const CSRF_COOKIES = ['__Host-veille_csrf', 'veille_csrf'];
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

function readCookie(names: string[]): string | null {
  const jar = new Map(
    document.cookie
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf('=');
        return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))] as const;
      }),
  );
  for (const name of names) {
    const value = jar.get(name);
    if (value) return value;
  }
  return null;
}

/** N'envoie jamais le jeton CSRF hors de notre propre API. */
function isOwnApi(url: string): boolean {
  return url.startsWith('/api/');
}

export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isOwnApi(req.url) || SAFE_METHODS.has(req.method)) {
    return next(req);
  }
  const token = readCookie(CSRF_COOKIES);
  return next(token ? req.clone({ setHeaders: { 'X-CSRF-Token': token } }) : req);
};

export const authErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthStore);
  const router = inject(Router);
  return next(req).pipe(
    catchError((error: unknown) => {
      const isAuthCall = req.url.startsWith('/api/auth/');
      if (error instanceof HttpErrorResponse && error.status === 401 && !isAuthCall) {
        // Une page chargée en parallèle peut déclencher plusieurs 401 : une seule redirection.
        const wasSignedIn = auth.me() !== null;
        auth.markSignedOut();
        if (wasSignedIn) {
          const mfa = problemCode(error) === 'mfa-required';
          const retour = safeReturnPath(router.url);
          const queryParams: Record<string, string> = mfa ? {} : { motif: 'expiree' };
          if (retour && retour !== '/') queryParams['retour'] = retour;
          void router.navigate([mfa ? '/connexion/code' : '/connexion'], { queryParams });
        }
      }
      return throwError(() => error);
    }),
  );
};

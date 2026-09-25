import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import {
  provideHttpClient,
  withFetch,
  withInterceptors,
  withNoXsrfProtection,
} from '@angular/common/http';
import { provideRouter, withComponentInputBinding } from '@angular/router';

import { routes } from './app.routes';
import { authErrorInterceptor, csrfInterceptor } from './core/http.interceptors';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(
      withFetch(),
      // L'intercepteur CSRF natif lit un seul nom de cookie ; le nôtre gère __Host- (prod)
      // et la variante non sécurisée (dev), et ne cible que /api/.
      withNoXsrfProtection(),
      withInterceptors([csrfInterceptor, authErrorInterceptor]),
    ),
  ],
};

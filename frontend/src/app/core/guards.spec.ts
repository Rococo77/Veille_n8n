import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';

import { AuthStore } from './auth.store';
import { guestOnly } from './guards';

describe('guestOnly', () => {
  // Régression NG0203 : inject(Router) appelé après l'await levait une erreur et laissait
  // une page blanche à l'utilisateur déjà connecté qui ouvrait /connexion.
  it('redirige un utilisateur déjà connecté vers le fil sans sortir du contexte d’injection', async () => {
    const refresh = vi.fn(async () => {
      await Promise.resolve();
      return { id: 'u1', email: 'a@b.fr', role: 'viewer' as const };
    });
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthStore, useValue: { me: () => undefined, refresh } },
      ],
    });

    const result = await TestBed.runInInjectionContext(() => guestOnly({} as never, [], {} as never));

    expect(refresh).toHaveBeenCalled();
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('laisse passer un visiteur non connecté', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthStore, useValue: { me: () => undefined, refresh: async () => null } },
      ],
    });

    await expect(
      TestBed.runInInjectionContext(() => guestOnly({} as never, [], {} as never)),
    ).resolves.toBe(true);
  });
});

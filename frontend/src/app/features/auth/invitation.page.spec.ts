import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';

import { AuthStore } from '../../core/auth.store';
import { InvitationPage } from './invitation.page';

describe('InvitationPage', () => {
  // Le jeton d'invitation vaut un mot de passe : il ne doit rester ni dans la barre
  // d'adresse ni dans l'historique une fois lu.
  it('retire le jeton de l’URL sans créer d’entrée d’historique', () => {
    const token = 'a'.repeat(43);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment: token } } },
        {
          provide: AuthStore,
          useValue: { lookupInvitation: () => new Promise(() => undefined) },
        },
      ],
    });
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    TestBed.createComponent(InvitationPage);

    expect(navigate).toHaveBeenCalledTimes(1);
    const [commands, extras] = navigate.mock.calls[0]!;
    expect(commands).toEqual([]);
    expect(extras?.replaceUrl).toBe(true);
    expect(extras?.fragment).toBeUndefined();
    expect(extras?.preserveFragment).toBeFalsy();
  });
});

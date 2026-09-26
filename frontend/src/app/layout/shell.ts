import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  untracked,
  viewChild,
} from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { AuthStore } from '../core/auth.store';
import { CatalogApi } from '../core/api';
import { ConfirmDialog } from '../core/confirm';
import { Group } from '../core/models';
import { valueOr } from '../core/resource';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ConfirmDialog],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.html',
  styleUrl: './shell.css',
})
export class Shell {
  protected readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogApi);
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('main');

  private readonly groups = httpResource<Group[]>(
    () => {
      this.catalog.version();
      return '/api/groups';
    },
    { defaultValue: [] },
  );

  /** Sources en erreur, tous groupes confondus : signalées dans la navigation. */
  protected readonly failing = computed(() =>
    valueOr(this.groups, []).reduce((sum, g) => sum + g.failing_source_count, 0),
  );

  private readonly navigationEnd = toSignal(
    this.router.events.pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd)),
  );

  constructor() {
    let previousPath: string | null = null;
    effect(() => {
      const event = this.navigationEnd();
      if (!event) return;
      untracked(() => {
        // Changer de page (pas seulement de filtre) : le lecteur d'écran repart du contenu,
        // sinon le focus reste sur un lien de navigation désormais sans rapport.
        const path = event.urlAfterRedirects.split(/[?#]/)[0] ?? '/';
        if (previousPath !== null && path !== previousPath) {
          this.main().nativeElement.focus();
        }
        previousPath = path;
      });
    });
  }

  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/connexion');
  }
}

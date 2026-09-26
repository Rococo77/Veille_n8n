import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';

import { AuthStore } from '../core/auth.store';
import { CatalogApi } from '../core/api';
import { ConfirmDialog } from '../core/confirm';
import { Group, Theme, VEILLE_TYPES } from '../core/models';
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

  /** Menu repliable sous 52rem ; sans effet sur desktop où la navigation est toujours visible. */
  protected readonly menuOpen = signal(false);

  protected readonly groups = httpResource<Group[]>(
    () => {
      this.catalog.version();
      return '/api/groups';
    },
    { defaultValue: [] },
  );
  protected readonly themes = httpResource<Theme[]>(
    () => {
      this.catalog.version();
      return '/api/themes';
    },
    { defaultValue: [] },
  );

  protected readonly groupList = computed(() => valueOr(this.groups, []));
  protected readonly themeList = computed(() => valueOr(this.themes, []));

  /** Les six types restent visibles même vides : c'est l'axe de lecture du produit. */
  protected readonly types = computed(() => {
    const groups = this.groupList();
    return VEILLE_TYPES.map((t) => ({
      ...t,
      groups: groups.filter((g) => g.veille_type === t.value).length,
    }));
  });

  protected readonly failing = computed(() =>
    this.groupList().reduce((sum, g) => sum + g.failing_source_count, 0),
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
        this.menuOpen.set(false);
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

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/connexion');
  }
}

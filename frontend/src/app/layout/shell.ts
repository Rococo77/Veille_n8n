import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthStore } from '../core/auth.store';
import { CatalogApi } from '../core/api';
import { Group, Theme, VEILLE_TYPES } from '../core/models';
import { valueOr } from '../core/resource';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.html',
  styleUrl: './shell.css',
})
export class Shell {
  protected readonly auth = inject(AuthStore);
  private readonly router = inject(Router);

  private readonly catalog = inject(CatalogApi);

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

  protected readonly types = computed(() => {
    const groups = this.groupList();
    return VEILLE_TYPES.map((t) => ({
      ...t,
      groups: groups.filter((g) => g.veille_type === t.value).length,
    })).filter((t) => t.groups > 0);
  });

  protected readonly failing = computed(() =>
    this.groupList().reduce((sum, g) => sum + g.failing_source_count, 0),
  );

  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/connexion');
  }
}

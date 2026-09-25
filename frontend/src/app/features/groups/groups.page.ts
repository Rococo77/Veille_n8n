import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';

import { CatalogApi } from '../../core/api';
import { AuthStore } from '../../core/auth.store';
import { Group, GroupInput, Theme, VEILLE_TYPES } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';
import { GroupForm } from './group-form';

@Component({
  selector: 'app-groups-page',
  imports: [RouterLink, GroupForm],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './groups.page.html',
  styleUrl: './groups.css',
})
export class GroupsPage {
  private readonly catalog = inject(CatalogApi);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthStore);

  private readonly groupsRes = httpResource<Group[]>(() => {
    this.catalog.version();
    return '/api/groups';
  });
  private readonly themesRes = httpResource<Theme[]>(() => {
    this.catalog.version();
    return '/api/themes';
  });
  protected readonly themes = computed(() => valueOr(this.themesRes, undefined) ?? []);
  protected readonly loadError = computed(() => errorOf(this.groupsRes));
  protected readonly loading = computed(() => this.groupsRes.isLoading());

  protected readonly sections = computed(() => {
    const groups = valueOr(this.groupsRes, undefined) ?? [];
    return VEILLE_TYPES.map((t) => ({
      ...t,
      groups: groups.filter((g) => g.veille_type === t.value),
    })).filter((s) => s.groups.length > 0);
  });

  protected readonly creating = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  async create(input: GroupInput): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      const group = await this.catalog.createGroup(input);
      this.creating.set(false);
      await this.router.navigate(['/groupes', group.id]);
    } catch (error) {
      this.error.set(problemMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}

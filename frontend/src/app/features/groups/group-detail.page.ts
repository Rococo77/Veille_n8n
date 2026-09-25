import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CatalogApi } from '../../core/api';
import { AuthStore } from '../../core/auth.store';
import { GroupDetail, GroupInput, Source, Theme, veilleTypeLabel } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';
import { GroupForm } from './group-form';

const dateTime = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'short' });

@Component({
  selector: 'app-group-detail-page',
  imports: [RouterLink, ReactiveFormsModule, GroupForm],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './group-detail.page.html',
  styleUrl: './groups.css',
})
export class GroupDetailPage {
  /** Paramètre de route :id (withComponentInputBinding). */
  readonly id = input.required<string>();

  private readonly catalog = inject(CatalogApi);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthStore);

  private readonly groupRes = httpResource<GroupDetail>(() => {
    this.catalog.version();
    return `/api/groups/${encodeURIComponent(this.id())}`;
  });
  private readonly themesRes = httpResource<Theme[]>(() => {
    this.catalog.version();
    return '/api/themes';
  });
  protected readonly group = computed(() => valueOr(this.groupRes, undefined));
  protected readonly themes = computed(() => valueOr(this.themesRes, undefined) ?? []);
  protected readonly loadError = computed(() => errorOf(this.groupRes));
  protected readonly formValue = computed<GroupInput | null>(() => {
    const g = this.group();
    return g
      ? {
          name: g.name,
          description: g.description,
          veille_type: g.veille_type,
          theme_id: g.theme.id,
          enabled: g.enabled,
        }
      : null;
  });

  protected readonly editing = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly sourceForm = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(120)],
    }),
    url: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.maxLength(2048),
        Validators.pattern(/^https?:\/\/\S+$/i),
      ],
    }),
  });

  protected typeLabel = veilleTypeLabel;

  protected date(iso: string | null): string {
    return iso ? dateTime.format(new Date(iso)) : 'jamais';
  }

  private async run(action: () => Promise<unknown>): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await action();
      return true;
    } catch (error) {
      this.error.set(problemMessage(error));
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  async save(input: GroupInput): Promise<void> {
    if (await this.run(() => this.catalog.updateGroup(this.id(), input))) {
      this.editing.set(false);
    }
  }

  async toggleGroup(group: GroupDetail): Promise<void> {
    await this.run(() => this.catalog.updateGroup(group.id, { enabled: !group.enabled }));
  }

  async deleteGroup(group: GroupDetail): Promise<void> {
    const ok = window.confirm(
      `Supprimer « ${group.name} », ses ${group.source_count} sources et tous leurs articles ?`,
    );
    if (ok && (await this.run(() => this.catalog.deleteGroup(group.id)))) {
      await this.router.navigateByUrl('/groupes');
    }
  }

  async addSource(): Promise<void> {
    if (this.sourceForm.invalid) {
      this.sourceForm.markAllAsTouched();
      return;
    }
    const value = this.sourceForm.getRawValue();
    const created = await this.run(() =>
      this.catalog.createSource(this.id(), { name: value.name.trim(), url: value.url.trim() }),
    );
    if (created) this.sourceForm.reset();
  }

  async toggleSource(source: Source): Promise<void> {
    await this.run(() => this.catalog.updateSource(source.id, { enabled: !source.enabled }));
  }

  async deleteSource(source: Source): Promise<void> {
    if (window.confirm(`Supprimer la source « ${source.name} » et ses articles ?`)) {
      await this.run(() => this.catalog.deleteSource(source.id));
    }
  }
}

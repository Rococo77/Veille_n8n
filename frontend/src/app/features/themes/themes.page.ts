import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { CatalogApi } from '../../core/api';
import { Theme } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';

const HEX = /^#[0-9a-fA-F]{6}$/;

@Component({
  selector: 'app-themes-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <h1>Thèmes</h1>
      <p class="muted">
        Un thème classe les groupes par sujet, quel que soit leur type de veille. Sa couleur marque
        les articles dans le fil.
      </p>
    </header>

    @if (error() ?? loadError(); as message) {
      <p class="alert" role="alert">{{ message }}</p>
    }

    <ul class="themes">
      @for (t of themes(); track t.id) {
        <li class="row">
          <input
            type="color"
            [value]="t.color"
            [attr.aria-label]="'Couleur de ' + t.name"
            (change)="recolor(t, $any($event.target).value)"
            [disabled]="busy()"
          />
          <span class="name">{{ t.name }}</span>
          <button
            class="btn-link small btn-danger"
            type="button"
            [disabled]="busy()"
            (click)="remove(t)"
          >
            Supprimer
          </button>
        </li>
      } @empty {
        <li class="muted">Aucun thème. Créez le premier ci-dessous.</li>
      }
    </ul>

    <form class="create row" [formGroup]="form" (ngSubmit)="create()" novalidate>
      <label class="visually-hidden" for="t-color">Couleur</label>
      <input id="t-color" type="color" formControlName="color" />
      <label class="visually-hidden" for="t-name">Nom du thème</label>
      <input
        id="t-name"
        type="text"
        formControlName="name"
        maxlength="60"
        placeholder="Nom du thème"
        [attr.aria-invalid]="form.controls.name.touched && form.controls.name.invalid"
      />
      <button class="btn btn-primary" type="submit" [disabled]="busy()">Créer le thème</button>
    </form>
  `,
  styles: `
    :host {
      display: block;
      max-width: 36rem;
    }
    .head {
      margin-bottom: var(--space-5);
    }
    .head p {
      margin: var(--space-1) 0 0;
    }
    .themes {
      list-style: none;
      margin: 0 0 var(--space-5);
      padding: 0;
      border-top: 1px solid var(--rule);
    }
    .themes li {
      padding: var(--space-2) 0;
      border-bottom: 1px solid var(--rule);
    }
    .name {
      flex: 1;
      font-weight: 600;
    }
    .create {
      flex-wrap: nowrap;
    }
    .create input[type='text'] {
      flex: 1;
    }
  `,
})
export class ThemesPage {
  private readonly catalog = inject(CatalogApi);

  private readonly themesRes = httpResource<Theme[]>(() => {
    this.catalog.version();
    return '/api/themes';
  });
  protected readonly themes = computed(() => valueOr(this.themesRes, undefined) ?? []);
  protected readonly loadError = computed(() => errorOf(this.themesRes));
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(60)],
    }),
    color: new FormControl('#1f4fd1', {
      nonNullable: true,
      validators: [Validators.pattern(HEX)],
    }),
  });

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

  async create(): Promise<void> {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, color } = this.form.getRawValue();
    if (await this.run(() => this.catalog.createTheme({ name: name.trim(), color }))) {
      this.form.reset();
    }
  }

  async recolor(theme: Theme, color: string): Promise<void> {
    if (HEX.test(color)) await this.run(() => this.catalog.updateTheme(theme.id, { color }));
  }

  async remove(theme: Theme): Promise<void> {
    if (window.confirm(`Supprimer le thème « ${theme.name} » ?`)) {
      await this.run(() => this.catalog.deleteTheme(theme.id));
    }
  }
}

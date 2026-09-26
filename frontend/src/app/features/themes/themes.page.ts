import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { CatalogApi } from '../../core/api';
import { ConfirmService } from '../../core/confirm';
import { Group, Theme } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';
import { isReadableThemeColor, nextThemeColor } from '../../core/theme-colors';

const HEX = /^#[0-9a-fA-F]{6}$/;
const READABLE_HINT =
  'Couleur trop proche du fond clair ou sombre : choisissez une teinte plus soutenue.';

@Component({
  selector: 'app-themes-page',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <h1>Thèmes et couleurs</h1>
      <p class="muted">
        Un thème classe les groupes par sujet, quel que soit leur type de veille. Son nom et sa
        couleur accompagnent chaque article du fil.
      </p>
    </header>

    @if (error() ?? loadError(); as message) {
      <p class="alert" role="alert">{{ message }}</p>
    }

    <ul class="themes">
      @for (t of themes(); track t.id) {
        @let used = usage().get(t.id) ?? 0;
        <li>
          <input
            type="color"
            [value]="t.color"
            [attr.aria-label]="'Couleur de ' + t.name"
            (change)="recolor(t, $any($event.target))"
            [disabled]="busy()"
          />
          <span class="name">{{ t.name }}</span>
          <a class="usage small" routerLink="/" [queryParams]="{ theme: t.id }">
            {{ used }} groupe{{ used > 1 ? 's' : '' }}
          </a>
          @if (used === 0) {
            <button
              class="btn-link small btn-danger"
              type="button"
              [disabled]="busy()"
              (click)="remove(t)"
            >
              Supprimer
            </button>
          } @else {
            <span class="small muted locked" [attr.title]="'Utilisé par ' + used + ' groupe(s)'"
              >Utilisé</span
            >
          }
        </li>
      } @empty {
        @if (!loading()) {
          <li class="muted">Aucun thème. Créez le premier ci-dessous.</li>
        }
      }
    </ul>
    @if (inUse() > 0) {
      <p class="small muted">
        Un thème utilisé par un groupe ne peut pas être supprimé : changez d'abord le thème de ces
        groupes.
      </p>
    }

    <form class="panel create" [formGroup]="form" (ngSubmit)="create()" novalidate>
      <h2>Nouveau thème</h2>
      <div class="create-row">
        <div class="field color">
          <label for="t-color">Couleur</label>
          <input
            id="t-color"
            type="color"
            formControlName="color"
            aria-describedby="t-color-hint"
            [attr.aria-invalid]="colorUnreadable()"
          />
        </div>
        <div class="field grow">
          <label for="t-name">Nom du thème</label>
          <input
            id="t-name"
            type="text"
            formControlName="name"
            maxlength="60"
            placeholder="Cloud, Concurrents, RGPD…"
            [attr.aria-invalid]="form.controls.name.touched && form.controls.name.invalid"
          />
        </div>
        <button
          class="btn btn-primary"
          type="submit"
          [disabled]="busy()"
          [attr.aria-busy]="busy()"
        >
          Créer le thème
        </button>
      </div>
      <span id="t-color-hint" [class]="colorUnreadable() ? 'field-error' : 'hint'">
        {{
          colorUnreadable()
            ? readableHint
            : 'Une couleur libre est proposée par défaut pour distinguer les thèmes.'
        }}
      </span>
    </form>
  `,
  styles: `
    :host {
      display: block;
      max-width: 40rem;
    }
    .head {
      margin-bottom: var(--space-5);
    }
    .head p {
      margin: var(--space-1) 0 0;
    }
    .themes {
      list-style: none;
      margin: 0 0 var(--space-3);
      padding: 0;
      border-top: 1px solid var(--rule);
    }
    .themes li {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      padding: var(--space-2) 0;
      border-bottom: 1px solid var(--rule);
    }
    .name {
      flex: 1;
      min-width: 0;
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .usage {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .themes .btn-link,
    .locked {
      min-width: 5.5rem;
      min-height: var(--target);
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
    }
    .create {
      margin-top: var(--space-5);
    }
    .create-row {
      display: flex;
      flex-wrap: wrap;
      align-items: end;
      gap: var(--space-3);
    }
    .create-row .field {
      margin-bottom: 0;
    }
    .grow {
      flex: 1 1 14rem;
    }
    .create .hint,
    .create .field-error {
      display: block;
      margin-top: var(--space-2);
    }
  `,
})
export class ThemesPage {
  private readonly catalog = inject(CatalogApi);
  private readonly confirm = inject(ConfirmService);
  protected readonly readableHint = READABLE_HINT;

  private readonly themesRes = httpResource<Theme[]>(() => {
    this.catalog.version();
    return '/api/themes';
  });
  private readonly groupsRes = httpResource<Group[]>(() => {
    this.catalog.version();
    return '/api/groups';
  });
  protected readonly themes = computed(() => valueOr(this.themesRes, undefined) ?? []);
  protected readonly loading = computed(() => this.themesRes.isLoading());
  protected readonly loadError = computed(() => errorOf(this.themesRes));
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  /** Nombre de groupes par thème : un thème utilisé est protégé contre la suppression. */
  protected readonly usage = computed(() => {
    const counts = new Map<string, number>();
    for (const g of valueOr(this.groupsRes, undefined) ?? []) {
      counts.set(g.theme.id, (counts.get(g.theme.id) ?? 0) + 1);
    }
    return counts;
  });
  protected readonly inUse = computed(
    () => this.themes().filter((t) => (this.usage().get(t.id) ?? 0) > 0).length,
  );

  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(60)],
    }),
    color: new FormControl<string>(nextThemeColor([]), {
      nonNullable: true,
      validators: [Validators.pattern(HEX)],
    }),
  });
  private readonly colorValue = toSignal(this.form.controls.color.valueChanges, {
    initialValue: this.form.controls.color.value,
  });
  protected readonly colorUnreadable = computed(() => !isReadableThemeColor(this.colorValue()));

  constructor() {
    // Proposer une teinte encore libre dès que la liste des thèmes est connue.
    effect(() => {
      const used = this.themes().map((t) => t.color);
      const control = this.form.controls.color;
      if (!control.dirty) control.setValue(nextThemeColor(used));
    });
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

  async create(): Promise<void> {
    if (this.form.invalid || this.colorUnreadable()) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, color } = this.form.getRawValue();
    if (await this.run(() => this.catalog.createTheme({ name: name.trim(), color }))) {
      this.form.reset({ name: '', color: nextThemeColor([...this.themes().map((t) => t.color), color]) });
    }
  }

  async recolor(theme: Theme, input: HTMLInputElement): Promise<void> {
    const color = input.value;
    if (!HEX.test(color)) return;
    if (!isReadableThemeColor(color)) {
      this.error.set(`${theme.name} : ${READABLE_HINT}`);
      input.value = theme.color;
      return;
    }
    await this.run(() => this.catalog.updateTheme(theme.id, { color }));
  }

  async remove(theme: Theme): Promise<void> {
    const ok = await this.confirm.ask({
      title: 'Supprimer le thème ?',
      body: `« ${theme.name} » n'est utilisé par aucun groupe. Sa suppression est définitive.`,
      confirmLabel: 'Supprimer le thème',
      danger: true,
    });
    if (ok) await this.run(() => this.catalog.deleteTheme(theme.id));
  }
}

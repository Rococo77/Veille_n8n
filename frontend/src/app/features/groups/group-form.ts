import { ChangeDetectionStrategy, Component, effect, input, output } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { GroupInput, Theme, VEILLE_TYPES, VeilleType } from '../../core/models';

/** Formulaire de groupe sans état serveur : le parent décide création ou modification. */
@Component({
  selector: 'app-group-form',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <div class="grid">
        <div class="field">
          <label for="g-name">Nom du groupe</label>
          <input
            id="g-name"
            type="text"
            formControlName="name"
            maxlength="120"
            [attr.aria-invalid]="form.controls.name.touched && form.controls.name.invalid"
          />
        </div>
        <div class="field">
          <label for="g-type">Type de veille</label>
          <select id="g-type" formControlName="veille_type">
            @for (t of types; track t.value) {
              <option [value]="t.value">{{ t.label }}</option>
            }
          </select>
        </div>
        <div class="field">
          <label for="g-theme">Thème</label>
          <select
            id="g-theme"
            formControlName="theme_id"
            [attr.aria-invalid]="form.controls.theme_id.touched && form.controls.theme_id.invalid"
          >
            <option value="" disabled>Choisir un thème</option>
            @for (t of themes(); track t.id) {
              <option [value]="t.id">{{ t.name }}</option>
            }
          </select>
        </div>
      </div>
      <div class="field">
        <label for="g-desc">Description</label>
        <textarea
          id="g-desc"
          formControlName="description"
          maxlength="1000"
          placeholder="Ce que ce groupe surveille et pourquoi"
        ></textarea>
      </div>
      <label class="check field">
        <input type="checkbox" formControlName="enabled" />
        Relever les sources de ce groupe
      </label>
      <div class="row">
        <button class="btn btn-primary" type="submit" [disabled]="busy()">
          {{ submitLabel() }}
        </button>
        <button class="btn" type="button" (click)="cancelled.emit()">Annuler</button>
      </div>
    </form>
  `,
  styles: `
    .grid {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: var(--space-3);
    }
    @media (max-width: 40rem) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class GroupForm {
  readonly themes = input.required<Theme[]>();
  readonly initial = input<GroupInput | null>(null);
  readonly submitLabel = input('Enregistrer');
  readonly busy = input(false);
  readonly submitted = output<GroupInput>();
  readonly cancelled = output<void>();

  protected readonly types = VEILLE_TYPES;
  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(120)],
    }),
    veille_type: new FormControl<VeilleType>('technologique', { nonNullable: true }),
    theme_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    description: new FormControl('', {
      nonNullable: true,
      validators: [Validators.maxLength(1000)],
    }),
    enabled: new FormControl(true, { nonNullable: true }),
  });

  constructor() {
    effect(() => {
      const initial = this.initial();
      if (initial) this.form.reset(initial);
    });
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.submitted.emit({
      ...value,
      name: value.name.trim(),
      description: value.description.trim(),
    });
  }
}

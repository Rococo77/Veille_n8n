import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

import { Router, RouterLink } from '@angular/router';

import { AuthStore } from '../../core/auth.store';
import { problemMessage } from '../../core/problem';

function samePasswords(group: AbstractControl): ValidationErrors | null {
  const next = group.get('next')?.value;
  const confirm = group.get('confirm')?.value;
  return next && confirm && next !== confirm ? { mismatch: true } : null;
}

@Component({
  selector: 'app-account-page',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Mon compte</h1>
    <p class="muted">Connecté en tant que {{ auth.me()?.email }}.</p>

    <!-- Sur mobile, la barre d'onglets n'a que quatre entrées : cette page porte le reste. -->
    <div class="session-actions">
      @if (auth.isAdmin()) {
        <nav class="admin-links" aria-label="Administration">
          <a routerLink="/admin/utilisateurs">Utilisateurs</a>
          <a routerLink="/admin/journal">Journal d'audit</a>
        </nav>
      }
      <button type="button" class="btn" [disabled]="loggingOut()" (click)="logout()">
        Se déconnecter
      </button>
    </div>

    <form class="panel" [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <h2>Changer de mot de passe</h2>
      @if (error(); as message) {
        <p class="alert" role="alert">{{ message }}</p>
      }
      @if (done()) {
        <p role="status">Mot de passe modifié. Vos autres sessions ont été fermées.</p>
      }
      <div class="field">
        <label for="a-current">Mot de passe actuel</label>
        <input
          id="a-current"
          type="password"
          formControlName="current"
          autocomplete="current-password"
        />
      </div>
      <div class="field">
        <label for="a-next">Nouveau mot de passe</label>
        <input
          id="a-next"
          type="password"
          formControlName="next"
          autocomplete="new-password"
          aria-describedby="a-next-hint"
          [attr.aria-invalid]="form.controls.next.touched && form.controls.next.invalid"
        />
        <span id="a-next-hint" class="hint"
          >12 caractères minimum. Une phrase de passe est plus simple à retenir.</span
        >
      </div>
      <div class="field">
        <label for="a-confirm">Confirmation</label>
        <input
          id="a-confirm"
          type="password"
          formControlName="confirm"
          autocomplete="new-password"
          [attr.aria-invalid]="form.touched && form.hasError('mismatch')"
          [attr.aria-describedby]="
            form.touched && form.hasError('mismatch') ? 'a-confirm-error' : null
          "
        />
        @if (form.touched && form.hasError('mismatch')) {
          <span id="a-confirm-error" class="field-error">Les deux mots de passe diffèrent.</span>
        }
      </div>
      <button class="btn btn-primary" type="submit" [disabled]="busy()" [attr.aria-busy]="busy()">
        Changer le mot de passe
      </button>
    </form>
  `,
  styles: `
    :host {
      display: block;
      max-width: 30rem;
    }
    .panel {
      margin-top: var(--space-5);
    }
    .session-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-4);
      margin-top: var(--space-4);
    }
    .admin-links {
      display: flex;
      gap: var(--space-4);
    }
    .admin-links a {
      display: inline-flex;
      align-items: center;
      min-height: 44px;
    }
  `,
})
export class AccountPage {
  protected readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  protected readonly busy = signal(false);
  protected readonly loggingOut = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

  protected readonly form = new FormGroup(
    {
      current: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
      next: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required, Validators.minLength(12), Validators.maxLength(256)],
      }),
      confirm: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    },
    { validators: samePasswords },
  );

  async submit(): Promise<void> {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.done.set(false);
    const { current, next } = this.form.getRawValue();
    try {
      await this.auth.changePassword(current, next);
      this.form.reset();
      this.done.set(true);
    } catch (error) {
      this.error.set(problemMessage(error));
    } finally {
      this.busy.set(false);
    }
  }

  async logout(): Promise<void> {
    this.loggingOut.set(true);
    try {
      await this.auth.logout();
    } finally {
      // AuthStore efface l'état local même si l'appel échoue : on quitte l'espace connecté
      // dans tous les cas, comme le fait le bouton du bandeau.
      this.loggingOut.set(false);
      await this.router.navigateByUrl('/connexion');
    }
  }
}

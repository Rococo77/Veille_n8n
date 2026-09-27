import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthStore } from '../../core/auth.store';
import { InvitationInfo, Role } from '../../core/models';
import { problemMessage } from '../../core/problem';

const ROLE_LABELS: Record<Role, string> = {
  viewer: 'Lecture',
  editor: 'Édition',
  admin: 'Administration',
};
const TOKEN_RE = /^[A-Za-z0-9_-]{32,64}$/;

function samePasswords(group: AbstractControl): ValidationErrors | null {
  const password = group.get('password')?.value;
  const confirm = group.get('confirm')?.value;
  return password && confirm && password !== confirm ? { mismatch: true } : null;
}

@Component({
  selector: 'app-invitation-page',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './auth.css',
  template: `
    <main class="auth">
      <h1 class="brand">Veille</h1>

      @if (state() === 'loading') {
        <p class="muted" role="status" aria-live="polite">Vérification du lien…</p>
      } @else if (state() === 'invalid') {
        <section class="panel-card" role="alert">
          <h2>Lien inutilisable</h2>
          <p>Ce lien est invalide, expiré ou déjà utilisé.</p>
          <p class="muted">Demandez un nouveau lien à l'administrateur qui vous a invité.</p>
          <p><a routerLink="/connexion">Aller à la connexion</a></p>
        </section>
      } @else if (info(); as i) {
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <h2>Activer votre compte</h2>
          <p class="muted small">{{ i.email }} · rôle {{ roleLabel(i.role) }}</p>

          @if (error(); as message) {
            <p class="alert" role="alert">{{ message }}</p>
          }

          <div class="field">
            <label for="i-password">Mot de passe</label>
            <input
              id="i-password"
              type="password"
              formControlName="password"
              autocomplete="new-password"
              aria-describedby="i-password-hint"
              [attr.aria-invalid]="form.controls.password.touched && form.controls.password.invalid"
            />
            <span id="i-password-hint" class="hint"
              >12 caractères minimum. Une phrase de passe est plus simple à retenir.</span
            >
          </div>
          <div class="field">
            <label for="i-confirm">Confirmation</label>
            <input
              id="i-confirm"
              type="password"
              formControlName="confirm"
              autocomplete="new-password"
              [attr.aria-invalid]="form.touched && form.hasError('mismatch')"
              [attr.aria-describedby]="
                form.touched && form.hasError('mismatch') ? 'i-confirm-error' : null
              "
            />
            @if (form.touched && form.hasError('mismatch')) {
              <span id="i-confirm-error" class="field-error"
                >Les deux mots de passe diffèrent.</span
              >
            }
          </div>

          <button
            class="btn btn-primary wide"
            type="submit"
            [disabled]="busy()"
            [attr.aria-busy]="busy()"
          >
            {{ busy() ? 'Activation…' : 'Continuer' }}
          </button>
          <p class="muted small">
            Vous configurerez ensuite une application d'authentification : le second facteur est
            obligatoire.
          </p>
        </form>
      }
    </main>
  `,
})
export class InvitationPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  /** Lu une fois depuis le fragment, puis retiré de la barre d'adresse et de l'historique. */
  private readonly token = this.route.snapshot.fragment ?? '';

  protected readonly state = signal<'loading' | 'invalid' | 'ready'>('loading');
  protected readonly info = signal<InvitationInfo | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly busy = signal(false);

  protected readonly form = new FormGroup(
    {
      password: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required, Validators.minLength(12), Validators.maxLength(256)],
      }),
      confirm: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    },
    { validators: samePasswords },
  );

  constructor() {
    void this.router.navigate([], { relativeTo: this.route, replaceUrl: true });
    void this.load();
  }

  protected roleLabel(role: Role): string {
    return ROLE_LABELS[role];
  }

  private async load(): Promise<void> {
    if (!TOKEN_RE.test(this.token)) {
      this.state.set('invalid');
      return;
    }
    try {
      this.info.set(await this.auth.lookupInvitation(this.token));
      this.state.set('ready');
    } catch {
      // 404 volontairement indistinct côté serveur (inconnu, expiré, déjà utilisé).
      this.state.set('invalid');
    }
  }

  async submit(): Promise<void> {
    if (this.form.invalid || this.busy()) {
      this.form.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      const result = await this.auth.acceptInvitation(
        this.token,
        this.form.controls.password.value,
      );
      const queryParams: Record<string, string> = result.mfa_enrolled ? {} : { nouveau: '1' };
      await this.router.navigate(['/connexion/code'], { queryParams, replaceUrl: true });
    } catch (error) {
      this.error.set(problemMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}

import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthStore } from '../../core/auth.store';
import { problemMessage } from '../../core/problem';
import { safeReturnPath } from '../../core/return-url';

@Component({
  selector: 'app-login-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.page.html',
  styleUrl: './auth.css',
})
export class LoginPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly query = inject(ActivatedRoute).snapshot.queryParamMap;

  protected readonly expired = this.query.get('motif') === 'expiree';
  private readonly retour = safeReturnPath(this.query.get('retour'));

  protected readonly form = new FormGroup({
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email, Validators.maxLength(254)],
    }),
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(256)],
    }),
  });
  protected readonly error = signal<string | null>(null);
  protected readonly busy = signal(false);

  async submit(): Promise<void> {
    if (this.form.invalid || this.busy()) {
      this.form.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    try {
      const result = await this.auth.login(email, password);
      const queryParams: Record<string, string> = result.mfa_enrolled ? {} : { nouveau: '1' };
      if (this.retour) queryParams['retour'] = this.retour;
      await this.router.navigate(['/connexion/code'], { queryParams });
    } catch (error) {
      this.error.set(problemMessage(error));
      this.form.controls.password.reset();
    } finally {
      this.busy.set(false);
    }
  }
}

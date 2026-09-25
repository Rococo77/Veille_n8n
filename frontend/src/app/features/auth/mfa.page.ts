import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { toCanvas } from 'qrcode';

import { AuthStore, MfaEnrollment } from '../../core/auth.store';
import { problemCode, problemMessage } from '../../core/problem';

@Component({
  selector: 'app-mfa-page',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './mfa.page.html',
  styleUrl: './auth.css',
})
export class MfaPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  private readonly qr = viewChild<ElementRef<HTMLCanvasElement>>('qr');

  protected readonly form = new FormGroup({
    code: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^\d{6}$/)],
    }),
  });
  protected readonly enrollment = signal<MfaEnrollment | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly expired = signal(false);
  protected readonly busy = signal(false);

  constructor() {
    if (this.route.snapshot.queryParamMap.has('nouveau')) {
      void this.startEnrollment();
    }
    effect(() => {
      const canvas = this.qr()?.nativeElement;
      const enrollment = this.enrollment();
      if (canvas && enrollment) {
        // QR généré localement : le secret ne transite par aucun service tiers.
        void toCanvas(canvas, enrollment.otpauth_uri, { width: 200, margin: 1 });
      }
    });
  }

  private async startEnrollment(): Promise<void> {
    try {
      this.enrollment.set(await this.auth.enroll());
    } catch (error) {
      this.handle(error);
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
      await this.auth.verify(this.form.controls.code.value);
      // Le secret n'a plus rien à faire en mémoire une fois le facteur validé.
      this.enrollment.set(null);
      await this.router.navigateByUrl('/');
    } catch (error) {
      this.handle(error);
      this.form.reset();
    } finally {
      this.busy.set(false);
    }
  }

  private handle(error: unknown): void {
    const code = problemCode(error);
    if (code === 'unauthenticated') {
      this.expired.set(true);
      this.enrollment.set(null);
    } else if (code !== 'conflict') {
      this.error.set(problemMessage(error));
    }
  }
}

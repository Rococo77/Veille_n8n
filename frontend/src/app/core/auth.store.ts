import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { Me, Role } from './models';

const RANK: Record<Role, number> = { viewer: 0, editor: 1, admin: 2 };

export interface MfaEnrollment {
  otpauth_uri: string;
  secret: string;
}

/**
 * Source de vérité côté client : uniquement ce que l'API confirme via /me.
 * Aucune donnée d'auth n'est stockée dans le navigateur (le jeton est un cookie HttpOnly).
 */
@Injectable({ providedIn: 'root' })
export class AuthStore {
  private readonly http = inject(HttpClient);

  /** undefined = pas encore vérifié, null = non connecté. */
  private readonly _me = signal<Me | null | undefined>(undefined);
  readonly me = this._me.asReadonly();
  readonly isEditor = computed(() => this.hasRole('editor'));
  readonly isAdmin = computed(() => this.hasRole('admin'));

  hasRole(minimum: Role): boolean {
    const me = this._me();
    return !!me && RANK[me.role] >= RANK[minimum];
  }

  async refresh(): Promise<Me | null> {
    try {
      const me = await firstValueFrom(this.http.get<Me>('/api/auth/me'));
      this._me.set(me);
      return me;
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        this._me.set(null);
        return null;
      }
      throw error;
    }
  }

  async login(email: string, password: string): Promise<{ mfa_enrolled: boolean }> {
    return firstValueFrom(
      this.http.post<{ mfa_enrolled: boolean }>('/api/auth/login', { email, password }),
    );
  }

  async enroll(): Promise<MfaEnrollment> {
    return firstValueFrom(this.http.post<MfaEnrollment>('/api/auth/mfa/enroll', null));
  }

  async verify(code: string): Promise<Me> {
    const me = await firstValueFrom(this.http.post<Me>('/api/auth/mfa/verify', { code }));
    this._me.set(me);
    return me;
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.post<void>('/api/auth/logout', null));
    } finally {
      this._me.set(null);
    }
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await firstValueFrom(
      this.http.post<void>('/api/auth/password', {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    );
  }

  /** Appelé par l'intercepteur quand l'API invalide la session. */
  markSignedOut(): void {
    this._me.set(null);
  }
}

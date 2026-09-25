import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { AdminApi } from '../../core/api';
import { AuthStore } from '../../core/auth.store';
import { Role, User } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';

const ROLES: readonly { value: Role; label: string }[] = [
  { value: 'viewer', label: 'Lecture' },
  { value: 'editor', label: 'Édition' },
  { value: 'admin', label: 'Administration' },
];

@Component({
  selector: 'app-users-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './users.page.html',
  styleUrl: './admin.css',
})
export class UsersPage {
  private readonly api = inject(AdminApi);
  protected readonly auth = inject(AuthStore);
  protected readonly roles = ROLES;

  private readonly version = signal(0);
  private readonly usersRes = httpResource<User[]>(() => {
    this.version();
    return '/api/users';
  });
  protected readonly users = computed(() => valueOr(this.usersRes, undefined) ?? []);
  protected readonly loadError = computed(() => errorOf(this.usersRes));
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = new FormGroup({
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email, Validators.maxLength(254)],
    }),
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(12), Validators.maxLength(256)],
    }),
    role: new FormControl<Role>('viewer', { nonNullable: true }),
  });

  protected isLocked(user: User): boolean {
    return !!user.locked_until && new Date(user.locked_until) > new Date();
  }

  private async run(action: () => Promise<unknown>): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await action();
      this.version.update((v) => v + 1);
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
    if (await this.run(() => this.api.createUser(this.form.getRawValue()))) this.form.reset();
  }

  async setRole(user: User, role: Role): Promise<void> {
    await this.run(() => this.api.updateUser(user.id, { role }));
  }

  async toggleActive(user: User): Promise<void> {
    await this.run(() => this.api.updateUser(user.id, { is_active: !user.is_active }));
  }

  async resetMfa(user: User): Promise<void> {
    const ok = window.confirm(
      `Réinitialiser le second facteur de ${user.email} ? Ses sessions seront fermées.`,
    );
    if (ok) await this.run(() => this.api.resetMfa(user.id));
  }

  async unlock(user: User): Promise<void> {
    await this.run(() => this.api.unlock(user.id));
  }
}

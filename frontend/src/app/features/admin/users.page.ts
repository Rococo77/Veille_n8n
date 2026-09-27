import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { AdminApi } from '../../core/api';
import { AuthStore } from '../../core/auth.store';
import { ConfirmService } from '../../core/confirm';
import { InvitationResult, Role, User } from '../../core/models';
import { problemMessage } from '../../core/problem';
import { errorOf, valueOr } from '../../core/resource';

const ROLES: readonly { value: Role; label: string }[] = [
  { value: 'viewer', label: 'Lecture' },
  { value: 'editor', label: 'Édition' },
  { value: 'admin', label: 'Administration' },
];

const ROLE_EFFECT: Record<Role, string> = {
  viewer: 'Ce compte pourra seulement consulter le fil.',
  editor: 'Ce compte pourra gérer thèmes, groupes et sources.',
  admin: 'Ce compte pourra gérer tous les comptes et lire le journal d’audit.',
};

const expiryFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'long',
  hour: '2-digit',
  minute: '2-digit',
});

function roleLabel(role: Role): string {
  return ROLES.find((r) => r.value === role)?.label ?? role;
}

@Component({
  selector: 'app-users-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './users.page.html',
  styleUrl: './admin.css',
})
export class UsersPage {
  private readonly api = inject(AdminApi);
  private readonly confirm = inject(ConfirmService);
  protected readonly auth = inject(AuthStore);
  protected readonly roles = ROLES;

  private readonly version = signal(0);
  private readonly usersRes = httpResource<User[]>(() => {
    this.version();
    return '/api/users';
  });
  protected readonly users = computed(() => valueOr(this.usersRes, undefined) ?? []);
  protected readonly loadError = computed(() => errorOf(this.usersRes));
  protected readonly loading = computed(
    () => this.usersRes.isLoading() && !this.usersRes.hasValue(),
  );
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = new FormGroup({
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email, Validators.maxLength(254)],
    }),
    role: new FormControl<Role>('viewer', { nonNullable: true }),
  });

  /** Dernière invitation émise : confirmation, ou lien à transmettre si le mail n'est pas parti. */
  protected readonly invitation = signal<InvitationResult | null>(null);
  protected readonly copied = signal(false);

  protected expiry(iso: string): string {
    return expiryFormat.format(new Date(iso));
  }

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
    await this.issue(() => this.api.inviteUser(this.form.getRawValue()), true);
  }

  async reinvite(user: User): Promise<void> {
    if (user.has_password) {
      const ok = await this.confirm.ask({
        title: 'Envoyer un lien de nouveau mot de passe ?',
        body: `${user.email} recevra un lien valable 48 h pour choisir un nouveau mot de passe. L'actuel reste valable jusqu'à l'utilisation du lien ; ses sessions seront alors fermées.`,
        confirmLabel: 'Envoyer le lien',
      });
      if (!ok) return;
    }
    await this.issue(() => this.api.reinvite(user.id), false);
  }

  private async issue(action: () => Promise<InvitationResult>, resetForm: boolean): Promise<void> {
    this.invitation.set(null);
    this.copied.set(false);
    let result: InvitationResult | null = null;
    const ok = await this.run(async () => {
      result = await action();
    });
    if (!ok || !result) return;
    this.invitation.set(result);
    if (resetForm) this.form.reset();
  }

  async copyLink(url: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(url);
      this.copied.set(true);
    } catch {
      // Presse-papiers refusé (contexte non sécurisé, permission) : le lien reste
      // affiché et sélectionnable à la main.
      this.copied.set(false);
    }
  }

  /**
   * Un select réagit à chaque flèche du clavier : sans confirmation, parcourir la liste
   * changerait réellement le rôle. On confirme, et on rétablit la valeur si l'on annule.
   */
  async setRole(user: User, select: HTMLSelectElement): Promise<void> {
    const role = select.value as Role;
    if (role === user.role) return;
    const ok = await this.confirm.ask({
      title: 'Changer le rôle ?',
      body: `${user.email} passera de « ${roleLabel(user.role)} » à « ${roleLabel(role)} ». ${ROLE_EFFECT[role]}`,
      confirmLabel: `Passer en ${roleLabel(role).toLowerCase()}`,
      danger: role === 'admin',
    });
    if (!ok || !(await this.run(() => this.api.updateUser(user.id, { role })))) {
      select.value = user.role;
    }
  }

  async toggleActive(user: User): Promise<void> {
    if (user.is_active) {
      const ok = await this.confirm.ask({
        title: 'Désactiver le compte ?',
        body: `${user.email} ne pourra plus se connecter. Le compte et son historique sont conservés ; vous pourrez le réactiver.`,
        confirmLabel: 'Désactiver',
        danger: true,
      });
      if (!ok) return;
    }
    await this.run(() => this.api.updateUser(user.id, { is_active: !user.is_active }));
  }

  async resetMfa(user: User): Promise<void> {
    const ok = await this.confirm.ask({
      title: 'Réinitialiser le second facteur ?',
      body: `${user.email} devra reconfigurer son application d'authentification à la prochaine connexion. Ses sessions ouvertes seront fermées.`,
      confirmLabel: 'Réinitialiser le 2FA',
      danger: true,
    });
    if (ok) await this.run(() => this.api.resetMfa(user.id));
  }

  async unlock(user: User): Promise<void> {
    await this.run(() => this.api.unlock(user.id));
  }
}

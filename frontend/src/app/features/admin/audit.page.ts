import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { httpResource } from '@angular/common/http';

import { AuditEvent, User } from '../../core/models';
import { errorOf, valueOr } from '../../core/resource';

const dateTime = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'medium' });

const ACTIONS: Record<string, string> = {
  'login.failed': 'Échec de connexion',
  'login.locked': 'Connexion refusée (compte verrouillé)',
  'login.password_ok': 'Mot de passe validé',
  'login.success': 'Connexion',
  'mfa.enrolled': 'Second facteur configuré',
  'mfa.failed': 'Code 2FA invalide',
  'mfa.too_many_attempts': 'Trop de codes 2FA invalides',
  logout: 'Déconnexion',
  'password.changed': 'Mot de passe modifié',
  'user.created': 'Compte créé',
  'user.updated': 'Compte modifié',
  'user.mfa_reset': 'Second facteur réinitialisé',
  'user.unlocked': 'Compte déverrouillé',
  'theme.created': 'Thème créé',
  'theme.updated': 'Thème modifié',
  'theme.deleted': 'Thème supprimé',
  'group.created': 'Groupe créé',
  'group.updated': 'Groupe modifié',
  'group.deleted': 'Groupe supprimé',
  'source.created': 'Source ajoutée',
  'source.updated': 'Source modifiée',
  'source.deleted': 'Source supprimée',
  'ingest.failed': 'Relevé de flux en échec',
};

@Component({
  selector: 'app-audit-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <h1>Journal d'audit</h1>
      <p class="muted">
        Les {{ limit() }} derniers événements de sécurité et de modification, du plus récent au
        plus ancien.
      </p>
    </header>
    @if (loadError(); as message) {
      <p class="alert" role="alert">{{ message }}</p>
    }
    <div class="toolbar">
      <label class="check">
        <input type="checkbox" #onlyAlerts (change)="alertsOnly.set(onlyAlerts.checked)" />
        Seulement les alertes ({{ alertCount() }})
      </label>
    </div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Événement</th>
            <th scope="col">Auteur</th>
            <th scope="col">Cible</th>
            <th scope="col">IP</th>
          </tr>
        </thead>
        <tbody [attr.aria-busy]="loading()">
          @if (loading()) {
            @for (i of [1, 2, 3]; track i) {
              <tr aria-hidden="true">
                <td colspan="5"><span class="skeleton"></span></td>
              </tr>
            }
          }
          @for (e of visible(); track e.id) {
            <tr [class.alerting]="isAlert(e.action)">
              <td class="when">{{ date(e.at) }}</td>
              <td>{{ label(e.action) }}</td>
              <td>{{ actor(e) }}</td>
              <td class="target">{{ e.target ?? '' }}</td>
              <td>{{ e.ip ?? '' }}</td>
            </tr>
          } @empty {
            @if (!loading() && !loadError()) {
              <tr>
                <td colspan="5" class="muted">
                  {{ alertsOnly() ? 'Aucune alerte parmi ces événements.' : 'Aucun événement enregistré.' }}
                </td>
              </tr>
            }
          }
        </tbody>
      </table>
    </div>
    @if (limit() < maxLimit && events().length >= limit()) {
      <p class="more">
        <button class="btn" type="button" (click)="limit.set(maxLimit)">
          Afficher jusqu'à {{ maxLimit }} événements
        </button>
      </p>
    }
  `,
  styles: `
    :host {
      display: block;
      max-width: 70rem;
    }
    .head {
      margin-bottom: var(--space-5);
    }
    .head p {
      margin: var(--space-1) 0 0;
    }
    .toolbar {
      margin-bottom: var(--space-2);
    }
    .when {
      white-space: nowrap;
    }
    .target {
      word-break: break-all;
      max-width: 18rem;
    }
    .more {
      margin-top: var(--space-4);
    }
    tr.alerting td:nth-child(2) {
      color: var(--alert);
      font-weight: 600;
    }
  `,
})
export class AuditPage {
  /** Plafond imposé par l'API (Query le=500). */
  protected readonly maxLimit = 500;
  protected readonly limit = signal(200);
  protected readonly alertsOnly = signal(false);

  private readonly eventsRes = httpResource<AuditEvent[]>(() => ({
    url: '/api/audit',
    params: { limit: this.limit() },
  }));
  protected readonly events = computed(() => valueOr(this.eventsRes, undefined) ?? []);
  protected readonly loading = computed(
    () => this.eventsRes.isLoading() && this.events().length === 0,
  );
  protected readonly alertCount = computed(
    () => this.events().filter((e) => this.isAlert(e.action)).length,
  );
  protected readonly visible = computed(() =>
    this.alertsOnly() ? this.events().filter((e) => this.isAlert(e.action)) : this.events(),
  );
  protected readonly loadError = computed(() => errorOf(this.eventsRes));
  private readonly usersRes = httpResource<User[]>(() => '/api/users');
  private readonly emails = computed(
    () => new Map((valueOr(this.usersRes, undefined) ?? []).map((u) => [u.id, u.email])),
  );

  protected actor(event: AuditEvent): string {
    if (event.actor_kind === 'service') return 'n8n';
    if (!event.actor_user_id) return 'anonyme';
    return this.emails().get(event.actor_user_id) ?? 'compte supprimé';
  }

  protected date(iso: string): string {
    return dateTime.format(new Date(iso));
  }

  protected label(action: string): string {
    return ACTIONS[action] ?? action;
  }

  protected isAlert(action: string): boolean {
    return action.endsWith('failed') || action.includes('locked') || action.includes('too_many');
  }
}

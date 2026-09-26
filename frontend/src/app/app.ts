import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map, take } from 'rxjs';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (!ready()) {
      <p class="boot" role="status">
        <span class="brand">Veille</span>
        <span class="muted small">Vérification de la session…</span>
      </p>
    }
    <router-outlet />
  `,
  styles: `
    .boot {
      min-height: 100dvh;
      margin: 0;
      display: grid;
      place-content: center;
      justify-items: center;
      gap: var(--space-2);
    }
    .brand {
      font-family: var(--font-read);
      font-size: var(--step-3);
      font-weight: 700;
    }
  `,
})
export class App {
  // Les gardes attendent /api/auth/me (serveur parfois lent à se réveiller) : sans cet état,
  // la première navigation affiche une page vide pendant plusieurs secondes.
  private readonly firstNavigationDone = toSignal(
    inject(Router).events.pipe(
      filter((e) => e instanceof NavigationEnd),
      take(1),
      map(() => true),
    ),
    { initialValue: false },
  );
  protected readonly ready = computed(() => this.firstNavigationDone());
}

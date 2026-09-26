import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injectable,
  computed,
  effect,
  signal,
  inject,
  viewChild,
} from '@angular/core';

export interface ConfirmRequest {
  title: string;
  body: string;
  confirmLabel: string;
  /** Action destructive : bouton rouge. */
  danger?: boolean;
  /** Texte à retaper pour confirmer (suppression en cascade). */
  typeToConfirm?: string;
}

interface Pending extends ConfirmRequest {
  resolve: (ok: boolean) => void;
}

/**
 * Remplace window.confirm : fenêtre native <dialog> (focus piégé, Échap) aux couleurs de
 * l'application, sans script inline donc compatible avec la CSP.
 */
@Injectable({ providedIn: 'root' })
export class ConfirmService {
  private readonly _pending = signal<Pending | null>(null);
  readonly pending = this._pending.asReadonly();

  ask(request: ConfirmRequest): Promise<boolean> {
    this._pending()?.resolve(false);
    return new Promise((resolve) => this._pending.set({ ...request, resolve }));
  }

  settle(ok: boolean): void {
    const pending = this._pending();
    this._pending.set(null);
    pending?.resolve(ok);
  }
}

@Component({
  selector: 'app-confirm-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <dialog #dialog aria-labelledby="confirm-title" (close)="onClose()" (cancel)="onCancel()">
      @if (service.pending(); as p) {
        <form method="dialog" (submit)="$event.preventDefault(); confirm()">
          <h2 id="confirm-title">{{ p.title }}</h2>
          <p>{{ p.body }}</p>
          @if (p.typeToConfirm) {
            <div class="field">
              <label for="confirm-text">Tapez « {{ p.typeToConfirm }} » pour confirmer</label>
              <input
                #typed
                id="confirm-text"
                type="text"
                autocomplete="off"
                spellcheck="false"
                (input)="typedValue.set(typed.value)"
              />
            </div>
          }
          <div class="actions">
            <button class="btn" type="button" (click)="service.settle(false)">Annuler</button>
            <button
              class="btn"
              [class.btn-danger-solid]="p.danger"
              [class.btn-primary]="!p.danger"
              type="submit"
              [disabled]="!canConfirm()"
            >
              {{ p.confirmLabel }}
            </button>
          </div>
        </form>
      }
    </dialog>
  `,
  styles: `
    dialog {
      width: min(28rem, calc(100vw - 2rem));
      padding: var(--space-5);
      border: 1px solid var(--rule);
      border-radius: var(--radius);
      background: var(--surface);
      color: var(--ink);
      box-shadow: 0 12px 32px -8px rgb(0 0 0 / 0.35);
    }
    dialog::backdrop {
      background: rgb(8 12 18 / 0.55);
    }
    h2 {
      margin-bottom: var(--space-3);
    }
    p {
      margin: 0 0 var(--space-4);
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: var(--space-3);
    }
  `,
})
export class ConfirmDialog {
  protected readonly service = inject(ConfirmService);
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  protected readonly typedValue = signal('');

  protected readonly canConfirm = computed(() => {
    const expected = this.service.pending()?.typeToConfirm;
    return !expected || this.typedValue().trim() === expected;
  });

  constructor() {
    effect(() => {
      const el = this.dialog().nativeElement;
      if (this.service.pending()) {
        this.typedValue.set('');
        if (!el.open) el.showModal();
      } else if (el.open) {
        el.close();
      }
    });
  }

  protected confirm(): void {
    if (this.canConfirm()) this.service.settle(true);
  }

  protected onCancel(): void {
    this.service.settle(false);
  }

  protected onClose(): void {
    if (this.service.pending()) this.service.settle(false);
  }
}

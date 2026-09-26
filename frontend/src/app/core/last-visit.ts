import { Injectable } from '@angular/core';

const LAST_VISIT_KEY = 'veille:derniere-visite';

/**
 * Date de la visite précédente, lue une seule fois par chargement de l'application.
 * Écrite dès la lecture : revenir sur le fil depuis une autre page ne doit pas effacer
 * les marqueurs « nouveau » de la visite en cours.
 *
 * Simple confort propre à ce navigateur : le stockage peut être indisponible (navigation
 * privée, stockage bloqué) sans que le fil en dépende.
 */
@Injectable({ providedIn: 'root' })
export class LastVisit {
  readonly previous: number | null = LastVisit.read();

  constructor() {
    try {
      localStorage.setItem(LAST_VISIT_KEY, String(Date.now()));
    } catch {
      // Stockage indisponible : le marquage « nouveau » est simplement absent.
    }
  }

  isNew(fetchedAt: string): boolean {
    return this.previous !== null && new Date(fetchedAt).getTime() > this.previous;
  }

  private static read(): number | null {
    try {
      const value = Number(localStorage.getItem(LAST_VISIT_KEY));
      return Number.isFinite(value) && value > 0 ? value : null;
    } catch {
      return null;
    }
  }
}

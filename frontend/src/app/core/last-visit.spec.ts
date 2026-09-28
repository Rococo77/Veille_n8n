import { TestBed } from '@angular/core/testing';

import { LastVisit } from './last-visit';

describe('LastVisit', () => {
  beforeEach(() => localStorage.clear());

  // La date est lue une fois par chargement : revenir sur le fil depuis une autre page
  // (nouvelle instance du composant) ne doit pas effacer les marqueurs « Nouveau ».
  it('garde la visite précédente pour toute la session, même après réécriture du stockage', () => {
    const before = Date.now() - 60_000;
    localStorage.setItem('veille:derniere-visite', String(before));

    const lastVisit = TestBed.inject(LastVisit);
    const recent = new Date(before + 30_000).toISOString();

    expect(Number(localStorage.getItem('veille:derniere-visite'))).toBeGreaterThan(before);
    expect(lastVisit.isNew(recent)).toBe(true);
    // Même service (root) au retour sur le fil : toujours « nouveau ».
    expect(TestBed.inject(LastVisit).isNew(recent)).toBe(true);
  });

  it('ne marque rien à la toute première visite', () => {
    expect(TestBed.inject(LastVisit).isNew(new Date().toISOString())).toBe(false);
  });
});

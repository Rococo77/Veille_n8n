import { Routes } from '@angular/router';

import { guestOnly, requireRole } from './core/guards';

export const routes: Routes = [
  {
    path: 'connexion',
    canMatch: [guestOnly],
    title: 'Connexion — Veille',
    loadComponent: () => import('./features/auth/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'connexion/code',
    title: 'Vérification — Veille',
    loadComponent: () => import('./features/auth/mfa.page').then((m) => m.MfaPage),
  },
  {
    path: '',
    canMatch: [requireRole('viewer')],
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        title: 'Fil — Veille',
        loadComponent: () => import('./features/feed/feed.page').then((m) => m.FeedPage),
      },
      {
        path: 'groupes',
        title: 'Groupes — Veille',
        loadComponent: () => import('./features/groups/groups.page').then((m) => m.GroupsPage),
      },
      {
        path: 'groupes/:id',
        title: 'Groupe — Veille',
        loadComponent: () =>
          import('./features/groups/group-detail.page').then((m) => m.GroupDetailPage),
      },
      {
        path: 'themes',
        title: 'Thèmes — Veille',
        canMatch: [requireRole('editor')],
        loadComponent: () => import('./features/themes/themes.page').then((m) => m.ThemesPage),
      },
      {
        path: 'compte',
        title: 'Mon compte — Veille',
        loadComponent: () => import('./features/account/account.page').then((m) => m.AccountPage),
      },
      {
        path: 'admin/utilisateurs',
        title: 'Utilisateurs — Veille',
        canMatch: [requireRole('admin')],
        loadComponent: () => import('./features/admin/users.page').then((m) => m.UsersPage),
      },
      {
        path: 'admin/journal',
        title: 'Journal — Veille',
        canMatch: [requireRole('admin')],
        loadComponent: () => import('./features/admin/audit.page').then((m) => m.AuditPage),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];

export type Role = 'viewer' | 'editor' | 'admin';

export type VeilleType =
  'technologique' | 'concurrentielle' | 'reglementaire' | 'securite' | 'marche' | 'autre';

export const VEILLE_TYPES: readonly { value: VeilleType; label: string }[] = [
  { value: 'technologique', label: 'Technologique' },
  { value: 'concurrentielle', label: 'Concurrentielle' },
  { value: 'reglementaire', label: 'Réglementaire' },
  { value: 'securite', label: 'Sécurité' },
  { value: 'marche', label: 'Marché' },
  { value: 'autre', label: 'Autre' },
];

export function veilleTypeLabel(value: VeilleType): string {
  return VEILLE_TYPES.find((t) => t.value === value)?.label ?? value;
}

export interface Me {
  id: string;
  email: string;
  role: Role;
}

export interface Theme {
  id: string;
  name: string;
  color: string;
}

export interface Source {
  id: string;
  group_id: string;
  name: string;
  url: string;
  enabled: boolean;
  last_fetch_at: string | null;
  last_status: 'ok' | 'error' | null;
  last_error: string | null;
  consecutive_failures: number;
}

export interface Group {
  id: string;
  name: string;
  description: string;
  veille_type: VeilleType;
  theme: Theme;
  enabled: boolean;
  source_count: number;
  failing_source_count: number;
  created_at: string;
  updated_at: string;
}

export interface GroupDetail extends Group {
  sources: Source[];
}

export interface GroupInput {
  name: string;
  description: string;
  veille_type: VeilleType;
  theme_id: string;
  enabled: boolean;
}

export interface Article {
  id: number;
  link: string;
  title: string;
  snippet: string;
  published_at: string;
  source: { id: string; name: string };
  group: { id: string; name: string; veille_type: VeilleType };
  theme: Theme;
}

export interface ArticlePage {
  items: Article[];
  next_cursor: string | null;
}

export interface ArticleFilters {
  veille_type?: VeilleType;
  theme_id?: string;
  group_id?: string;
  q?: string;
}

export interface User {
  id: string;
  email: string;
  role: Role;
  is_active: boolean;
  totp_confirmed: boolean;
  locked_until: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  at: string;
  actor_kind: 'user' | 'service' | 'anonymous';
  actor_user_id: string | null;
  action: string;
  target: string | null;
  ip: string | null;
}

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthStore } from '../../core/auth.store';
import { CatalogApi } from '../../core/api';
import { FeedStore } from '../../core/feed.store';
import {
  Article,
  ArticleFilters,
  Group,
  Theme,
  VEILLE_TYPES,
  VeilleType,
  veilleTypeLabel,
} from '../../core/models';
import { valueOr } from '../../core/resource';

interface DaySection {
  key: string;
  label: string;
  /** Date complète à côté de « Aujourd'hui » / « Hier ». */
  detail: string | null;
  articles: Article[];
}

/** Pourquoi le fil est vide : chaque cas appelle une action différente. */
type EmptyReason = 'filtered' | 'no-theme' | 'no-group' | 'no-source' | 'awaiting-fetch';

const TYPE_VALUES = new Set<string>(VEILLE_TYPES.map((t) => t.value));
const MIN_QUERY = 2;
const dayFormat = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
});
const shortDate = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' });
const timeFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

const LAST_VISIT_KEY = 'veille:derniere-visite';

// Simple confort d'affichage propre à ce navigateur : le stockage peut être indisponible
// (navigation privée, stockage bloqué) sans que le fil en dépende.
function readLastVisit(): number | null {
  try {
    const value = Number(localStorage.getItem(LAST_VISIT_KEY));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

function writeLastVisit(value: number): void {
  try {
    localStorage.setItem(LAST_VISIT_KEY, String(value));
  } catch {
    // Stockage indisponible : le marquage « nouveau » est simplement absent.
  }
}

@Component({
  selector: 'app-feed-page',
  imports: [RouterLink, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feed.page.html',
  styleUrl: './feed.page.css',
})
export class FeedPage {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogApi);
  protected readonly auth = inject(AuthStore);
  protected readonly feed = inject(FeedStore);

  protected readonly types = VEILLE_TYPES;
  protected readonly minQuery = MIN_QUERY;
  protected readonly searchForm = new FormGroup({
    q: new FormControl('', { nonNullable: true }),
  });
  protected readonly searchTooShort = signal(false);

  private readonly groupsRes = httpResource<Group[]>(() => {
    this.catalog.version();
    return '/api/groups';
  });
  private readonly themesRes = httpResource<Theme[]>(() => {
    this.catalog.version();
    return '/api/themes';
  });
  protected readonly groups = computed(() => valueOr(this.groupsRes, undefined) ?? []);
  protected readonly themes = computed(() => valueOr(this.themesRes, undefined) ?? []);
  private readonly catalogReady = computed(
    () => this.groupsRes.hasValue() && this.themesRes.hasValue(),
  );

  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });

  protected readonly filters = computed<ArticleFilters>(() => {
    const p = this.params();
    const type = p.get('type');
    const q = p.get('q')?.trim() ?? '';
    return {
      veille_type: type && TYPE_VALUES.has(type) ? (type as VeilleType) : undefined,
      theme_id: p.get('theme') ?? undefined,
      group_id: p.get('group') ?? undefined,
      source_id: p.get('source') ?? undefined,
      q: q.length >= MIN_QUERY ? q.slice(0, 100) : undefined,
    };
  });

  protected readonly hasFilters = computed(() =>
    Object.values(this.filters()).some((value) => value !== undefined),
  );

  /** Le nom de la source filtrée n'est connu que par les articles affichés. */
  private readonly sourceName = computed(() => {
    const id = this.filters().source_id;
    return id ? this.feed.items().find((a) => a.source.id === id)?.source.name : undefined;
  });

  /** Tous les filtres actifs, dans l'ordre du plus large au plus précis. */
  protected readonly activeFilters = computed(() => {
    const f = this.filters();
    const parts: string[] = [];
    if (f.veille_type) parts.push(`Veille ${veilleTypeLabel(f.veille_type).toLowerCase()}`);
    if (f.theme_id) {
      parts.push(`Thème ${this.themes().find((t) => t.id === f.theme_id)?.name ?? '…'}`);
    }
    if (f.group_id) {
      parts.push(`Groupe ${this.groups().find((g) => g.id === f.group_id)?.name ?? '…'}`);
    }
    if (f.source_id) parts.push(`Source ${this.sourceName() ?? '…'}`);
    if (f.q) parts.push(`« ${f.q} »`);
    return parts;
  });

  protected readonly heading = computed(() => {
    const [first] = this.activeFilters();
    return first ?? 'Tout le fil';
  });

  protected readonly emptyReason = computed<EmptyReason>(() => {
    if (this.hasFilters()) return 'filtered';
    if (this.themes().length === 0) return 'no-theme';
    const groups = this.groups();
    if (groups.length === 0) return 'no-group';
    if (groups.every((g) => g.source_count === 0)) return 'no-source';
    return 'awaiting-fetch';
  });

  /** Premier groupe sans source : destination directe de l'étape « ajouter une source ». */
  protected readonly firstEmptyGroup = computed(() =>
    this.groups().find((g) => g.source_count === 0),
  );

  protected readonly showEmpty = computed(
    () =>
      !this.feed.loading() &&
      !this.feed.error() &&
      this.feed.items().length === 0 &&
      (this.hasFilters() || this.catalogReady()),
  );

  protected readonly sections = computed<DaySection[]>(() => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const sections: DaySection[] = [];
    for (const article of this.feed.items()) {
      const date = new Date(article.published_at);
      const key = dayKey(date);
      let section = sections.at(-1);
      if (!section || section.key !== key) {
        const relative =
          key === dayKey(today) ? "Aujourd'hui" : key === dayKey(yesterday) ? 'Hier' : null;
        section = {
          key,
          label: relative ?? dayFormat.format(date),
          detail: relative ? shortDate.format(date) : null,
          articles: [],
        };
        sections.push(section);
      }
      section.articles.push(article);
    }
    return sections;
  });

  /** Desks : les six types de veille, avec le nombre de groupes rangés dessous. */
  protected readonly desks = computed(() =>
    VEILLE_TYPES.map((t) => ({
      ...t,
      groups: this.groups().filter((g) => g.veille_type === t.value).length,
    })),
  );

  /** Filtres secondaires (thème, groupe, source, recherche) : repliés tant qu'ils sont vides. */
  protected readonly refineOpen = signal(false);
  protected readonly refineCount = computed(() => {
    const f = this.filters();
    return [f.theme_id, f.group_id, f.source_id, f.q].filter(Boolean).length;
  });

  /** Date de la visite précédente : tout ce qui est paru depuis est marqué « nouveau ». */
  protected readonly lastVisit = readLastVisit();

  protected isNew(article: Article): boolean {
    return this.lastVisit !== null && new Date(article.published_at).getTime() > this.lastVisit;
  }

  constructor() {
    writeLastVisit(Date.now());
    // Arrivée par un lien filtré (thème, groupe, source, recherche) : montrer ces filtres.
    if (this.refineCount() > 0) this.refineOpen.set(true);
    effect(() => {
      const filters = this.filters();
      untracked(() => {
        this.searchForm.controls.q.setValue(filters.q ?? '', { emitEvent: false });
        this.searchTooShort.set(false);
        void this.feed.reset(filters);
      });
    });
  }

  protected time(iso: string): string {
    return timeFormat.format(new Date(iso));
  }

  protected typeLabel(value: VeilleType): string {
    return veilleTypeLabel(value);
  }

  protected setFilter(key: 'type' | 'theme' | 'group' | 'source', value: string): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { [key]: value || null },
      queryParamsHandling: 'merge',
    });
  }

  protected submitSearch(): void {
    const q = this.searchForm.controls.q.value.trim();
    if (q.length > 0 && q.length < MIN_QUERY) {
      this.searchTooShort.set(true);
      return;
    }
    this.searchTooShort.set(false);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { q: q || null },
      queryParamsHandling: 'merge',
    });
  }

  protected clearFilters(): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: {} });
  }
}

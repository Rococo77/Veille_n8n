import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

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
  articles: Article[];
}

const TYPE_VALUES = new Set<string>(VEILLE_TYPES.map((t) => t.value));
const dayFormat = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
});
const timeFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
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
  protected readonly feed = inject(FeedStore);

  protected readonly types = VEILLE_TYPES;
  protected readonly searchForm = new FormGroup({
    q: new FormControl('', { nonNullable: true }),
  });

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

  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });

  protected readonly filters = computed<ArticleFilters>(() => {
    const p = this.params();
    const type = p.get('type');
    const q = p.get('q')?.trim() ?? '';
    return {
      veille_type: type && TYPE_VALUES.has(type) ? (type as VeilleType) : undefined,
      theme_id: p.get('theme') ?? undefined,
      group_id: p.get('group') ?? undefined,
      q: q.length >= 2 ? q.slice(0, 100) : undefined,
    };
  });

  protected readonly heading = computed(() => {
    const f = this.filters();
    if (f.group_id) return this.groups().find((g) => g.id === f.group_id)?.name ?? 'Groupe';
    if (f.theme_id) return this.themes().find((t) => t.id === f.theme_id)?.name ?? 'Thème';
    if (f.veille_type) return `Veille ${veilleTypeLabel(f.veille_type).toLowerCase()}`;
    return 'Tout le fil';
  });

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
        const label =
          key === dayKey(today)
            ? "Aujourd'hui"
            : key === dayKey(yesterday)
              ? 'Hier'
              : dayFormat.format(date);
        section = { key, label, articles: [] };
        sections.push(section);
      }
      section.articles.push(article);
    }
    return sections;
  });

  constructor() {
    effect(() => {
      const filters = this.filters();
      untracked(() => {
        this.searchForm.controls.q.setValue(filters.q ?? '', { emitEvent: false });
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

  protected setFilter(key: 'type' | 'theme' | 'group', value: string): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { [key]: value || null },
      queryParamsHandling: 'merge',
    });
  }

  protected submitSearch(): void {
    const q = this.searchForm.controls.q.value.trim();
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { q: q.length >= 2 ? q : null },
      queryParamsHandling: 'merge',
    });
  }

  protected clearFilters(): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: {} });
  }
}

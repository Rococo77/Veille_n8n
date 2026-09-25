import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { Article, ArticleFilters, ArticlePage } from './models';
import { problemMessage } from './problem';

const PAGE_SIZE = 30;

/** Fil d'articles paginé par curseur (append), rechargé à chaque changement de filtres. */
@Injectable({ providedIn: 'root' })
export class FeedStore {
  private readonly http = inject(HttpClient);

  private readonly _items = signal<Article[]>([]);
  private readonly _cursor = signal<string | null>(null);
  private readonly _loading = signal(false);
  private readonly _error = signal<string | null>(null);
  // Jeton de génération : une réponse arrivée après un changement de filtre est ignorée.
  private generation = 0;
  private filters: ArticleFilters = {};

  readonly items = this._items.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly hasMore = computed(() => this._cursor() !== null);

  async reset(filters: ArticleFilters): Promise<void> {
    this.filters = filters;
    this._items.set([]);
    this._cursor.set(null);
    await this.fetch(null);
  }

  async loadMore(): Promise<void> {
    const cursor = this._cursor();
    if (cursor && !this._loading()) await this.fetch(cursor);
  }

  private async fetch(cursor: string | null): Promise<void> {
    const generation = ++this.generation;
    this._loading.set(true);
    this._error.set(null);
    let params = new HttpParams().set('limit', PAGE_SIZE);
    for (const [key, value] of Object.entries(this.filters)) {
      if (value) params = params.set(key, value);
    }
    if (cursor) params = params.set('cursor', cursor);
    try {
      const page = await firstValueFrom(this.http.get<ArticlePage>('/api/articles', { params }));
      if (generation !== this.generation) return;
      this._items.update((items) => (cursor ? [...items, ...page.items] : page.items));
      this._cursor.set(page.next_cursor);
    } catch (error) {
      if (generation === this.generation) this._error.set(problemMessage(error));
    } finally {
      if (generation === this.generation) this._loading.set(false);
    }
  }
}

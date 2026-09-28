import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { FeedStore } from './feed.store';
import { Article, ArticlePage } from './models';

function page(title: string): ArticlePage {
  return {
    items: [{ id: 1, title } as Article],
    next_cursor: null,
  };
}

describe('FeedStore', () => {
  // Deux changements de filtre rapprochés : la réponse du premier, arrivée en retard,
  // ne doit pas écraser le fil du second.
  it('ignore une réponse arrivée après un changement de filtre', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const store = TestBed.inject(FeedStore);
    const http = TestBed.inject(HttpTestingController);

    const first = store.reset({ veille_type: 'securite' });
    const second = store.reset({ veille_type: 'marche' });
    const [stale, fresh] = http.match((req) => req.url === '/api/articles');

    fresh!.flush(page('marché'));
    await second;
    stale!.flush(page('sécurité, en retard'));
    await first;

    expect(store.items().map((a) => a.title)).toEqual(['marché']);
    expect(store.loading()).toBe(false);
    http.verify();
  });
});

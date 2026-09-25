import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { GroupDetail, GroupInput, Source, Theme, User, Role } from './models';

/** Mutations uniquement : les lectures passent par httpResource dans les pages. */
@Injectable({ providedIn: 'root' })
export class CatalogApi {
  private readonly http = inject(HttpClient);
  private readonly _version = signal(0);
  /** Lu par les httpResource du catalogue : toute mutation les fait recharger. */
  readonly version = this._version.asReadonly();

  private async mutate<T>(request: Promise<T>): Promise<T> {
    const result = await request;
    this._version.update((v) => v + 1);
    return result;
  }

  createTheme(input: { name: string; color: string }): Promise<Theme> {
    return this.mutate(firstValueFrom(this.http.post<Theme>('/api/themes', input)));
  }

  updateTheme(id: string, input: Partial<{ name: string; color: string }>): Promise<Theme> {
    return this.mutate(
      firstValueFrom(this.http.patch<Theme>(`/api/themes/${encodeURIComponent(id)}`, input)),
    );
  }

  deleteTheme(id: string): Promise<void> {
    return this.mutate(
      firstValueFrom(this.http.delete<void>(`/api/themes/${encodeURIComponent(id)}`)),
    );
  }

  createGroup(input: GroupInput): Promise<GroupDetail> {
    return this.mutate(firstValueFrom(this.http.post<GroupDetail>('/api/groups', input)));
  }

  updateGroup(id: string, input: Partial<GroupInput>): Promise<GroupDetail> {
    return this.mutate(
      firstValueFrom(this.http.patch<GroupDetail>(`/api/groups/${encodeURIComponent(id)}`, input)),
    );
  }

  deleteGroup(id: string): Promise<void> {
    return this.mutate(
      firstValueFrom(this.http.delete<void>(`/api/groups/${encodeURIComponent(id)}`)),
    );
  }

  createSource(groupId: string, input: { name: string; url: string }): Promise<Source> {
    return this.mutate(
      firstValueFrom(
        this.http.post<Source>(`/api/groups/${encodeURIComponent(groupId)}/sources`, input),
      ),
    );
  }

  updateSource(
    id: string,
    input: Partial<{ name: string; url: string; enabled: boolean }>,
  ): Promise<Source> {
    return this.mutate(
      firstValueFrom(this.http.patch<Source>(`/api/sources/${encodeURIComponent(id)}`, input)),
    );
  }

  deleteSource(id: string): Promise<void> {
    return this.mutate(
      firstValueFrom(this.http.delete<void>(`/api/sources/${encodeURIComponent(id)}`)),
    );
  }
}

@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);

  createUser(input: { email: string; password: string; role: Role }): Promise<User> {
    return firstValueFrom(this.http.post<User>('/api/users', input));
  }

  updateUser(id: string, input: Partial<{ role: Role; is_active: boolean }>): Promise<User> {
    return firstValueFrom(this.http.patch<User>(`/api/users/${encodeURIComponent(id)}`, input));
  }

  resetMfa(id: string): Promise<User> {
    return firstValueFrom(
      this.http.post<User>(`/api/users/${encodeURIComponent(id)}/reset-mfa`, null),
    );
  }

  unlock(id: string): Promise<User> {
    return firstValueFrom(
      this.http.post<User>(`/api/users/${encodeURIComponent(id)}/unlock`, null),
    );
  }
}

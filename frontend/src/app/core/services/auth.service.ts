import { Injectable, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { isPlatformBrowser } from '@angular/common';
import { Observable, tap, catchError, throwError } from 'rxjs';
import {
  LoginRequest, LoginResponse, TokenResponse, MfaVerifyRequest,
  RefreshRequest, MfaSetupResponse, TokenPayload, Role, MessageResponse,
} from '../models';

const ACCESS_KEY  = 'cdtool_access';
const REFRESH_KEY = 'cdtool_refresh';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http       = inject(HttpClient);
  private readonly router     = inject(Router);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly isBrowser  = isPlatformBrowser(this.platformId);

  // ── Signals ─────────────────────────────────────────────────────────────────
  private readonly _accessToken  = signal<string | null>(this._loadToken(ACCESS_KEY));
  private readonly _refreshToken = signal<string | null>(this._loadToken(REFRESH_KEY));

  readonly accessToken   = this._accessToken.asReadonly();
  readonly refreshToken  = this._refreshToken.asReadonly();
  readonly isLoggedIn    = computed(() => !!this._accessToken());
  readonly currentPayload = computed<TokenPayload | null>(() => {
    const t = this._accessToken();
    return t ? this._decode(t) : null;
  });
  readonly currentRole = computed<Role | null>(() => this.currentPayload()?.role ?? null);
  readonly tenantId    = computed<string | null>(() => this.currentPayload()?.tenant_id ?? null);

  // ── Public API ───────────────────────────────────────────────────────────────
  login(body: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/api/v1/auth/login', body).pipe(
      tap(res => {
        if ('access_token' in res) this._storeTokens(res);
      }),
    );
  }

  mfaVerify(body: MfaVerifyRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/api/v1/auth/mfa/verify', body).pipe(
      tap(res => this._storeTokens(res)),
    );
  }

  refreshTokens(): Observable<TokenResponse> {
    const rt = this._refreshToken();
    if (!rt) return throwError(() => new Error('No refresh token'));
    return this.http
      .post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: rt } satisfies RefreshRequest)
      .pipe(tap(res => this._storeTokens(res)));
  }

  setupMfa(): Observable<MfaSetupResponse> {
    return this.http.post<MfaSetupResponse>('/api/v1/auth/mfa/setup', {});
  }

  confirmMfa(totp_code: string): Observable<MessageResponse> {
    const body: MfaVerifyRequest = { temp_token: this._accessToken() ?? '', totp_code };
    return this.http.post<MessageResponse>('/api/v1/auth/mfa/confirm', body);
  }

  logout(): void {
    this._clearTokens();
    this.router.navigate(['/login']);
  }

  hasRole(...roles: Role[]): boolean {
    const r = this.currentRole();
    if (r === 'super_admin') return true;
    return r !== null && roles.includes(r);
  }

  // ── Internal ─────────────────────────────────────────────────────────────────
  private _storeTokens(res: TokenResponse): void {
    this._accessToken.set(res.access_token);
    this._refreshToken.set(res.refresh_token);
    if (this.isBrowser) {
      localStorage.setItem(ACCESS_KEY,  res.access_token);
      localStorage.setItem(REFRESH_KEY, res.refresh_token);
    }
  }

  private _clearTokens(): void {
    this._accessToken.set(null);
    this._refreshToken.set(null);
    if (this.isBrowser) {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    }
  }

  private _loadToken(key: string): string | null {
    if (isPlatformBrowser(this.platformId)) return localStorage.getItem(key);
    return null;
  }

  private _decode(token: string): TokenPayload | null {
    try {
      const payload = token.split('.')[1];
      return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    } catch {
      return null;
    }
  }
}

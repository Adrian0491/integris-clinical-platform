import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { throwError, catchError, switchMap, BehaviorSubject, filter, take } from 'rxjs';
import { AuthService } from '../services/auth.service';

let isRefreshing = false;
const refreshDone$ = new BehaviorSubject<boolean>(false);

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  // Skip auth header for login / refresh endpoints
  if (_isAuthEndpoint(req)) return next(req);

  const token = auth.accessToken();
  const authedReq = token ? _addToken(req, token) : req;

  return next(authedReq).pipe(
    catchError(err => {
      if (err instanceof HttpErrorResponse && err.status === 401 && !_isAuthEndpoint(req)) {
        return _handle401(req, next, auth);
      }
      return throwError(() => err);
    }),
  );
};

function _addToken(req: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
  return req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}

function _isAuthEndpoint(req: HttpRequest<unknown>): boolean {
  return req.url.includes('/auth/login') ||
         req.url.includes('/auth/refresh') ||
         req.url.includes('/auth/mfa/verify');
}

function _handle401(
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
  auth: AuthService,
) {
  if (!isRefreshing) {
    isRefreshing = true;
    refreshDone$.next(false);

    return auth.refreshTokens().pipe(
      switchMap(tokens => {
        isRefreshing = false;
        refreshDone$.next(true);
        return next(_addToken(req, tokens.access_token));
      }),
      catchError(err => {
        isRefreshing = false;
        auth.logout();
        return throwError(() => err);
      }),
    );
  }

  // If refresh already in flight, queue the request
  return refreshDone$.pipe(
    filter(done => done),
    take(1),
    switchMap(() => {
      const t = auth.accessToken();
      return t ? next(_addToken(req, t)) : throwError(() => new Error('No token'));
    }),
  );
}

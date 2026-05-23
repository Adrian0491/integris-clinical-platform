import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { NotificationService } from '../services/notification.service';
import { AuthService } from '../services/auth.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const notify = inject(NotificationService);
  const auth   = inject(AuthService);

  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 0) {
        notify.error('Cannot reach the server. Check your connection.');
      } else if (err.status === 401 && req.url.includes('/auth/login')) {
        // Let the login component handle this
      } else if (err.status === 403) {
        notify.error('You do not have permission to perform this action.');
      } else if (err.status === 409) {
        const detail = err.error?.detail ?? 'Conflict — this record already exists.';
        notify.error(detail);
      } else if (err.status === 422) {
        notify.error('Validation error — check your input.');
      } else if (err.status >= 500) {
        notify.error('Server error. Please try again or contact support.');
      }
      return throwError(() => err);
    }),
  );
};

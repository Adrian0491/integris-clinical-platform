import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { Role } from '../models';

/** Usage: canActivate: [roleGuard('tenant_admin', 'validator')] */
export function roleGuard(...roles: Role[]): CanActivateFn {
  return () => {
    const auth   = inject(AuthService);
    const router = inject(Router);

    if (!auth.isLoggedIn()) return router.createUrlTree(['/login']);
    if (auth.hasRole(...roles)) return true;
    return router.createUrlTree(['/']);
  };
}

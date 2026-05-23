import { Component, inject, signal, computed } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  roles?: string[];
}

@Component({
  selector: 'app-shell',
  imports: [
    RouterOutlet, RouterLink, RouterLinkActive,
    MatSidenavModule, MatToolbarModule, MatListModule,
    MatIconModule, MatButtonModule, MatMenuModule, MatDividerModule,
  ],
  templateUrl: './shell.html',
  styleUrl: './shell.css',
})
export class ShellComponent {
  readonly auth   = inject(AuthService);
  private readonly bp = inject(BreakpointObserver);

  readonly isHandset = toSignal(
    this.bp.observe(Breakpoints.Handset).pipe(map(r => r.matches)),
    { initialValue: false },
  );

  readonly sidenavOpen = signal(true);

  readonly navItems: NavItem[] = [
    { label: 'Dashboard',   icon: 'dashboard',       route: '/dashboard' },
    { label: 'Studies',     icon: 'science',          route: '/studies' },
    { label: 'Datasets',    icon: 'folder_open',      route: '/datasets' },
    { label: 'Validation',  icon: 'rule',             route: '/validation' },
    { label: 'Findings',    icon: 'bug_report',       route: '/validation/findings' },
    { label: 'Reports',     icon: 'summarize',        route: '/reports' },
    { label: 'Audit Trail', icon: 'history',          route: '/audit' },
  ];

  readonly userInitials = computed(() => {
    const payload = this.auth.currentPayload();
    if (!payload) return '?';
    // Use first letter of sub (user ID) as fallback
    return payload.role.charAt(0).toUpperCase();
  });

  toggleSidenav(): void {
    this.sidenavOpen.update(v => !v);
  }

  logout(): void { this.auth.logout(); }
}

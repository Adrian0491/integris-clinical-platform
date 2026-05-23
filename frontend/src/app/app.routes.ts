import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  // Public
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login').then(m => m.LoginComponent),
  },
  {
    path: 'mfa',
    loadComponent: () =>
      import('./features/auth/mfa/mfa').then(m => m.MfaComponent),
  },

  // Authenticated shell
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/shell/shell').then(m => m.ShellComponent),
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard').then(m => m.DashboardComponent),
      },
      {
        path: 'studies',
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/studies/studies').then(m => m.StudiesComponent),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/studies/study-detail/study-detail').then(m => m.StudyDetailComponent),
          },
        ],
      },
      {
        path: 'datasets',
        loadComponent: () =>
          import('./features/datasets/datasets').then(m => m.DatasetsComponent),
      },
      {
        path: 'validation',
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/validation/jobs/jobs').then(m => m.JobsComponent),
          },
          {
            path: 'run',
            loadComponent: () =>
              import('./features/validation/validation-run/validation-run').then(m => m.ValidationRunComponent),
          },
          {
            path: 'findings',
            loadComponent: () =>
              import('./features/validation/findings/findings').then(m => m.FindingsComponent),
          },
        ],
      },
      {
        path: 'reports',
        loadComponent: () =>
          import('./features/reports/reports').then(m => m.ReportsComponent),
      },
      {
        path: 'audit',
        loadComponent: () =>
          import('./features/audit/audit').then(m => m.AuditComponent),
      },
    ],
  },

  { path: '**', redirectTo: '' },
];

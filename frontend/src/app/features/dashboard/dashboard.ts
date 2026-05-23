import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { DatePipe, NgClass } from '@angular/common';
import { StudiesService } from '../../core/services/studies.service';
import { ValidationService } from '../../core/services/validation.service';
import { Study, ValidationJob } from '../../core/models';

@Component({
  selector: 'app-dashboard',
  imports: [
    RouterLink, DatePipe, NgClass,
    MatCardModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatProgressSpinnerModule, MatDividerModule,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit {
  private readonly studiesSvc    = inject(StudiesService);
  private readonly validationSvc = inject(ValidationService);

  readonly loading  = signal(true);
  readonly studies  = signal<Study[]>([]);
  readonly recentJobs = signal<ValidationJob[]>([]);

  readonly activeStudies  = () => this.studies().filter(s => s.status === 'active').length;
  readonly archivedStudies = () => this.studies().filter(s => s.status === 'archived').length;
  readonly completedJobs  = () => this.recentJobs().filter(j => j.status === 'completed').length;
  readonly failedJobs     = () => this.recentJobs().filter(j => j.status === 'failed').length;

  ngOnInit(): void {
    this.studiesSvc.list().subscribe({
      next: studies => {
        this.studies.set(studies);
        // Load recent jobs for active studies
        this.validationSvc.listJobs().subscribe({
          next: jobs => {
            this.recentJobs.set(jobs.slice(0, 10));
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => this.loading.set(false),
    });
  }

  statusClass(status: string): string {
    return `chip-${status}`;
  }
}

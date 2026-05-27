import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DatePipe, NgClass, SlicePipe } from '@angular/common';
import { interval, Subscription } from 'rxjs';
import { ValidationService } from '../../../core/services/validation.service';
import { ValidationJob } from '../../../core/models';

@Component({
  selector: 'app-jobs',
  imports: [
    RouterLink, DatePipe, NgClass, SlicePipe,
    MatTableModule, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatChipsModule, MatTooltipModule,
  ],
  templateUrl: './jobs.html',
  styleUrl: './jobs.css',
})
export class JobsComponent implements OnInit, OnDestroy {
  private readonly svc   = inject(ValidationService);
  private readonly route = inject(ActivatedRoute);
  private poll?: Subscription;

  readonly loading = signal(true);
  readonly jobs    = signal<ValidationJob[]>([]);
  readonly columns = ['created_at', 'study_id', 'status', 'rule_profile', 'datasets', 'duration', 'actions'];

  ngOnInit(): void {
    this.load();
    // Auto-refresh every 5s while there are running/queued jobs
    this.poll = interval(5000).subscribe(() => {
      if (this.jobs().some(j => j.status === 'queued' || j.status === 'running')) {
        this.load(false);
      }
    });
  }

  ngOnDestroy(): void { this.poll?.unsubscribe(); }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    const studyId = this.route.snapshot.queryParamMap.get('study_id') ?? undefined;
    this.svc.listJobs(studyId).subscribe({
      next: j => { this.jobs.set(j); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  duration(job: ValidationJob): string {
    if (!job.started_at || !job.completed_at) return '—';
    const ms = new Date(job.completed_at).getTime() - new Date(job.started_at).getTime();
    return ms < 60000 ? `${(ms / 1000).toFixed(1)}s` : `${(ms / 60000).toFixed(1)}m`;
  }

  statusIcon(status: string): string {
    return { queued: 'schedule', running: 'sync', completed: 'check_circle', failed: 'error' }[status] ?? 'help';
  }

  statusClass(s: string): string { return `chip-${s}`; }
}

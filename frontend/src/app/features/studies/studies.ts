import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DatePipe, NgClass } from '@angular/common';
import { StudiesService } from '../../core/services/studies.service';
import { NotificationService } from '../../core/services/notification.service';
import { AuthService } from '../../core/services/auth.service';
import { Study } from '../../core/models';
import { StudyFormDialogComponent } from './study-form-dialog/study-form-dialog';

@Component({
  selector: 'app-studies',
  imports: [
    RouterLink, DatePipe, NgClass,
    MatTableModule, MatButtonModule, MatIconModule,
    MatDialogModule, MatChipsModule, MatProgressSpinnerModule, MatTooltipModule,
  ],
  templateUrl: './studies.html',
  styleUrl: './studies.css',
})
export class StudiesComponent implements OnInit {
  private readonly svc    = inject(StudiesService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);
  readonly auth           = inject(AuthService);

  readonly loading = signal(true);
  readonly studies = signal<Study[]>([]);

  readonly columns = ['study_id', 'title', 'phase', 'status', 'created_at', 'actions'];

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.svc.list().subscribe({
      next: s => { this.studies.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  openCreate(): void {
    this.dialog.open(StudyFormDialogComponent, { width: '520px' })
      .afterClosed().subscribe(created => { if (created) this.load(); });
  }

  openEdit(study: Study): void {
    this.dialog.open(StudyFormDialogComponent, { width: '520px', data: { study } })
      .afterClosed().subscribe(updated => { if (updated) this.load(); });
  }

  archive(study: Study): void {
    if (!confirm(`Archive study "${study.study_id}"? This cannot be undone easily.`)) return;
    this.svc.archive(study.id).subscribe({
      next: () => { this.notify.success('Study archived.'); this.load(); },
    });
  }

  statusClass(s: string): string { return `chip-${s}`; }
}

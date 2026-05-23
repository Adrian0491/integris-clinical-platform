import { Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatDividerModule } from '@angular/material/divider';
import { DatePipe, NgClass } from '@angular/common';
import { StudiesService } from '../../../core/services/studies.service';
import { DatasetsService } from '../../../core/services/datasets.service';
import { ValidationService } from '../../../core/services/validation.service';
import { Study, Dataset, ValidationJob } from '../../../core/models';

@Component({
  selector: 'app-study-detail',
  imports: [
    RouterLink, DatePipe, NgClass,
    MatCardModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatProgressSpinnerModule, MatTableModule, MatDividerModule,
  ],
  templateUrl: './study-detail.html',
  styleUrl: './study-detail.css',
})
export class StudyDetailComponent implements OnInit {
  private readonly studiesSvc    = inject(StudiesService);
  private readonly datasetsSvc   = inject(DatasetsService);
  private readonly validationSvc = inject(ValidationService);

  readonly id = input.required<string>();

  readonly loading  = signal(true);
  readonly study    = signal<Study | null>(null);
  readonly datasets = signal<Dataset[]>([]);
  readonly jobs     = signal<ValidationJob[]>([]);

  readonly jobColumns     = ['created_at', 'status', 'rule_profile', 'actions'];
  readonly datasetColumns = ['filename', 'domain', 'file_format', 'row_count', 'created_at'];

  ngOnInit(): void {
    this.studiesSvc.getById(this.id()).subscribe({
      next: s => {
        this.study.set(s);
        this.datasetsSvc.list(s.id).subscribe(ds => this.datasets.set(ds));
        this.validationSvc.listJobs(s.id).subscribe(jobs => this.jobs.set(jobs));
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  statusClass(s: string): string { return `chip-${s}`; }
}

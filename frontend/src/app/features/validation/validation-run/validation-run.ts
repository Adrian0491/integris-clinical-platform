import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { ValidationService } from '../../../core/services/validation.service';
import { StudiesService } from '../../../core/services/studies.service';
import { DatasetsService } from '../../../core/services/datasets.service';
import { NotificationService } from '../../../core/services/notification.service';
import { Study, Dataset } from '../../../core/models';

@Component({
  selector: 'app-validation-run',
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatFormFieldModule, MatSelectModule,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule,
    MatCheckboxModule, MatDividerModule,
  ],
  templateUrl: './validation-run.html',
  styleUrl: './validation-run.css',
})
export class ValidationRunComponent implements OnInit {
  private readonly fb            = inject(FormBuilder);
  private readonly validationSvc = inject(ValidationService);
  private readonly studiesSvc    = inject(StudiesService);
  private readonly datasetsSvc   = inject(DatasetsService);
  private readonly router        = inject(Router);
  private readonly notify        = inject(NotificationService);

  readonly studies      = signal<Study[]>([]);
  readonly datasets     = signal<Dataset[]>([]);
  readonly submitting   = signal(false);
  readonly loadingDatasets = signal(false);

  readonly selectedDatasets = signal<Set<string>>(new Set());

  readonly profiles = ['sdtm_default', 'sdtm_strict', 'sdtm_minimal'];

  readonly form = this.fb.nonNullable.group({
    study_id:     ['', Validators.required],
    rule_profile: ['sdtm_default'],
  });

  ngOnInit(): void {
    this.studiesSvc.list().subscribe(s => this.studies.set(s.filter(x => x.status === 'active')));
    this.form.controls.study_id.valueChanges.subscribe(id => {
      if (id) this.loadStudyDatasets(id);
    });
  }

  loadStudyDatasets(studyId: string): void {
    this.loadingDatasets.set(true);
    this.selectedDatasets.set(new Set());
    this.datasetsSvc.list(studyId).subscribe({
      next: ds => { this.datasets.set(ds); this.loadingDatasets.set(false); },
      error: () => this.loadingDatasets.set(false),
    });
  }

  toggleDataset(id: string): void {
    this.selectedDatasets.update(set => {
      const next = new Set(set);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  selectAll(): void {
    this.selectedDatasets.set(new Set(this.datasets().map(d => d.id)));
  }

  submit(): void {
    if (this.form.invalid || !this.selectedDatasets().size) return;
    this.submitting.set(true);
    const { study_id, rule_profile } = this.form.getRawValue();

    this.validationSvc.runValidation({
      study_id,
      dataset_ids: [...this.selectedDatasets()],
      rule_profile,
    }).subscribe({
      next: job => {
        this.submitting.set(false);
        this.notify.success(`Validation job queued (ID: ${job.id.slice(0, 8)}…)`);
        this.router.navigate(['/validation']);
      },
      error: () => this.submitting.set(false),
    });
  }
}

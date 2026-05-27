import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ReportsService } from '../../../core/services/reports.service';
import { NotificationService } from '../../../core/services/notification.service';
import { ValidationJob } from '../../../core/models';
import { SlicePipe } from '@angular/common';

export interface GenerateReportDialogData {
  jobs: ValidationJob[];
}

@Component({
  selector: 'app-generate-report-dialog',
  imports: [
    ReactiveFormsModule, SlicePipe,
    MatDialogModule, MatButtonModule,
    MatFormFieldModule, MatInputModule,
    MatSelectModule, MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>Generate Compliance Report</h2>
    <mat-dialog-content>
      <form [formGroup]="form" id="genForm" (ngSubmit)="generate()" style="display:flex;flex-direction:column;gap:16px;padding-top:8px">
        <mat-form-field appearance="outline">
          <mat-label>Validation Job</mat-label>
          <mat-select formControlName="job_id">
            @for (j of data.jobs; track j.id) {
              <mat-option [value]="j.id">{{ j.rule_profile }} — {{ j.created_at | slice:0:10 }}</mat-option>
            }
          </mat-select>
          @if (form.controls.job_id.hasError('required') && form.controls.job_id.touched) {
            <mat-error>Please select a validation job.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Report Type</mat-label>
          <mat-select formControlName="report_type">
            <mat-option value="full">Full Compliance Report</mat-option>
            <mat-option value="summary">Executive Summary</mat-option>
            <mat-option value="cdisc_findings">CDISC Findings Only</mat-option>
          </mat-select>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button [mat-dialog-close]="false" [disabled]="saving()">Cancel</button>
      <button mat-flat-button form="genForm" type="submit" [disabled]="saving() || form.invalid">
        @if (saving()) { <mat-spinner diameter="18" /> } @else { Generate }
      </button>
    </mat-dialog-actions>
  `,
})
export class GenerateReportDialogComponent {
  private readonly svc    = inject(ReportsService);
  private readonly notify = inject(NotificationService);
  private readonly ref    = inject(MatDialogRef<GenerateReportDialogComponent>);
  readonly data           = inject<GenerateReportDialogData>(MAT_DIALOG_DATA);
  private readonly fb     = inject(FormBuilder);

  readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    job_id:      ['', Validators.required],
    report_type: ['full'],
  });

  generate(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const { job_id, report_type } = this.form.getRawValue();
    this.svc.generate({ job_id, report_type }).subscribe({
      next: () => {
        this.notify.success('Report generation started');
        this.ref.close(true);
      },
      error: () => this.saving.set(false),
    });
  }
}

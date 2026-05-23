import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { NgClass } from '@angular/common';
import { ValidationService } from '../../../core/services/validation.service';
import { NotificationService } from '../../../core/services/notification.service';
import { Finding } from '../../../core/models';

export interface ResolveDialogData {
  finding: Finding;
}

@Component({
  selector: 'app-resolve-dialog',
  imports: [
    ReactiveFormsModule, NgClass,
    MatDialogModule, MatButtonModule,
    MatFormFieldModule, MatInputModule,
    MatRadioModule, MatProgressSpinnerModule,
    MatIconModule,
  ],
  templateUrl: './resolve-dialog.html',
  styles: [`
    .finding-summary { background: var(--mat-sys-surface-container-low); border-radius: 8px; padding: 12px 16px; }
    .finding-badge-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
    .sev-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; font-size: .76rem; font-weight: 600; }
    .sev-icon { font-size: 14px; width: 14px; height: 14px; }
    .rule-code { font-family: monospace; font-size: .8rem; background: var(--mat-sys-surface-container-high); padding: 2px 6px; border-radius: 4px; }
    .domain-badge { font-size: .78rem; padding: 2px 8px; border-radius: 8px; background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); }
    .finding-message { margin: 0; font-size: .9rem; color: var(--mat-sys-on-surface); }
    pre.evidence { margin: 8px 0 0; font-size: .78rem; white-space: pre-wrap; color: var(--mat-sys-on-surface-variant); }
    .radio-label { font-size: .85rem; font-weight: 500; color: var(--mat-sys-on-surface-variant); display: block; margin-bottom: 8px; }
    .status-radio-group { display: flex; flex-direction: column; gap: 4px; }
    .radio-content { display: flex; align-items: flex-start; gap: 10px; padding: 4px 0; }
    .radio-icon { font-size: 20px; width: 20px; height: 20px; margin-top: 2px; }
    .resolved-icon { color: #2e7d32; }
    .waived-icon { color: #9e9e9e; }
    .radio-desc { font-size: .8rem; color: var(--mat-sys-on-surface-variant); }
    .full-width { width: 100%; }
    mat-dialog-content { min-width: 440px; }
  `],
})
export class ResolveDialogComponent {
  private readonly svc    = inject(ValidationService);
  private readonly notify = inject(NotificationService);
  private readonly ref    = inject(MatDialogRef<ResolveDialogComponent>);
  readonly data           = inject<ResolveDialogData>(MAT_DIALOG_DATA);
  private readonly fb     = inject(FormBuilder);

  readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    status:          ['resolved' as 'resolved' | 'waived'],
    resolution_note: ['', Validators.maxLength(1000)],
  });

  get finding(): Finding { return this.data.finding; }

  sevClass(): string { return `chip-${this.finding.severity}`; }
  sevIcon(): string {
    return { CRIT: 'dangerous', HIGH: 'warning', MED: 'info', LOW: 'check_circle' }[this.finding.severity] ?? 'help';
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const { status, resolution_note } = this.form.getRawValue();
    this.svc.resolveFinding(this.finding.id, { status, resolution_note: resolution_note || undefined })
      .subscribe({
        next: () => {
          this.notify.success(`Finding marked as ${status}`);
          this.ref.close(true);
        },
        error: () => this.saving.set(false),
      });
  }
}

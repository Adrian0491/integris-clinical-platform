import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { StudiesService } from '../../../core/services/studies.service';
import { NotificationService } from '../../../core/services/notification.service';
import { Study } from '../../../core/models';

@Component({
  selector: 'app-study-form-dialog',
  styleUrls: ['./study-form-dialog.css'],
  imports: [
    ReactiveFormsModule,
    MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatProgressSpinnerModule,
  ],
  templateUrl: './study-form-dialog.html',
})
export class StudyFormDialogComponent {
  private readonly fb     = inject(FormBuilder);
  private readonly svc    = inject(StudiesService);
  private readonly notify = inject(NotificationService);
  private readonly ref    = inject(MatDialogRef<StudyFormDialogComponent>);
  readonly data: { study?: Study } = inject(MAT_DIALOG_DATA, { optional: true }) ?? {};

  readonly saving  = signal(false);
  readonly isEdit  = !!this.data?.study;
  readonly title   = this.isEdit ? 'Edit Study' : 'New Study';

  readonly form = this.fb.nonNullable.group({
    study_id:         [this.data?.study?.study_id ?? '', Validators.required],
    title:            [this.data?.study?.title ?? ''],
    phase:            [this.data?.study?.phase ?? ''],
    therapeutic_area: [this.data?.study?.therapeutic_area ?? ''],
    sponsor:          [this.data?.study?.sponsor ?? ''],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const val = this.form.getRawValue();

    const obs = this.isEdit
      ? this.svc.update(this.data.study!.id, val)
      : this.svc.create(val);

    obs.subscribe({
      next: () => {
        this.saving.set(false);
        this.notify.success(this.isEdit ? 'Study updated.' : 'Study created.');
        this.ref.close(true);
      },
      error: () => this.saving.set(false),
    });
  }
}

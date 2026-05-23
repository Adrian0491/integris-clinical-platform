import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { DatePipe } from '@angular/common';
import { AuditService } from '../../core/services/audit.service';
import { AuditLog } from '../../core/models';

@Component({
  selector: 'app-audit',
  imports: [
    ReactiveFormsModule, DatePipe,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatDatepickerModule,
    MatPaginatorModule, MatProgressSpinnerModule,
    MatTooltipModule, MatChipsModule,
  ],
  templateUrl: './audit.html',
  styleUrl: './audit.css',
})
export class AuditComponent implements OnInit {
  private readonly svc = inject(AuditService);
  private readonly fb  = inject(FormBuilder);

  readonly loading  = signal(true);
  readonly logs     = signal<AuditLog[]>([]);

  readonly pageSize  = signal(50);
  readonly pageIndex = signal(0);
  readonly offset    = computed(() => this.pageIndex() * this.pageSize());

  readonly columns = ['occurred_at', 'user_id', 'action', 'target_type', 'target_id', 'ip_address'];

  readonly knownActions = [
    'login', 'logout', 'login_failed',
    'study.create', 'study.update', 'study.delete',
    'dataset.upload',
    'validation.run',
    'finding.resolve',
    'report.generate', 'report.sign',
  ];

  readonly filters = this.fb.nonNullable.group({
    action:    [''],
    user_id:   [''],
    from_date: [null as Date | null],
    to_date:   [null as Date | null],
  });

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    const f = this.filters.getRawValue();
    this.svc.list({
      action:    f.action   || undefined,
      user_id:   f.user_id  || undefined,
      from_date: f.from_date ? this._toIso(f.from_date) : undefined,
      to_date:   f.to_date   ? this._toIso(f.to_date)   : undefined,
      offset:    this.offset(),
      limit:     this.pageSize(),
    }).subscribe({
      next: logs => { this.logs.set(logs); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  applyFilters(): void {
    this.pageIndex.set(0);
    this.load();
  }

  clearFilters(): void {
    this.filters.reset();
    this.pageIndex.set(0);
    this.load();
  }

  onPage(e: PageEvent): void {
    this.pageIndex.set(e.pageIndex);
    this.pageSize.set(e.pageSize);
    this.load();
  }

  actionColor(action: string): string {
    if (action.includes('delete') || action.includes('failed')) return 'warn-action';
    if (action.includes('sign') || action.includes('resolve')) return 'success-action';
    return 'default-action';
  }

  private _toIso(d: Date): string {
    return d.toISOString().split('T')[0];
  }
}

import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import {
  ValidationJob, ValidationRunRequest, ValidationSummary,
  Finding, FindingFilters, FindingResolveRequest,
} from '../models';

@Injectable({ providedIn: 'root' })
export class ValidationService extends ApiService {
  // ── Jobs ─────────────────────────────────────────────────────────────────────
  runValidation(body: ValidationRunRequest): Observable<ValidationJob> {
    return this.post<ValidationJob>('/validation/run', body);
  }

  listJobs(studyId?: string): Observable<ValidationJob[]> {
    return this.get<ValidationJob[]>('/validation/jobs', { study_id: studyId });
  }

  getJob(id: string): Observable<ValidationJob> {
    return this.get<ValidationJob>(`/validation/jobs/${id}`);
  }

  getSummary(jobId: string): Observable<ValidationSummary> {
    return this.get<ValidationSummary>(`/validation/summary/${jobId}`);
  }

  // ── Findings ──────────────────────────────────────────────────────────────────
  listFindings(filters: FindingFilters = {}): Observable<Finding[]> {
    return this.get<Finding[]>('/validation/findings', filters as Record<string, string | number | boolean | null | undefined>);
  }

  getFinding(id: string): Observable<Finding> {
    return this.get<Finding>(`/validation/findings/${id}`);
  }

  resolveFinding(id: string, body: FindingResolveRequest): Observable<Finding> {
    return this.patch<Finding>(`/validation/findings/${id}`, body);
  }
}

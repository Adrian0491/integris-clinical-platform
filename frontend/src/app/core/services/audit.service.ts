import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { AuditLog } from '../models';

export interface AuditFilters {
  action?: string;
  user_id?: string;
  from_date?: string;
  to_date?: string;
  offset?: number;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class AuditService extends ApiService {
  list(filters: AuditFilters = {}): Observable<AuditLog[]> {
    return this.get<AuditLog[]>('/audit', filters as Record<string, string | number | boolean | null | undefined>);
  }
}

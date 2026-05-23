import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpEvent, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Dataset } from '../models';

@Injectable({ providedIn: 'root' })
export class DatasetsService extends ApiService {
  list(studyId: string): Observable<Dataset[]> {
    return this.get<Dataset[]>('/datasets', { study_id: studyId });
  }

  getById(id: string): Observable<Dataset> {
    return this.get<Dataset>(`/datasets/${id}`);
  }

  /** Upload with progress reporting via HttpEvents */
  upload(
    studyId: string,
    domain: string,
    file: File,
  ): Observable<HttpEvent<Dataset>> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('study_id', studyId);
    form.append('domain', domain);

    const req = new HttpRequest('POST', '/api/v1/datasets/upload', form, {
      reportProgress: true,
    });
    return this.http.request<Dataset>(req);
  }
}

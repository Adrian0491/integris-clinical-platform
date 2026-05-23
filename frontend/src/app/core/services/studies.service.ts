import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Study, StudyCreate, StudyUpdate } from '../models';

@Injectable({ providedIn: 'root' })
export class StudiesService extends ApiService {
  list(): Observable<Study[]> {
    return this.get<Study[]>('/studies');
  }

  getById(id: string): Observable<Study> {
    return this.get<Study>(`/studies/${id}`);
  }

  create(body: StudyCreate): Observable<Study> {
    return this.post<Study>('/studies', body);
  }

  update(id: string, body: StudyUpdate): Observable<Study> {
    return this.put<Study>(`/studies/${id}`, body);
  }

  archive(id: string): Observable<void> {
    return this.delete<void>(`/studies/${id}`);
  }
}

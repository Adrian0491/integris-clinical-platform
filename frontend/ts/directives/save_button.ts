import { Component, DestroyRef, inject } from '@angular/core';
import { Subject, of } from 'rxjs';
import { exhaustMap, finalize, tap, delay } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

@Component({
    selector: 'app-other',
    templateUrl: './other.component.html',
})

export class OtherComponent {
    private destroyRef = inject(DestroyRef);
    private saveClick$ = new Subject<void>();

    //variables you want to store
    siteId = '';
    studyName = '';
    notes = '';

    isSaving = false;

    constructor() {
        this.saveClick$
            .pipe(
                tap(() => (this.isSaving = true)),
                exhaustMap(() => {
                    // build payload from variables
                    const payload = {
                        siteId: this.siteId,
                        studyName: this.studyName,
                        notes: this.notes,
                    };

                    console.log('Saving payload:', payload);

                    // replace this with HttpClient call:
                    // return this.http.post('/api/save', payload)
                    return of(payload).pipe(delay(800));
                }),
                finalize(() => (this.isSaving = false)),
                takeUntilDestroyed(this.destroyRef)
            )
            .subscribe();
    }

    triggerSave() {
        this.saveClick$.next();
    }

    ngOnInit(){
        this.siteId = 'site123';
    }
}
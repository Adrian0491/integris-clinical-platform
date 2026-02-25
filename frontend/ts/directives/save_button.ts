import { Component, OnInit, OnDestroy, Input, ViewChild, ElementRef } from '@angular/core';
import { fromEvent, Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-save-button',
  standalone: true,
  imports: [
    MatButtonModule,
    MatIconModule,],
  templateUrl: './save-button.ng.html',
  styleUrls: ['./save-button.css']
})
  
export class SaveButtonComponent implements OnInit, OnDestroy {

  /** Prefix for the downloaded file (date will be added automatically) */
  /** @Input() filenamePrefix: string = 'clinical-compliance-report'; */
  @Input() 

  /** Optional: pass your own clean HTML string if you don't want the whole page */
  @Input() customHTML?: string;

  @ViewChild('saveBtn') private saveBtnRef!: ElementRef<HTMLButtonElement>;

  private destroy$ = new Subject<void>();

  ngOnInit(): void {
    if (!this.saveBtnRef?.nativeElement) {
      console.warn('SaveButtonComponent: button ref not found');
      return;
    }

    // RxJS Observable on click → save when pressed
    fromEvent(this.saveBtnRef.nativeElement, 'click')
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        console.log('Save clicked → generating HTML report...');
        this.performSave();
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    console.log('SaveButtonComponent destroyed – observable cleaned up');
  }

  private performSave(): void {
    // Use custom HTML if provided, otherwise full current page (Option 1)
    let content = this.customHTML || document.documentElement.outerHTML;

    const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const fullFilename = `${this.filenamePrefix}-${timestamp}.html`;

    const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = fullFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    console.log(`Report saved → ${fullFilename}`);
  }
}

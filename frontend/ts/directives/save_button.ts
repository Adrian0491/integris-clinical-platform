import { Component, OnInit, OnDestroy, ViewChild, ElementRef, Input } from "@angular/core";
import { fromEvent, Subject } from "rxjs";
import { takeUntil } from "rxjs/operators";

@Component({
  selector: "app-save-button",
  templateUrl: "./save_button.ng.html",
  styleUrls: ["./save_button.css"]
})

export class SaveButton implements OnInit, OnDestroy {

    @Input() reportData: any; // Assuming this is the data to be saved
    @ViewChild('saveBtn', { static: true }) saveBtn!: ElementRef<HTMLButtonElement>;
    private destroy$ = new Subject<void>();

    ngOnInit() {
        fromEvent(this.saveBtn.nativeElement, 'click')
            .pipe(takeUntil(this.destroy$))
            .subscribe(() => this.handleSave());
        console.log('Save button initialized and click event listener added.');
    }

    handleSave() {
        const blob = new Blob([this.reportData], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'compliance_report.html';
        a.click();
        URL.revokeObjectURL(url);
    }

    ngOnDestroy() {
        this.destroy$.next();
        this.destroy$.complete();
    }
}
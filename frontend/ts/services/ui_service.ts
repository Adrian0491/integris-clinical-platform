import { Component } from '@angular/core';

@Component({
    selector: 'app-ui-service',
    template: `
    <button (click)="openDialog()">Open Dialog</button>

    <div *ngIf="isDialogOpen" class="bp3-dialog">
      <h2>Dialog Title</h2>
      <div>This is the content of the dialog.</div>
      <button (click)="closeDialog()">Close</button>
    </div>
  `
})
export class UiServiceComponent {
    isDialogOpen = false;

    openDialog() {
        this.isDialogOpen = true;
    }

    closeDialog() {
        this.isDialogOpen = false;
    }
}
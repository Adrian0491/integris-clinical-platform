import {button} from "npm/angular-bootstrap";

import {UIService} from "./ui_service";
import {BootstrapDialog} from "npm/bootstrap-dialog";

export class UIServiceImpl implements UIService {
    showAlert(title: string, message: string): void {
        BootstrapDialog.show({
            title: title,
            message: message,
            buttons: [{
                label: 'OK',
                action: (dialog: BootstrapDialog) => {
                    dialog.close();
                }
            }]
        });
}
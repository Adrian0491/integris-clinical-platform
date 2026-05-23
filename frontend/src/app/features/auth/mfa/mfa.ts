import { Component, inject, signal, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-mfa',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule, MatInputModule, MatButtonModule,
    MatCardModule, MatIconModule, MatProgressSpinnerModule,
  ],
  templateUrl: './mfa.html',
  styleUrl: './mfa.css',
})
export class MfaComponent implements OnInit {
  private readonly fb       = inject(FormBuilder);
  private readonly auth     = inject(AuthService);
  private readonly router   = inject(Router);

  private tempToken = '';
  readonly loading  = signal(false);
  readonly errorMsg = signal('');

  readonly form = this.fb.nonNullable.group({
    totp_code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });

  ngOnInit(): void {
    const nav = this.router.getCurrentNavigation();
    this.tempToken = nav?.extras?.state?.['temp_token'] ?? '';
    if (!this.tempToken) this.router.navigate(['/login']);
  }

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.errorMsg.set('');
    this.auth.mfaVerify({ temp_token: this.tempToken, totp_code: this.form.value.totp_code! })
      .subscribe({
        next: () => { this.loading.set(false); this.router.navigate(['/']); },
        error: err => {
          this.loading.set(false);
          this.errorMsg.set(err.error?.detail ?? 'Invalid code. Try again.');
        },
      });
  }

  back(): void { this.router.navigate(['/login']); }
}

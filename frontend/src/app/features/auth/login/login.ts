import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule, MatInputModule, MatButtonModule,
    MatCardModule, MatIconModule, MatProgressSpinnerModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class LoginComponent {
  private readonly fb     = inject(FormBuilder);
  private readonly auth   = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route  = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  readonly loading   = signal(false);
  readonly hidePass  = signal(true);
  readonly errorMsg  = signal('');

  readonly form = this.fb.nonNullable.group({
    email:    ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.errorMsg.set('');

    this.auth.login(this.form.getRawValue()).subscribe({
      next: res => {
        this.loading.set(false);
        if ('mfa_required' in res) {
          this.router.navigate(['/mfa'], { state: { temp_token: res.temp_token } });
        } else {
          const ret = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/';
          this.router.navigateByUrl(ret);
        }
      },
      error: err => {
        this.loading.set(false);
        this.errorMsg.set(err.error?.detail ?? 'Login failed. Check your credentials.');
      },
    });
  }
}

export enum ErrorCode {
  VALIDATION_FAILED = 'VALIDATION_FAILED',
  FORM_NOT_FOUND = 'FORM_NOT_FOUND',
  TOKEN_EXPIRED = 'TOKEN_EXPIRED',
  INCOMPLETE_SUBMISSION = 'INCOMPLETE_SUBMISSION',
  FILE_TOO_LARGE = 'FILE_TOO_LARGE',
  UNSUPPORTED_FILE_TYPE = 'UNSUPPORTED_FILE_TYPE',
  RATE_LIMITED = 'RATE_LIMITED',
}

export interface ApiErrorDetail {
  field_id?: string;
  message: string;
}

export interface ApiError {
  error: {
    code: ErrorCode;
    message: string;
    details?: ApiErrorDetail[];
  };
}

/** A superseded response must not navigate or mutate the next authentication attempt. */
export class AuthOperationSuperseded extends Error {
  constructor() { super('auth_operation_superseded'); this.name = 'AuthOperationSuperseded' }
}
export function isAuthOperationSuperseded(error: unknown): error is AuthOperationSuperseded {
  return error instanceof AuthOperationSuperseded
}

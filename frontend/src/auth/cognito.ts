/**
 * Thin promise-based wrapper around amazon-cognito-identity-js.
 * The SPA talks to Cognito directly; we only ever surface { email, sub, idToken }.
 */
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";

const POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;

/** True when a real Cognito pool is configured (else only guest mode is offered). */
export const cognitoEnabled = Boolean(POOL_ID && CLIENT_ID);

const pool =
  cognitoEnabled
    ? new CognitoUserPool({ UserPoolId: POOL_ID!, ClientId: CLIENT_ID! })
    : null;

export interface AuthUser {
  email: string;
  sub: string;
  idToken: string;
}

function userFromSession(session: CognitoUserSession, email: string): AuthUser {
  const payload = session.getIdToken().decodePayload();
  return {
    email: (payload.email as string) || email,
    sub: payload.sub as string,
    idToken: session.getIdToken().getJwtToken(),
  };
}

function cognitoUser(email: string): CognitoUser {
  return new CognitoUser({ Username: email, Pool: pool! });
}

export function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    pool!.signUp(
      email,
      password,
      [new CognitoUserAttribute({ Name: "email", Value: email })],
      [],
      (err) => (err ? reject(err) : resolve()),
    );
  });
}

export function confirmSignUp(email: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    cognitoUser(email).confirmRegistration(code, true, (err) =>
      err ? reject(err) : resolve(),
    );
  });
}

export function resendCode(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    cognitoUser(email).resendConfirmationCode((err) =>
      err ? reject(err) : resolve(),
    );
  });
}

export function signIn(email: string, password: string): Promise<AuthUser> {
  return new Promise((resolve, reject) => {
    const user = cognitoUser(email);
    user.authenticateUser(
      new AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: (session) => resolve(userFromSession(session, email)),
        onFailure: (err) => reject(err),
      },
    );
  });
}

export function forgotPassword(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    cognitoUser(email).forgotPassword({
      onSuccess: () => resolve(),
      onFailure: (err) => reject(err),
    });
  });
}

export function confirmForgotPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    cognitoUser(email).confirmPassword(code, newPassword, {
      onSuccess: () => resolve(),
      onFailure: (err) => reject(err),
    });
  });
}

/** Restore an existing session on app load (refreshes tokens if needed). */
export function getCurrentUser(): Promise<AuthUser | null> {
  return new Promise((resolve) => {
    if (!pool) return resolve(null);
    const current = pool.getCurrentUser();
    if (!current) return resolve(null);
    current.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session || !session.isValid()) return resolve(null);
      const email =
        (session.getIdToken().decodePayload().email as string) || current.getUsername();
      resolve(userFromSession(session, email));
    });
  });
}

export function signOut(): void {
  pool?.getCurrentUser()?.signOut();
}

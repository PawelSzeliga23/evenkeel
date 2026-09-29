import { ApiError } from "./client";

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Coś poszło nie tak. Spróbuj ponownie.";
}

import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { formErrors } from "./forms";

describe("formErrors", () => {
  it("puts a validation error at the field named by its location", () => {
    const error = new ApiError(422, "validation_error", "x", { errors: [{ loc: ["body", "first_deposit", "amount"] }] });
    expect(formErrors(error)).toEqual({ fields: { amount: "Sprawdź tę wartość." }, general: null });
  });

  it("maps a known code to its field with the API's message", () => {
    const error = new ApiError(422, "date_in_future", "Data z przyszłości.");
    expect(formErrors(error, { date_in_future: "date" })).toEqual({ fields: { date: "Data z przyszłości." }, general: null });
  });

  it("gives a general message for anything else", () => {
    const result = formErrors(new Error("boom"));
    expect(result.fields).toEqual({});
    expect(result.general).toEqual(expect.any(String));
  });
});

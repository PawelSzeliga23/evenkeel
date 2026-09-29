import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

describe("add screen", () => {
  it("offers the four ways to add something", async () => {
    mockFetch(SIGNED_IN);
    renderApp("/dodaj");

    expect(await screen.findByRole("heading", { name: "Dodaj" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Import z XTB/ })).toHaveAttribute("href", "/dodaj/xtb");
    expect(screen.getByRole("link", { name: /Obligacja/ })).toHaveAttribute("href", "/dodaj/obligacja");
    expect(screen.getByRole("link", { name: /Konto oszczędnościowe/ })).toHaveAttribute("href", "/dodaj/konto-oszczednosciowe");
    expect(screen.getByRole("link", { name: /Operacja gotówkowa/ })).toHaveAttribute("href", "/dodaj/operacja");
  });
});

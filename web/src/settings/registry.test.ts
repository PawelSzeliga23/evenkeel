import { describe, expect, it } from "vitest";
import { fold, searchSettings } from "./registry";

const accounts = [{ id: 1, name: "XTB IKE" }, { id: 4, name: "Łódź — konto" }];
const tags = [{ id: 3, name: "Emerytura" }];

describe("settings search", () => {
  it("folds case and Polish letters", () => {
    expect(fold("Zmień HASŁO")).toBe("zmien haslo");
  });

  it("finds an option inside a subpage and says where it is", () => {
    const [hit] = searchSettings("haslo", accounts, tags);

    expect(hit).toEqual({ title: "Zmień hasło", place: "Profil", to: "/ustawienia/haslo" });
  });

  it("finds by keyword, by account name and by tag name", () => {
    expect(searchSettings("oko", accounts, tags).map((h) => h.title)).toContain("Ukrywanie kwot");
    expect(searchSettings("lodz", accounts, tags)).toContainEqual(
      { title: "Łódź — konto", place: "Konta", to: "/ustawienia/konta/4" });
    expect(searchSettings("emery", accounts, tags)).toContainEqual(
      { title: "Emerytura", place: "Tagi walorów", to: "/ustawienia/tagi" });
  });

  it("finds nothing for a blank or unknown query", () => {
    expect(searchSettings("   ", accounts, tags)).toEqual([]);
    expect(searchSettings("qwerty", accounts, tags)).toEqual([]);
  });
});

import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NETWORK_MESSAGE } from "../../api/client";
import { IMPORT_FILE, PREVIEW } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const xlsx = (name = IMPORT_FILE.filename) => new File(["xlsx"], name, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

function sentNames(init: RequestInit | undefined): string[] {
  return (init!.body as FormData).getAll("files").map((f) => (f as File).name);
}

describe("import screen", () => {
  it("previews the files, then saves the same files and leads to the dashboard", async () => {
    const sent: string[][] = [];
    mockFetch([
      ...SIGNED_IN,
      { method: "POST", path: "/api/imports/preview", respond: (_u, init) => { sent.push(sentNames(init)); return PREVIEW; } },
      {
        method: "POST", path: "/api/imports",
        respond: (_u, init) => { sent.push(sentNames(init)); return json(201, { ...PREVIEW, files: [{ ...IMPORT_FILE, import_id: 9, account_id: 5 }] }); },
      },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx(), xlsx("XTB_56204082.xlsx")]);

    const card = await screen.findByRole("region", { name: IMPORT_FILE.filename });
    expect(within(card).getByText("Zostanie założone konto: IKE 56216965")).toBeInTheDocument();
    expect(within(card).getByText("01.01.2006 – 26.09.2026")).toBeInTheDocument();
    expect(within(card).getByText("Nowe operacje").nextSibling).toHaveTextContent("42");
    expect(within(card).getByText("Ilość SXR8.DE różni się od XTB.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Zapisz import" }));

    expect(await screen.findByRole("heading", { name: "Import zapisany" })).toBeInTheDocument();
    expect(screen.getByText("Dodano 42 nowe operacje. Wycena przelicza się w tle.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zobacz pulpit" })).toHaveAttribute("href", "/");
    expect(sent).toEqual([[IMPORT_FILE.filename, "XTB_56204082.xlsx"], [IMPORT_FILE.filename, "XTB_56204082.xlsx"]]);
  });

  it("shows an unreadable file next to the others and does not offer to save", async () => {
    mockFetch([
      ...SIGNED_IN,
      {
        method: "POST", path: "/api/imports/preview",
        respond: () => ({ ...PREVIEW, errors: [{ filename: "zepsuty.xlsx", code: "bad_workbook", message: "Plik nie jest eksportem XTB." }], skipped: ["notatki.txt"] }),
      },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx(), xlsx("zepsuty.xlsx")]);

    expect(await screen.findByText("zepsuty.xlsx: Plik nie jest eksportem XTB.")).toBeInTheDocument();
    expect(screen.getByText("Pominięto plik notatki.txt, bo nie jest plikiem XLSX.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: IMPORT_FILE.filename })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zapisz import" })).toBeDisabled();
    expect(screen.getByText("Niektórych plików nie da się odczytać. Wybierz pliki bez nich, żeby zapisać import.")).toBeInTheDocument();
  });

  it("explains that there is nothing new to save", async () => {
    mockFetch([
      ...SIGNED_IN,
      { method: "POST", path: "/api/imports/preview", respond: () => ({ ...PREVIEW, files: [{ ...IMPORT_FILE, new_account: false, account_id: 5, new_transactions: 0 }] }) },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx()]);

    expect(await screen.findByText("Nic nowego do zapisania. Wszystkie operacje są już w aplikacji.")).toBeInTheDocument();
    expect(screen.getByText("Konto: IKE 56216965")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zapisz import" })).toBeDisabled();
  });

  it("keeps the chosen files when the preview fails and tries again", async () => {
    let attempts = 0;
    const fetchMock = mockFetch([...SIGNED_IN, { method: "POST", path: "/api/imports/preview", respond: () => PREVIEW }]);
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation((input: string, init?: RequestInit) =>
      String(input) === "/api/imports/preview" && ++attempts === 1 ? Promise.reject(new TypeError("Failed to fetch")) : original(input, init));
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx()]);
    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
    expect(screen.getByText(IMPORT_FILE.filename)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByRole("region", { name: IMPORT_FILE.filename })).toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { Account } from "../api/types";
import { keys } from "../api/queryKeys";
import { createQueryClient } from "../providers";
import { ACCOUNTS } from "../test/fixtures";
import { mockFetch } from "../test/render";
import { AccountSelectionProvider, useAccountSelection } from "./AccountSelection";
import { normalizeSelection, readSelection, selectionLabel, storageKey, toggleAccount, writeSelection } from "./selection";

const THREE = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }, { id: 4, name: "Oszczędności" }] as Account[];
const FIVE = [1, 2, 3, 4, 5].map((id) => ({ id, name: `K${id}` })) as Account[];

describe("selection helpers", () => {
  it("sorts, removes repeats and unknown accounts, and treats every account as none", () => {
    expect(normalizeSelection([4, 1, 4], [1, 2, 4])).toEqual([1, 4]);
    expect(normalizeSelection([1, 9], [1, 2, 4])).toEqual([1]);
    expect(normalizeSelection([4, 2, 1], [1, 2, 4])).toEqual([]);
    expect(normalizeSelection([9], [1, 2])).toEqual([]);
    expect(normalizeSelection([4, 1], null)).toEqual([1, 4]); // accounts not known yet: keep what is stored
  });

  it("ticks and unticks accounts; the last one off or the last one on is the whole portfolio", () => {
    expect(toggleAccount([], 2, [1, 2, 4])).toEqual([2]);
    expect(toggleAccount([2], 1, [1, 2, 4])).toEqual([1, 2]);
    expect(toggleAccount([1, 2], 4, [1, 2, 4])).toEqual([]);
    expect(toggleAccount([2], 2, [1, 2, 4])).toEqual([]);
  });

  it("describes the choice on the button", () => {
    expect(selectionLabel([], THREE)).toBe("Cały portfel");
    expect(selectionLabel([4], THREE)).toBe("Oszczędności");
    expect(selectionLabel([1, 4], THREE)).toBe("IKE, Oszczędności");
    expect(selectionLabel([1, 2, 3], FIVE)).toBe("3 konta");
    expect(selectionLabel([1, 2, 3, 4], [...FIVE, { id: 6, name: "K6" } as Account])).toBe("4 konta");
    expect(selectionLabel([1, 2, 3, 4, 5], [...FIVE, { id: 6, name: "K6" } as Account])).toBe("5 kont");
  });

  it("remembers the choice per user and ignores anything that is not a list of ids", () => {
    writeSelection(7, [1, 4]);
    expect(localStorage.getItem(storageKey(7))).toBe("[1,4]");
    expect(readSelection(7)).toEqual([1, 4]);
    expect(readSelection(8)).toEqual([]);
    for (const junk of ["nie json", "{\"a\":1}", "[\"1\",2]", "[0,-3,1.5]", "null"]) {
      localStorage.setItem(storageKey(7), junk);
      expect(readSelection(7)).toEqual([]);
    }
  });

  it("works without storage (private mode)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(readSelection(7)).toEqual([]);
    expect(() => writeSelection(7, [1])).not.toThrow();
    vi.restoreAllMocks();
  });
});

function Probe() {
  const [ids, setIds, ready] = useAccountSelection();
  return (
    <>
      <output>{ready ? `ready:${ids.join(",")}` : "waiting"}</output>
      <button type="button" onClick={() => setIds([2, 1, 1])}>wybierz</button>
    </>
  );
}

function renderProbe(userId: number, accounts: () => unknown = () => ACCOUNTS) {
  mockFetch([{ path: "/api/accounts", respond: accounts }]);
  const client = createQueryClient({ test: true });
  const view = (id: number) => (
    <QueryClientProvider client={client}>
      <AccountSelectionProvider key={id} userId={id}><Probe /></AccountSelectionProvider>
    </QueryClientProvider>
  );
  const utils = render(view(userId));
  return { ...utils, client, rerenderFor: (id: number) => utils.rerender(view(id)) };
}

describe("shared selection", () => {
  it("starts with the whole portfolio and is ready at once", () => {
    renderProbe(7);
    expect(screen.getByRole("status")).toHaveTextContent(/^ready:$/);
  });

  it("stores a normalized choice and restores it for the same user only", async () => {
    const { rerenderFor, unmount } = renderProbe(7, () => [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 3, name: "Trzecie" }]);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/^ready:$/));
    await userEvent.click(screen.getByRole("button", { name: "wybierz" }));
    expect(screen.getByRole("status")).toHaveTextContent("ready:1,2");
    expect(localStorage.getItem(storageKey(7))).toBe("[1,2]");

    rerenderFor(8);
    expect(screen.getByRole("status")).toHaveTextContent(/^ready:$/);
    unmount();

    renderProbe(7, () => [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 3, name: "Trzecie" }]);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1,2"));
  });

  it("waits for the account list before using a stored choice and drops a deleted account", async () => {
    writeSelection(7, [1, 9]);
    let answer: (value: unknown) => void = () => {};
    renderProbe(7, () => new Promise((resolve) => { answer = resolve; }));
    expect(screen.getByRole("status")).toHaveTextContent("waiting");
    answer(ACCOUNTS);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1"));
  });

  it("uses the stored choice when the account list cannot be loaded", async () => {
    writeSelection(7, [1]);
    renderProbe(7, () => new Response(null, { status: 500 }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1"));
  });

  it("forgets a deleted account for good: a later new account does not revive the old choice", async () => {
    writeSelection(7, [1, 2]);
    let list = [1, 2, 3].map((id) => ({ ...ACCOUNTS[0]!, id, name: `K${id}` }));
    const { client } = renderProbe(7, () => list);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1,2"));

    list = list.filter((account) => account.id !== 3);
    await client.invalidateQueries({ queryKey: keys.accounts });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/^ready:$/));
    await waitFor(() => expect(localStorage.getItem(storageKey(7))).toBe("[]"));

    list = [...list, { ...ACCOUNTS[0]!, id: 5, name: "K5" }];
    await client.invalidateQueries({ queryKey: keys.accounts });
    await waitFor(() => expect(client.getQueryData<Account[]>(keys.accounts)).toHaveLength(3));
    expect(screen.getByRole("status")).toHaveTextContent(/^ready:$/);
  });
});

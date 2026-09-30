import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Account } from "../api/types";
import { AccountChips, AccountPicker, AccountSelect } from "./AccountPicker";
import { HeroAmount, Money } from "./Amount";
import { ListRow } from "./ListRow";
import { Segmented } from "./Segmented";
import { ErrorState } from "./States";

const S = "\u00a0";
const T = " "; // Testing Library normalizes NBSP to a plain space in text matchers
const ACCOUNTS = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }] as Account[];
const THREE = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }, { id: 4, name: "Oszcz\u0119dno\u015bci" }] as Account[];

describe("amounts", () => {
  it("draws the grosze and the currency smaller in a hero amount", () => {
    const { container } = render(<HeroAmount value="184302.17" />);
    expect(container.textContent).toBe(`184${S}302,17zł`);
    expect(container.querySelector("[data-part=grosze]")).toHaveTextContent(",17");
  });

  it("colours a change by its sign", () => {
    render(<><Money value="12.5" sign tone /><Money value="-3" sign tone /><Money value="0" sign tone /></>);
    expect(screen.getByText(`+12,50${T}zł`)).toHaveClass("num", "up");
    expect(screen.getByText(`\u22123,00${T}zł`)).toHaveClass("down");
    expect(screen.getByText(`0,00${T}zł`)).not.toHaveClass("up");
  });
});

describe("controls", () => {
  it("marks the chosen segment and reports a change", async () => {
    const onChange = vi.fn();
    render(<Segmented label="Zakres" value="1R" onChange={onChange}
      options={[{ value: "1M", label: "1M" }, { value: "1R", label: "1R" }]} />);
    expect(screen.getByRole("button", { name: "1R" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1M" }));
    expect(onChange).toHaveBeenCalledWith("1M");
  });

  it("chooses the whole portfolio or one account", async () => {
    const onChange = vi.fn();
    render(<AccountPicker accounts={ACCOUNTS} value={null} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Konto" }), "2");
    expect(onChange).toHaveBeenLastCalledWith(2);
    expect(screen.getByRole("option", { name: "Cały portfel" })).toBeInTheDocument();
  });

  it("filters by account with chips", async () => {
    const onChange = vi.fn();
    render(<AccountChips accounts={ACCOUNTS} value={1} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "IKE" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Wszystkie" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("shows the choice on a button and opens checkboxes for the accounts", async () => {
    const onChange = vi.fn();
    render(<AccountSelect accounts={THREE} value={[]} onChange={onChange} />);
    const button = screen.getByRole("button", { name: "Konta: Cały portfel" });
    expect(button).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("group", { name: "Wybór kont" });
    expect(within(panel).getAllByRole("checkbox").map((c) => c.getAttribute("aria-label") ?? c.parentElement!.textContent))
      .toEqual(["Cały portfel", "IKE", "XTB", "Oszczędności"]);
    expect(screen.getByRole("checkbox", { name: "Cały portfel" })).toBeChecked();

    await userEvent.click(screen.getByRole("checkbox", { name: "Oszczędności" }));
    expect(onChange).toHaveBeenLastCalledWith([4]);
    expect(button).toHaveAttribute("aria-expanded", "true"); // stays open for more ticks
  });

  it("adds, removes and clears accounts", async () => {
    const onChange = vi.fn();
    render(<AccountSelect accounts={THREE} value={[1, 4]} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Konta: IKE, Oszczędności" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Konta:/ }));

    expect(screen.getByRole("checkbox", { name: "IKE" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Cały portfel" })).not.toBeChecked();
    await userEvent.click(screen.getByRole("checkbox", { name: "XTB" }));
    expect(onChange).toHaveBeenLastCalledWith([]); // every account ticked = the whole portfolio
    await userEvent.click(screen.getByRole("checkbox", { name: "IKE" }));
    expect(onChange).toHaveBeenLastCalledWith([4]);
    await userEvent.click(screen.getByRole("checkbox", { name: "Cały portfel" }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("closes on Escape and on a click outside", async () => {
    render(<><AccountSelect accounts={THREE} value={[]} onChange={() => {}} /><p>obok</p></>);
    const button = screen.getByRole("button", { name: "Konta: Cały portfel" });

    await userEvent.click(button);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Wybór kont" })).not.toBeInTheDocument();
    expect(button).toHaveFocus();

    await userEvent.click(button);
    await userEvent.click(screen.getByText("obok"));
    expect(screen.queryByRole("group", { name: "Wybór kont" })).not.toBeInTheDocument();
  });
});

describe("states and rows", () => {
  it("says what went wrong and offers a retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError(500, "x", "Serwer ma problem.")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Serwer ma problem.");
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("makes a whole row a link when it leads somewhere", () => {
    render(<MemoryRouter><ListRow lead="CDR" title="CD Projekt" value="1 zł" to="/pozycje/1/2" /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /CD Projekt/ })).toHaveAttribute("href", "/pozycje/1/2");
  });
});

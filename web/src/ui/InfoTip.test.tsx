import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { InfoTip } from "./InfoTip";

function setup() {
  const user = userEvent.setup();
  render(<div><InfoTip label="XIRR" help={{ what: "Twój osobisty zwrot.", how: "stopa jak w Excelu." }} /><p>obok</p></div>);
  return { user, button: screen.getByRole("button", { name: "Co to jest: XIRR" }) };
}

describe("InfoTip", () => {
  it("opens on hover and closes when the mouse leaves", async () => {
    const { user, button } = setup();

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.hover(button);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Twój osobisty zwrot.Jak liczymy: stopa jak w Excelu.");
    expect(button).toHaveAccessibleDescription(/Twój osobisty zwrot\.\s*Jak liczymy: stopa jak w Excelu\./);
    await user.unhover(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("toggles on a tap and closes on Escape or a tap elsewhere", async () => {
    const { user, button } = setup();

    await user.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(button);
    await user.click(screen.getByText("obok"));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(button);
    await user.click(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("keeps the bubble inside a narrow screen", async () => {
    window.innerWidth = 320;
    const { user, button } = setup();

    await user.click(button);
    const bubble = screen.getByRole("tooltip");
    expect(bubble.style.left).toBe("16px");
    expect(bubble.style.width).toBe("260px");
  });

  it("opens above the button near the bottom of the screen", async () => {
    window.innerHeight = 740;
    const { user, button } = setup();
    button.getBoundingClientRect = () => ({ top: 700, bottom: 722, left: 278, right: 300, width: 22, height: 22, x: 278, y: 700, toJSON: () => ({}) });

    await user.click(button);
    expect(screen.getByRole("tooltip").style.top).toBe("694px");
  });
});

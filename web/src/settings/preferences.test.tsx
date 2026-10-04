import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { AppProviders, createQueryClient } from "../providers";
import { SIGNED_IN, USER, mockFetch } from "../test/render";
import { DEFAULT_PREFERENCES, usePreferences, useSavePreferences } from "./preferences";

const wrapper = ({ children }: { children: ReactNode }) =>
  <AppProviders client={createQueryClient({ test: true })}>{children}</AppProviders>;

describe("preferences", () => {
  it("fill what the server did not send with the defaults", async () => {
    mockFetch([...SIGNED_IN.filter((r) => r.path !== "/api/auth/me"),
      { path: "/api/auth/me", respond: () => ({ ...USER, preferences: { value_range: "ALL" } }) }]);

    const { result } = renderHook(() => usePreferences(), { wrapper });

    await waitFor(() => expect(result.current.value_range).toBe("ALL"));
    expect(result.current.analysis_period).toBe(DEFAULT_PREFERENCES.analysis_period);
  });

  it("are saved and take effect at once", async () => {
    mockFetch([...SIGNED_IN,
      { method: "PATCH", path: "/api/me/preferences",
        respond: (_url, init) => ({ ...DEFAULT_PREFERENCES, ...JSON.parse(String(init.body)) }) }]);

    const { result } = renderHook(() => ({ prefs: usePreferences(), save: useSavePreferences() }), { wrapper });
    await waitFor(() => expect(result.current.prefs.start_screen).toBe("dashboard"));
    result.current.save.mutate({ start_screen: "analysis" });

    await waitFor(() => expect(result.current.prefs.start_screen).toBe("analysis"));
  });
});

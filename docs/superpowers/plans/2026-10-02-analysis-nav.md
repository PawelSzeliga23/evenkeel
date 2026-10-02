# Analiza in the bottom bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On phones the bottom bar becomes `Pulpit · Pozycje · [+] Dodaj · Historia · Analiza`, Ustawienia move to a new top row of Pulpit (logo left, gear right); the desktop sidebar keeps every item.

**Architecture:** `Nav` gains an Analiza item; the Ustawienia item gets a `desktopOnly` class hidden below 900 px. Pulpit renders a `phoneOnly` top row with the inline logo and a gear link to `/ustawienia`. Ustawienia get a phone-only back link to Pulpit.

**Tech Stack:** React, CSS modules, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-02-ai-review-design.md` §1 (mockup variant A).

## Global Constraints
- Labels: „Analiza”, gear link `aria-label="Ustawienia"`, back link „Pulpit”. 44 px touch target for the gear.
- Breakpoint 900 px as elsewhere; jsdom has no media queries, so tests check classes/links, not visibility.

## Review Focus
1. Analiza stays marked active on `/analiza/symulator` and `/analiza/przeglad` (NavLink without `end`) — test.
2. Desktop: Ustawienia still in the sidebar (class only hides it below 900 px) — test that the link exists with `desktopOnly`.

---

### Task 1: Navigation, Pulpit top row, Ustawienia back link
- [ ] Tests in `src/shell/shell.test.tsx`: the nav has a link „Analiza” to `/analiza`, marked current on `/analiza/symulator`; the „Ustawienia” nav link carries the desktop-only class. In `dashboard.test.tsx`: Pulpit has a link „Ustawienia” to `/ustawienia` in its top row. In `settings.test.tsx`: a back link „Pulpit” to `/`.
- [ ] Implement: `AnalysisIcon` in `icons.tsx`; `Nav.tsx` order Pulpit, Pozycje, Dodaj, Historia, Analiza, Ustawienia (`className={`${styles.item} ${styles.desktopOnly}`}`); CSS `.desktopOnly { display: none }` below 900 px, `display: grid` from 900 px; Pulpit top row `.topRow` (logo inline + gear `Link`, hidden from 900 px); SettingsScreen `BackLink to="/" label="Pulpit"` wrapped in a phone-only class.
- [ ] `npx vitest run`, `npx tsc --noEmit`, e2e if the settings test navigates via the bar (update it to the gear). Commit, merge.

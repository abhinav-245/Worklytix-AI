import { test, expect } from "@playwright/test";

/**
 * Reusable WorkLytix AI browser UI smoke suite (real Chromium).
 *
 * Covers: homepage load, minimal navbar, Menu interaction, Try Out
 * flow, route availability (+ /profile removal), dropdown usability,
 * responsive layout, console/page/network errors, and checkpoint
 * screenshots. Keep this suite small; add per-phase specs separately.
 */

const EXPECTED_MENU_ITEMS = [
  "AI Analysis",
  "Home",
  "Overview",
  "PR",
  "Progression",
  "Volume",
  "Plateau",
  "Muscles",
  "Exercises",
];

test.beforeEach(async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const badRequests: string[] = [];
  const backendUnreachable: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("requestfailed", (req) => {
    // The Python API backend (:8000) is intentionally not required for
    // UI smoke; the app handles its absence with empty states.
    if (req.url().includes(":8000")) {
      backendUnreachable.push(req.url());
      return;
    }
    badRequests.push(req.url());
  });
  page.on("response", (res) => {
    if (res.status() >= 500 && new URL(res.url()).port !== "8000") {
      badRequests.push(`${res.status()} ${res.url()}`);
    }
  });
  (page as unknown as { __errors?: object }).__errors = {
    consoleErrors,
    pageErrors,
    badRequests,
    backendUnreachable,
  };
});

test.afterEach(async ({ page }) => {
  const errors = (page as unknown as { __errors?: {
    consoleErrors: string[];
    pageErrors: string[];
    badRequests: string[];
    backendUnreachable: string[];
  } }).__errors;
  // Each failed fetch to the optional :8000 backend also surfaces as a
  // browser "Failed to load resource" console error; those are expected
  // and filtered only when backend traffic actually failed.
  const unexpectedConsole = (errors?.consoleErrors ?? []).filter(
    (msg) =>
      !(
        /Failed to load resource/.test(msg) &&
        (errors?.backendUnreachable ?? []).length > 0
      )
  );
  expect(unexpectedConsole, "console.error").toEqual([]);
  expect(errors?.pageErrors ?? [], "pageerror").toEqual([]);
  expect(errors?.badRequests ?? [], "failed/bad requests").toEqual([]);
});

test.describe("homepage", () => {
  test("loads with branding, hero, runner and Try Out CTA", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: "WorkLytix AI home" })
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /TURN YOUR/ })
    ).toBeVisible();
    await expect(
      page.getByRole("img", { name: /gold runner/ })
    ).toBeVisible();
    await expect(
      page.locator("header").getByRole("link", { name: "AI Analysis" })
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/home-${test.info().project.name}.png`,
    });
  });

  test("no horizontal overflow", async ({ page }) => {
    await page.goto("/");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});

test.describe("navbar refinement", () => {
  test("floating pill has side breathing room and rounded glass", async ({
    page,
  }) => {
    await page.goto("/");
    const pill = page.locator("header").locator("div").first();
    await expect(pill).toBeVisible();
    const box = await pill.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      const vw = page.viewportSize()?.width ?? 0;
      expect(box.x).toBeGreaterThanOrEqual(8);
      expect(box.x + box.width).toBeLessThanOrEqual(vw - 8);
    }
    const styles = await pill.evaluate((el) => {
      const cs = getComputedStyle(el);
      return {
        radius: cs.borderTopLeftRadius,
        backdrop: cs.backdropFilter,
        background: cs.backgroundColor,
      };
    });
    expect(parseFloat(styles.radius)).toBeGreaterThanOrEqual(12);
    expect(styles.backdrop).toContain("blur");
    expect(styles.background).toMatch(/rgba?\(/);
  });

  test("brand uses PP Pangaia, interface uses DM Sans", async ({
    page,
  }) => {
    await page.goto("/");
    const wordmark = page
      .getByRole("link", { name: "WorkLytix AI home" })
      .locator("span")
      .last();
    await expect(wordmark).toBeVisible();
    const brandFont = await wordmark.evaluate(
      (el) => getComputedStyle(el).fontFamily
    );
    expect(brandFont).toContain("PP Pangaia");
    const bodyFont = await page.evaluate(
      () => getComputedStyle(document.body).fontFamily
    );
    expect(bodyFont).toContain("DM Sans");
    const heroFont = await page
      .getByRole("heading", { name: /TURN YOUR/ })
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(heroFont).toContain("DM Sans");
  });
});

test.describe("navbar menu", () => {
  test("Menu opens, lists sections without Profile, closes", async ({
    page,
  }) => {
    await page.goto("/");
    const menuButton = page.getByRole("button", { name: "Menu" });
    await expect(menuButton).toBeVisible();
    await menuButton.click();
    const menu = page.getByRole("menu", { name: "Site sections" });
    await expect(menu).toBeVisible();
    for (const item of EXPECTED_MENU_ITEMS) {
      await expect(
        menu.getByRole("menuitem", { name: item, exact: true })
      ).toBeVisible();
    }
    await expect(
      menu.getByRole("menuitem", { name: "Profile" })
    ).toHaveCount(0);
    await expect(menu.getByText("Profile")).toHaveCount(0);
    await page.screenshot({
      path: `test-results/menu-open-${test.info().project.name}.png`,
    });
    await page.keyboard.press("Escape");
    await expect(menu).toBeHidden();
  });

  test("menu navigates to a section", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Menu" }).click();
    await page
      .getByRole("menu", { name: "Site sections" })
      .getByRole("menuitem", { name: "Overview" })
      .click();
    await expect(page).toHaveURL(/\/overview/);
    await expect(
      page.getByRole("heading", { name: "Overview" }).first()
    ).toBeVisible();
  });
});

test.describe("try out flow", () => {
  test("Try Out navigates to onboarding, no submit", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("main")
      .getByRole("link", { name: "Try Out" })
      .click();
    await expect(page).toHaveURL(/#get-started/);
    await expect(
      page.getByRole("button", { name: /CSV drop zone/ })
    ).toBeVisible();
    await expect(page.getByLabel("Age")).toBeVisible();
    await expect(page.getByLabel("Weight")).toBeVisible();
    await expect(page.getByLabel("Goal")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Upload & Analyze" })
    ).toBeVisible();
  });
});

test.describe("routes", () => {
  const existingRoutes = [
    ["/overview", "Overview"],
    ["/pr", "Personal Records"],
    ["/ai-analysis", "AI Analysis"],
  ] as const;

  for (const [route, heading] of existingRoutes) {
    test(`${route} responds with its page`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.status()).toBeLessThan(400);
      await expect(
        page.getByRole("heading", { name: heading }).first()
      ).toBeVisible();
    });
  }

  test("/insights redirects to the AI conversation", async ({ page }) => {
    await page.goto("/insights");
    await expect(page).toHaveURL(/\/ai-analysis/);
    await expect(
      page.getByRole("heading", { name: "AI Analysis" })
    ).toBeVisible();
  });

  test("/profile is not an application route", async ({ page }) => {
    const response = await page.goto("/profile");
    expect(response?.status()).toBe(404);
    // The expected 404 navigation itself logs one resource console
    // error; drop it so the global error check stays meaningful.
    const errors = (page as unknown as { __errors?: {
      consoleErrors: string[];
    } }).__errors;
    if (errors) {
      errors.consoleErrors = errors.consoleErrors.filter(
        (msg) => !msg.includes("status of 404")
      );
    }
  });
});

test.describe("ai-analysis conversation", () => {
  test("mock analysis renders as assistant turn, not cards", async ({
    page,
  }) => {
    await page.goto("/ai-analysis?e2e_mock=1");
    const log = page.getByRole("log", { name: "AI Analysis conversation" });
    await expect(log).toBeVisible();
    const assistantTurns = log.locator('[data-turn="assistant"]');
    await expect(assistantTurns).toHaveCount(1);
    await expect(
      assistantTurns.getByRole("heading", { name: "Your Training Analysis" })
    ).toBeVisible();
    await expect(log.locator('[data-turn="user"]')).toHaveCount(0);
    // Conversation turns are content, never dashboard cards.
    await expect(log.locator(".glass")).toHaveCount(0);
    await page.screenshot({
      path: `test-results/ai-analysis-${test.info().project.name}.png`,
    });
  });

  test("composer sends a follow-up as a user turn", async ({ page }) => {
    await page.goto("/ai-analysis?e2e_mock=1");
    const log = page.getByRole("log", { name: "AI Analysis conversation" });
    await expect(
      log.locator('[data-turn="assistant"]')
    ).toHaveCount(1);
    const composer = page.getByLabel("Ask a follow-up question");
    await expect(composer).toBeVisible();
    await expect(composer).toBeEnabled();
    await composer.fill("Why has my bench press stopped progressing?");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(log.locator('[data-turn="user"]')).toHaveCount(1);
    await expect(
      log
        .locator('[data-turn="user"]')
        .getByText("Why has my bench press stopped progressing?")
    ).toBeVisible();
    await expect(log.locator('[data-turn="assistant"]')).toHaveCount(2);
  });

  test("recommendations arrive as another assistant message", async ({
    page,
  }) => {
    await page.goto("/ai-analysis?e2e_mock=1");
    const log = page.getByRole("log", { name: "AI Analysis conversation" });
    await expect(
      log.locator('[data-turn="assistant"]')
    ).toHaveCount(1);
    await page.getByRole("button", { name: "Get recommendations" }).click();
    const recTurn = log.locator('[data-turn="assistant"]').nth(1);
    await expect(recTurn).toBeVisible();
    await expect(
      recTurn.getByRole("heading", { name: "Recommendations" })
    ).toBeVisible();
    await expect(log.locator(".glass")).toHaveCount(0);
  });

  test("empty state guides to onboarding without dataset", async ({
    page,
  }) => {
    await page.goto("/ai-analysis");
    await expect(
      page.getByRole("heading", { name: "AI Analysis" })
    ).toBeVisible();
    await expect(page.getByText("No workout data yet")).toBeVisible();
  });
});

test.describe("dropdown readability", () => {
  test("goal select is usable with dark popup scheme", async ({
    page,
  }) => {
    await page.goto("/#get-started");
    const goal = page.getByLabel("Goal");
    await expect(goal).toBeVisible();
    await expect(goal).toBeEnabled();
    const optionCount = await goal.locator("option").count();
    expect(optionCount).toBeGreaterThan(1);
    await goal.selectOption("strength");
    await expect(goal).toHaveValue("strength");
    const colorScheme = await page.evaluate(
      () => getComputedStyle(document.documentElement).colorScheme
    );
    expect(colorScheme).toContain("dark");
  });
});

test.describe("responsive", () => {
  test("mobile viewport keeps brand, menu, hero and Try Out usable", async ({
    page,
  }) => {
    test.skip(
      test.info().project.name !== "chromium-mobile",
      "mobile viewport assertions"
    );
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: "WorkLytix AI home" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Menu" })
    ).toBeVisible();
    await expect(
      page.locator("header").getByRole("link", { name: "AI Analysis" })
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /TURN YOUR/ })
    ).toBeVisible();
    // Hero CTA and runner must not overlap or overflow on small screens.
    const ctaBox = await page
      .getByRole("main")
      .getByRole("link", { name: "Try Out" })
      .boundingBox();
    const runnerBox = await page
      .getByRole("img", { name: /gold runner/ })
      .boundingBox();
    expect(ctaBox).not.toBeNull();
    expect(runnerBox).not.toBeNull();
    if (ctaBox && runnerBox) {
      const overlap =
        ctaBox.y < runnerBox.y + runnerBox.height &&
        runnerBox.y < ctaBox.y + ctaBox.height &&
        ctaBox.x < runnerBox.x + runnerBox.width &&
        runnerBox.x < ctaBox.x + ctaBox.width;
      expect(overlap).toBe(false);
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});

import type { Page } from "playwright";
import type { TenderListItem } from "../types";
import { parseRuPublishedAt } from "../time";

const REQUESTS_LIST_URL = "https://bidzaar.com/requests/public/buy";

export async function gotoRequestsList(page: Page): Promise<void> {
  await page.goto(REQUESTS_LIST_URL, { waitUntil: "domcontentloaded" });
  // Angular app: content often appears after initial DOMContentLoaded.
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  // Wait until list items render.
  await page.locator("cgn-prs-public-info a").first().waitFor({ timeout: 20_000 }).catch(() => undefined);
}

function pickFirst<T>(arr: T[]): T | undefined {
  return arr.length > 0 ? arr[0] : undefined;
}

export async function parseListPage(page: Page): Promise<TenderListItem[]> {
  // Bidzaar list structure (from provided HTML):
  // cgn-prs-public-info > a (card link)
  // inside: cgn-prs-publish-date span => "Опубликован DD.MM.YYYY"
  const cardLinks = page.locator("cgn-prs-public-info a");
  const count = await cardLinks.count();

  const items: TenderListItem[] = [];
  for (let i = 0; i < count; i++) {
    const a = cardLinks.nth(i);
    const url = await a
      .evaluate((el) => (el instanceof HTMLAnchorElement ? el.href : ""))
      .catch(() => "");
    if (!url) continue;

    const publishedText = (await a.locator("cgn-prs-publish-date").innerText().catch(() => "")).trim();
    const publishedAt = publishedText ? parseRuPublishedAt(publishedText) : undefined;

    const containerText = (await a.innerText().catch(() => "")).trim();
    const tenderNumber = (() => {
      const m = containerText.match(/№\s*([0-9A-Za-zА-Яа-я-]+)/);
      return m?.[1];
    })();

    // Title is typically the first non-empty line of the card text.
    const title = containerText
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean)[0];

    items.push({ title: title || url, url, publishedAt, tenderNumber });
  }

  // Deduplicate by url (list pages sometimes contain repeated links)
  const seen = new Set<string>();
  return items.filter((it) => {
    if (seen.has(it.url)) return false;
    seen.add(it.url);
    return true;
  });
}

export async function gotoNextListPage(page: Page): Promise<boolean> {
  // Try common pagination patterns.
  const candidates = [
    page.getByRole("link", { name: /след/i }),
    page.getByRole("button", { name: /след/i }),
    page.locator('a[rel="next"]'),
    page.locator('button[rel="next"]'),
  ];
  for (const c of candidates) {
    if ((await c.count()) > 0 && (await c.first().isVisible().catch(() => false))) {
      const btn = c.first();
      const disabled =
        (await btn.getAttribute("aria-disabled").catch(() => null)) === "true" ||
        (await btn.isDisabled().catch(() => false));
      if (disabled) return false;
      await Promise.all([
        page.waitForLoadState("domcontentloaded").catch(() => undefined),
        btn.click({ timeout: 10_000 }).catch(() => undefined),
      ]);
      return true;
    }
  }
  return false;
}


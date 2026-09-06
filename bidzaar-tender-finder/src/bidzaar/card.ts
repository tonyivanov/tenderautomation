import type { BrowserContext, Page } from "playwright";
import { promises as fs } from "node:fs";
import path from "node:path";
import type { TenderDetails, TenderDocument } from "../types";
import { parseRuPublishedAt } from "../time";

function textOrUndefined(s: string | null | undefined): string | undefined {
  const t = (s ?? "").trim();
  return t ? t : undefined;
}

export async function parseTenderCard(page: Page, url: string): Promise<TenderDetails> {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  // Give SPA time to render content.
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);

  const bodyText = await page.locator("body").innerText().catch(() => "");

  // Prefer on-page/metadata title over browser tab title (often just "Bidzaar").
  const ogTitle = await page
    .locator('meta[property="og:title"]')
    .getAttribute("content")
    .catch(() => undefined);
  const h1Title = await page.locator("h1").first().innerText().catch(() => undefined);
  const title =
    textOrUndefined(ogTitle) ??
    textOrUndefined(h1Title) ??
    (() => {
      const firstLine = bodyText
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean)[0];
      return textOrUndefined(firstLine);
    })();

  const organizer = (() => {
    const m = bodyText.match(/Организатор\s*[:\n]\s*(.+)/i);
    return textOrUndefined(m?.[1]);
  })();

  const publishedAt = (() => {
    const publishText = bodyText.match(/Опубликован\s+\d{2}\.\d{2}\.\d{4}(?:\s*,\s*\d{2}:\d{2})?/);
    return publishText ? parseRuPublishedAt(publishText[0]) : undefined;
  })();

  const deadlineAt = (() => {
    // Heuristic: look for "Окончание подачи" with date time nearby in same Russian format.
    const m = bodyText.match(/(Окончание подачи|Дата окончания подачи)[^\d]*(\d{2}\.\d{2}\.\d{4}\s*,\s*\d{2}:\d{2})/i);
    if (!m) return undefined;
    return parseRuPublishedAt(m[2] ?? "");
  })();

  // Best-effort description: try to capture a section that includes "Описание"
  const descriptionText = (() => {
    const m = bodyText.match(/Описание закупки\s*[:\n]([\s\S]{0,4000})/i);
    const t = textOrUndefined(m?.[1]);
    return t ? t.slice(0, 4000) : undefined;
  })();

  const documents = await collectDocumentLinks(page);

  return {
    url,
    title,
    organizer,
    descriptionText,
    publishedAt,
    deadlineAt,
    documents,
  };
}

async function collectDocumentLinks(page: Page): Promise<TenderDocument[]> {
  // Keep it strict: only filestorage downloads (and the zip "download?ids=...") from Bidzaar.
  const a = page.locator('a[href*="/api/filestorage/files/download"]');
  const count = await a.count();
  const docs: TenderDocument[] = [];
  for (let i = 0; i < count; i++) {
    const el = a.nth(i);
    const href = await el.getAttribute("href");
    if (!href) continue;
    const name = (await el.innerText().catch(() => "")).trim();
    const fullUrl = href.startsWith("http") ? href : `https://bidzaar.com${href}`;
    docs.push({ name: name || fullUrl, url: fullUrl });
  }
  // Dedup
  const seen = new Set<string>();
  return docs.filter((d) => {
    const k = d.url ?? d.name;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

export async function downloadDocumentsBestEffort(opts: {
  context: BrowserContext;
  page: Page;
  documents: TenderDocument[];
  downloadDir: string;
}): Promise<TenderDocument[]> {
  const { context, page, documents, downloadDir } = opts;
  const results: TenderDocument[] = [];

  const mimeToExt: Record<string, string> = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/x-7z-compressed": "7z",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
  };

  let idx = 0;
  for (const doc of documents) {
    idx += 1;
    const url = doc.url;
    if (!url) {
      results.push({ ...doc, downloadedOk: false, error: "No URL" });
      continue;
    }

    // Attempt A: direct HTTP fetch (works when it is a plain file URL)
    try {
      const resp = await context.request.get(url, { timeout: 30_000 });
      if (resp.ok()) {
        const buf = await resp.body();
        const disp = resp.headers()["content-disposition"];
        const nameFromDisp = disp ? /filename\*?=(?:UTF-8''|\"?)([^\";]+)/i.exec(disp)?.[1] : undefined;
        const contentType = (resp.headers()["content-type"] ?? "").split(";")[0]?.trim().toLowerCase();
        const extFromName = nameFromDisp?.match(/\.([a-z0-9]{1,8})$/i)?.[1]?.toLowerCase();
        const ext = extFromName ?? (contentType ? mimeToExt[contentType] : undefined) ?? "bin";
        const fileName = `file-${String(idx).padStart(3, "0")}.${ext}`;
        const fullPath = path.join(downloadDir, fileName.replace(/[\\/:*?"<>|]/g, "_"));
        await fs.writeFile(fullPath, buf);
        results.push({ ...doc, localPath: fullPath, downloadedOk: true });
        continue;
      }
    } catch {
      // fallthrough
    }

    results.push({ ...doc, downloadedOk: false, error: "Could not download" });
  }

  return results;
}


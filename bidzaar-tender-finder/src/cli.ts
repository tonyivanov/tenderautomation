import "dotenv/config";
import { Command } from "commander";
import path from "node:path";
import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import { gotoRequestsList, gotoNextListPage, parseListPage } from "./bidzaar/list";
import { downloadDocumentsBestEffort, parseTenderCard } from "./bidzaar/card";
import { ensureDir, runFolderName, safeSlug, writeJson, writeText } from "./io";
import { loadState, saveState } from "./state";
import type { RunMeta, TenderDetails, TenderListItem } from "./types";
import { toIso } from "./time";

type CommonOpts = {
  headless: boolean;
  statePath: string;
  storageStatePath: string;
  outDir: string;
};

async function waitForEnter(prompt: string): Promise<void> {
  const { stdin, stdout } = process;
  if (!stdin || !stdout) return;
  stdout.write(`${prompt}\n`);
  stdin.setEncoding("utf8");
  stdin.resume();
  await new Promise<void>((resolve) => {
    const onData = () => {
      stdin.off("data", onData);
      resolve();
    };
    stdin.on("data", onData);
  });
}

type ProxySettings =
  | undefined
  | {
      server: string;
      username?: string;
      password?: string;
    };

function getProxyFromEnv(): ProxySettings {
  // If your environment sets a broken proxy (ERR_PROXY_CONNECTION_FAILED),
  // you can either unset HTTPS_PROXY/HTTP_PROXY in PowerShell, or set
  // BIDZAAR_PROXY_SERVER explicitly.
  const server =
    process.env.BIDZAAR_PROXY_SERVER ??
    process.env.PLAYWRIGHT_PROXY_SERVER ??
    process.env.HTTPS_PROXY ??
    process.env.HTTP_PROXY;
  if (!server) return undefined;
  return {
    server,
    username: process.env.BIDZAAR_PROXY_USERNAME ?? process.env.PLAYWRIGHT_PROXY_USERNAME,
    password: process.env.BIDZAAR_PROXY_PASSWORD ?? process.env.PLAYWRIGHT_PROXY_PASSWORD,
  };
}

async function withBrowser<T>(
  opts: { headless: boolean; storageStatePath?: string },
  fn: (ctx: BrowserContext, page: Page, browser: Browser) => Promise<T>,
): Promise<T> {
  const proxy = getProxyFromEnv();
  const disableSystemProxy = process.env.BIDZAAR_DISABLE_SYSTEM_PROXY !== "0";
  const browser = await chromium.launch({
    headless: opts.headless,
    proxy,
    args: disableSystemProxy && !proxy ? ["--no-proxy-server"] : undefined,
  });
  const context = await browser.newContext(
    opts.storageStatePath ? { storageState: opts.storageStatePath } : undefined,
  );
  const page = await context.newPage();
  try {
    return await fn(context, page, browser);
  } finally {
    await context.close().catch(() => undefined);
    await browser.close().catch(() => undefined);
  }
}

async function saveArtifacts(params: {
  page: Page;
  artifactsDir: string;
  name: string;
}): Promise<void> {
  const { page, artifactsDir, name } = params;
  await ensureDir(artifactsDir);
  const screenshotPath = path.join(artifactsDir, `${name}.png`);
  const htmlPath = path.join(artifactsDir, `${name}.html`);
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => undefined);
  const html = await page.content().catch(() => "");
  await writeText(htmlPath, html).catch(() => undefined);
}

const program = new Command();

program
  .name("bidzaar-tender-finder")
  .description("Parse new tenders from Bidzaar since last run")
  .option("--headful", "Run with visible browser (global; must be before subcommand)", false)
  .option("--statePath <path>", "Path to state.json", "state.json")
  .option("--storageStatePath <path>", "Path to storageState.json", "storageState.json")
  .option("--outDir <dir>", "Output base directory", "out");

program
  .command("login")
  .description("Open browser to login manually and save storageState.json")
  .action(async () => {
    const o = program.opts();
    const headless = !o.headful;
    const storageStatePath = String(o.storageStatePath);

    await withBrowser({ headless: false }, async (ctx, page) => {
      await page.goto("https://bidzaar.com/home", { waitUntil: "domcontentloaded" });
      console.log("Browser opened for manual login.");
      console.log("Please complete login in the browser, then come back here.");
      await waitForEnter("Press Enter to save session (storageState) and close the browser.");

      // Basic sanity check: don't save if we're obviously still on a login page.
      const url = page.url();
      if (/\/auth\/login|\/login/i.test(url)) {
        throw new Error(
          `Still on login page (${url}). Login did not complete; not saving storageState.`,
        );
      }
      await ctx.storageState({ path: storageStatePath });
      console.log(`Saved storage state to: ${storageStatePath}`);
    });
  });

program
  .command("parse-new")
  .description("Parse tenders published after lastRunAt")
  .option("--maxPages <n>", "Max list pages to scan", "10")
  .option("--maxNew <n>", "Max new tenders to deep-parse", "200")
  .option("--downloadDocs", "Download documents for new tenders", false)
  .option("--headful", "Run with visible browser (command-local)", false)
  .action(async (cmdOpts) => {
    const o = program.opts();
    const headfulCmd = Boolean(cmdOpts.headful);
    const common: CommonOpts = {
      headless: !(Boolean(o.headful) || headfulCmd),
      statePath: String(o.statePath),
      storageStatePath: String(o.storageStatePath),
      outDir: String(o.outDir),
    };

    const maxPages = Number(cmdOpts.maxPages);
    const maxNew = Number(cmdOpts.maxNew);
    const downloadDocs = Boolean(cmdOpts.downloadDocs);

    const runDir = path.join(common.outDir, runFolderName(new Date()));
    const artifactsDir = path.join(runDir, "artifacts");
    const downloadsDir = path.join(runDir, "downloads");

    const meta: RunMeta = {
      startedAt: new Date().toISOString(),
      errors: [],
    };

    const state = await loadState(common.statePath);
    meta.lastRunAt = state.lastRunAt;
    const lastRunAt = state.lastRunAt ? new Date(state.lastRunAt) : new Date(0);

    const newTenders: TenderDetails[] = [];
    let maxPublishedSeen: Date | undefined;

    await withBrowser(
      { headless: common.headless, storageStatePath: common.storageStatePath },
      async (ctx, page) => {
        console.log(`Opening requests list (${common.headless ? "headless" : "headful"})...`);
        // quick session check
        await gotoRequestsList(page);
        console.log(`At: ${page.url()}`);
        const looksLikeLogin =
          /\/auth\/login|\/login/i.test(page.url()) ||
          ((await page.getByRole("heading", { name: /вход|авторизац/i }).count().catch(() => 0)) > 0 &&
            (await page.locator('input[type="password"]').count().catch(() => 0)) > 0);
        if (looksLikeLogin) {
          meta.errors.push({
            where: "ensureLogin",
            message: "Session seems expired (login page detected); run `npm.cmd run login`.",
          });
          await saveArtifacts({ page, artifactsDir, name: "session-expired" });
          return;
        }

        const listItems: TenderListItem[] = [];
        for (let p = 0; p < maxPages; p++) {
          console.log(`Scanning list page ${p + 1}/${maxPages}...`);
          try {
            const itemsOnPage = await parseListPage(page);
            if (itemsOnPage.length === 0) {
              await saveArtifacts({ page, artifactsDir, name: `list-empty-page-${p + 1}` });
            }
            listItems.push(...itemsOnPage);

            // Early stop: if sorted by newest first and this page already contains items <= lastRunAt
            const oldestOnThisPage = itemsOnPage
              .map((x) => x.publishedAt)
              .filter((d): d is Date => !!d)
              .sort((a, b) => a.getTime() - b.getTime())[0];
            if (oldestOnThisPage && oldestOnThisPage <= lastRunAt) break;
          } catch (e: any) {
            meta.errors.push({ where: "parseListPage", message: String(e?.message ?? e), url: page.url() });
            await saveArtifacts({ page, artifactsDir, name: `list-parse-error-page-${p + 1}` });
          }

          const hasNext = await gotoNextListPage(page);
          if (!hasNext) break;
          await page.waitForTimeout(400);
        }

        const newItems = listItems
          .filter((it) => {
            if (!it.publishedAt) return false;
            if (it.publishedAt > lastRunAt) return true;
            // List page may show only the date (no time). If it's the same calendar day as lastRunAt,
            // include it for deep-parse (card usually contains time).
            return (
              it.publishedAt.getFullYear() === lastRunAt.getFullYear() &&
              it.publishedAt.getMonth() === lastRunAt.getMonth() &&
              it.publishedAt.getDate() === lastRunAt.getDate()
            );
          })
          .sort((a, b) => (b.publishedAt?.getTime() ?? 0) - (a.publishedAt?.getTime() ?? 0))
          .slice(0, maxNew);
        console.log(`Found ${newItems.length} new items (after ${meta.lastRunAt ?? "epoch"})`);

        for (const it of newItems) {
          try {
            console.log(`Opening tender: ${it.title}`);
            const details = await parseTenderCard(page, it.url);
            details.tenderNumber ??= it.tenderNumber;
            details.title ??= it.title;
            details.publishedAt ??= it.publishedAt;
            newTenders.push(details);
            if (details.publishedAt && (!maxPublishedSeen || details.publishedAt > maxPublishedSeen)) {
              maxPublishedSeen = details.publishedAt;
            }

            if (downloadDocs && details.documents.length > 0) {
              const slug = safeSlug(details.tenderNumber ?? details.title ?? "tender");
              const perTenderDir = path.join(downloadsDir, slug);
              await ensureDir(perTenderDir);
              details.documents = await downloadDocumentsBestEffort({
                context: ctx,
                page,
                documents: details.documents,
                downloadDir: perTenderDir,
              });
            }
          } catch (e: any) {
            meta.errors.push({ where: "parseTenderCard", message: String(e?.message ?? e), url: it.url });
            await saveArtifacts({ page, artifactsDir, name: `card-error-${safeSlug(it.title)}` });
          }

          await page.waitForTimeout(500);
        }
      },
    );

    meta.newCount = newTenders.length;
    meta.finishedAt = new Date().toISOString();

    await ensureDir(runDir);
    await writeJson(path.join(runDir, "tenders.json"), {
      lastRunAt: meta.lastRunAt,
      parsedAt: meta.startedAt,
      tenders: newTenders.map((t) => ({
        ...t,
        publishedAt: toIso(t.publishedAt),
        deadlineAt: toIso(t.deadlineAt),
      })),
    });
    await writeJson(path.join(runDir, "run.json"), meta);

    // Update state to max publishedAt we've actually seen (fallback: now)
    const nextLastRunAt = (maxPublishedSeen ?? new Date()).toISOString();
    await saveState(common.statePath, { lastRunAt: nextLastRunAt });
    console.log(`New tenders: ${newTenders.length}`);
    console.log(`Updated lastRunAt: ${nextLastRunAt}`);
    console.log(`Output: ${runDir}`);
  });

program.parseAsync(process.argv).catch((e) => {
  console.error(e);
  process.exitCode = 1;
});


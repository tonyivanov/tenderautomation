import { promises as fs } from "node:fs";
import path from "node:path";

export type AppState = {
  lastRunAt?: string; // ISO
};

export async function loadState(statePath: string): Promise<AppState> {
  try {
    const raw = await fs.readFile(statePath, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object") {
      const obj = parsed as { lastRunAt?: unknown };
      if (typeof obj.lastRunAt === "string") return { lastRunAt: obj.lastRunAt };
      return {};
    }
    return {};
  } catch (e: any) {
    if (e?.code === "ENOENT") return {};
    throw e;
  }
}

export async function saveState(statePath: string, state: AppState): Promise<void> {
  await fs.mkdir(path.dirname(statePath), { recursive: true });
  await fs.writeFile(statePath, JSON.stringify(state, null, 2), "utf8");
}


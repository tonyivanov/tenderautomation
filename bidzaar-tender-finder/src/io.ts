import { promises as fs } from "node:fs";
import path from "node:path";

export function runFolderName(d = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  return `run-${yyyy}-${mm}-${dd}_${hh}-${mi}`;
}

export async function ensureDir(p: string): Promise<void> {
  await fs.mkdir(p, { recursive: true });
}

export async function writeJson(filePath: string, data: unknown): Promise<void> {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), "utf8");
}

export async function writeText(filePath: string, data: string): Promise<void> {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, data, "utf8");
}

export function safeSlug(input: string, maxLen = 80): string {
  const s = input
    .trim()
    .toLowerCase()
    .replace(/[ё]/g, "е")
    .replace(/[^a-z0-9а-я]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/(^-|-$)/g, "");
  return s.length > maxLen ? s.slice(0, maxLen) : s;
}


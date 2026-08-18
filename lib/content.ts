import fs from "node:fs";
import path from "node:path";

export type Article = {
  slug: string;
  title: string;
  dek: string;
  body: string[];
  category: string;
  tags: string[];
  source_name: string;
  source_url: string;
  published_at: string;
};

const NEWS_DIR = path.join(process.cwd(), "content", "news");

function readArticleFile(filename: string): Article {
  const raw = fs.readFileSync(path.join(NEWS_DIR, filename), "utf-8");
  const data = JSON.parse(raw);
  const slug = data.slug ?? filename.replace(/\.json$/, "");
  return { ...data, slug };
}

export function getAllArticles(): Article[] {
  if (!fs.existsSync(NEWS_DIR)) return [];
  const files = fs.readdirSync(NEWS_DIR).filter((f) => f.endsWith(".json"));
  const articles = files.map(readArticleFile);
  return articles.sort(
    (a, b) =>
      new Date(b.published_at).getTime() - new Date(a.published_at).getTime(),
  );
}

export function getArticleBySlug(slug: string): Article | undefined {
  return getAllArticles().find((a) => a.slug === slug);
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

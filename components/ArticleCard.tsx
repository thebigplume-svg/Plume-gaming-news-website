import Link from "next/link";
import type { Article } from "@/lib/content";
import { formatRelativeTime } from "@/lib/content";

export default function ArticleCard({ article }: { article: Article }) {
  return (
    <Link href={`/article/${article.slug}`} className="card">
      <div className="kicker-row">
        <span className="pill">{article.category}</span>
      </div>
      <h3>{article.title}</h3>
      <p>{article.dek}</p>
      {article.tags.length > 0 && (
        <div className="tags">
          {article.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      )}
      <div className="meta mono">
        <span className="source">{article.source_name}</span>
        <span>{formatRelativeTime(article.published_at)}</span>
      </div>
    </Link>
  );
}

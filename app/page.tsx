import Link from "next/link";
import Masthead from "@/components/Masthead";
import ArticleCard from "@/components/ArticleCard";
import { getAllArticles, formatRelativeTime } from "@/lib/content";

export default function Home() {
  const articles = getAllArticles();
  const [lead, ...rest] = articles;

  return (
    <div className="page">
      <Masthead />

      {articles.length === 0 && (
        <div className="empty-state">
          <p>
            No stories yet — the news agent publishes here automatically once
            it starts pulling headlines. Check back soon.
          </p>
        </div>
      )}

      {lead && (
        <Link href={`/article/${lead.slug}`} className="hero">
          <div className="plume-trail" aria-hidden="true" />
          <div className="kicker-row">
            <span className="pill">{lead.category}</span>
            <span className="status-chip published">Latest</span>
          </div>
          <h1>{lead.title}</h1>
          <p className="dek">{lead.dek}</p>
          <div className="byline">
            <span>{formatRelativeTime(lead.published_at)}</span>
            <span className="dot">·</span>
            <span>Source: {lead.source_name}</span>
          </div>
        </Link>
      )}

      {rest.length > 0 && (
        <>
          <div className="feed-head">
            <h2>Latest</h2>
            <span>
              {rest.length + 1} {rest.length === 0 ? "story" : "stories"}
            </span>
          </div>
          <div className="grid">
            {rest.map((article) => (
              <ArticleCard key={article.slug} article={article} />
            ))}
          </div>
        </>
      )}

      <footer className="site-footer mono">
        <span>© {new Date().getFullYear()} Plume Gaming</span>
        <span>Original reporting with source attribution on every story</span>
      </footer>
    </div>
  );
}

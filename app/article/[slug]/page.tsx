import Link from "next/link";
import { notFound } from "next/navigation";
import Masthead from "@/components/Masthead";
import { getAllArticles, getArticleBySlug, formatRelativeTime } from "@/lib/content";

export function generateStaticParams() {
  return getAllArticles().map((article) => ({ slug: article.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const article = getArticleBySlug(slug);
  if (!article) return {};
  return {
    title: `${article.title} | Plume`,
    description: article.dek,
  };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const article = getArticleBySlug(slug);
  if (!article) notFound();

  return (
    <div className="page">
      <Masthead />
      <article className="article">
        <Link href="/" className="back-link">
          ← Back to Plume
        </Link>
        <div className="kicker-row">
          <span className="pill">{article.category}</span>
        </div>
        <h1>{article.title}</h1>
        <p className="dek">{article.dek}</p>
        <div className="byline">
          <span>By Plume News Agent</span>
          <span className="dot">·</span>
          <span>{formatRelativeTime(article.published_at)}</span>
        </div>

        <div className="body">
          {article.body.map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
        </div>

        {article.tags.length > 0 && (
          <div className="tags">
            {article.tags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
        )}

        <div className="source-box">
          Source:{" "}
          <a href={article.source_url} target="_blank" rel="noopener noreferrer">
            {article.source_name}
          </a>
        </div>
      </article>
    </div>
  );
}

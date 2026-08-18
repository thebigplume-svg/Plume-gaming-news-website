import Image from "next/image";
import Link from "next/link";

export default function Masthead() {
  return (
    <header className="masthead">
      <Link href="/" className="brand">
        <Image
          src="/logo.svg"
          alt=""
          width={240}
          height={240}
          className="logo-mark"
          priority
        />
        <span className="wordmark">
          <span className="mark">
            PLU<em>M</em>E
          </span>
          <span className="tagline">Gaming, reported daily</span>
        </span>
      </Link>
      <nav className="sections">
        <span className="current">News</span>
        <span>Reviews</span>
        <span>Guides</span>
        <span>Esports</span>
      </nav>
    </header>
  );
}

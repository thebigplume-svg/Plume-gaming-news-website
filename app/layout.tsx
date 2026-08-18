import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plume | Gaming, reported daily",
  description:
    "Plume covers current gaming news — releases, industry moves, esports, and hardware — with original summaries linked back to the source.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

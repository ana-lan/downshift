import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Downshift \u00b7 Cut LLM costs per PR",
  description:
    "Find every LLM call in your repo, prove which ones can use cheaper models, and show the cost impact of every PR.",
  openGraph: {
    title: "Downshift \u00b7 Cut LLM costs per PR",
    description:
      "Find every LLM call in your repo, prove which ones can use cheaper models, and show the cost impact of every PR.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem('theme')==='light'){document.documentElement.classList.remove('dark')}}catch(e){}`,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <Nav />
        <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-4 sm:pt-6 pb-10">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}

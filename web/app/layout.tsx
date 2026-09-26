import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

const title = "Downshift \u00b7 Cut LLM costs per PR";
const description =
  "Find every LLM call in your repo, prove which ones can use cheaper models, and show the cost impact of every PR.";

export const metadata: Metadata = {
  title,
  description,
  openGraph: { title, description },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem('theme')==='light'){document.documentElement.classList.remove('dark')}}catch(e){}`,
          }}
        />
      </head>
      <body className={`${inter.variable} ${jetbrains.variable} font-sans antialiased`}>
        <Nav />
        <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-16">{children}</main>
        <Footer />
      </body>
    </html>
  );
}

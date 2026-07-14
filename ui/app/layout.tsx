import type { Metadata } from "next";
import { Providers } from "./providers";
import { ToastHost } from "@/components/toaster";
import { UpdateNotice } from "@/components/update-notice";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local Stream Engine",
  description: "Local real-time streaming and BI control plane",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
        <ToastHost />
        <UpdateNotice />
      </body>
    </html>
  );
}

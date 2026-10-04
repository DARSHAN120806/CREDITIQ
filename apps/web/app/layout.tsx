import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "CreditIQ | Your financial outlook", description: "Understand your risk, explore repayment options and track your financial health." };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }

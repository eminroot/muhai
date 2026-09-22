# Muhai · Akıllı Muhasebe

AI-powered accounting & financial management platform for Turkish SMEs. Clean
white "Precision Ledger" UI with emerald signature, animated analytics, a
dual-language (TR/EN) interface, and a Gemini-powered RAG assistant.

![stack](https://img.shields.io/badge/Vite-React_18-0E9F6E) ![lang](https://img.shields.io/badge/i18n-TR%20%2F%20EN-0A7D56)

## Modules

1. **Fatura Yönetimi (Invoices)** — animated OCR scan demo (Tesseract 5.0 + CNN), auto-parsed line items, confidence scoring.
2. **Vergi & e-Beyanname (Tax)** — live VAT calculator, filing calendar, tax-burden donut, declaration history.
3. **Stok Yönetimi (Inventory)** — real-time movement bars, top-movers, stock table with status.
4. **Bordro & SGK (Payroll)** — one-click payroll run synced with SGK, cost-breakdown donut, employee table.
5. **Finansal Asistan (AI)** — Gemini 2.5 Flash chatbot grounded with RAG over a Firebase RTDB knowledge base; cites its sources.
6. **Akıllı Analitik (Dashboard)** — animated cash-flow area chart, KPI cards with count-up + sparklines, expense breakdown.

## Stack

- **Vite + React 18** (JSX), **react-router-dom** routing
- **Framer Motion** — page transitions, staggered reveals, animated counters
- **Custom SVG charts** — area, grouped bar, donut, sparkline (all self-animating)
- **Firebase RTDB** — RAG knowledge base (`muhai/knowledgeBase`)
- **Gemini 2.5 Flash** via REST — grounded answers in TR/EN
- Fonts: **Clash Display** + **Satoshi** (Fontshare)

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production bundle in dist/
```

## How RAG works

`src/lib/gemini.js` → fetches the knowledge base from Firebase RTDB
(`src/lib/firebase.js`, seeded once from `src/lib/ragKnowledge.js`), retrieves the
top-3 most relevant docs for the question (Turkish-aware keyword/tag scoring in
`ragKnowledge.js → retrieve()`), injects them plus a live business summary into the
Gemini system prompt, and returns the answer with the source documents.

## Structure

This is the web frontend only; it lives in `web/` inside the Muhai repo. The
FastAPI backend is in `../backend/`, project docs in `../docs/`.

```
src/
  i18n/            LanguageContext + TR/EN dictionary
  lib/             firebase, gemini, ragKnowledge, format
  data/            mockData (business figures powering the UI)
  components/
    layout/        Sidebar, Topbar, AppLayout, LanguageToggle
    charts/        AreaChart, BarChart, DonutChart, Sparkline
    ui/            StatCard, Badge, AnimatedNumber
    chatbot/       ChatWidget, ChatMessages, ChatComposer, useChat
  pages/           Landing, Dashboard, Invoices, Tax, Inventory, Payroll, Assistant
  styles/          components, layout, pages, landing, chat
```

## Note on secrets

The Gemini key is no longer hardcoded — it is read from `VITE_GEMINI_API_KEY`
(copy `.env.example` to `.env.local`). Note that **any** `VITE_`-prefixed value is
public once bundled, so this is a stopgap: Phase 1 routes the assistant through the
backend's `/api/chat` instead. The previously committed key must still be rotated
(finding F3 in `../CLAUDE.md`).

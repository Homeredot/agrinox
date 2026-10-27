"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  BadgeCheck,
  BarChart3,
  BookOpen,
  Bot,
  ExternalLink,
  FileSearch,
  History,
  Languages,
  LibraryBig,
  LoaderCircle,
  MessageCircleQuestion,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import type { Language } from "@/lib/i18n";
import DistrictIntelligence from "./DistrictIntelligence";

type Source = { id: number; title: string; publisher: string; url: string; published_date?: string | null };
type Article = {
  id: number;
  slug: string;
  title_en: string;
  title_rw: string;
  title: string;
  summary: string;
  content_en?: string;
  content_rw?: string;
  content?: string;
  category: string;
  author: string;
  reviewer: string;
  review_status: string;
  last_updated: string;
  sources: Source[];
};
type Citation = { article_id: number | null; article_title: string; source_url: string; rank: number; score: number };
type Message = { id?: number; role: "user" | "assistant"; content: string; response_mode?: string | null; model_name?: string | null; citations?: Citation[] };
type Conversation = { id: number; title: string; language: Language; updated_at: string; messages?: Message[] };
type Overview = { article_count: number; verified_count: number; categories: string[]; ai_available: boolean; model?: string | null };

const CATEGORY_NAMES: Record<string, { en: string; rw: string }> = {
  rwandan_crops: { en: "Rwandan crops", rw: "Ibihingwa byo mu Rwanda" },
  planting_seasons: { en: "Planting seasons", rw: "Ibihembwe by'ihinga" },
  soil_management: { en: "Soil management", rw: "Imicungire y'ubutaka" },
  irrigation_practices: { en: "Irrigation", rw: "Kuhira" },
  crop_diseases: { en: "Crop diseases", rw: "Indwara z'ibihingwa" },
  pest_management: { en: "Pest management", rw: "Kurwanya udukoko" },
  harvesting_practices: { en: "Harvesting", rw: "Gusarura" },
  storage_practices: { en: "Storage", rw: "Guhunika" },
  agricultural_terminology: { en: "Terminology", rw: "Amagambo y'ubuhinzi" },
  traditional_knowledge: { en: "Gakondo", rw: "Ubumenyi gakondo" },
  organizations_programs: { en: "Organizations & programs", rw: "Ibigo na gahunda" },
};

function categoryName(category: string, language: Language) {
  return CATEGORY_NAMES[category]?.[language] ?? category.replaceAll("_", " ");
}

export default function KnowledgeBase({ token, language }: { token: string; language: Language }) {
  const [feature, setFeature] = useState<"library" | "district">("library");
  const [answerLanguage, setAnswerLanguage] = useState<Language>(language);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [question, setQuestion] = useState("");
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setAnswerLanguage(language);
  }, [language]);

  useEffect(() => {
    let active = true;
    Promise.all([
      api<Overview>("/knowledge/overview", {}, token),
      api<Conversation[]>("/knowledge/conversations", {}, token),
    ])
      .then(([summary, history]) => {
        if (!active) return;
        setOverview(summary);
        setConversations(history);
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Could not load the knowledge base"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ language: answerLanguage });
      if (query.trim()) params.set("q", query.trim());
      if (category) params.set("category", category);
      api<Article[]>(`/knowledge/articles?${params}`, {}, token)
        .then(setArticles)
        .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Search failed"));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [answerLanguage, category, query, token]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  const words = useMemo(
    () => ({
      heading: answerLanguage === "rw" ? "Ubumenyi bwizewe ku buhinzi bwo mu Rwanda" : "Verified knowledge for Rwandan agriculture",
      subheading: answerLanguage === "rw" ? "Shakisha inyandiko zifite amasoko, ubaze umufasha, cyangwa usesengure imibare ya NISR ku turere." : "Search sourced articles, ask the verified assistant, or explore official NISR district statistics.",
      all: answerLanguage === "rw" ? "Byose" : "All topics",
      search: answerLanguage === "rw" ? "Shakisha Tubura, ibihembwe, kuhira…" : "Search Tubura, seasons, irrigation…",
      ask: answerLanguage === "rw" ? "Baza ikibazo cy'ubuhinzi…" : "Ask an agricultural question…",
      empty: answerLanguage === "rw" ? "Nta nyandiko ibonetse." : "No matching verified article.",
    }),
    [answerLanguage],
  );

  async function openArticle(slug: string) {
    try {
      setSelectedArticle(await api<Article>(`/knowledge/articles/${slug}?language=${answerLanguage}`, {}, token));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not open article");
    }
  }

  async function openConversation(id: number) {
    try {
      const record = await api<Conversation>(`/knowledge/conversations/${id}`, {}, token);
      setConversationId(record.id);
      setAnswerLanguage(record.language);
      setMessages(record.messages ?? []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not open conversation");
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setQuestion("");
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || asking) return;
    setQuestion("");
    setError("");
    setMessages((current) => [...current, { role: "user", content: text }]);
    setAsking(true);
    try {
      const result = await api<{
        conversation_id: number;
        answer: string;
        response_mode: string;
        model_name?: string | null;
        citations: Citation[];
      }>(
        "/knowledge/ask",
        { method: "POST", body: JSON.stringify({ question: text, language: answerLanguage, conversation_id: conversationId }) },
        token,
      );
      setConversationId(result.conversation_id);
      setMessages((current) => [...current, {
        role: "assistant", content: result.answer, response_mode: result.response_mode,
        model_name: result.model_name, citations: result.citations,
      }]);
      setConversations(await api<Conversation[]>("/knowledge/conversations", {}, token));
    } catch (requestError) {
      setMessages((current) => current.slice(0, -1));
      setQuestion(text);
      setError(requestError instanceof Error ? requestError.message : "Could not answer the question");
    } finally {
      setAsking(false);
    }
  }

  if (loading) {
    return <div className="grid min-h-[65vh] place-items-center"><LoaderCircle className="animate-spin text-[#d5a74e]" size={38} /></div>;
  }

  return (
    <div>
      <header className="theme-on-dark relative isolate overflow-hidden rounded-3xl border border-[#596044] bg-[#20271d] p-4 shadow-2xl shadow-black/20 sm:p-8">
        <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-[center_48%]" style={{ backgroundImage: "url('/rwanda-knowledge-hero.jpg')" }}/>
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(19,27,18,.96)_0%,rgba(25,35,21,.87)_48%,rgba(27,43,24,.56)_100%)]"/>
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-t from-[#151b14]/85 via-transparent to-black/20"/>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <h1 className="text-2xl font-semibold drop-shadow-md sm:text-4xl">{words.heading}</h1>
            <p className="mobile-secondary mt-2 max-w-2xl text-[#dce3dc] drop-shadow-sm">{words.subheading}</p>
          </div>
          <button
            onClick={() => setAnswerLanguage((current) => current === "en" ? "rw" : "en")}
            className="flex items-center gap-2 rounded-full border border-white/25 bg-black/35 px-4 py-2 text-sm font-semibold shadow-lg backdrop-blur-md hover:bg-black/50"
          >
            <Languages size={17} /> {answerLanguage === "en" ? "Kinyarwanda" : "English"}
          </button>
        </div>
        <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={answerLanguage === "rw" ? "Inyandiko" : "Articles"} value={overview?.article_count ?? 0} />
          <Stat label={answerLanguage === "rw" ? "Zagenzuwe" : "Source verified"} value={overview?.verified_count ?? 0} />
          <Stat label={answerLanguage === "rw" ? "Ibyiciro" : "Categories"} value={overview?.categories.length ?? 0} />
          <div className="flex min-h-[86px] items-center justify-center rounded-2xl border border-white/15 bg-[#172019]/80 p-4 shadow-lg backdrop-blur-md">
            <p className="flex items-center gap-2 font-semibold tracking-wide text-[#cddba9]">
              {overview?.ai_available ? <Sparkles size={18} /> : <FileSearch size={18} />}
              AI ASSISTANT
            </p>
          </div>
        </div>
      </header>

      <div className="mt-5 flex max-w-2xl gap-2 rounded-2xl border border-[#41463e] bg-[#222522] p-1.5">
        <button
          type="button"
          onClick={() => setFeature("library")}
          className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition ${feature === "library" ? "bg-[#665332] text-[#ffe0a0] shadow-sm" : "text-[#aeb5ae] hover:bg-[#2d302c]"}`}
        >
          <LibraryBig size={17} /> Knowledge Library &amp; AI
        </button>
        <button
          type="button"
          onClick={() => setFeature("district")}
          className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition ${feature === "district" ? "bg-[#34452d] text-[#c9e59a] shadow-sm" : "text-[#aeb5ae] hover:bg-[#2d302c]"}`}
        >
          <BarChart3 size={17} /> District Agricultural Intelligence
        </button>
      </div>

      {feature === "district" ? (
        <div className="mt-7">
          <DistrictIntelligence token={token} />
        </div>
      ) : (
        <>
          {error && (
            <div role="alert" className="mt-5 flex items-center justify-between rounded-xl border border-[#713e3e] bg-[#3b2424] p-4 text-[#ffc1c1]">
              {error}<button onClick={() => setError("")} aria-label="Close error"><X size={18} /></button>
            </div>
          )}

          <div className="mt-7 grid gap-6 xl:grid-cols-[1.05fr_.95fr]">
        <section className="min-w-0">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[#90958f]" size={18} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={words.search} className="h-12 w-full rounded-2xl border border-[#434843] bg-[#232624] pl-11 pr-4 outline-none focus:border-[#71844a]" />
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto pb-2">
            <button onClick={() => setCategory("")} className={`whitespace-nowrap rounded-full px-3 py-2 text-xs font-semibold ${!category ? "bg-[#697b37] text-white" : "border border-[#454a45] text-[#b7bcb8]"}`}>{words.all}</button>
            {overview?.categories.map((item) => (
              <button key={item} onClick={() => setCategory(item)} className={`whitespace-nowrap rounded-full px-3 py-2 text-xs font-semibold ${category === item ? "bg-[#697b37] text-white" : "border border-[#454a45] text-[#b7bcb8]"}`}>{categoryName(item, answerLanguage)}</button>
            ))}
          </div>
          <div className="mt-3 space-y-3">
            {articles.map((article) => (
              <button key={article.id} onClick={() => void openArticle(article.slug)} className="group w-full rounded-2xl border border-[#3e433f] bg-[#232624] p-5 text-left hover:border-[#69734f] hover:bg-[#282c27]">
                <div className="flex items-start justify-between gap-3">
                  <span className="rounded-full bg-[#31382a] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#b9d281]">{categoryName(article.category, answerLanguage)}</span>
                  <BadgeCheck size={18} className="shrink-0 text-[#71bc7e]" />
                </div>
                <h2 className="mt-3 text-lg font-semibold group-hover:text-[#dbe9b5]">{article.title}</h2>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#aeb4af]">{article.summary}</p>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[#373c38] pt-3 text-xs text-[#7f8781]">
                  <span>{article.sources[0]?.publisher}</span>
                  <span>{new Date(article.last_updated).toLocaleDateString()}</span>
                </div>
              </button>
            ))}
            {!articles.length && <div className="rounded-2xl border border-dashed border-[#464b47] p-10 text-center text-[#8e958f]"><BookOpen className="mx-auto mb-3" />{words.empty}</div>}
          </div>
        </section>

        <section className="xl:sticky xl:top-24 xl:h-[calc(100vh-7rem)]">
          <div className="flex h-full min-h-[650px] flex-col overflow-hidden rounded-3xl border border-[#454239] bg-[#22231f]">
            <div className="border-b border-[#3d3d35] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#6d5530] text-[#ffdfa0]"><Bot size={21} /></span>
                  <div><h2 className="font-semibold">Agrinox Knowledge Assistant</h2><p className="text-xs text-[#90968f]">Verified library + trusted web sources · citations included</p></div>
                </div>
                <button onClick={newConversation} className="rounded-full border border-[#51544c] px-3 py-1.5 text-xs hover:bg-[#30322e]">New chat</button>
              </div>
              {!!conversations.length && (
                <div className="mt-3 flex gap-2 overflow-x-auto">
                  <History size={15} className="mt-2 shrink-0 text-[#8f958f]" />
                  {conversations.slice(0, 5).map((item) => (
                    <button key={item.id} onClick={() => void openConversation(item.id)} className={`max-w-40 truncate rounded-full px-3 py-1.5 text-xs ${conversationId === item.id ? "bg-[#4e5e31] text-white" : "bg-[#30322f] text-[#b2b6b2]"}`}>{item.title}</button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {!messages.length && (
                <div className="grid h-full place-items-center text-center">
                  <div className="max-w-sm"><MessageCircleQuestion className="mx-auto text-[#cda75c]" size={38} /><h3 className="mt-4 text-xl font-semibold">Ask from verified records</h3><p className="mt-2 text-sm leading-6 text-[#969c96]">Try “What does Tubura mean?” or “Ni ryari igihembwe A gitangira?”</p></div>
                </div>
              )}
              {messages.map((message, index) => (
                <div key={message.id ?? `${message.role}-${index}`} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  {message.role === "assistant" && <span className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#6d5530]"><Bot size={16} /></span>}
                  <div className={`max-w-[84%] rounded-2xl p-3.5 ${message.role === "user" ? "bg-[#465c31] text-white" : "border border-[#41423a] bg-[#292a26]"}`}>
                    <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                    {message.role === "assistant" && (
                      <div className="mt-3 border-t border-[#41423a] pt-2">
                        <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#8fb986]"><ShieldCheck size={13} /> {message.citations?.length ? "Verified AI answer · sources included" : "AI Assistant"}</p>
                        {!!message.citations?.length && <div className="mt-2 space-y-1.5">{message.citations.map((citation) => <a key={`${citation.rank}-${citation.article_id}`} href={citation.source_url} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-xs text-[#d2b879] hover:underline"><span>[{citation.rank}]</span><span>{citation.article_title}</span><ExternalLink className="mt-0.5 shrink-0" size={12} /></a>)}</div>}
                      </div>
                    )}
                  </div>
                  {message.role === "user" && <span className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#3d4b3f]"><UserRound size={16} /></span>}
                </div>
              ))}
              {asking && <div className="flex items-center gap-3 text-sm text-[#aeb3ae]"><span className="grid h-8 w-8 place-items-center rounded-full bg-[#6d5530]"><LoaderCircle className="animate-spin" size={16} /></span>Searching verified records…</div>}
              <div ref={chatEnd} />
            </div>
            <form onSubmit={ask} className="border-t border-[#3d3d35] p-4">
              <div className="flex items-end gap-2 rounded-2xl border border-[#4a4d45] bg-[#292b27] p-2 focus-within:border-[#7c865b]">
                <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows={2} placeholder={words.ask} className="max-h-32 min-h-12 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none" />
                <button disabled={asking || !question.trim()} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#71803d] text-white disabled:opacity-40" aria-label="Send question"><ArrowUp size={19} /></button>
              </div>
              <p className="mt-2 text-center text-[10px] text-[#777d77]">No verified record → no invented answer. Confirm treatments with RAB or an agronomist.</p>
            </form>
          </div>
        </section>
          </div>

          {selectedArticle && (
            <div className="fixed inset-0 z-[1300] flex items-end overflow-y-auto bg-black/75 p-0 backdrop-blur-sm sm:block sm:p-4" onClick={() => setSelectedArticle(null)}>
          <article className="mx-auto max-h-[calc(100dvh-0.5rem)] w-full max-w-4xl overflow-y-auto rounded-t-3xl border border-[#4a4b41] bg-[#22241f] shadow-2xl sm:my-8 sm:max-h-[calc(100dvh-4rem)] sm:rounded-3xl" onClick={(event) => event.stopPropagation()}>
            <header className="relative border-b border-[#3c433b] bg-[linear-gradient(135deg,#29342a,#22251f)] px-5 pb-6 pt-5 sm:px-9 sm:pb-8 sm:pt-8">
              <button onClick={() => setSelectedArticle(null)} className="absolute right-4 top-4 grid h-10 w-10 place-items-center rounded-full border border-white/10 bg-black/15 hover:bg-white/10" aria-label="Close article"><X size={18} /></button>
              <span className="inline-flex rounded-full bg-[#3a482f] px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-[#c4de8d]">{categoryName(selectedArticle.category, answerLanguage)}</span>
              <h2 className="mt-4 max-w-3xl pr-10 text-2xl font-semibold leading-tight sm:text-4xl">{selectedArticle.title}</h2>
              <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#929b93]"><span>{answerLanguage === "rw" ? "Yanditswe na" : "By"} <strong className="font-semibold text-[#c6cec7]">{selectedArticle.author}</strong></span><span className="inline-flex items-center gap-1 text-[#8fc78d]"><BadgeCheck size={14}/>{selectedArticle.review_status.replaceAll("_", " ")}</span><span>{answerLanguage === "rw" ? "Yavuguruwe" : "Updated"} {new Date(selectedArticle.last_updated).toLocaleDateString()}</span></div>
            </header>
            <div className="px-5 py-6 sm:px-9 sm:py-8">
              <ArticleBody content={selectedArticle.content || ""} language={answerLanguage}/>
              <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#3d443d] pt-4"><p className="text-xs text-[#838c84]">{answerLanguage === "rw" ? "Byasuzumwe na" : "Reviewed by"} <strong className="font-medium text-[#aeb7af]">{selectedArticle.reviewer}</strong></p><div className="flex flex-wrap items-center gap-2"><span className="mr-1 text-[10px] font-bold uppercase tracking-[.16em] text-[#7f8981]">{answerLanguage === "rw" ? "Amasoko" : "Sources"}</span>{selectedArticle.sources.map((source, index) => <SourceReference key={source.id} source={source} index={index + 1} language={answerLanguage}/>)}</div></div>
            </div>
          </article>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RichSentence({ text }: { text: string }) {
  const pattern = /(‘[^’]+’|“[^”]+”|"[^"]+"|\([^)]{2,}\)|\b(?:MINAGRI|NISR|RAB|SAS|IPM|Tubura|One Acre Fund|Season [ABC]|Igihembwe [ABC])\b)/giu;
  return <>{text.split(pattern).filter(Boolean).map((part, index) => {
    if (/^[‘“"(]/u.test(part)) return <em key={`${part}-${index}`} className="text-[#d8cda9]">{part}</em>;
    if (/^(MINAGRI|NISR|RAB|SAS|IPM|Tubura|One Acre Fund|Season [ABC]|Igihembwe [ABC])$/iu.test(part)) return <strong key={`${part}-${index}`} className="font-semibold text-[#e5eadf]">{part}</strong>;
    return <span key={`${part}-${index}`}>{part}</span>;
  })}</>;
}

function ArticleBody({ content, language }: { content: string; language: Language }) {
  const sentences = (content.replace(/\s+/g, " ").match(/[^.!?]+(?:[.!?]+|$)/g) || [content]).map((item) => item.trim()).filter(Boolean);
  const lead = sentences[0] || content;
  const keyPoint = sentences.length > 1 ? sentences[sentences.length - 1] : null;
  const details = sentences.slice(1, keyPoint ? -1 : undefined);
  return <section className="knowledge-article-copy">
    <p className="border-l-4 border-[#8ebc61] pl-4 text-lg font-medium leading-8 text-[#e1e6de] sm:text-xl"><RichSentence text={lead}/></p>
    {details.length > 0 && <section className="mt-7"><h3 className="text-xs font-bold uppercase tracking-[.18em] text-[#94bd72]">{language === "rw" ? "Ibisobanuro by'ingenzi" : "What the verified record says"}</h3><div className="mt-4 space-y-4">{details.map((sentence, index) => <p key={`${sentence}-${index}`} className="text-[15px] leading-7 text-[#bcc5bd]"><RichSentence text={sentence}/></p>)}</div></section>}
    {keyPoint && <aside className="mt-7 rounded-2xl border border-[#596344] bg-[#2d3327] p-4 sm:p-5"><mark className="rounded-md bg-[#d6b75a] px-2 py-1 text-[10px] font-bold uppercase tracking-[.16em] text-[#29210d]">{language === "rw" ? "Icy'ingenzi" : "Key point"}</mark><p className="mt-3 text-[15px] font-medium leading-7 text-[#e1dfcf]"><RichSentence text={keyPoint}/></p></aside>}
  </section>;
}

function sourceLabel(source: Source) {
  const publisher = source.publisher.toLowerCase();
  if (publisher.includes("national institute of statistics")) return "NISR";
  if (publisher.includes("agriculture and animal resources development board")) return "RAB";
  if (publisher.includes("ministry of agriculture")) return "MINAGRI";
  if (publisher.includes("one acre fund")) return "Tubura";
  return source.publisher.split(/\s+/).slice(0, 2).join(" ");
}

function SourceReference({ source, index, language }: { source: Source; index: number; language: Language }) {
  return <details className="group relative"><summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-full border border-[#465047] bg-[#292f2a] px-2.5 text-[11px] font-semibold text-[#aeb9af] hover:border-[#748066] hover:text-[#dce5d8] [&::-webkit-details-marker]:hidden"><span className="text-[#c6a95b]">[{index}]</span>{sourceLabel(source)}</summary><div role="tooltip" className="invisible absolute bottom-10 right-0 z-20 w-64 max-w-[calc(100vw-3rem)] translate-y-1 rounded-xl border border-[#566050] bg-[#1d211d] p-3 opacity-0 shadow-2xl transition group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-open:visible group-open:translate-y-0 group-open:opacity-100"><strong className="block text-xs leading-5 text-[#e0e5df]">{source.title}</strong><span className="mt-1 block text-[11px] leading-4 text-[#929c94]">{source.publisher}{source.published_date ? ` · ${source.published_date}` : ""}</span><a href={source.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-[#b8cf79] hover:underline">{language === "rw" ? "Fungura isoko" : "Open source"}<ExternalLink size={11}/></a></div></details>;
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-2xl border border-white/15 bg-[#172019]/80 p-4 shadow-lg backdrop-blur-md"><p className="text-xs uppercase tracking-wider text-[#b2bdb3]">{label}</p><strong className="mt-1 block text-2xl text-[#f0f4ee]">{value}</strong></div>;
}

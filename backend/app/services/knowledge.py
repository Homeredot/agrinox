import re
from difflib import SequenceMatcher, get_close_matches
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import (
    KnowledgeArticle,
    KnowledgeConversation,
    KnowledgeMessage,
    KnowledgeRetrieval,
    KnowledgeSource,
)
from app.services.knowledge_seed import KNOWLEDGE_SEED


VERIFIED_STATUSES = {"source_verified", "agronomist_reviewed"}
TRUSTED_AGRICULTURE_DOMAINS = [
    "rab.gov.rw",
    "minagri.gov.rw",
    "statistics.gov.rw",
    "microdata.statistics.gov.rw",
    "meteo.gov.rw",
    "rwanda.gov.rw",
    "fao.org",
    "cgiar.org",
    "irri.org",
    "cipotato.org",
    "oneacrefund.org",
]
STOP_WORDS = {
    "about", "after", "and", "are", "can", "does", "for", "from", "how", "into", "the", "this", "what", "when", "where", "with",
    "ari", "iki", "ku", "mu", "na", "ni", "uko", "yo", "za", "zo",
}

CATEGORY_TERMS = {
    "rwandan_crops": {"crop", "crops", "production", "yield", "statistics", "ibihingwa", "umusaruro", "imibare"},
    "planting_seasons": {"plant", "planting", "sow", "season", "seasons", "calendar", "gutera", "igihembwe", "ibihembwe", "ihinga"},
    "soil_management": {"soil", "fertility", "fertilizer", "compost", "erosion", "npk", "ubutaka", "ifumbire", "uburumbuke"},
    "irrigation_practices": {"irrigate", "irrigation", "water", "rain", "moisture", "kuhira", "amazi", "imvura", "ubuhehere"},
    "crop_diseases": {"disease", "diseases", "sick", "symptom", "symptoms", "infection", "indwara", "ibimenyetso"},
    "pest_management": {"pest", "pests", "insect", "insects", "worm", "worms", "ipm", "udukoko", "agakoko"},
    "harvesting_practices": {"harvest", "harvesting", "ripe", "maturity", "gusarura", "isarura"},
    "storage_practices": {"store", "storage", "postharvest", "post-harvest", "warehouse", "guhunika", "ububiko"},
    "agricultural_terminology": {"term", "terms", "definition", "meaning", "sas", "extension", "ijambo", "amagambo", "igisobanuro"},
    "traditional_knowledge": {"traditional", "tradition", "gakondo", "umuco"},
    "organizations_programs": {"organization", "organizations", "programme", "program", "tubura", "minagri", "rab", "nisr", "one acre"},
}

CASUAL_PHRASES = {
    "hello", "hello there", "hi", "hi there", "hey", "hey there",
    "good morning", "good afternoon", "good evening",
    "muraho", "bite", "amakuru", "mwaramutse", "mwiriwe", "uraho",
    "thank you", "thanks", "murakoze", "bye", "goodbye",
    "who are you", "what can you do", "uri nde", "wakora iki",
}

# Retrieval hints only: these connect common English and Kinyarwanda farming
# concepts without adding any factual claim to an answer.
CONCEPT_GROUPS = (
    {"crop", "igihingwa", "ibihingwa"},
    {"potato", "ibirayi"},
    {"tomato", "inyanya"},
    {"maize", "corn", "ibigori"},
    {"bean", "beans", "ibishyimbo"},
    {"rice", "umuceri"},
    {"season", "seasons", "igihembwe", "ibihembwe", "ihinga"},
    {"soil", "ubutaka"},
    {"fertilizer", "ifumbire"},
    {"irrigation", "irrigate", "kuhira", "amazi"},
    {"rain", "rainfall", "imvura"},
    {"disease", "diseases", "indwara"},
    {"pest", "pests", "udukoko"},
    {"harvest", "harvesting", "gusarura", "isarura"},
    {"storage", "store", "guhunika", "ububiko"},
    {"meaning", "definition", "igisobanuro", "bisobanura"},
)

COMMON_QUERY_CORRECTIONS = {
    "igihebwe": "igihembwe",
    "igihemwe": "igihembwe",
    "ibiray": "ibirayi",
    "ibirai": "ibirayi",
    "ifumbir": "ifumbire",
    "irrigaton": "irrigation",
    "irigation": "irrigation",
    "potatoe": "potato",
    "tuburra": "tubura",
}


def seed_knowledge(db: Session) -> None:
    existing = set(db.scalars(select(KnowledgeArticle.slug)).all())
    changed = False
    for record in KNOWLEDGE_SEED:
        if record["slug"] in existing:
            continue
        article = KnowledgeArticle(
            slug=record["slug"], title_en=record["title_en"], title_rw=record["title_rw"],
            content_en=record["content_en"], content_rw=record["content_rw"], category=record["category"],
            author="Agrinox knowledge team", reviewer="Source verification review",
            review_status="source_verified", last_updated=datetime.now(timezone.utc),
        )
        for title, publisher, url, published_date in record["sources"]:
            article.sources.append(KnowledgeSource(
                title=title, publisher=publisher, url=url, published_date=published_date,
            ))
        db.add(article)
        changed = True
    if changed:
        db.commit()


def source_view(source: KnowledgeSource) -> dict:
    return {
        "id": source.id, "title": source.title, "publisher": source.publisher,
        "url": source.url, "published_date": source.published_date,
    }


def article_summary(content: str, limit: int = 220) -> str:
    clean = " ".join(content.split())
    sentences = re.findall(r"[^.!?]+(?:[.!?]+|$)", clean)
    candidate = " ".join(sentence.strip() for sentence in sentences[:2] if sentence.strip()) or clean
    if len(candidate) <= limit:
        return candidate
    shortened = candidate[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{shortened}…"


def article_view(article: KnowledgeArticle, language: str = "en", include_content: bool = True) -> dict:
    content = article.content_rw if language == "rw" else article.content_en
    result = {
        "id": article.id, "slug": article.slug, "title_en": article.title_en, "title_rw": article.title_rw,
        "title": article.title_rw if language == "rw" else article.title_en,
        "category": article.category, "author": article.author, "reviewer": article.reviewer,
        "review_status": article.review_status, "last_updated": article.last_updated.isoformat(),
        "sources": [source_view(source) for source in article.sources],
        "summary": article_summary(content),
    }
    if include_content:
        result.update({"content_en": article.content_en, "content_rw": article.content_rw, "content": content})
    return result


def normalized_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text.lower())
    result = set()
    for word in words:
        if len(word) < 3 or word in STOP_WORDS:
            continue
        for suffix in ("ing", "es", "s"):
            if word.endswith(suffix) and len(word) > len(suffix) + 3:
                word = word[:-len(suffix)]
                break
        result.add(word)
    return result


def _correct_tokens(tokens: set[str], vocabulary: set[str]) -> set[str]:
    """Conservatively repair likely spelling mistakes for retrieval only."""
    corrected = set()
    choices = sorted(word for word in vocabulary if len(word) >= 4)
    for token in tokens:
        if token in vocabulary:
            corrected.add(token)
            continue
        if token in COMMON_QUERY_CORRECTIONS:
            corrected.add(COMMON_QUERY_CORRECTIONS[token])
            continue
        if len(token) < 4:
            corrected.add(token)
            continue
        match = get_close_matches(token, choices, n=1, cutoff=0.79)
        # Keep corrections close in length so a vague word cannot silently turn
        # into an unrelated agricultural concept.
        if match and abs(len(match[0]) - len(token)) <= 2:
            corrected.add(match[0])
        else:
            corrected.add(token)
    return corrected


def _expand_concepts(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in CONCEPT_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


def _interpreted_question(
    question: str,
    retrieved: list[tuple[KnowledgeArticle, float]],
) -> str:
    vocabulary = set(COMMON_QUERY_CORRECTIONS.values())
    for article, _score in retrieved:
        vocabulary.update(normalized_tokens(
            f"{article.title_en} {article.title_rw} {article.content_en} {article.content_rw}"
        ))

    def replace(match: re.Match) -> str:
        original = match.group(0)
        corrected = next(iter(_correct_tokens({original.lower()}, vocabulary)))
        return corrected.capitalize() if original[:1].isupper() else corrected

    return re.sub(r"[a-zA-ZÀ-ÿ0-9]+", replace, question)


def query_categories(query: str) -> set[str]:
    lowered = query.lower()
    words = set(re.findall(r"[a-zA-ZÀ-ÿ0-9-]+", lowered))
    return {
        category for category, terms in CATEGORY_TERMS.items()
        if any((term in lowered if " " in term else term in words) for term in terms)
    }


def retrieve_articles(db: Session, query: str, limit: int = 5) -> list[tuple[KnowledgeArticle, float]]:
    articles = db.scalars(
        select(KnowledgeArticle)
        .where(KnowledgeArticle.review_status.in_(VERIFIED_STATUSES))
        .options(selectinload(KnowledgeArticle.sources))
    ).all()
    raw_query_tokens = normalized_tokens(query)
    if not raw_query_tokens:
        return []
    vocabulary = set(COMMON_QUERY_CORRECTIONS.values())
    for article in articles:
        vocabulary.update(normalized_tokens(
            f"{article.title_en} {article.title_rw} {article.content_en} {article.content_rw} {article.category.replace('_', ' ')}"
        ))
    corrected_tokens = _correct_tokens(raw_query_tokens, vocabulary)
    query_tokens = _expand_concepts(corrected_tokens)
    interpreted_query = " ".join(sorted(query_tokens))
    intended_categories = query_categories(f"{query} {interpreted_query}")
    lowered = query.strip().lower()
    ranked = []
    for article in articles:
        title_tokens = normalized_tokens(f"{article.title_en} {article.title_rw}")
        body_tokens = normalized_tokens(f"{article.content_en} {article.content_rw} {article.category.replace('_', ' ')}")
        title_hits = len(query_tokens & title_tokens)
        body_hits = len(query_tokens & body_tokens)
        fuzzy_title_hits = sum(
            1 for token in query_tokens
            if token not in title_tokens
            and any(SequenceMatcher(None, token, candidate).ratio() >= 0.88 for candidate in title_tokens)
        )
        haystack = f"{article.title_en} {article.title_rw} {article.content_en} {article.content_rw}".lower()
        phrase_bonus = 8 if len(lowered) >= 5 and lowered in haystack else 0
        category_bonus = 10 if article.category in intended_categories else 0
        score = title_hits * 6 + fuzzy_title_hits * 4 + body_hits * 1.5 + phrase_bonus + category_bonus
        # One incidental body-word match is not enough evidence. A result needs a
        # title match, a clear question intent/category match, or several body hits.
        if score >= 6 and (title_hits or fuzzy_title_hits or category_bonus or body_hits >= 4):
            ranked.append((article, float(score)))
    ranked.sort(key=lambda item: (-item[1], item[0].title_en))
    if not ranked:
        return []
    strongest = ranked[0][1]
    return [item for item in ranked if item[1] >= strongest * 0.65][:limit]


def _extract_gemini_result(payload: dict, citation_offset: int = 0) -> tuple[str | None, list[dict]]:
    candidates = payload.get("candidates") or []
    if not candidates:
        return None, []
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    # Thinking models may return internal thought summaries as text parts. Only
    # user-facing answer parts belong in the chat response.
    text = "\n".join(
        part.get("text", "")
        for part in parts
        if part.get("text") and not part.get("thought", False)
    ).strip()
    metadata = candidate.get("groundingMetadata") or {}
    chunks = metadata.get("groundingChunks") or []
    citations = []
    chunk_to_rank = {}
    seen_urls = set()
    for chunk_index, chunk in enumerate(chunks):
        web = chunk.get("web") or {}
        url = web.get("uri")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        rank = citation_offset + len(citations) + 1
        chunk_to_rank[chunk_index] = rank
        citations.append({
            "article_id": None,
            "article_title": (web.get("title") or "Gemini grounded web source")[:240],
            "source_url": url[:1000],
            "score": 1.0,
        })

    # Gemini returns exact text segments linked to grounding chunks. Add compact
    # markers to those segments while the UI renders each numbered source below.
    supports = sorted(
        metadata.get("groundingSupports") or [],
        key=lambda item: item.get("segment", {}).get("endIndex", 0),
        reverse=True,
    )
    for support in supports:
        end_index = support.get("segment", {}).get("endIndex")
        ranks = [chunk_to_rank[index] for index in support.get("groundingChunkIndices", []) if index in chunk_to_rank]
        if isinstance(end_index, int) and 0 <= end_index <= len(text) and ranks:
            marker = " " + "".join(f"[{rank}]" for rank in sorted(set(ranks)))
            text = text[:end_index] + marker + text[end_index:]
    return text or None, citations


def _is_casual_conversation(question: str) -> bool:
    normalized = re.sub(r"[^a-zA-ZÀ-ÿ']+", " ", question.lower()).strip()
    if normalized in CASUAL_PHRASES:
        return True
    # Farmers often type on small phone keyboards. A close spelling is accepted
    # only for a short chat message; agricultural questions still require evidence.
    if not normalized or len(normalized.split()) > 3:
        return False
    return any(
        abs(len(normalized) - len(phrase)) <= 2
        and SequenceMatcher(None, normalized, phrase).ratio() >= 0.78
        for phrase in CASUAL_PHRASES
    )


def _gemini_answer(
    question: str,
    language: str,
    retrieved: list[tuple[KnowledgeArticle, float]],
    history: list[KnowledgeMessage],
) -> tuple[str, list[dict], str, str] | None:
    if not settings.gemini_api_key:
        return None
    language_name = "Kinyarwanda" if language == "rw" else "English"
    models = list(dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]))

    # Greetings and simple conversational messages do not require factual
    # retrieval or Google Search. Send them directly to Gemini and prefer the
    # lower-demand fallback model for a faster response.
    if _is_casual_conversation(question):
        casual_body = {
            "systemInstruction": {"parts": [{"text": (
                "You are Agrinox's friendly agricultural assistant. "
                f"Reply only in {language_name}. Respond naturally in one or two short sentences. "
                "For a greeting, greet the farmer and briefly invite an agricultural question. "
                "Do not make factual agricultural claims in this conversational reply."
            )}]},
            "contents": [{"role": "user", "parts": [{"text": question.strip()}]}],
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.3,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        for model in reversed(models):
            try:
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                    json=casual_body,
                    timeout=25,
                )
                response.raise_for_status()
                text, _citations = _extract_gemini_result(response.json())
                if text:
                    return text, [], model, "gemini_conversation"
            except (httpx.HTTPError, ValueError):
                continue
        return None

    records = []
    for index, (article, _score) in enumerate(retrieved, 1):
        content = article.content_rw if language == "rw" else article.content_en
        sources = ", ".join(source.url for source in article.sources)
        records.append(f"[{index}] {article.title_rw if language == 'rw' else article.title_en}\n{content}\nSources: {sources}")
    recent = "\n".join(f"{message.role}: {message.content}" for message in history[-6:])
    interpreted_question = _interpreted_question(question, retrieved)
    instructions = (
        "You are Agrinox's retrieval-grounded agricultural assistant. "
        f"Answer only in {language_name}. First use the supplied verified records. When they are insufficient, use web search only for trusted primary agricultural or Rwanda government sources. "
        f"Preferred source domains are: {', '.join(TRUSTED_AGRICULTURE_DOMAINS)}. "
        "Never use general model memory as evidence. Never invent policies, statistics, pesticide treatments, fertilizer rates, eligibility rules, or source details. "
        "Cite every factual answer using the supplied record numbers or web-search citations. If neither source type answers the question, say verified information is unavailable. "
        "The farmer may make spelling mistakes in English or Kinyarwanda. Infer an obvious correction from the verified records; when two meanings are plausible, ask one short clarifying question instead of guessing. "
        "When the prompt includes an interpreted question, answer that corrected intent directly and do not discuss the typo unless the correction is genuinely ambiguous. "
        "Give the direct answer in the first sentence. Use at most three short sentences or three short bullets. "
        "Do not repeat the question, introduce the topic, copy an entire record, or add generic filler. State an important limitation only when it affects the decision."
    )
    interpretation = (
        f"\nInterpreted question after conservative spelling correction:\n{interpreted_question}"
        if interpreted_question.lower() != question.lower() else ""
    )
    prompt = f"Recent local conversation:\n{recent}\n\nOriginal question:\n{question}{interpretation}\n\nVerified records:\n" + "\n\n".join(records)
    body = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "maxOutputTokens": 1000,
            "temperature": 0.2,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    transient_statuses = {429, 500, 502, 503, 504}
    for model in models:
        for attempt in range(1):
            try:
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                    json=body,
                    timeout=40,
                )
                if response.status_code in transient_statuses:
                    # Move directly to the fallback model. Waiting and retrying
                    # an overloaded primary made the chat appear unresponsive.
                    break
                response.raise_for_status()
                text, citations = _extract_gemini_result(response.json(), citation_offset=len(retrieved))
                if text:
                    return text, citations, model, "gemini_grounded_web"
                break
            except (httpx.HTTPError, ValueError):
                break

    # Search grounding has a separate quota and can be temporarily unavailable
    # even when Gemini generation is healthy. In that case, let Gemini compose a
    # concise answer strictly from the retrieved, reviewed records. Never use
    # this path without local evidence, and label it separately from web grounding.
    if retrieved:
        local_body = {
            **body,
            "systemInstruction": {"parts": [{"text": instructions + " Web search is unavailable for this request. Use only the supplied verified records; if they are insufficient, say so."}]},
        }
        local_body.pop("tools", None)
        for model in reversed(models):
            try:
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                    json=local_body,
                    timeout=40,
                )
                response.raise_for_status()
                text, citations = _extract_gemini_result(response.json(), citation_offset=len(retrieved))
                if text:
                    return text, citations, model, "gemini_verified_retrieval"
            except (httpx.HTTPError, ValueError):
                continue
    return None


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _direct_extract(question: str, content: str) -> list[str]:
    question_tokens = normalized_tokens(question)
    lowered_question = question.lower()
    definition_question = any(marker in lowered_question for marker in ("what is", "what does", "define", "meaning", "iki", "bisobanura"))
    timing_question = any(marker in lowered_question for marker in ("when", "which month", "season", "ryari", "gihe"))
    action_question = any(marker in lowered_question for marker in ("how", "should", "can i", "what do", "uko", "nakora", "gute"))
    ranked = []
    for position, sentence in enumerate(_sentences(content)):
        lowered = sentence.lower()
        sentence_tokens = normalized_tokens(sentence)
        overlap = len(question_tokens & sentence_tokens)
        score = overlap * 4
        if definition_question and any(marker in lowered for marker in (" means ", " meaning ", " is ", " ni ", "rivuga", "bisobanura")):
            score += 5
        if timing_question and (re.search(r"\b(20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december)\b", lowered) or "kuva" in lowered):
            score += 4
        if action_question and any(marker in lowered for marker in ("should", "must", "before", "use ", "confirm", "contact", "igomba", "banza", "koresha")):
            score += 3
        ranked.append((score, position, sentence))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked:
        return []
    selected = [ranked[0]]
    if not definition_question and len(ranked) > 1 and ranked[1][0] >= max(4, ranked[0][0] * 0.6):
        selected.append(ranked[1])
    elif action_question and not definition_question:
        # Guidance records often place the safety limitation immediately after
        # the recommended action. Keep that adjacent caveat when it stays brief.
        following_position = ranked[0][1] + 1
        following = next((item for item in ranked if item[1] == following_position), None)
        if following and len(ranked[0][2]) + len(following[2]) <= 520:
            selected.append(following)
    return [item[2] for item in selected]


def _retrieval_answer(question: str, language: str, retrieved: list[tuple[KnowledgeArticle, float]]) -> str:
    if not retrieved:
        return (
            "Nta makuru yagenzuwe ahagije ari muri iri bubiko kugira ngo nsubize icyo kibazo. Baza RAB, MINAGRI cyangwa umujyanama w'ubuhinzi wo hafi."
            if language == "rw" else
            "I do not have enough verified information in this library to answer that question. Please consult RAB, MINAGRI or a local agricultural extension officer."
        )
    article = retrieved[0][0]
    content = article.content_rw if language == "rw" else article.content_en
    extracted = _direct_extract(question, content)
    if not extracted:
        return (
            "Nta gisubizo kigufi cyizewe cyabonetse muri iyi nyandiko. Baza umujyanama w'ubuhinzi wo hafi."
            if language == "rw" else
            "No concise verified answer was found in this record. Please consult a local agricultural extension officer."
        )
    return " ".join(extracted) + " [1]"


def conversation_view(conversation: KnowledgeConversation) -> dict:
    messages = sorted(conversation.messages, key=lambda item: item.created_at)
    return {
        "id": conversation.id, "title": conversation.title, "language": conversation.language,
        "created_at": conversation.created_at.isoformat(), "updated_at": conversation.updated_at.isoformat(),
        "messages": [{
            "id": message.id, "role": message.role, "content": message.content,
            "response_mode": message.response_mode, "model_name": message.model_name,
            "created_at": message.created_at.isoformat(),
            "citations": [{
                "article_id": retrieval.article_id, "article_title": retrieval.article_title,
                "source_url": retrieval.source_url, "rank": retrieval.rank, "score": retrieval.score,
            } for retrieval in sorted(message.retrievals, key=lambda item: item.rank)],
        } for message in messages],
    }


def answer_question(db: Session, owner_id: int, question: str, language: str, conversation_id: int | None) -> dict:
    seed_knowledge(db)
    if conversation_id:
        conversation = db.scalar(
            select(KnowledgeConversation)
            .where(KnowledgeConversation.id == conversation_id, KnowledgeConversation.owner_id == owner_id)
            .options(selectinload(KnowledgeConversation.messages).selectinload(KnowledgeMessage.retrievals))
        )
        if not conversation:
            raise LookupError("Conversation not found")
    else:
        conversation = KnowledgeConversation(
            owner_id=owner_id, title=question.strip()[:90], language=language,
        )
        db.add(conversation)
        db.flush()

    history = sorted(conversation.messages, key=lambda item: item.created_at)
    user_message = KnowledgeMessage(conversation_id=conversation.id, role="user", content=question.strip())
    db.add(user_message)
    db.flush()
    retrieved = retrieve_articles(db, question)
    generated = _gemini_answer(question, language, retrieved, history)
    if generated:
        answer, web_citations, model, mode = generated
        citations = [{
            "article_id": article.id,
            "article_title": article.title_rw if language == "rw" else article.title_en,
            "source_url": article.sources[0].url if article.sources else "",
            "score": score,
        } for article, score in retrieved]
        known_urls = {citation["source_url"] for citation in citations}
        citations.extend(citation for citation in web_citations if citation["source_url"] not in known_urls)
    elif _is_casual_conversation(question):
        retrieved = []
        answer = (
            "Muraho! Ndi umufasha wawe wa Agrinox. Mbaza ikibazo kijyanye n'ubuhinzi."
            if language == "rw" else
            "Hello! I am your Agrinox assistant. Ask me a question about farming."
        )
        mode, model, citations = "conversation_fallback", None, []
    else:
        retrieved = retrieved[:1]
        interpreted_question = _interpreted_question(question, retrieved)
        answer, mode, model = _retrieval_answer(interpreted_question, language, retrieved), "verified_retrieval", None
        citations = [{
            "article_id": article.id,
            "article_title": article.title_rw if language == "rw" else article.title_en,
            "source_url": article.sources[0].url if article.sources else "",
            "score": score,
        } for article, score in retrieved]
    assistant = KnowledgeMessage(
        conversation_id=conversation.id, role="assistant", content=answer,
        response_mode=mode, model_name=model,
    )
    db.add(assistant)
    db.flush()
    for rank, citation in enumerate(citations, 1):
        db.add(KnowledgeRetrieval(
            message_id=assistant.id, article_id=citation["article_id"], query=question.strip(),
            rank=rank, score=citation["score"], authorized=True,
            article_title=citation["article_title"], source_url=citation["source_url"],
        ))
    conversation.language = language
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "conversation_id": conversation.id, "message_id": assistant.id, "answer": answer,
        "response_mode": mode, "model_name": model,
        "citations": [{**citation, "rank": rank} for rank, citation in enumerate(citations, 1)],
    }

"""
Knowledge Base — 平台知识中枢
轻量本地 RAG：Ollama embedding + 本地 JSON 向量库（无需额外服务）。
数据量超过 ~5 万 chunk 后，按 agents.yaml 注释切换 Milvus。

action:
  ingest — 文档入库（自动分块 + 向量化）
  query  — 向量检索 + LLM 生成带引用的回答
  list   — 列出已入库文档
"""
import os
import json
import math
import hashlib
from datetime import datetime
import httpx
from app.services.ollama_client import OllamaClient

STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "knowledge")
DB_PATH = os.path.join(STORE_DIR, "vector_store.json")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHUNK_SIZE = 500      # 每块字符数
CHUNK_OVERLAP = 80


class KnowledgeBaseAgent:
    def __init__(self):
        self.name = "KnowledgeBaseAgent"
        self.description = "文档入库、向量检索、RAG 问答（平台知识中枢）"
        self.client = OllamaClient(model_key="qwen")
        os.makedirs(STORE_DIR, exist_ok=True)
        if not os.path.exists(DB_PATH):
            self._save_db({"documents": [], "chunks": []})

    # ---------- 向量库基础操作 ----------

    def _load_db(self) -> dict:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_db(self, db: dict):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)

    async def _embed(self, texts: list) -> list:
        async with httpx.AsyncClient(timeout=120.0) as c:
            vectors = []
            for t in texts:
                r = await c.post(f"{OLLAMA_URL}/api/embeddings",
                                 json={"model": EMBED_MODEL, "prompt": t})
                vectors.append(r.json()["embedding"])
            return vectors

    @staticmethod
    def _cosine(a: list, b: list) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1e-9
        nb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / na / nb

    @staticmethod
    def _chunk(text: str) -> list:
        chunks, i = [], 0
        while i < len(text):
            chunks.append(text[i:i + CHUNK_SIZE])
            i += CHUNK_SIZE - CHUNK_OVERLAP
        return [c for c in chunks if c.strip()]

    # ---------- action ----------

    async def run(self, input_data: dict) -> dict:
        action = input_data.get("action", "query")
        if action == "ingest":
            return await self._ingest(input_data)
        if action == "list":
            db = self._load_db()
            return {"status": "success", "documents": db["documents"],
                    "chunk_count": len(db["chunks"])}
        return await self._query(input_data)

    async def _ingest(self, input_data: dict) -> dict:
        docs = input_data.get("documents", [])
        if not docs:
            return {"status": "error", "error": "ingest 需要提供 documents"}

        db = self._load_db()
        total_chunks = 0
        for doc in docs:
            doc_id = hashlib.md5(
                (doc.get("title", "") + doc.get("content", "")).encode()
            ).hexdigest()[:12]
            if any(d["doc_id"] == doc_id for d in db["documents"]):
                continue  # 已入库，跳过

            chunks = self._chunk(doc.get("content", ""))
            vectors = await self._embed(chunks)
            for i, (ck, vec) in enumerate(zip(chunks, vectors)):
                db["chunks"].append({
                    "doc_id": doc_id, "seq": i, "text": ck, "vector": vec,
                    "title": doc.get("title", "未命名"),
                    "source": doc.get("source", ""),
                    "date": doc.get("date", ""),
                })
            db["documents"].append({
                "doc_id": doc_id, "title": doc.get("title", "未命名"),
                "source": doc.get("source", ""), "date": doc.get("date", ""),
                "chunks": len(chunks), "ingested_at": datetime.now().isoformat(),
            })
            total_chunks += len(chunks)

        self._save_db(db)
        return {"status": "success", "ingested_docs": len(docs),
                "new_chunks": total_chunks,
                "total_docs": len(db["documents"]),
                "timestamp": datetime.now().isoformat()}

    async def _query(self, input_data: dict) -> dict:
        question = input_data.get("question", "")
        top_k = int(input_data.get("top_k", 5))
        if not question:
            return {"status": "error", "error": "query 需要提供 question"}

        db = self._load_db()
        if not db["chunks"]:
            return {"status": "success", "result": "知识库为空，请先 ingest 文档。", "sources": []}

        qvec = (await self._embed([question]))[0]
        scored = sorted(
            ((self._cosine(qvec, c["vector"]), c) for c in db["chunks"]),
            key=lambda x: x[0], reverse=True,
        )[:top_k]

        context = "\n\n".join(
            f"[{i+1}] 《{c['title']}》（{c.get('source','')}, {c.get('date','')}）\n{c['text']}"
            for i, (_, c) in enumerate(scored)
        )
        sources = [{"title": c["title"], "source": c.get("source", ""),
                    "score": round(s, 3)} for s, c in scored]

        system_prompt = """你是能源投资平台的知识库助手。基于给定的检索片段回答问题。

规则：
- 只使用检索片段中的信息；片段没有的内容回答"知识库中未找到相关信息"
- 回答中用 [1][2] 标注引用来源编号
- 涉及数字、日期、政策条款必须忠实于原文"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n检索片段：\n{context}\n\n问题：{question}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="qwen")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        return {
            "status": "success",
            "result": response["content"],
            "sources": sources,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

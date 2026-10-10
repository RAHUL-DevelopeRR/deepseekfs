"""Real local-model checks using synthetic files and isolated state."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import faulthandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    faulthandler.enable()
    faulthandler.dump_traceback_later(45, repeat=True)
    print("Starting isolated desktop flow checks", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix="neucockpit-flows-", ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        os.environ["NEURON_STORAGE_DIR"] = str(root / "state")
        os.environ["NEURON_LLM_BACKEND"] = "worker"
        os.environ["NEURON_LLM_THREADS"] = "3"
        os.environ["NEURON_LLM_BATCH"] = "128"
        os.environ["NEURON_CHAT_RESPONSE_CACHE"] = "0"
        os.environ["NEURON_CHAT_HISTORY_LIMIT"] = "12"
        os.environ["NEURON_LOG_STDERR"] = "1"
        from core.embeddings.embedder import get_embedder
        from core.indexing.index_builder import IndexBuilder
        from services.memory_os import MemoryOSAgent
        from services.agent.executor import TaskExecutor
        from services.agent.task import Task
        from services.llm_engine import get_llm_engine
        from services.tools import get_tool_schemas
        from services.events import get_event_store
        from services.memory_context import get_memory_context_store
        import numpy as np

        report = {}
        started = time.monotonic()
        embedder = get_embedder()
        assert "bge" in embedder.identity.lower() and "onnx-cls" in embedder.identity
        dense = "資料測定検索結果" * 150
        parts = embedder.split_chunks([{"text": dense, "offset_start": 30, "section": "Dense text"}])
        assert len(parts) > 1
        for part in parts:
            assert len(embedder._backend.chunk_tokenizer.encode(part["text"]).ids) <= 512
            begin, end = part["offset_start"] - 30, part["offset_end"] - 30
            assert dense[begin:end] == part["text"]
        assert parts[0]["offset_start"] == 30 and parts[-1]["offset_end"] == len(dense) + 30
        vectors = embedder.encode([part["text"] for part in parts])
        assert vectors.shape == (len(parts), 384) and np.isfinite(vectors).all()
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
        report["bge"] = {"backend": embedder.identity, "dense_chunks": len(parts),
                         "normalized": True, "seconds": round(time.monotonic() - started, 3)}

        documents = root / "documents"
        documents.mkdir()
        notes = documents / "meeting.txt"
        notes.write_text("Weekly project meeting: Atlas deployment is scheduled for Friday.")
        index = IndexBuilder()
        assert index.add_folder(str(documents))
        assert index.add_file(str(notes))
        hits = index.search_chunks(np.array([embedder.encode_single("When will Atlas deploy?")]))
        assert any("Friday" in hit["text"] for hit in hits)
        report["retrieval"] = {"files_and_folders": index._db.count(), "chunks": index.index.ntotal}

        engine = get_llm_engine()
        try:
            agent = MemoryOSAgent()
            agent._engine = engine
            first = agent.chat("Remember that my project name is Atlas.", "chat")
            agent = MemoryOSAgent()  # Reopen persisted context.
            agent._engine = engine
            recall = agent.chat("What is my project's name?", "chat")
            assert "atlas" in recall.lower(), recall
            report["chat"] = {"persisted_recall": recall, "first_response": first}

            executor = TaskExecutor(engine)
            list_task = Task(f"List the files in this folder: {documents}")
            listed = executor.run(list_task)
            assert list_task.status == "completed", listed
            assert any(step.action == "folder_list" and step.status == "success" for step in list_task.steps), listed

            target = documents / "proof.txt"
            executor.on_confirmation = lambda name, args: name == "file_write" and Path(args.get("path", "")).resolve() == target.resolve()
            write_task = Task(f"Create a text file at {target} containing exactly TOOL_ACTION_OK.")
            written = executor.run(write_task)
            assert write_task.status == "completed", written
            assert target.is_file() and "TOOL_ACTION_OK" in target.read_text(), written
            report["action"] = {"listing_tools": [step.action for step in list_task.steps],
                                "writing_tools": [step.action for step in write_task.steps], "file_verified": True}
            report["tools"] = {"exposed": [schema["function"]["name"] for schema in get_tool_schemas()],
                               "mcp_transport": False}
            report["ok"] = True
            print(json.dumps(report, indent=2))
        finally:
            engine.unload()
            index._db.close()
            get_event_store().close()
            get_memory_context_store()._conn().close()
            faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()

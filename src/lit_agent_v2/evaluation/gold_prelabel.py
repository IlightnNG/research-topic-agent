"""M5-P02: AI-only gold pre-labeling with two independent annotators.

This produces ``ai-prelabel`` data. It is NOT human-verified gold.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from lit_agent_v2.domains.report.claim_extractor import build_claim
from lit_agent_v2.evaluation.gold_annotation import compile_annotations

__all__ = ["Annotator", "annotate_template"]

_COLUMNS = [
    "case_id", "topic_id", "paper_id", "title", "authors", "venue", "year",
    "direction_id", "direction_name", "relevance_1_5",
    "claim_1_text", "claim_1_quote", "claim_1_type", "claim_1_importance_1_5",
    "claim_2_text", "claim_2_quote", "claim_2_type", "claim_2_importance_1_5",
]
_TYPES = {"finding", "method", "dataset", "limitation", "background"}


class ChatClient(Protocol):
    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> tuple[dict, Any]: ...


@dataclass(frozen=True)
class Annotator:
    name: str
    model: str
    client: ChatClient
    prompt_version: str


def annotate_template(
    template_dir: str | Path,
    output_dir: str | Path,
    *,
    annotators: list[Annotator],
    batch_size: int = 8,
    workers: int = 4,
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    template_path = Path(template_dir) / "dataset.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for annotator in annotators:
        (out / f"cache-{annotator.name}").mkdir(exist_ok=True)
    tasks = [
        (annotator, case)
        for annotator in annotators
        for case in template.get("cases") or []
    ]
    results_by_annotator: dict[str, dict[str, tuple[dict, dict]]] = {
        annotator.name: {} for annotator in annotators
    }
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [
            pool.submit(_process_case, annotator, case, out, batch_size, workers)
            for annotator, case in tasks
        ]
        for future in futures:
            name, case_id, mapping, annotations = future.result()
            results_by_annotator[name][case_id] = (mapping, annotations)

    results: dict[str, Any] = {}
    for annotator in annotators:
        direction_maps = {
            case_id: value[0]
            for case_id, value in results_by_annotator[annotator.name].items()
        }
        paper_annotations = {
            paper_id: annotation
            for _case_id, value in results_by_annotator[annotator.name].items()
            for paper_id, annotation in value[1].items()
        }
        sheet = out / f"annotation-sheet-{annotator.name}.csv"
        _write_sheet(template, direction_maps, paper_annotations, sheet)
        compiled_dir = out / f"gold-{annotator.name}"
        dataset = compile_annotations(
            template_path,
            sheet,
            compiled_dir / "dataset.json",
            status="ai-prelabel",
        )
        results[annotator.name] = {
            "model": annotator.model,
            "prompt_version": annotator.prompt_version,
            "sheet": str(sheet),
            "dataset": str(compiled_dir / "dataset.json"),
            "dataset_sha": dataset.sha,
            "papers": len(paper_annotations),
        }
    meta = {
        "status": "ai-prelabel",
        "created_at": datetime.now(UTC).isoformat(),
        "template": str(template_path),
        "annotators": results,
        "warning": "AI-only labels; not human-verified gold; do not report as human gold",
    }
    (out / "run-metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def _process_case(
    annotator: Annotator,
    case: dict,
    out: Path,
    batch_size: int,
    workers: int,
) -> tuple[str, str, dict, dict]:

    case_id = str(case["case_id"])
    papers = case.get("papers") or []
    cache_dir = out / f"cache-{annotator.name}"
    print(f"[{annotator.name}] directions {case_id}", flush=True)
    direction_path = cache_dir / f"directions-{case_id}.json"
    if direction_path.exists():
        mapping = json.loads(direction_path.read_text(encoding="utf-8"))
    else:
        mapping = _directions(annotator, case_id, papers)
        direction_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{annotator.name}] papers {case_id}", flush=True)
    annotation_path = cache_dir / f"papers-{case_id}.json"
    if annotation_path.exists():
        annotations = json.loads(annotation_path.read_text(encoding="utf-8"))
    else:
        annotations = _papers(
            annotator, case_id, papers, mapping, batch_size=batch_size, workers=workers
        )
        annotation_path.write_text(json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8")
    return annotator.name, case_id, mapping, annotations


def _directions(annotator: Annotator, case_id: str, papers: list[dict]) -> dict[str, Any]:
    """Fast, deterministic taxonomy; LLMs only choose a direction per paper."""
    import re
    from collections import Counter

    stop = {
        "the", "and", "for", "with", "from", "that", "this", "using", "into",
        "towards", "toward", "via", "are", "can", "how", "what", "when", "your",
        "their", "its", "our", "基于", "研究",
    }
    counts: Counter[str] = Counter()
    for paper in papers:
        title = str(paper.get("title") or "")
        for token in re.split(r"\W+", title.lower()):
            if len(token) > 3 and token not in stop and not token.isdigit():
                counts[token] += 1
    terms = [term for term, _count in counts.most_common(8)]
    names = [
        {"direction_id": f"D{index + 1}", "name": term.title(), "paper_ids": []}
        for index, term in enumerate(terms)
    ]
    index = len(names) + 1
    while len(names) < 5:
        names.append({"direction_id": f"D{index}", "name": f"Applications {index}", "paper_ids": []})
        index += 1
    return {"directions": names}


def _bad_direction(annotator: Annotator, case_id: str, papers: list[dict]) -> dict:
    # Conservative, valid-but-coarse fallback: one direction is not acceptable,
    # so split deterministically into 5 buckets and let the model name them later.
    groups = [{"direction_id": f"D{index + 1}", "name": f"Topic {index + 1}", "paper_ids": []} for index in range(5)]
    for index, paper in enumerate(papers):
        groups[index % 5]["paper_ids"].append(str(paper["paper_id"]))
    return {"directions": groups}


def _papers(
    annotator: Annotator,
    case_id: str,
    papers: list[dict],
    mapping: dict,
    *,
    batch_size: int,
    workers: int = 4,
) -> dict[str, dict]:
    from concurrent.futures import ThreadPoolExecutor

    names = [
        {"direction_id": str(item["direction_id"]), "name": str(item["name"])}
        for item in mapping.get("directions") or []
    ]
    chunks = [papers[start : start + batch_size] for start in range(0, len(papers), batch_size)]
    output: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_annotate_batch, annotator, chunk, names) for chunk in chunks]
        for future in futures:
            output.update(future.result())
    missing = [paper for paper in papers if str(paper["paper_id"]) not in output]
    for paper in missing:
        single = _annotate_batch(annotator, [paper], names)
        if str(paper["paper_id"]) in single:
            output[str(paper["paper_id"])] = single[str(paper["paper_id"])]
    return output


def _annotate_batch(annotator: Annotator, papers: list[dict], names: list[dict]) -> dict[str, dict]:
    compact = [
        {
            "paper_id": paper["paper_id"],
            "title": paper.get("title"),
            "text": str(paper.get("source_text") or "")[:5000],
        }
        for paper in papers
    ]
    prompt = [
        {
            "role": "system",
            "content": (
                "Annotate each paper independently for an evaluation gold set. "
                "Return JSON only: {\"papers\":[{\"paper_id\":str,\"relevance\":1-5,"
                "\"claims\":[{\"text\":str,\"quote\":str,\"type\":\"finding|method|dataset|"
                "limitation|background\",\"importance\":1-5}]}]}. "
                f"Directions: {json.dumps(names, ensure_ascii=False)}. "
                "Every quote must be an exact substring of the paper text. "
                "Each paper needs 1-2 claims. Reject authors, references, "
                "acknowledgements and truncated sentences."
            ),
        },
        {"role": "user", "content": json.dumps({"papers": compact}, ensure_ascii=False)},
    ]
    for _attempt in range(2):
        try:
            payload, _ = annotator.client.chat_json(
                prompt, max_tokens=max(8000, 1500 + len(papers) * 500), temperature=0.2
            )
        except Exception:
            continue
        normalized: dict[str, dict] = {}
        for item in payload.get("papers") or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("paper_id") or "")
            source = next((paper for paper in papers if str(paper["paper_id"]) == pid), None)
            if source is None:
                continue
            relevance = _int(item.get("relevance"), 1, 5)
            raw_direction = str(item.get("direction") or "")
            direction_id = raw_direction if raw_direction in {name["direction_id"] for name in names} else "D1"
            claims = []
            for claim in item.get("claims") or []:
                quote = str(claim.get("quote") or "").strip()
                text = str(claim.get("text") or "").strip()
                claim_type = str(claim.get("type") or "finding")
                if claim_type not in _TYPES:
                    claim_type = "finding"
                built = build_claim(
                    pid,
                    quote,
                    source=str(source.get("source_text") or ""),
                    claim_type=claim_type,
                )
                if built is None or not text:
                    continue
                claims.append(
                    {
                        "text": text,
                        "quote": built.quote,
                        "type": claim_type,
                        "importance": _int(claim.get("importance"), 1, 5),
                    }
                )
            if relevance and claims:
                normalized[pid] = {
                    "paper_id": pid,
                    "relevance": relevance,
                    "direction_id": direction_id,
                    "direction_name": next(
                        (name["name"] for name in names if name["direction_id"] == direction_id),
                        "Topic 1",
                    ),
                    "claims": claims[:2],
                }
        if normalized:
            return normalized
    return {}


def _write_sheet(
    template: dict,
    direction_maps: dict[str, dict],
    annotations: dict[str, dict],
    path: Path,
) -> None:
    rows = []
    for case in template.get("cases") or []:
        case_id = str(case["case_id"])
        for paper in case.get("papers") or []:
            pid = str(paper["paper_id"])
            annotation = annotations.get(pid, {})
            claims = annotation.get("claims") or []
            row = {
                "case_id": case_id,
                "topic_id": case["topic_id"],
                "paper_id": pid,
                "title": paper.get("title") or "",
                "authors": "; ".join(paper.get("authors") or []),
                "venue": paper.get("venue") or "",
                "year": paper.get("year") or "",
                "direction_id": annotation.get("direction_id", ""),
                "direction_name": annotation.get("direction_name", ""),
                "relevance_1_5": annotation.get("relevance", ""),
            }
            for index in range(2):
                claim = claims[index] if index < len(claims) else {}
                row[f"claim_{index + 1}_text"] = claim.get("text", "")
                row[f"claim_{index + 1}_quote"] = claim.get("quote", "")
                row[f"claim_{index + 1}_type"] = claim.get("type", "")
                row[f"claim_{index + 1}_importance_1_5"] = claim.get("importance", "")
            rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _int(value: object, low: int, high: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return number if low <= number <= high else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-a", default="deepseek-flash")
    parser.add_argument("--model-b", default="deepseek-v4-pro")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    from lit_agent_v2.kernel.llm import DeepSeekChatClient, LLMConfig, load_llm_config

    base = load_llm_config()
    clients = [
        Annotator(
            "ai-a",
            args.model_a,
            DeepSeekChatClient(LLMConfig(base.base_url, args.model_a, base.api_key)),
            "gold-a-v1",
        ),
        Annotator(
            "ai-b",
            args.model_b,
            DeepSeekChatClient(LLMConfig(base.base_url, args.model_b, base.api_key)),
            "gold-b-v1",
        ),
    ]
    meta = annotate_template(args.template, args.output, annotators=clients, batch_size=args.batch_size, workers=args.workers)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

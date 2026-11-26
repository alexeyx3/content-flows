"""Validate v2 materials; record QA and explicit human approvals with content hashes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from article_materials import (article_errors, digest, export_errors, is_v2, job_path,
                              qa_fingerprint, qa_is_pass, read_json, validate_inputs,
                              visual_qa_errors, writer_ready_errors, write_json)
from delivery_contract import qa_errors as delivery_qa_errors


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--job", required=True)
    check.add_argument("--target", choices=["inputs", "writer", "visual", "qa", "review", "strapi"], default="qa",
                       help="qa checks readiness to start independent review; seal-qa accepts its final verdict.")
    check.add_argument("--offline", action="store_true", help="local checks only")
    seal = sub.add_parser("seal-qa")
    seal.add_argument("--job", required=True)
    quotes = sub.add_parser("approve-quotes", help="only after explicit approval by a person")
    quotes.add_argument("--job", required=True)
    quotes.add_argument("--ids", nargs="+", required=True)
    quotes.add_argument("--by", required=True)
    quotes.add_argument("--reference", required=True, help="link to the document/message with the approval")
    review = sub.add_parser("approve-review", help="only after explicit approval by a person")
    review.add_argument("--job", required=True)
    review.add_argument("--by", required=True)
    review.add_argument("--reference", required=True)
    args = ap.parse_args()
    job = job_path(args.job)
    if args.command == "check":
        errors = (validate_inputs(job) if args.target == "inputs" else
                  writer_ready_errors(job) if args.target == "writer" else
                  validate_inputs(job) + visual_qa_errors(job) if args.target == "visual" else
                  article_errors(job, "qa", remote=not args.offline) if args.target == "qa" else
                  export_errors(job, args.target, remote=not args.offline))
        if errors:
            raise SystemExit("BLOCK:\n- " + "\n- ".join(errors))
        verdict = "READY" if args.target == "qa" else "PASS"
        print(f"{verdict}: {args.target}" + (" (offline)" if args.offline else ""))
    elif args.command == "seal-qa":
        errors = article_errors(job, "qa")
        from answer_contract import qa_errors as answer_qa_errors
        errors.extend(answer_qa_errors(job))
        errors.extend(delivery_qa_errors(job))
        if errors or not qa_is_pass(job):
            raise SystemExit("cannot record QA: " + "; ".join(errors or ["overall: PASS without BLOCK gates is required"]))
        write_json(job / "qa_receipt.json", {"at": now(), "hashes": qa_fingerprint(job)})
        print("QA PASS recorded for the current materials")
    elif args.command == "approve-quotes":
        data = read_json(job / "expert_quotes.json")
        ids = set(args.ids)
        if ids - {q["id"] for q in data["quotes"]}:
            raise SystemExit("unknown quote id")
        if not args.by.strip() or not args.reference.strip():
            raise SystemExit("a person and a source of the explicit approval must be given")
        for q in data["quotes"]:
            if q["id"] in ids:
                q["status"] = "approved"
                q["approval"] = {"by": args.by, "reference": args.reference, "at": now(),
                                 "text_sha256": digest(q["text"] + "\n" + q["attribution"])}
        write_json(job / "expert_quotes.json", data)
        print("quote approval recorded")
    else:
        errors = export_errors(job, "review", remote=False)
        if errors:
            raise SystemExit("first prepare the verified version:\n- " + "\n- ".join(errors))
        if not args.by.strip() or not args.reference.strip():
            raise SystemExit("a person and a source of the explicit approval must be given")
        write_json(job / "review_approval.json", {"by": args.by, "reference": args.reference,
                   "at": now(), "article_sha256": digest((job / "edited.md").read_bytes())})
        print("article approval recorded for the current text")


if __name__ == "__main__":
    main()

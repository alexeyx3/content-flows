"""Exercise the ordinary writer route with a simulated OpenRouter response."""

import argparse
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import glossary_job
import glossary_writer as writer
import openrouter_pilot as api


class GlossaryWriterTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        jobs = self.root / "jobs"
        jobs.mkdir()
        route_patch = patch.object(glossary_job, "ROOT", self.root)
        route_patch.start()
        self.addCleanup(route_patch.stop)
        writer_patch = patch.object(writer, "ROOT", self.root)
        writer_patch.start()
        self.addCleanup(writer_patch.stop)
        glossary_job.new_job(argparse.Namespace(
            term="Invoice log", slug="invoice-log", date="2026-11-22", author="john.roe",
            writer_backend=None,
        ))
        self.job = jobs / "2026-11-22-invoice-log"
        self.route = writer.configured_writer()["route"]
        self.directory = self.job / "writer-api"
        self.ledger = api.CompletionLedger(self.root, self.directory, (self.directory / "api",), 0.25)

        for filename, content in {
            "brief.md": "Explain how to record and verify the invoice.",
            "serp.hybrid_outline.md": "The reader needs a receipt and the approval reference.",
            "research.md": "### R-01\nThe approval reference can be retained.",
            "evidence.md": "### Claim REC-01\n- R-01: https://example.org/records\n"
                           "- **Verdict:** supports.\n- **Article link:** required.\n",
        }.items():
            (self.job / filename).write_text(content, encoding="utf-8")
        api.write(self.job / "meta.json", {
            "term": "Invoice log", "slug": "invoice-log", "locale": "en",
            "definition": "A log records the invoices and their approval references.",
            "metaTitle": "Invoice log", "metaDescription": "How a invoice log is used.",
        })
        api.write(self.job / "sections.json", {"sections": [
            {"id": "records", "title": "Recording invoices", "subheadings": [
                {"level": 3, "title": "Keep the receipt"}, {"level": 4, "title": "File it"},
                {"level": 3, "title": "Check approval"},
            ]},
            {"id": "changes", "title": "Maintain the log"},
        ], "information_gain": [{"section_id": "records", "research_ref": "R-01", "reader_value": "Verify approval"}]})
        self.visual = {
            "id": "approval", "section_id": "records", "type": "process", "purpose": "Show the check.",
            "title": "Approval verification", "alt": "Connect the receipt to approval.", "caption": "Verify the reference.",
            "sources": [{"label": "Records", "url": "https://example.org/records"}],
            "data": {"nodes": [{"id": "receipt", "label": "Receipt", "evidence_ids": ["REC-01"]},
                               {"id": "approval", "label": "Approval", "evidence_ids": ["REC-01"]}],
                     "edges": [{"from": "receipt", "to": "approval"}]},
        }
        api.write(self.job / "visuals.json", {"visuals": [self.visual]})
        api.write(self.job / "expert_quotes.json", {"quotes": [], "omission_reason": "No attributed example needed."})

        self.responses = []
        self.payloads = []
        self.transport = Mock(side_effect=self.respond)
        self.check = Mock(return_value={"endpoint": {
            "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
        }})
        key = patch.object(api, "glossary_key", return_value="sk-or-synthetic-test")
        key.start()
        self.addCleanup(key.stop)
        complete = patch.object(writer, "completion", side_effect=self.complete_with_test_endpoint)
        complete.start()
        self.addCleanup(complete.stop)

    def respond(self, _, key, payload, **kwargs):
        self.payloads.append(copy.deepcopy(payload))
        response = self.responses.pop(0)
        return 200, {"id": f"gen-test-{self.transport.call_count}", "model": self.route["model"],
                     "provider": self.route["expected_provider_name"], "usage": {"cost": 0.001},
                     "choices": [{"message": {"content": response}, "finish_reason": "stop"}]}

    def complete_with_test_endpoint(self, job, route, ledger, call_id, messages, retry):
        return api.run_completion(job, ledger.api_dirs[0], ledger, call_id, route, messages,
                                  execute=True, max_tokens=100, retry=retry,
                                  transport=self.transport, check=self.check)

    def invoke(self, *arguments):
        with patch.object(sys, "argv", ["glossary_writer.py", *arguments, "--job", str(self.job)]):
            writer.main()

    def draft(self):
        self.responses.extend([
            "## Recording invoices\n\nRecord the date.\n\n### Keep the receipt\n\nKeep it.\n\n#### File it\n\nUse the log.",
            "### Check approval\n\nThis first answer forgot the required marker.",
            "### Check approval\n\n[Match the reference](https://example.org/records).\n\n[[VISUAL:approval]]",
            "## Maintain the log\n\nKeep earlier entries and record any change.\n\n| Row |\n| :---: |\n| Date |",
        ])
        self.invoke("write", "--execute")
        glossary_job.assemble(argparse.Namespace(job=str(self.job)))

    def test_default_and_explicit_codex_assignment(self):
        self.assertEqual(api.read(self.job / "request.json")["writer_backend"], "openrouter")
        glossary_job.new_job(argparse.Namespace(
            term="Legacy", slug="legacy", date="2026-11-22", author="john.roe", writer_backend="codex",
        ))
        with self.assertRaisesRegex(ValueError, "Codex writer"):
            writer.api_job(self.job.parent / "2026-11-22-legacy")
        original = api.read(self.job / "request.json")
        del original["writer_backend"]
        api.write(self.job / "request.json", original)
        with self.assertRaisesRegex(ValueError, "Codex writer"):
            writer.api_job(self.job)

    def test_preview_does_not_write_or_contact_openrouter(self):
        self.invoke("write")
        self.assertFalse(self.directory.exists())
        self.transport.assert_not_called()
        self.check.assert_not_called()

    def test_draft_reuses_one_context_and_resumes_after_partial_handoff(self):
        meta = (self.job / "meta.json").read_bytes()
        self.draft()
        calls = self.payloads
        self.assertEqual(len(calls), 4)
        system_prompt = calls[0]["messages"][0]["content"]
        self.assertIn("Your final answer is the Markdown", system_prompt)
        self.assertIn("Use only facts marked", system_prompt)
        self.assertNotIn("create `sections/<id>.md`", system_prompt)
        self.assertNotIn("do not paste the prose", system_prompt)
        self.assertIn("Keep the receipt", calls[1]["messages"][-2]["content"])
        self.assertIn("missing visual markers", calls[2]["messages"][-1]["content"])
        self.assertIn("[[VISUAL:approval]]", calls[3]["messages"][-2]["content"])
        self.assertEqual(meta, (self.job / "meta.json").read_bytes())
        self.assertIn("| --- |", (self.job / "out/draft.md").read_text())
        self.assertEqual(self.ledger.usage()["attempts"], 4)

        (self.directory / "draft-complete.json").unlink()
        (self.directory / "api/write-records-02-format/success.json").unlink()
        (self.job / "sections/changes.md").unlink()
        self.invoke("write", "--execute")
        self.assertTrue((self.job / "sections/changes.md").is_file())
        self.assertEqual(self.transport.call_count, 4)
        self.assertEqual(self.ledger.usage()["attempts"], 4)

    def test_second_format_repair_gets_exact_headings_without_replaying_calls(self):
        accepted = "## Recording invoices\n\n### Keep the receipt\n\nKeep it.\n\n#### File it\n\nUse the log."
        overshot = accepted + "\n\n### Check approval\n\nThis belongs to a later unit."
        self.responses.extend([
            overshot,
            overshot,
            accepted,
            "### Check approval\n\nVerify the reference.\n\n[[VISUAL:approval]]",
            "## Maintain the log\n\nRecord each change.",
        ])
        self.invoke("write", "--execute")
        followup = self.payloads[2]["messages"][-1]["content"]
        self.assertIn('["## Recording invoices", "### Keep the receipt", "#### File it"]', followup)
        self.assertNotIn("This belongs to a later unit", (self.job / "sections/records.md").read_text())
        self.assertTrue(any("write-records-01-format-02" in p.parts for p in self.ledger.receipts()))
        (self.directory / "draft-complete.json").unlink()
        self.invoke("write", "--execute")
        self.assertEqual(self.transport.call_count, 5)

    def test_repair_targets_current_unit_and_keeps_bound_figure_intact(self):
        self.draft()
        block = "![Connect the receipt to approval.](https://example.org/approval.png)\n\nCaption: Verify the reference."
        self.visual["inserted_markdown"] = block
        api.write(self.job / "visuals.json", {"visuals": [self.visual]})
        edited = (self.job / "assembled.md").read_text().replace("[[VISUAL:approval]]", block)
        (self.job / "edited.md").write_text(edited)
        self.responses.append("### Check approval\n\nMatch the receipt to the approval reference.\n\n[[VISUAL:approval]]")
        arguments = ("repair", "--unit", "records-02", "--feedback", "Specify the matching document.")
        self.invoke(*arguments)
        self.assertEqual(self.transport.call_count, 4)
        self.invoke(*arguments, "--execute")
        self.assertEqual(self.transport.call_count, 5)
        candidates = list((self.directory / "repairs").glob("*.md"))
        self.assertEqual(len(candidates), 1)
        self.assertIn(block, candidates[0].read_text())
        packet = self.payloads[-1]["messages"][-1]["content"]
        self.assertIn("Specify the matching document.", packet)
        self.assertNotIn("Keep earlier entries", packet)
        self.assertEqual((self.job / "edited.md").read_text(), edited)
        self.invoke(*arguments, "--execute")
        self.assertEqual(self.transport.call_count, 5)


if __name__ == "__main__":
    unittest.main()

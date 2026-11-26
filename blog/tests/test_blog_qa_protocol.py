import copy
import json
from pathlib import Path

import pytest

from scripts import blog_qa_protocol as qa


TEXT = "# Article\n\nAn order is not receipt evidence. Finance needs linked records.\n\nOld condition.\n"
PAIR = "An order is not receipt evidence. Finance needs linked records."


@pytest.fixture
def env(tmp_path):
    article = tmp_path / "article.md";article.write_text(TEXT)
    policy = tmp_path / "policy.md";policy.write_text("Stable blog rules, no numeric style quotas.\n")
    report = tmp_path / "qa_report.md";report.write_text("Overall: PASS\n")
    return dict(article=article, policy=policy, history=tmp_path / "history",
                context=tmp_path / "context.json", review=tmp_path / "review.json", report=report)


def prepare(e, **kw):
    return qa.prepare(e["article"], e["history"], e["context"], e["policy"], **kw)


def review(packet, **kw):
    return {"schema_version": 1, **{k:packet[k] for k in ("article_sha256", "parent_review_sha256", "policy_sha256")},
            "overall": "PASS", "scope": "Full coverage and changed/high-risk claims checked.",
            "coverage_guard_checked": True, "quote_pair_count": 0,
            "decisions": [], "new_findings": [], "contrast_audit": [], **kw}


def finding(**kw):
    return dict(id="QA-0001", severity="major", category="factual", rule_id="facts.condition",
                section="Article", passage="Old condition.", description="Condition is wrong.",
                acceptance_condition="Correct the condition without losing its scope.", evidence_ids=["F-01"], **kw)


def contrast(decision="exclude", **kw):
    return dict(id="C-0001", passage=PAIR, decision=decision, reason="Explicit semantic adjudication.",
                rejected="An order is not receipt evidence.", affirmed="Finance needs linked records.",
                slot="Evidence of receipt", **kw)


def save(e, r):
    qa.write(e["review"], r);e["report"].write_text(f"Overall: {r['overall']}\nFull reasoning.\n")


def seal(e, r):
    save(e, r)
    return qa.seal(e["article"],e["review"],e["report"],e["context"],e["history"])


def test_initial_block_is_preserved_and_repair_gets_full_parent_context(env):
    packet=prepare(env);key=seal(env, review(packet,overall="BLOCK",new_findings=[finding()]))
    assert qa.state(env["history"])["findings"]["QA-0001"]["status"]=="open"
    env["article"].write_text(TEXT.replace("Old condition.","Correct condition."))
    packet=prepare(env)
    assert packet["parent_review_sha256"]==key and "QA-0001" in packet["prior_findings"]
    assert packet["review_template"]["decisions"][0]["id"]=="QA-0001"
    with pytest.raises(qa.ProtocolError):qa.advance(packet,packet["review_template"],env["article"].read_text())
    assert "-Old condition." in Path(packet["diff"]).read_text()
    r=review(packet,decisions=[dict(id="QA-0001",status="resolved",passage="Correct condition.",reason="Criterion met and scope preserved.")])
    next_key=seal(env,r);assert next_key!=key
    state=qa.state(env["history"])
    assert state["findings"]["QA-0001"]["acceptance_condition"]==finding()["acceptance_condition"]
    assert state["findings"]["QA-0001"]["status"]=="resolved"
    assert (env["history"]/key/"article.md").read_text()==TEXT


def test_sealing_does_not_change_claim_packet_fingerprint(env):
    packet=prepare(env);before=qa.packet_digest(env["context"])
    key=seal(env,review(packet));assert qa.packet_digest(env["context"])==before
    assert seal(env,review(packet))==key
    env["report"].write_text("Overall: PASS\nChanged after sealed.\n")
    with pytest.raises(qa.ProtocolError,match="already sealed"):
        qa.seal(env["article"],env["review"],env["report"],env["context"],env["history"])


def test_all_previous_ids_required_and_cannot_be_renamed(env):
    seal(env,review(prepare(env),overall="BLOCK",new_findings=[finding()]))
    packet=prepare(env)
    with pytest.raises(qa.ProtocolError,match="Every previous finding"):
        qa.advance(packet,review(packet),TEXT)
    r=review(packet,decisions=[dict(id="QA-0001",status="resolved",reason="Removed.")],new_findings=[{**finding(),"id":"QA-0002"}])
    with pytest.raises(qa.ProtocolError,match="retain its existing"):
        qa.advance(packet,r,TEXT)
    r["new_findings"]=[];r["decisions"][0]["acceptance_condition"]="Weaker rule"
    with pytest.raises(qa.ProtocolError,match="cannot redefine"):
        qa.advance(packet,r,TEXT)


def test_withdrawal_and_reopening_require_explicit_reasons(env):
    seal(env,review(prepare(env),overall="BLOCK",new_findings=[finding()]))
    packet=prepare(env);decision=dict(id="QA-0001",status="withdrawn",reason="Original finding was mistaken.")
    with pytest.raises(qa.ProtocolError,match="reversal_reason"):
        qa.advance(packet,review(packet,decisions=[decision]),TEXT)
    decision["reversal_reason"]="F-01 establishes the preserved condition; initial QA misread scope."
    seal(env,review(packet,decisions=[decision]));packet=prepare(env)
    reopened=dict(id="QA-0001",status="open",reason="New decisive source.",passage="Old condition.")
    with pytest.raises(qa.ProtocolError,match="Use reopened"):
        qa.advance(packet,review(packet,overall="BLOCK",decisions=[reopened]),TEXT)
    reopened.update(status="reopened",reversal_reason="New source F-02 contradicts previous interpretation.")
    assert qa.advance(packet,review(packet,overall="BLOCK",decisions=[reopened]),TEXT)[0]["QA-0001"]["status"]=="reopened"


def test_unchanged_contrast_cannot_silently_flip_or_disappear(env):
    seal(env,review(prepare(env),contrast_audit=[contrast()]))
    packet=prepare(env)
    with pytest.raises(qa.ProtocolError,match="Every previous contrast"):
        qa.advance(packet,review(packet),TEXT)
    with pytest.raises(qa.ProtocolError,match="reversal_reason"):
        qa.advance(packet,review(packet,contrast_audit=[contrast("count")]),TEXT)
    item=contrast("count",reversal_reason="Same proof slot; rubric example establishes the initial exclusion was wrong.")
    assert qa.advance(packet,review(packet,contrast_audit=[item]),TEXT)[1]["C-0001"]["decision"]=="count"
    item["id"]="C-0002"
    with pytest.raises(qa.ProtocolError,match="Every previous contrast"):
        qa.advance(packet,review(packet,contrast_audit=[item]),TEXT)


def test_removed_contrast_remains_in_history_but_cannot_hide_current_text(env):
    seal(env,review(prepare(env),contrast_audit=[contrast("count")]))
    packet=prepare(env);item=contrast("absent")
    with pytest.raises(qa.ProtocolError,match="still occurs"):
        qa.advance(packet,review(packet,contrast_audit=[item]),TEXT)
    env["article"].write_text(TEXT.replace(PAIR,"Finance verifies receipt using linked records."))
    packet=prepare(env);seal(env,review(packet,contrast_audit=[item]))
    assert qa.state(env["history"])["adjudications"]["C-0001"]["decision"]=="absent"


def test_audit_cannot_move_an_id_to_a_different_passage(env):
    seal(env,review(prepare(env),contrast_audit=[contrast()]))
    packet=prepare(env);item=contrast();item["passage"]="Old condition."
    with pytest.raises(qa.ProtocolError,match="cannot change"):
        qa.advance(packet,review(packet,contrast_audit=[item]),TEXT)


@pytest.mark.parametrize("change,match",[
    ({"article_sha256":"f"*64},"article_sha256"),
    ({"parent_review_sha256":"f"*64},"parent_review_sha256"),
    ({"policy_sha256":"f"*64},"policy_sha256"),
    ({"coverage_guard_checked":False},"coverage"),
    ({"overall":"BLOCK"},"specific active"),
    ({"new_findings":[finding()]},"open major/critical"),
])
def test_unbound_or_inconsistent_reviews_are_rejected(env,change,match):
    p=prepare(env)
    with pytest.raises(qa.ProtocolError,match=match):qa.advance(p,review(p,**change),TEXT)


def test_major_findings_block_but_minor_findings_do_not(env):
    p=prepare(env);f=finding();f["severity"]="minor"
    assert qa.advance(p,review(p,new_findings=[f]),TEXT)[0][f["id"]]["status"]=="open"
    f["passage"]="Invented passage"
    with pytest.raises(qa.ProtocolError,match="occur exactly"):
        qa.advance(p,review(p,new_findings=[f]),TEXT)


def test_contrast_components_checked_without_importing_geo_caps(env):
    p=prepare(env);bad=contrast("count");bad["rejected"]="Missing component"
    with pytest.raises(qa.ProtocolError,match="both components"):
        qa.advance(p,review(p,contrast_audit=[bad]),TEXT)
    text="\n\n".join(f"No X{i}. Use Y{i}." for i in range(4));env["article"].write_text(text);p=prepare(env)
    items=[dict(id=f"C-{i+1:04d}",passage=f"No X{i}. Use Y{i}.",decision="count",rejected=f"No X{i}.",affirmed=f"Use Y{i}.",slot="choice",reason="One corrective choice") for i in range(4)]
    assert len(qa.advance(p,review(p,contrast_audit=items,quote_pair_count=8),text)[1])==4


def test_report_and_review_must_agree(env):
    p=prepare(env);save(env,review(p));env["report"].write_text("Overall: BLOCK\n")
    with pytest.raises(qa.ProtocolError,match="first line"):
        qa.validate(env["article"],env["review"],env["report"],env["context"])


def test_snapshot_tampering_and_history_rollback_are_detected(env):
    first=seal(env,review(prepare(env)));seal(env,review(prepare(env),scope="Fresh recheck of unchanged text."))
    qa.write(env["history"]/"latest.json",{"review_sha256":first})
    with pytest.raises(qa.ProtocolError,match="orphan/fork"):qa.state(env["history"])
    (env["history"]/first/"article.md").write_text("Tampered")
    with pytest.raises(qa.ProtocolError,match="hash mismatch"):qa.state(env["history"])


def test_reference_tampering_invalidates_packet(env):
    key=seal(env,review(prepare(env)));prepare(env)
    (env["history"]/key/"report.md").write_text("Tampered")
    with pytest.raises(qa.ProtocolError,match="reference hash"):qa.packet_digest(env["context"])


def test_stale_parallel_review_cannot_replace_newer_history(env):
    p=prepare(env);old_context=env["context"].with_name("stale.json");old_context.write_bytes(env["context"].read_bytes())
    seal(env,review(p));save(env,review(p,scope="Parallel old review"))
    with pytest.raises(qa.ProtocolError,match="advanced after claim"):
        qa.seal(env["article"],env["review"],env["report"],old_context,env["history"])


def test_editor_packet_has_prior_defects_and_remains_stable_during_edit(env):
    seal(env,review(prepare(env),overall="BLOCK",new_findings=[finding()]))
    p=prepare(env,mode="editor");before=qa.packet_digest(env["context"])
    env["article"].write_text("Changed by editor.")
    assert qa.packet_digest(env["context"])==before and "QA-0001" in p["prior_findings"]
    save(env,review(p))
    with pytest.raises(qa.ProtocolError,match="QA-mode"):
        qa.validate(env["article"],env["review"],env["report"],env["context"])


def test_cli_and_explicit_job_version(env,tmp_path,capsys):
    args=["--article",str(env["article"]),"--context",str(env["context"])]
    assert qa.main(["prepare",*args,"--history",str(env["history"]),"--policy",str(env["policy"])])==0
    save(env,review(qa.load(env["context"])))
    assert qa.main(["validate",*args,"--review",str(env["review"]),"--report",str(env["report"])])==0
    assert qa.main(["seal",*args,"--review",str(env["review"]),"--report",str(env["report"])])==2
    assert "--history" in capsys.readouterr().out
    job=tmp_path/"job";job.mkdir();config=job/"job.yaml";config.write_text("topic: example\n")
    assert qa.version(job)==""
    config.write_text("blog_pilot_qa_protocol: v1 # comment\n");assert qa.version(job)=="v1"
    for text in ("blog_pilot_qa_protocol: v99\n","blog_pilot_qa_protocol: \n","blog_pilot_qa_protocol: v1\nblog_pilot_qa_protocol: v1\n"):
        config.write_text(text)
        with pytest.raises(qa.ProtocolError):qa.version(job)

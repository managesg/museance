from agents.mesh import captions, commands

STRUCK = [{"id": "c03", "text": "1 / 8 rounds to 0.13", "expect": "0.13", "original": "0.12", "bond": 90, "confidence": 0.6},
          {"id": "c07", "text": "Enter adds the task", "expect": "A", "original": "", "bond": 160, "confidence": 0.8}]
R = {"case_id": "todo-1", "app": "todo", "counts": {"LOCKED": 7, "STRUCK": 2, "FABRICATED": 1, "UNSWORN": 1},
     "claims": 11, "attacks": 105, "refused": 0, "catches": 9, "fidelity": 62, "brier": 0.214,
     "credibility_start": 1000, "credibility_end": 871, "struck": STRUCK, "funniest": captions.funniest(STRUCK[1]),
     "chain": "241 events, chain intact"}
IDS = {"case_id": "todo-1", "app": "todo"}
PAYLOADS = {  # event -> (payload, numbers its caption must show)
    "open": ({**IDS, "requester": "", "front_door": "", "evidence": 48, "lines": 21}, ["48", "21"]),
    "summon": ({**IDS, "who": "hoot", "for": "reveal", "attacks": 105}, ["105"]),
    "sealed": ({**IDS, "attacks": 105, "attacks_sha256": "18f15bb0e1", "p4_match": True,
                "p4_sealed_utc": "2026-11-07T20:44:51Z"}, ["105", "18f15bb0", "20:44:51"]),
    "testimony": ({**IDS, "claims": 11, "dropped": 2, "refused": [], "fabricated": 1, "bond": 1450},
                  ["11", "1450", "2 cards"]),
    "reveal": ({**IDS, "accepted": 104, "refused": [{"id": "a009", "why": "x"}], "p4_problems": []}, ["105", "104", "1 thrown out"]),
    "court": ({**IDS, "claims": 11, "attacks": 105}, ["11", "105", "464"]),
    "ruling": (R, ["7 LOCKED", "2 STRUCK", "Fidelity 62", "1000 -> 871 (-129)"]),
    "remark": ({**IDS, "speaker": "hoot", "text": "Hoo.\nStruck!"}, ["Dr. Hoot: Hoo. Struck!"]),
    "closed": ({**IDS, **{k: R[k] for k in ("counts", "catches", "attacks", "credibility_start", "credibility_end")}},
               ["9 catches in 105", "871", "-129"]),
    "adjourned": ({**IDS, "reason": "Dr. Hoot did not answer in 60 s"}, ["60 s"]),
}


def test_every_event_has_one_deterministic_line_with_its_numbers():
    assert set(PAYLOADS) == set(captions.CAPTIONS)
    for event, (payload, numbers) in PAYLOADS.items():
        line = captions.caption(event, payload)
        assert "\n" not in line and line == captions.caption(event, payload)
        assert all(n in line for n in numbers), (event, line)


def test_ruling_text_taunt_and_objection_carry_numbers():
    text = captions.ruling_text(R)
    for s in ("LOCKED 7", "STRUCK 2", "Fidelity 62", "1000 -> 871 (-129)", "9 catches in 105 attacks",
              "Funniest strike: c07", "241 events"):
        assert s in text
    taunt = captions.taunt(R)
    assert taunt.index("c07") < taunt.index("c03")  # most overconfident first
    assert "160 points" in taunt and "90 points" in taunt and "9 catches" in taunt and "871" in taunt
    assert "9 of my 11 claims" in captions.objection(R)
    clean = {**R, "struck": [], "counts": {**R["counts"], "STRUCK": 0}}
    assert "Zero strikes" in captions.taunt(clean) and "0 STRUCK" in captions.objection(clean)
    prompt = captions.objection_prompt(R, "Hoo hoo")
    assert "871" in prompt and "Hoo hoo" in prompt


def test_help_cards_list_every_command():
    for role, cmds in commands.COMMANDS.items():
        card = captions.help_card(role)
        assert all(example in card for _, example, _ in cmds.values()), role


def test_refusal_names_the_docket():
    msg = captions.refusal("pong", {"todo": "", "app1": "no revival"})
    assert "0 pieces of evidence" in msg and "todo (ready)" in msg and "app1 (not ready: no revival)" in msg
    assert "on the docket but not ready: no revival" in captions.refusal("app1", {"app1": "no revival"})


def test_seal_line_needs_both_hashes_to_match():
    seal = {"attacks": [{}] * 3, "attacks_sha256": "a" * 64, "regression_sha256": "r" * 64}
    p4 = {**seal, "created_utc": "2026-11-07T20:44:51Z"}
    assert "matches the seal P4 committed at 2026-11-07T20:44:51Z" in captions.seal_line("app1", seal, p4)
    assert "does NOT match" in captions.seal_line("app1", seal, {**p4, "regression_sha256": "x" * 64})

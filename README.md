# DrillReady

DrillReady is a standalone GenLayer Intelligent Contract for assessing emergency drill records against a facility's approved procedure. It returns **COMPLIANT**, **PARTIAL**, **FAILED**, or **INCONCLUSIVE**. Its scope is the submitted record and the registered procedure. Real-world emergency safety requires separate inspection and judgment.

## Studionet

- [Contract explorer](https://explorer-studio.genlayer.com/address/0x7C81b3813C34d029f7FA8aebE748508C1dA87403)
- [Finalized deployment](https://explorer-studio.genlayer.com/tx/0x0d6175fb222de188a77c5691899cc52c7816aefc482a1e5631f2d4472900f675) · chain ID 61999
- Deployment constructor succeeded in full consensus mode. Studio returned a plan ID in a non-persistent registration simulation. Live reviewer attestation and receipt finalization remain unverified.

## Run it

1. Open [GenLayer Studio](https://studio.genlayer.com/contracts) and import the deployed address, or upload `contracts/drill_ready.py` and deploy with no constructor arguments.
2. From the facility wallet, call `register_plan(plan_json)` with the object below serialized as a JSON string. Replace the reviewer with a separate wallet you control or trust for the drill. Use Unix seconds and choose a future opening time and a deadline at or after it. Each facility/cycle pair is immutable within the registering wallet's namespace.
3. After the drill, use the designated reviewer wallet to call `attest_drill(plan_id, evidence_json)`. Use the ID from registration and the evidence format below.
4. Call `get_latest_receipt(plan_id)` against finalized state and pass the returned ID to `get_receipt(receipt_id)`. The receipt contains the threshold checks and one finding per criterion. Observation indices are zero-based. Follow `previous` to review earlier assessments.

Example plan fields:

```json
{
  "facility": "Training Annex",
  "cycle": "2026 drill 01",
  "reviewer": "0x2222222222222222222222222222222222222222",
  "opens_at": 1794300000,
  "due_at": 1794400000,
  "min_participants": 24,
  "max_seconds": 240,
  "criteria": [
    "Wardens completed evacuation training",
    "The blocked exit signage corrective action was closed and verified"
  ]
}
```

Example evidence fields:

```json
{
  "report_ref": "DR-2026-01",
  "attendance_ref": "AT-2026-01",
  "completed_at": 1794350000,
  "attended": 26,
  "evacuation_seconds": 217,
  "observations": [
    "Training register TR-01 records every assigned warden as having completed evacuation training.",
    "Closeout CA-07 records replacement of the blocked exit sign and an observer's successful visibility check."
  ]
}
```

## Assessment and trust

- The wallet attestation binds the exact structured evidence and observation excerpts to the designated reviewer. The reviewer is responsible for checking original drill reports, attendance totals, incident notes and corrective actions before attesting. Document references are for audit lookup. The contract does not fetch source files or verify external issuer signatures.
- The contract checks the inclusive completion window, minimum attendance and maximum evacuation duration. A missed threshold or a consensus-supported material breach produces `FAILED`. With passing thresholds, all procedural criteria met yields `COMPLIANT`, some met and others unknown yields `PARTIAL`, and all unknown yields `INCONCLUSIVE`.
- Leader and validators independently classify each criterion through GenLayer's nondeterministic execution. They compare normalized statuses and evidence line indices. Malformed classifications become unknown. Disagreement can prevent consensus and therefore prevent a receipt. Grounding identifies the cited excerpt, while the validators judge whether its content supports the finding.
- A plan allows three distinct evidence revisions. Identical canonical evidence is rejected, and each receipt hashes the policy, the evidence and the previous receipt ID. Treat each revision as an assessment of that packet. Revisions can change outcomes and older receipts stay readable.
- Transactions and stored excerpts are public. Submit aggregate attendance and redacted excerpts. A missing submission leaves no assessment.

## Local verification

```sh
python -m unittest discover -s tests -v
```

The tests exercise all four outcomes, evidence validation, reviewer authorization, duplicate rejection, revision limits and the consensus boundary using a local stub. Studionet verifies deployment and the registration simulation separately.

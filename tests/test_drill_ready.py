"""Local state and consensus-boundary tests with a small GenLayer stub."""
import importlib.util
import json
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


def consensus(leader, validator):
    result = Return(leader())
    if not validator(result):
        raise RuntimeError("Validator disagreement")
    return result.calldata


gl = types.SimpleNamespace(
    Contract=object,
    public=types.SimpleNamespace(write=lambda fn: fn, view=lambda fn: fn),
    message=types.SimpleNamespace(sender_address=""),
    message_raw={},
    nondet=types.SimpleNamespace(exec_prompt=None),
    vm=types.SimpleNamespace(Return=Return, run_nondet_unsafe=consensus),
)
spec = importlib.util.spec_from_file_location(
    "drill_ready", Path(__file__).resolve().parents[1] / "contracts/drill_ready.py",
)
contract = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"genlayer": types.SimpleNamespace(Address=str, TreeMap=dict, gl=gl)}):
    spec.loader.exec_module(contract)


class DrillReadyTests(unittest.TestCase):
    owner = "0x" + "11" * 20
    reviewer = "0x" + "22" * 20

    def act(self, address, timestamp):
        gl.message.sender_address = address
        gl.message_raw["datetime"] = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    def setUp(self):
        self.contract = contract.DrillReady()
        for name in ("plans", "receipts", "heads", "used_reports"):
            setattr(self.contract, name, {})
        self.plan = dict(facility="Training Annex", cycle="Demo", reviewer=self.reviewer,
                         opens_at=110, due_at=150, min_participants=24, max_seconds=240,
                         criteria=["Wardens completed training", "Signage correction was closed"])
        self.report = dict(report_ref="DR-01", attendance_ref="AT-01", completed_at=150,
                           attended=24, evacuation_seconds=240,
                           observations=["Wardens completed training.", "New signs installed and checked."])
        gl.nondet.exec_prompt = lambda _: '{"findings":[["MET",0],["MET",1]]}'
        self.act(self.owner, 100)
        self.plan_id = self.contract.register_plan(json.dumps(self.plan))
        self.act(self.reviewer, 155)

    def attest(self, **changes):
        receipt_id = self.contract.attest_drill(self.plan_id, json.dumps(self.report | changes))
        receipt = json.loads(self.contract.get_receipt(receipt_id))
        self.assertEqual(receipt_id, contract.digest(receipt))
        return receipt_id, receipt

    def test_threshold_boundaries_pass(self):
        _, receipt = self.attest()
        self.assertEqual(receipt["outcome"], "COMPLIANT")
        self.assertTrue(all(receipt["checks"].values()))

    def test_numeric_violations_fail(self):
        _, receipt = self.attest(completed_at=151, attended=23, evacuation_seconds=241)
        self.assertEqual(receipt["outcome"], "FAILED")
        self.assertFalse(any(receipt["checks"].values()))

    def test_partial_evidence(self):
        gl.nondet.exec_prompt = lambda _: '{"findings":[["MET",0],["UNKNOWN",-1]]}'
        self.assertEqual(self.attest()[1]["outcome"], "PARTIAL")

    def test_explicit_breach(self):
        gl.nondet.exec_prompt = lambda _: '{"findings":[["MET",0],["BREACH",1]]}'
        self.assertEqual(self.attest()[1]["outcome"], "FAILED")

    def test_invalid_grounding_is_inconclusive(self):
        gl.nondet.exec_prompt = lambda _: '{"findings":[["MET",20],["MET",1]]}'
        self.assertEqual(self.attest()[1]["outcome"], "INCONCLUSIVE")

    def test_disagreement_leaves_no_receipt(self):
        answers = iter(['{"findings":[["MET",0],["MET",1]]}',
                        '{"findings":[["MET",0],["UNKNOWN",-1]]}'])
        gl.nondet.exec_prompt = lambda _: next(answers)
        with self.assertRaises(RuntimeError):
            self.attest()
        self.assertEqual(self.contract.get_latest_receipt(self.plan_id), "")
        self.assertFalse(self.contract.used_reports)

    def test_reviewer_only(self):
        self.act(self.owner, 155)
        with self.assertRaisesRegex(ValueError, "designated reviewer"):
            self.attest()

    def test_plan_is_immutable(self):
        self.act(self.owner, 100)
        self.plan["max_seconds"] = 300
        with self.assertRaisesRegex(ValueError, "already registered"):
            self.contract.register_plan(json.dumps(self.plan))
        self.assertEqual(json.loads(self.contract.get_plan(self.plan_id))["max_seconds"], 240)

    def test_replay_revision_limit_and_chain(self):
        first, _ = self.attest()
        with self.assertRaisesRegex(ValueError, "already assessed"):
            self.attest()
        second, receipt = self.attest(report_ref="DR-02")
        self.assertEqual(receipt["previous"], first)
        third, receipt = self.attest(report_ref="DR-03")
        self.assertEqual(receipt["previous"], second)
        self.assertEqual(self.contract.get_latest_receipt(self.plan_id), third)
        with self.assertRaisesRegex(ValueError, "limit"):
            self.attest(report_ref="DR-04")
        self.assertTrue(self.contract.get_receipt(first))

    def test_rejects_future_evidence_boolean_counts_and_duplicate_keys(self):
        for changes in ({"completed_at": 156}, {"attended": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.attest(**changes)
        raw = json.dumps(self.report)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.contract.attest_drill(self.plan_id, raw[:-1] + ', "attended": 24}')


if __name__ == "__main__":
    unittest.main()

"""Synthetic opcode safety tests for Twitch 31.8.0 Hermes timestamp override."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patch_hermes_timestamps import patch_hasm, EXPECTED


class TimestampHermesTests(unittest.TestCase):
    def setUp(self):
        self.hasm = (
            '003b  GetById r18, r11, 3, "showTimestamp"\n'
            + EXPECTED
            + '\n0d53  GetById r22, r32, 96, "isHistorical"\n'
            + '0d5e  GetById r68, r32, 97, "tmiSentTs"\n'
            + '1505  GetById r79, r71, 121, "TimestampPart"\n'
        )

    def test_only_same_size_opcodes_are_changed(self):
        result = patch_hasm(self.hasm)
        changes = [(a, b) for a, b in zip(self.hasm.splitlines(), result.splitlines()) if a != b]
        self.assertEqual(changes, [
            ('00d8  LoadConstFalse r22', '00d8  LoadConstTrue r22'),
            ('00de  Mov r22, r18', '00de  Mov r22, r22'),
        ])
        self.assertEqual(len(result.splitlines()), len(self.hasm.splitlines()))

    def test_refuses_unknown_renderer_version(self):
        with self.assertRaises(ValueError):
            patch_hasm(self.hasm.replace('00d8  LoadConstFalse r22', '00d8  LoadConstTrue r22'))

    def test_refuses_missing_historical_renderer(self):
        with self.assertRaises(ValueError):
            patch_hasm(self.hasm.replace('"TimestampPart"', '"UnknownComponent"'))

    def test_refuses_duplicate_hooks(self):
        with self.assertRaises(ValueError):
            patch_hasm(self.hasm + EXPECTED)


if __name__ == '__main__':
    unittest.main()

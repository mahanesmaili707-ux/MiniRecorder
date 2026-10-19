import unittest
from minirecorder import FORMAT_NAME, FORMAT_VERSION, validate_recording, key_to_text, text_to_key
from pynput.keyboard import Key, KeyCode

class RecordingFormatTests(unittest.TestCase):
    def test_valid_empty_recording(self):
        data = {"format": FORMAT_NAME, "version": FORMAT_VERSION, "events": []}
        self.assertIs(validate_recording(data), data)
    def test_rejects_wrong_format(self):
        with self.assertRaises(ValueError): validate_recording({"format": "other", "version": 1, "events": []})
    def test_rejects_decreasing_timestamps(self):
        data = {"format": FORMAT_NAME, "version": 1, "events": [{"type": "mouse_move", "t": 1.0}, {"type": "mouse_move", "t": 0.5}]}
        with self.assertRaises(ValueError): validate_recording(data)
    def test_rejects_unknown_event(self):
        with self.assertRaises(ValueError): validate_recording({"format": FORMAT_NAME, "version": 1, "events": [{"type": "mystery", "t": 0}]})
    def test_character_key_roundtrip(self):
        self.assertEqual(text_to_key(key_to_text(KeyCode.from_char("a"))).char, "a")
    def test_special_key_roundtrip(self):
        self.assertEqual(text_to_key(key_to_text(Key.enter)), Key.enter)

if __name__ == "__main__": unittest.main()

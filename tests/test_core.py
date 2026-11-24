import unittest

from nexa_ai.file_store import guess_mime_type
from nexa_ai.local_backend import _parse_content, prepare_messages


class CoreTests(unittest.TestCase):
    def test_guess_mime_type_for_mp4(self):
        self.assertEqual(guess_mime_type("clip.mp4"), "video/mp4")

    def test_supplied_mime_type_wins(self):
        self.assertEqual(guess_mime_type("photo.bin", "image/jpeg"), "image/jpeg")

    def test_octet_stream_falls_back_to_extension(self):
        self.assertEqual(guess_mime_type("notes.pdf", "application/octet-stream"), "application/pdf")

    def test_parse_openai_text_content(self):
        self.assertEqual(_parse_content("hello"), "hello")
        self.assertEqual(_parse_content([{"type": "text", "text": "one"}, {"text": " two"}]), "one two")

    def test_prepare_plain_chat_messages(self):
        messages = [{"role": "user", "content": "hello"}]
        self.assertEqual(prepare_messages(messages), messages)


if __name__ == "__main__":
    unittest.main()

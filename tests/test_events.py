import unittest

from agent_notify.events import normalize_event


class NormalizeEventTests(unittest.TestCase):
    def test_codex_permission_request(self):
        event = normalize_event(
            {
                "hook_event_name": "PermissionRequest",
                "permission_mode": "default",
                "model": "gpt-5",
                "turn_id": "turn-1",
                "cwd": "C:/work/demo",
                "tool_name": "shell_command",
                "tool_input": {"command": "git status"},
            }
        )

        self.assertEqual(event.source, "codex")
        self.assertEqual(event.kind, "permission")
        self.assertEqual(event.workspace, "demo")
        self.assertEqual(event.tool_name, "shell_command")
        self.assertEqual(event.summary, "git status")

    def test_claude_elicitation_is_question(self):
        event = normalize_event(
            {
                "hook_event_name": "Elicitation",
                "cwd": "/Users/test/demo",
                "prompt": "Which deployment target should I use?",
            }
        )

        self.assertEqual(event.source, "claude")
        self.assertEqual(event.kind, "question")
        self.assertEqual(event.summary, "Which deployment target should I use?")

    def test_claude_ask_user_question_is_question(self):
        event = normalize_event(
            {
                "hook_event_name": "PreToolUse",
                "cwd": "/Users/test/demo",
                "tool_name": "AskUserQuestion",
                "tool_input": {
                    "questions": [
                        {
                            "question": "Which framework?",
                            "header": "Framework",
                            "options": [{"label": "React"}, {"label": "Vue"}],
                        }
                    ]
                },
            }
        )

        self.assertEqual(event.source, "claude")
        self.assertEqual(event.kind, "question")
        self.assertEqual(event.summary, "Which framework?")

    def test_other_pre_tool_use_is_ignored(self):
        self.assertIsNone(
            normalize_event(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "git status"},
                }
            )
        )

    def test_codex_request_user_input_is_question(self):
        event = normalize_event(
            {
                "hook_event_name": "PreToolUse",
                "permission_mode": "plan",
                "model": "gpt-5",
                "turn_id": "turn-3",
                "cwd": "C:/work/demo",
                "tool_name": "request_user_input",
                "tool_input": {
                    "questions": [
                        {
                            "header": "通知测试",
                            "question": "你收到提问通知了吗？",
                            "options": [
                                {"label": "收到了"},
                                {"label": "没收到"},
                            ],
                        }
                    ]
                },
            }
        )

        self.assertEqual(event.source, "codex")
        self.assertEqual(event.kind, "question")
        self.assertEqual(event.summary, "你收到提问通知了吗？")

    def test_codex_stop_uses_last_assistant_message(self):
        event = normalize_event(
            {
                "hook_event_name": "Stop",
                "permission_mode": "plan",
                "model": "gpt-5",
                "turn_id": "turn-2",
                "cwd": "/tmp/demo",
                "last_assistant_message": "Implementation finished.",
            }
        )

        self.assertEqual(event.source, "codex")
        self.assertEqual(event.kind, "stop")
        self.assertEqual(event.summary, "Implementation finished.")

    def test_unknown_event_returns_none(self):
        self.assertIsNone(normalize_event({"hook_event_name": "SessionStart"}))

    def test_explicit_question_fallback(self):
        event = normalize_event(
            {
                "hook_event_name": "Question",
                "source": "codex",
                "cwd": "/tmp/demo",
                "prompt": "Choose A or B",
            }
        )

        self.assertEqual(event.kind, "question")
        self.assertEqual(event.source, "codex")


if __name__ == "__main__":
    unittest.main()

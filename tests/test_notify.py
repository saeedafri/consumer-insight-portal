import smtplib

from etl import notify


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        FakeSMTP.sent.append((self.host, self.port, self.user, message))


def test_send_attaches_workbook(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("EMAIL_PASSWORD", "x")
    assert notify.send("subject", "body", ["a@coresight.com"], [("w.xlsx", b"PK")], "<p>hi</p>")
    host, port, user, message = FakeSMTP.sent[-1]
    assert (host, port, user) == ("smtp.office365.com", 587, "dataautomation@coresight.com")
    assert message["To"] == "a@coresight.com"
    assert [a.get_filename() for a in message.iter_attachments()] == ["w.xlsx"]
    assert message.get_body(("html",)).get_content().strip() == "<p>hi</p>"


def test_send_without_password_does_nothing(monkeypatch):
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    assert notify.send("subject", "body", ["a@coresight.com"]) is False


def test_recipients_fall_back_to_default():
    assert notify.recipients("tracker") == notify.recipients("default")


def test_failure_emails_and_posts_to_teams_once(monkeypatch, tmp_path):
    sent, posted = [], []
    monkeypatch.setattr(notify, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(notify, "send", lambda subject, body, to, attachments=(), page="": sent.append(subject) or True)
    monkeypatch.setattr(notify, "teams", posted.append)
    assert notify.failure("survey X did not load", "boom")
    assert notify.failure("survey X did not load", "boom") is False          # same failure inside the window
    assert sent == ["CIP pipeline FAILED: survey X did not load"]
    assert posted == ["\u274c CIP pipeline failed: survey X did not load. Details in the email; the next run retries."]

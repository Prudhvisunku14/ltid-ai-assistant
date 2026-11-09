import json
from types import SimpleNamespace

import pytest

from app.classifier import OpenAIClassifier, RuleBasedClassifier, build_classifier
from app.config import Settings
from app.models import Category, Priority


def fake_client(content=None, exc=None):
    def create(**kwargs):
        if exc:
            raise exc
        create.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


# ------------------------------------------------------------------ rules
@pytest.mark.parametrize("title,desc,cat,pri", [
    ("Site is down", "The whole website is down for every user", Category.technical_issue, Priority.urgent),
    ("Charged twice", "I was charged twice for my subscription", Category.billing, Priority.urgent),
    ("Refund request", "Please refund last month's invoice", Category.billing, Priority.high),
    ("Opening hours", "Question about your opening hours", Category.general_inquiry, Priority.low),
    ("Hello", "Just saying hello to the team", Category.general_inquiry, Priority.medium),
])
def test_rule_based(title, desc, cat, pri):
    r = RuleBasedClassifier().classify(title, desc)
    assert (r.category, r.priority, r.source) == (cat, pri, "rules")
    assert r.reasoning


def test_rule_based_uses_word_boundaries():
    # "download" must not trigger the keyword "down"
    r = RuleBasedClassifier().classify("Download link", "Where is the download page for the brochure")
    assert r.priority != Priority.urgent


# -------------------------------------------------------------------- GPT
def test_gpt_happy_path_and_prompt_shape():
    payload = json.dumps({"category": "billing", "priority": "urgent", "reasoning": "Money taken twice."})
    client = fake_client(payload)
    r = OpenAIClassifier(client=client, model="gpt-test").classify("Charged twice", "see title")
    assert (r.category, r.priority, r.source) == (Category.billing, Priority.urgent, "ai")
    assert r.reasoning == "Money taken twice."
    sent = client.chat.completions.create.kwargs
    assert sent["model"] == "gpt-test" and sent["response_format"] == {"type": "json_object"}
    assert "<ticket>" in sent["messages"][1]["content"]


@pytest.mark.parametrize("content,exc", [
    ("this is not json", None),
    (json.dumps({"category": "weather", "priority": "low", "reasoning": "x"}), None),
    (json.dumps({"category": "billing"}), None),
    (None, RuntimeError("network down")),
])
def test_gpt_failures_fall_back_to_rules(content, exc):
    r = OpenAIClassifier(client=fake_client(content, exc)).classify("Charged twice", "subscription charge")
    assert r.source == "rules"
    assert "fallback" in r.reasoning
    assert r.category == Category.billing


def test_gpt_reasoning_is_truncated():
    payload = json.dumps({"category": "billing", "priority": "low", "reasoning": "x" * 2000})
    r = OpenAIClassifier(client=fake_client(payload)).classify("t", "d")
    assert len(r.reasoning) == 500


def test_build_classifier_selects_implementation():
    assert build_classifier(Settings(openai_api_key="")).name == "rules"
    assert build_classifier(Settings(openai_api_key="sk-test", openai_model="m")).name == "openai:m"

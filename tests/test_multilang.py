"""Tests for multi-language profile loading and validation."""
import pytest
import json
from pathlib import Path

from src.translate_pipeline import (
    load_lang_profile,
    validate_translations,
    load_symbol_map,
    load_glossary_exceptions,
)


PROJECT_ROOT = Path(__file__).parent.parent


# ── 1. 언어 프로파일 로딩 ──

def test_load_ja_ko_profile():
    """ja-ko 프로파일 로드 시 필수 키 존재 확인."""
    profile = load_lang_profile("ja-ko")
    assert profile is not None
    assert profile["source_lang"] == "ja"
    assert profile["target_lang"] == "ko"
    assert "glossary" in profile
    assert "symbol_map" in profile
    assert "validation" in profile
    assert "font_candidates" in profile
    assert "pdf_labels" in profile


def test_load_ja_en_profile():
    """ja-en 프로파일 로드 시 필수 키 존재 확인."""
    profile = load_lang_profile("ja-en")
    assert profile is not None
    assert profile["target_lang"] == "en"
    assert profile["target_name"] == "English"
    assert "glossary" in profile


def test_load_ja_de_profile():
    """ja-de 프로파일 로드 시 필수 키 존재 확인."""
    profile = load_lang_profile("ja-de")
    assert profile is not None
    assert profile["target_lang"] == "de"
    assert profile["target_name"] == "Deutsch"
    assert "glossary" in profile


def test_load_none_returns_none():
    """lang=None이면 None 반환."""
    result = load_lang_profile(None)
    assert result is None


def test_load_invalid_lang_exits(monkeypatch):
    """존재하지 않는 언어 코드는 sys.exit(1)."""
    with pytest.raises(SystemExit):
        load_lang_profile("xx-yy")


# ── 2. 프로파일 기반 glossary/symbol_map 로딩 ──

def test_glossary_from_profile():
    """lang_profile에서 glossary 예외 목록 로드."""
    profile = load_lang_profile("ja-en")
    exceptions = load_glossary_exceptions(profile)
    assert "ふわふわ" in exceptions
    assert "龍神様" in exceptions


def test_symbol_map_from_profile():
    """lang_profile에서 symbol_map 로드."""
    profile = load_lang_profile("ja-en")
    sm = load_symbol_map(profile)
    assert "preserve" in sm
    assert "convert" in sm


# ── 3. 다국어 검증 로직 ──

def test_en_validation_skips_translationese():
    """영어 번역에서 번역투 검사 건너뜀."""
    profile = load_lang_profile("ja-en")
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "This is a test of the translation pipeline.",
    }]
    result = validate_translations(pages, lang_profile=profile)
    assert result["qa_summary"]["번역투_패턴"] == "N/A (비한국어 번역)"
    assert result["qa_summary"]["종결어미_통계"] == "N/A (비한국어 번역)"


def test_en_validation_detects_japanese_remnant():
    """영어 번역에서도 일본어 잔존 감지."""
    profile = load_lang_profile("ja-en")
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "This is a test with ひらがな remnants.",
    }]
    result = validate_translations(pages, lang_profile=profile)
    assert not result["ok"]
    assert any("원문 스크립트 잔존" in e for e in result["errors"])


def test_ko_validation_runs_translationese():
    """한국어 번역에서 번역투 검사 실행."""
    profile = load_lang_profile("ja-ko")
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "성공의 비결의 핵심의 이야기가 있습니다.",
    }]
    result = validate_translations(pages, lang_profile=profile)
    assert "전체 통과" not in result["qa_summary"]["번역투_패턴"]


def test_de_validation_skips_translationese():
    """독일어 번역에서 번역투 검사 건너뜀."""
    profile = load_lang_profile("ja-de")
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "Dies ist ein Test der Übersetzungspipeline.",
    }]
    result = validate_translations(pages, lang_profile=profile)
    assert result["qa_summary"]["번역투_패턴"] == "N/A (비한국어 번역)"


def test_en_glossary_consistency():
    """영어 프로파일에서 용어집 일관성 검증."""
    profile = load_lang_profile("ja-en")
    pages = [{
        "page": 1,
        "original": "龍神様が現れた。",
        "translated": "The Dragon God appeared.",
    }]
    result = validate_translations(pages, lang_profile=profile)
    # "Dragon God" is in translated, so no glossary issue
    glossary_warnings = [w for w in result["warnings"] if "용어집" in w]
    assert len(glossary_warnings) == 0


def test_en_glossary_missing_term():
    """영어 프로파일에서 용어 미반영 감지."""
    profile = load_lang_profile("ja-en")
    pages = [{
        "page": 1,
        "original": "龍神様が現れた。",
        "translated": "The deity appeared.",  # "Dragon God" 미사용
    }]
    result = validate_translations(pages, lang_profile=profile)
    glossary_warnings = [w for w in result["warnings"] if "용어집" in w]
    assert len(glossary_warnings) > 0

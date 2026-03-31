"""Tests for translation quality QA checks (#9-#12)."""
import pytest

from src.translate_pipeline import validate_translations


# ── 9. 번역투 패턴 감지 ──

def test_no_chain_detected():
    """Detect '~의' chain (3+ consecutive)."""
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "성공의 비결의 핵심의 이야기가 있습니다.",
    }]
    result = validate_translations(pages)
    assert "번역투_패턴" in result["qa_summary"]
    assert "전체 통과" not in result["qa_summary"]["번역투_패턴"]


def test_no_chain_clean():
    """No false positive for natural Korean 의 usage."""
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "성공의 비결을 알려드립니다.",
    }]
    result = validate_translations(pages)
    assert "전체 통과" in result["qa_summary"]["번역투_패턴"]


def test_passive_pattern_detected():
    """Detect passive/causative patterns."""
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "사랑이 느껴지게 된다고 생각되어지면 좋겠습니다.",
    }]
    result = validate_translations(pages)
    has_passive_warning = any("수동태/사역형" in w for w in result["warnings"])
    assert has_passive_warning


# ── 10. 단락 구조 일치 검증 ──

def test_paragraph_mismatch():
    """Detect paragraph count mismatch."""
    pages = [{
        "page": 1,
        "original": "テスト文。　次の段落。　三つ目の段落。　四つ目の段落。　五つ目の段落です。",
        "translated": "테스트 문장입니다. 하나로 합쳐진 번역문입니다.",
    }]
    result = validate_translations(pages)
    assert "단락_구조_일치" in result["qa_summary"]


def test_paragraph_match():
    """No warning when paragraph counts roughly match."""
    pages = [{
        "page": 1,
        "original": "最初の段落。　二番目の段落。　三番目の段落終わり。",
        "translated": "첫 번째 단락입니다.\n\n두 번째 단락입니다.\n\n세 번째 단락입니다.",
    }]
    result = validate_translations(pages)
    assert "전체 통과" in result["qa_summary"]["단락_구조_일치"]


# ── 11. 종결어미 통계 ──

def test_ending_stats():
    """Verify ending statistics are collected."""
    pages = [{
        "page": 1,
        "original": "テスト",
        "translated": "이것은 테스트입니다.\n행복합니다.\n좋습니다.",
    }]
    result = validate_translations(pages)
    assert "종결어미_통계" in result["qa_summary"]
    # Should detect 하십시오체 endings
    stats = result["qa_summary"]["종결어미_통계"]
    assert "하십시오체" in stats


# ── 12. 감탄사/줄임표 밀도 ──

def test_exclamation_density():
    """Report exclamation density statistics."""
    pages = [{
        "page": 1,
        "original": "すごい！素晴らしい！最高！やった！",
        "translated": "대단해! 훌륭해! 최고! 해냈다!",
    }]
    result = validate_translations(pages)
    assert "감탄사_줄임표_밀도" in result["qa_summary"]


def test_ellipsis_density():
    """Report ellipsis density statistics."""
    pages = [{
        "page": 1,
        "original": "えっと……うーん……まぁ……それは……",
        "translated": "음……글쎄……뭐……그건……",
    }]
    result = validate_translations(pages)
    density = result["qa_summary"]["감탄사_줄임표_밀도"]
    assert "감소" in density
